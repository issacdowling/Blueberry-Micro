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

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var intents map[string]Intent = make(map[string]Intent)
var collections map[string]Collection = make(map[string]Collection)

var broker *mqtt.ClientOptions

var deviceId *string
var friendlyName string = "Intent Parser"

var l logData

func main() {

	//// MQTT Setup
	// Take in CLI args for host, port, uname, passwd

	mqttHost := flag.String("host", "localhost", "the hostname/IP of the MQTT broker")
	mqttPort := flag.Int("port", 1883, "the hostname/IP of the MQTT broker")
	mqttUser := flag.String("user", "", "the hostname/IP of the MQTT broker")
	mqttPass := flag.String("pass", "", "the hostname/IP of the MQTT broker")
	deviceId = flag.String("device-id", "test", "the hostname/IP of the MQTT broker")
	flag.Parse()

	l.uuid = *deviceId
	l.name = friendlyName

	//// Set up MQTT
	bLog("Setting up MQTT", l)
	broker = mqtt.NewClientOptions()
	broker.AddBroker(fmt.Sprintf("tcp://%s:%v", *mqttHost, *mqttPort))

	bLog(fmt.Sprintf("Broker at: tcp://%s:%v\n", *mqttHost, *mqttPort), l)

	broker.SetClientID(fmt.Sprintf("%v - %s", *deviceId, friendlyName))

	bLog(fmt.Sprintf("MQTT client name: %v - %s\n", *deviceId, friendlyName), l)

	broker.OnConnect = onConnect
	if *mqttPass != "" && *mqttUser != "" {
		broker.SetPassword(*mqttPass)
		broker.SetUsername(*mqttUser)
		bLog("Using MQTT authenticated", l)
	} else {
		bLog("Using MQTT unauthenticated", l)
	}
	client := mqtt.NewClient(broker)

	l.client = client

	if token := client.Connect(); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.Subscribe(fmt.Sprintf("bloob/%s/collections/+", *deviceId), bloobQOS, collectionHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.Subscribe(fmt.Sprintf("bloob/%s/cores/+/intents/+", *deviceId), bloobQOS, intentHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.Subscribe(fmt.Sprintf("bloob/%s/cores/intent_parser_util/run", *deviceId), bloobQOS, parseHandler); token.Wait() && token.Error() != nil {
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

	coreConfigJson, err := json.Marshal(coreConfig)
	if err != nil {
		bLogFatal(fmt.Sprintf("Failed to JSON encode the core config: %s", err.Error()), l)
	}

	if token := client.Publish(fmt.Sprintf("bloob/%s/cores/%s/config", *deviceId, coreId), bloobQOS, true, coreConfigJson); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}

	// Block until CTRL+C'd
	doneChannel := make(chan os.Signal, 1)
	signal.Notify(doneChannel, syscall.SIGINT, syscall.SIGTERM)

	<-doneChannel
}

func parseIntent(text string) IntentParse {
	var potentialIntents []IntentParse

	bLog(fmt.Sprintf("Received request to parse \"%s\"", text), l)
	textToParse := preCleanText(text)
	bLog(fmt.Sprintf("Cleaned text to: \"%s\"", textToParse), l)
	for _, intent := range intents {
		var intentCheckDepth int = 0
		// Clean the text, inline mentioned Collections, complete all necessary substitutions
		bLog(intent.Id, l)
		collectionKeyphraseUnwrap(intent)
		textToParse = preProcessText(textToParse, intent)
		bLog(fmt.Sprintf("Performed substitutions for %s: \"%s\"", intent.Id, textToParse), l)

		intentPass := true

		// This should eventually be a for loop that adapts to any future checks...
		// it's not that yet.
		if intent.AdvancedKeyphrases != nil || intent.Keyphrases != nil {
			checkPass, checkDepth, checkLog := keyphraseCheck(textToParse, intent)
			if !checkPass {
				intentPass = false
			}
			intentCheckDepth += checkDepth
			bLog(checkLog, l)
		}

		if intent.Prefixes != nil {
			checkPass, checkDepth, checkLog := prefixCheck(textToParse, intent)
			if !checkPass {
				intentPass = false
			}
			intentCheckDepth += checkDepth
			bLog(checkLog, l)
		}

		if intent.Suffixes != nil {
			checkPass, checkDepth, checkLog := suffixCheck(textToParse, intent)
			if !checkPass {
				intentPass = false
			}
			intentCheckDepth += checkDepth
			bLog(checkLog, l)
		}

		if intent.Numbers != nil {
			checkPass, checkDepth, checkLog := numberCheck(textToParse, intent)
			if !checkPass {
				intentPass = false
			}
			intentCheckDepth += checkDepth
			bLog(checkLog, l)
		}

		if intentPass {
			potentialIntents = append(potentialIntents, IntentParse{Intent: intent, CheckDepth: intentCheckDepth, ParsedText: textToParse})
		}

	}

	if len(potentialIntents) != 1 {
		// Check through the intents to see if one has more detailed checks than the others. If so,
		// it's likely that this was the intended intent.
		bLog(fmt.Sprintf("Attempting to resolve detection of multiple Intents: %v", potentialIntents), l)
		var highestDepth int = 0
		var mostLikelyIntentParse IntentParse
		var resolved bool = true
		for _, intentParse := range potentialIntents {
			bLog(fmt.Sprintf("%s with depth %d", intentParse.Intent.Id, intentParse.CheckDepth), l)
			if intentParse.CheckDepth > highestDepth {
				mostLikelyIntentParse = intentParse
				highestDepth = intentParse.CheckDepth
			} else if intentParse.CheckDepth == highestDepth {
				bLog("Multiple Intents with the same check depth found, can't resolve Intent.", l)
				resolved = false
				break
			}
		}
		if resolved {
			return mostLikelyIntentParse
		} else {
			return IntentParse{}
		}

	}

	return potentialIntents[0]
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
func collectionKeyphraseUnwrap(intent Intent) {
	// For each set of keyphrases, for each keyphrase, if it's a Collection ($),
	// check that this Collection exists, then go through it and add each of its keyphrases and substitute
	// values (keys and values) to the keyphraseSet of the Intent. Each Collection essentially just has one
	// keyphraseset.
	if intent.AdvancedKeyphrases != nil {
		for _, keyphraseSet := range intent.AdvancedKeyphrases {
			for keyphrase, newphrase := range keyphraseSet {
				if keyphrase[0] == '$' {
					// keyphrase[1:] is used to remove the $ and just get the Collection name
					if collection, ok := collections[keyphrase[1:]]; ok {
						bLog(fmt.Sprintf("Inlining the Collection \"%s\" with the intent \"%s\"", keyphrase[1:], intent.Id), l)
						// If the newphrase next to the Collection is blank, set the newphrases to their original values in the Collection
						// If it's not blank, set the newphrases from the Collection equal to the original newphrase.

						if collection.AdvancedKeyphrases != nil {
							if newphrase == "" {
								for collectionKeyphrase, collectionNewphrase := range collection.AdvancedKeyphrases {
									keyphraseSet[collectionKeyphrase] = collectionNewphrase
								}
							} else {
								for collectionKeyphrase := range collection.AdvancedKeyphrases {
									keyphraseSet[collectionKeyphrase] = newphrase
								}
							}
						}

						if collection.Keyphrases != nil {
							for _, keyphrase := range collection.Keyphrases {
								keyphraseSet[keyphrase] = keyphrase
							}
						}

						// Deletes the Collection name from the Intent's keyphrases
						delete(keyphraseSet, keyphrase)

					} else {
						bLog(fmt.Sprintf("The Collection \"%s\" doesn't exist, but was called for by \"%s\"", keyphrase[1:], intent.Id), l)
					}
				}
			}
		}
	}

	if intent.Keyphrases != nil {
		for keyphraseSetIndex := range intent.Keyphrases {
			for _, keyphrase := range intent.Keyphrases[keyphraseSetIndex] {
				if keyphrase[0] == '$' {
					if collection, ok := collections[keyphrase[1:]]; ok {
						bLog(fmt.Sprintf("Inlining the Collection \"%s\" with the intent \"%s\"", keyphrase[1:], intent.Id), l)

						if collection.Keyphrases != nil {
							intent.Keyphrases[keyphraseSetIndex] = append(intent.Keyphrases[keyphraseSetIndex], collection.Keyphrases...)
						}

						if collection.AdvancedKeyphrases != nil {
							for key, new := range collection.AdvancedKeyphrases {
								if new == "" {
									intent.Keyphrases[keyphraseSetIndex] = append(intent.Keyphrases[keyphraseSetIndex], key)
								} else {
									intent.Keyphrases[keyphraseSetIndex] = append(intent.Keyphrases[keyphraseSetIndex], new)
								}
							}
						}

					} else {
						bLog(fmt.Sprintf("The Collection \"%s\" doesn't exist, but was called for by \"%s\"", keyphrase[1:], intent.Id), l)
					}
				}
			}
		}
	}
}
