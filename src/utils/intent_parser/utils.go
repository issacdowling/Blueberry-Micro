package main

import (
	"fmt"
	"log"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type logData struct {
	uuid   string
	client mqtt.Client
	name   string
}

func bTextMatches(text string, checks []string) map[int]string {
	matches := make(map[int]string)
	for _, check := range checks {
		// If the check is one word, check for whole-word matches, multi-word gets regular .Contains
		if len(strings.Split(check, " ")) == 1 {
			// Replace matches & for loop so indices preserved for multiple checks, catches multiple of same word
			for _, word := range strings.Split(text, " ") {
				if word == check {
					matches[strings.Index(text, check)] = check
					text = strings.Replace(text, check, strings.Repeat("_", len(check)), 1)
				}
			}
		} else {
			for strings.Contains(text, check) {
				matches[strings.Index(text, check)] = check
				text = strings.Replace(text, check, strings.Repeat("_", len(check)), 1)
			}
		}
	}

	return matches
}

func bTextReplace(text string, oldPhrase string, newPhrase string) (string, bool) {
	changeMade := false
	// If the check is one word, check for whole-word matches, multi-word gets regular .Contains
	untouchedText := text
	if len(strings.Split(oldPhrase, " ")) == 1 {
		var tempText string
		for _, word := range strings.Split(text, " ") {
			if word == oldPhrase {
				tempText = strings.Join([]string{tempText, newPhrase}, " ")
			} else {
				tempText = strings.Join([]string{tempText, word}, " ")
			}
		}
		text = tempText
	} else {
		text = strings.Replace(text, oldPhrase, newPhrase, -1)
	}

	if untouchedText != text {
		changeMade = true
	}

	return text, changeMade
}

func bLog(text string, ld logData) {
	logMessage := fmt.Sprintf("[%s] %s", ld.name, text)
	if ld.client != nil && ld.uuid != "" {
		ld.client.Publish(fmt.Sprintf("bloob/%s/logs", ld.uuid), bloobQOS, false, logMessage)
	} else {
		logMessage = fmt.Sprintf("[NO MQTT LOGS] %s", logMessage)
	}

	log.Print(logMessage)
}

func bLogFatal(text string, ld logData) {
	logMessage := fmt.Sprintf("!FATAL! [%s] %s", ld.name, text)

	if ld.client != nil {
		ld.client.Publish(fmt.Sprintf("bloob/%s/logs", ld.uuid), bloobQOS, false, logMessage)
	}
	log.Fatal(logMessage)
}
