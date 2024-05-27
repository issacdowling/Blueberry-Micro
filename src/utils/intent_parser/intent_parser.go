package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
)

type Intent struct {
	Id            string
	CoreId        string
	Keyphrases    []map[string]string
	CollectionIds [][]string `json:"collection_ids"`
	Prefixes      []string
	Suffixes      []string
}

type Collection struct {
}

type Check struct {
	Id  string
	Run func(string, Intent)
}

var checks []Check = []Check{
	{Id: "keyphrases", Run: keyphraseCheck},
	{Id: "prefixes", Run: prefixCheck},
	{Id: "suffixes", Run: suffixCheck},
	{Id: "collections", Run: collectionCheck},
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
		"collection_ids": [["colours", "boolean"], ["set"]],
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
	fmt.Println(postProcessText(preCleanText("Good evening, hey, hello there, time times"), testDataJson))
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

func parseIntent(text string) (Intent, string) {
	for _, intent := range intents {

		for _, check := range checks {
			check.Run(text, intent)
		}

	}

	return Intent{}, ""
}

func postProcessText(text string, intent Intent) string {

	// For all keyphrases, replace with their substitute values if not empty
	for _, keyphraseSet := range intent.Keyphrases {
		for keyphrase, newPhrase := range keyphraseSet {
			text = bReplace(text, keyphrase, newPhrase)

		}
	}

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

	return text
}
