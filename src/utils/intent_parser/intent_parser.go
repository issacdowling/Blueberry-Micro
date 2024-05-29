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
	Id            string
	CoreId        string
	Keyphrases    []map[string]string
	CollectionIds [][]string `json:"collections"`
	Prefixes      []string
	Suffixes      []string
	Variables     []map[string]interface{}
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
		"keyphrases": [{"hello there": "hi", "hey": ""}, {"time": "1", "times": "2"}],
		"core_id": "wled",
		"collections": [["devices"], ["set"]],
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

	fmt.Println(testDataJson)
	fmt.Println(testCollectionJson)

	fmt.Println(parseIntent(preCleanText("ask wled to hello there, time, thanks"), []Intent{testDataJson}))

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
		// Clean the text, complete all necessary substitutions
		tempText := preCleanText(text)
		tempText = preProcessText(tempText, intent)

		intentPass := true
		// This should eventually be a for loop that adapts to any future checks...
		// it's not that yet.
		if intent.Keyphrases != nil {
			checkPass, log := keyphraseCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			fmt.Println(log)
		}

		if intent.Prefixes != nil {
			checkPass, log := prefixCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			fmt.Println(log)
		}

		if intent.Suffixes != nil {
			checkPass, log := suffixCheck(tempText, intent)
			if !checkPass {
				intentPass = false
			}
			fmt.Println(log)
		}

		// if intent.Keyphrases != nil {
		// 	checkPass, _ := keyphraseCheck(tempText, intent)
		// 	if !checkPass {
		// 		intentPass = false
		// 	}
		// }

		if intentPass {
			potentialIntents = append(potentialIntents, intent)
		}

	}

	return potentialIntents, ""
}

func preProcessText(text string, intent Intent) string {

	// Definitely feels like all of these for loops should be somehow optimisable
	if intent.CollectionIds != nil {
		for _, setOfCollections := range intent.CollectionIds {
			for _, collectionId := range setOfCollections {
				if collection, ok := collections[collectionId]; ok {
					if collection.Keyphrases != nil {
						for _, setOfKeyphrases := range collection.Keyphrases {
							for keyphrase, newphrase := range setOfKeyphrases {
								text, _ = bTextReplace(text, keyphrase, newphrase)
							}
						}
					}
				} else {
					fmt.Printf("The Collection \"%s\" doesn't exist, but was called for by %s", collectionId, intent.Id)
				}
			}

		}
	}

	if intent.Keyphrases != nil {
		for _, setOfKeyphrases := range intent.Keyphrases {
			for keyphrase, newphrase := range setOfKeyphrases {
				text, _ = bTextReplace(text, keyphrase, newphrase)
			}
		}

	}
	// Do the same for keyphrases in Collections eventually

	return strings.TrimSpace(text)

}

// Will always return lowercase text
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
