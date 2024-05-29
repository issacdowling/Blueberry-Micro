package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"regexp"
	"strings"
)

type Intent struct {
	Id         string
	CoreId     string
	Keyphrases []map[string]string
	Prefixes   []string
	Suffixes   []string
	Variables  []map[string]interface{}
}

type Collection struct {
	Id         string
	Keyphrases []map[string]string
	Variables  []map[string]interface{}
}

var intents map[string]Intent = make(map[string]Intent)

var collections map[string]Collection = make(map[string]Collection)

func main() {
	// Test data
	testData := []byte(`
	{
		"id": "setWLED",
		"keyphrases": [{"hello there": "hi", "hey": ""}, {"time": "1", "times": "2"}, {"$devices": ""}],
		"core_id": "wled",
		"prefixes": ["ask wled to", "do"],
		"suffixes": ["thanks", "or else"]
	}	
	`)

	var testDataJson Intent
	err := json.Unmarshal(testData, &testDataJson)
	if err != nil {
		log.Panic(err)
	}

	testCollection := []byte(`{
	"id": "devices",
	"keyphrases": [
		{"doorlight": "door light"},
		{"door light": ""},
		{"doleight": "door light"},
		{"delight": "door light"}
		],
	"variables": [
		{"door light": [0,233234,232443]}
	]
	}	
	`)

	var testCollectionJson Collection

	err = json.Unmarshal(testCollection, &testCollectionJson)
	if err != nil {
		log.Panic(err)
	}
	collections[testCollectionJson.Id] = testCollectionJson

	// fmt.Println(testDataJson)
	// fmt.Println(testCollectionJson)

	fmt.Println(parseIntent("ask wled to hello there, time, doorlight thanks ", []Intent{testDataJson}))

	os.Exit(0)
	//////////////

	//// MQTT Setup
	// Take in CLI args for host, port, uname, passwd
	mqttHost := "localhost"
	mqttPort := 1883

	coreId := "intent_parser"

	//// Publish Config
	core_config := map[string]map[string]interface{}{
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
	fmt.Println(core_config, mqttHost, mqttPort)
}

func parseIntent(text string, intents []Intent) ([]Intent, string) {
	var potentialIntents []Intent
	for _, intent := range intents {
		// Clean the text, inline mentioned Collections, complete all necessary substitutions
		tempText := preCleanText(text)
		collectionKeyphraseUnwrap(&intent)
		tempText = preProcessText(tempText, intent)

		intentPass := true

		// This should eventually be a for loop that adapts to any future checks...
		// it's not that yet.
		if intent.Keyphrases != nil {
			checkPass, checkLog := keyphraseCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			log.Println(checkLog)
		}

		if intent.Prefixes != nil {
			checkPass, checkLog := prefixCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			log.Println(checkLog)
		}

		if intent.Suffixes != nil {
			checkPass, checkLog := suffixCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			log.Println(checkLog)
		}

		if intentPass {
			potentialIntents = append(potentialIntents, intent)
		}

	}

	return potentialIntents, ""
}

func preProcessText(text string, intent Intent) string {
	if intent.Keyphrases != nil {
		for _, setOfKeyphrases := range intent.Keyphrases {
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

	if intent.Keyphrases != nil {
		// For each set of keyphrases, for each keyphrase, if it's a Collection ($),
		// check that this Collection exists, then go through it and add each of its keyphrases and substitute
		// values (keys and values) to the keyphraseSet of the Intent. Each Collection essentially just has one
		// keyphraseset.
		for _, keyphraseSet := range intent.Keyphrases {
			for keyphrase := range keyphraseSet {
				if keyphrase[0] == '$' {
					// keyphrase[1:] is used to remove the $ and just get the Collection name
					if collection, ok := collections[keyphrase[1:]]; ok {
						log.Printf("Merging the Collection \"%s\" with the intent \"%s\"", keyphrase[1:], intent.Id)
						for _, collectionKeyphrasePair := range collection.Keyphrases {
							for keyphrase, newphrase := range collectionKeyphrasePair {
								keyphraseSet[keyphrase] = newphrase
							}

						}
						// Deletes the Collection name from the Intent's keywords
						delete(keyphraseSet, keyphrase)
					} else {
						log.Printf("The Collection \"%s\" doesn't exist, but was called for by \"%s\"", keyphrase[1:], intent.Id)
					}
				}
			}
		}

	}
}
