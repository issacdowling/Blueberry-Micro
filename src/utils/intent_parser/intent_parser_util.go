package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"syscall"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var intents map[string]Intent = make(map[string]Intent)
var collections map[string]Collection = make(map[string]Collection)

var broker *mqtt.ClientOptions
var client *mqtt.Client

var deviceId string
var friendlyName string = "Intent Parser"

var l logData

func main() {
	// Test data
	testData := []byte(`
	{
		"id": "setWLED",
		"adv_keyphrases": [{"hello there": "hi", "hey": ""}, {"time": "1", "times": "2"}, {"$get": ""}],
		"core_id": "wled",
		"prefixes": ["ask wled to", "do"],
		"suffixes": ["thanks", "or else"]
	}	
	`)

	var testIntentJson Intent
	err := json.Unmarshal(testData, &testIntentJson)
	if err != nil {
		bLogFatal(err.Error(), l)
	}

	intents[testIntentJson.Id] = testIntentJson

	//////////////

	//// MQTT Setup
	// Take in CLI args for host, port, uname, passwd

	mqttHost := *flag.String("host", "localhost", "the hostname/IP of the MQTT broker")
	mqttPort := *flag.Int("port", 1883, "the hostname/IP of the MQTT broker")
	mqttUser := *flag.String("user", "", "the hostname/IP of the MQTT broker")
	mqttPass := *flag.String("pass", "", "the hostname/IP of the MQTT broker")
	deviceId = *flag.String("device-id", "test", "the hostname/IP of the MQTT broker")
	flag.Parse()

	l.uuid = deviceId
	l.name = friendlyName

	//// Set up MQTT
	bLog("Setting up MQTT", l)
	broker = mqtt.NewClientOptions()
	broker.AddBroker(fmt.Sprintf("tcp://%s:%v", mqttHost, mqttPort))

	bLog(fmt.Sprintf("Broker at: tcp://%s:%v\n", mqttHost, mqttPort), l)

	broker.SetClientID(fmt.Sprintf("%v - %s", deviceId, friendlyName))

	bLog(fmt.Sprintf("MQTT client name: %v - %s\n", deviceId, friendlyName), l)

	broker.OnConnect = onConnect
	if mqttPass != "" && mqttUser != "" {
		broker.SetPassword(mqttPass)
		broker.SetUsername(mqttUser)
		bLog("Using MQTT authenticated", l)
	} else {
		bLog("Using MQTT unauthenticated", l)
	}
	client := mqtt.NewClient(broker)

	l.client = client

	if token := client.Connect(); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.Subscribe(fmt.Sprintf("bloob/%s/cores/+/collections", deviceId), bloobQOS, collectionHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.Subscribe(fmt.Sprintf("bloob/%s/cores/+/intents", deviceId), bloobQOS, intentHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}

	coreId := "intent_parser_util"

	//// Publish Config
	coreConfig := map[string]map[string]interface{}{
		"metadata": {
			"core_id":       coreId,
			"friendly_name": "Intent Parser",
			"link":          "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/utils/intent_parser",
			"author":        "Issac Dowling",
			"icon":          nil,
			"description":   "Parses what task you want completed based on your speech",
			"version":       "0.1",
			"license":       "AGPLv3",
		},
	}
	fmt.Println(coreConfig)

	time.Sleep(2 * time.Second)

	fmt.Println(parseIntent("ask wled to get hello there, time, doorlight thanks "))

	// Block until CTRL+C'd
	doneChannel := make(chan os.Signal, 1)
	signal.Notify(doneChannel, syscall.SIGINT, syscall.SIGTERM)

	<-doneChannel
}

func parseIntent(text string) ([]Intent, string) {
	var potentialIntents []Intent
	for _, intent := range intents {
		// Clean the text, inline mentioned Collections, complete all necessary substitutions
		tempText := preCleanText(text)
		collectionKeyphraseUnwrap(&intent)
		tempText = preProcessText(tempText, intent)

		intentPass := true

		// This should eventually be a for loop that adapts to any future checks...
		// it's not that yet.
		if intent.AdvancedKeyphrases != nil {
			checkPass, checkLog := keyphraseCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			bLog(checkLog, l)
		}

		if intent.Prefixes != nil {
			checkPass, checkLog := prefixCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			bLog(checkLog, l)
		}

		if intent.Suffixes != nil {
			checkPass, checkLog := suffixCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			bLog(checkLog, l)
		}

		if intentPass {
			potentialIntents = append(potentialIntents, intent)
		}

	}

	return potentialIntents, ""
}

func preProcessText(text string, intent Intent) string {
	if intent.AdvancedKeyphrases != nil {
		for _, setOfKeyphrases := range intent.AdvancedKeyphrases {
			for keyphrase, newphrase := range setOfKeyphrases {
				if newphrase != "" {
					text, _ = bTextReplace(text, keyphrase, newphrase)
				}
			}
		}
	}

	return strings.TrimSpace(text)
}

func preCleanText(text string) string {
	text = strings.ToLower(text)
	replaceValues := map[string]string{
		"&": " and ",

		"+": " plus ",
		"*": " times ",
		"-": " minus ",
		"/": " over ",
		"%": " percent ",
	}

	for original, replacement := range replaceValues {
		text = strings.Replace(text, original, replacement, -1)
	}

	// Remove any non-replaced special characters
	text = regexp.MustCompile(`[^a-zA-Z0-9 ]+`).ReplaceAllString(text, "")

	return strings.TrimSpace(text)
}

// intent needs to be a pointer because collectionUnwrap will modify the Intent
func collectionKeyphraseUnwrap(intent *Intent) {

	if intent.AdvancedKeyphrases != nil {
		// For each set of keyphrases, for each keyphrase, if it's a Collection ($),
		// check that this Collection exists, then go through it and add each of its keyphrases and substitute
		// values (keys and values) to the keyphraseSet of the Intent. Each Collection essentially just has one
		// keyphraseset.
		for _, keyphraseSet := range intent.AdvancedKeyphrases {
			for keyphrase, newphrase := range keyphraseSet {
				if keyphrase[0] == '$' {
					// keyphrase[1:] is used to remove the $ and just get the Collection name
					if collection, ok := collections[keyphrase[1:]]; ok {
						bLog(fmt.Sprintf("Inlining the Collection \"%s\" with the intent \"%s\"", keyphrase[1:], intent.Id), l)
						// If the newphrase next to the Collection is blank, set the newphrases to their original values in the Collection
						// If it's not blank, set the newphrases from the Collection equal to the original newphrase.
						if newphrase == "" {
							for collectionKeyphrase, collectionNewphrase := range collection.AdvancedKeyphrases {
								keyphraseSet[collectionKeyphrase] = collectionNewphrase
							}
						} else {
							for collectionKeyphrase := range collection.AdvancedKeyphrases {
								keyphraseSet[collectionKeyphrase] = newphrase
							}
						}

						// Deletes the Collection name from the Intent's keywords
						delete(keyphraseSet, keyphrase)

					} else {
						bLog(fmt.Sprintf("The Collection \"%s\" doesn't exist, but was called for by \"%s\"", keyphrase[1:], intent.Id), l)
					}
				}
			}
		}

	}
}
