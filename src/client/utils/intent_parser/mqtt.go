package main

import (
	"encoding/json"
	"fmt"

	bloob "blueberry/gobloob"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var onConnect mqtt.OnConnectHandler = func(client mqtt.Client) {
	c.Log("Connected to MQTT broker")
}

const parseResponseTopic string = "bloob/%s/cores/intent_parser_util/finished"
const instantIntentListTopic string = "bloob/%s/instant_intents"

var parseHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var currentParse bloob.ParseRequest
	err := json.Unmarshal(message.Payload(), &currentParse)
	if err != nil {
		c.LogFatal(err.Error())
	}

	intentParsed := parseIntent(currentParse.Text)

	parseResponseToSend, err := json.Marshal(bloob.ParseResponse{Id: currentParse.Id, Text: intentParsed.ParsedText, CoreId: intentParsed.CoreId, IntentId: intentParsed.IntentId})
	if err != nil {
		c.LogFatal(fmt.Sprintf("Could not JSON encode Intent Parse response: %s", err.Error()))
	}
	if token := client.Publish(fmt.Sprintf(parseResponseTopic, *deviceId), bloob.BloobQOS, false, parseResponseToSend); token.Wait() && token.Error() != nil {
		c.LogFatal(token.Error().Error())
	}

	c.Log(fmt.Sprintf("Intent: %s, Core: %s, Parsed Text: %s", intentParsed.IntentId, intentParsed.CoreId, intentParsed.ParsedText))

}

var collectionHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedCollection bloob.Collection
	err := json.Unmarshal(message.Payload(), &receivedCollection)
	if err != nil {
		c.LogFatal(err.Error())
	}

	c.Log(fmt.Sprintf("Received Collection: %s", receivedCollection.Id))

	collections[receivedCollection.Id] = receivedCollection

}

var intentHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedIntent bloob.Intent
	err := json.Unmarshal(message.Payload(), &receivedIntent)
	if err != nil {
		c.LogFatal(fmt.Sprintf("Failed to parse received intent: %s", err.Error()))
	}
	c.Log(fmt.Sprintf("Received intent \"%s\" for Core \"%s\"", receivedIntent.Id, receivedIntent.CoreId))
	intents[receivedIntent.Id] = receivedIntent

	// if there are wakewords associated with an Intent, register those
	if receivedIntent.Wakewords != nil {
		for _, wakeword := range receivedIntent.Wakewords {
			instantIntents[wakeword] = receivedIntent
		}
		instantIntentListJson, err := json.Marshal(instantIntents)
		if err != nil {
			c.LogFatal(fmt.Sprintf("Failed to encode the list of Instant Intents: %s", err.Error()))
		}
		client.Publish(fmt.Sprintf(instantIntentListTopic, *deviceId), bloob.BloobQOS, true, instantIntentListJson)
	}
}
