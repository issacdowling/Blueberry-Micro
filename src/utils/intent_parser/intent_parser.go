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
}

type Collection struct {
}

var intents []Intent

var collections []Collection

func main() {
	// Test data
	testData := []byte(`
	{
		"id": "setWLED",
		"keyphrases": [{"hello there": "hi", "hey": ""}, {"time": "1", "times": "2"}],
		"core_id": "wled",
		"collections": [["colours", "boolean"], ["set"]],
		"prefixes": ["ask wled to", "do"],
		"suffixes": ["thanks", "or else"]
	}	
	`)

	var testDataJson Intent
	err := json.Unmarshal(testData, &testDataJson)
	if err != nil {
		log.Panic(err)
	}

	fmt.Println(testDataJson)

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
		intentPass := true
		// This should eventually be a for loop that adapts to any future checks...
		// it's not that yet.
		if intent.Keyphrases != nil {
			checkPass, log := keyphraseCheck(text, intent)
			if !checkPass {
				intentPass = false
			}
			fmt.Println(log)
		}

		if intent.Prefixes != nil {
			checkPass, log := prefixCheck(text, intent)
			if !checkPass {
				intentPass = false
			}
			fmt.Println(log)
		}

		if intent.Suffixes != nil {
			checkPass, log := suffixCheck(text, intent)
			if !checkPass {
				intentPass = false
			}
			fmt.Println(log)
		}

		// if intent.Keyphrases != nil {
		// 	checkPass, _ := keyphraseCheck(text, intent)
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

func postProcessText(text string, intent Intent) string {

	// Do the same for keyphrases in Collections eventually

	return text

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

	return text
}
