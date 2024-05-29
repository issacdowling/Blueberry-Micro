package main

import (
	"encoding/json"
	"fmt"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const bloobQOS byte = 2

var collectionIds []string

var onConnect mqtt.OnConnectHandler = func(client mqtt.Client) {
	bLog("Connected to MQTT broker", l)
}

const parseResponseTopic string = "bloob/%s/cores/intent_parser_util/finished"

var parseHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var currentParse ParseRequest
	err := json.Unmarshal(message.Payload(), &currentParse)
	if err != nil {
		bLogFatal(err.Error(), l)
	}

	intentToFire, coreToFire, parsedText := parseIntent(currentParse.Text)

	parseResponseToSend, err := json.Marshal(ParseResponse{Id: currentParse.Id, Text: parsedText, CoreId: coreToFire, IntentId: intentToFire})
	if err != nil {
		bLogFatal(fmt.Sprintf("Could not JSON encode Intent Parse response: %s", err.Error()), l)
	}
	client.Publish(fmt.Sprintf(parseResponseTopic, *deviceId), bloobQOS, false, parseResponseToSend)

	bLog(fmt.Sprintf("Intent: %s, Core: %s, Parsed Text: %s", intentToFire, coreToFire, parsedText), l)

}

var collectionHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedCollection Collection
	err := json.Unmarshal(message.Payload(), &receivedCollection)
	if err != nil {
		bLogFatal(err.Error(), l)
	}

	bLog(fmt.Sprintf("Received Collection: %s", receivedCollection.Id), l)

	collections[receivedCollection.Id] = receivedCollection

}

var intentHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedIntent Intent
	err := json.Unmarshal(message.Payload(), &receivedIntent)
	if err != nil {
		bLogFatal(fmt.Sprintf("Failed to parse received intent: %s", err.Error()), l)
	}
	bLog(fmt.Sprintf("Received intent \"%s\" for Core \"%s\"", receivedIntent.Id, receivedIntent.CoreId), l)
	intents[receivedIntent.Id] = receivedIntent
}
