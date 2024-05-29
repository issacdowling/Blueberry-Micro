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

var collectionHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedCollectionJson map[string]interface{}
	err := json.Unmarshal(message.Payload(), &receivedCollectionJson)
	if err != nil {
		bLogFatal(err.Error(), l)
	}
	receivedCollections := receivedCollectionJson["collections"].([]interface{})

	// For each received list of Collections, split it out into the individual Collections, store them, and add them to the list
	for _, collectionInterface := range receivedCollections {
		// This marshalling then unmarshalling is awkward and there must be a better way
		currentCollectionJson, err := json.Marshal(collectionInterface)
		if err != nil {
			bLogFatal(err.Error(), l)
		}
		var currentCollection Collection
		json.Unmarshal(currentCollectionJson, &currentCollection)

		bLog(fmt.Sprintf("Received Collection: %s", currentCollection.Id), l)

		collections[currentCollection.Id] = currentCollection
		collectionIds = append(collectionIds, currentCollection.Id)

		// Publish the list of known Collections as new ones are received.
		listCollectionsJson, err := json.Marshal(map[string]interface{}{
			"loaded_collections": collectionIds,
		})
		if err != nil {
			bLogFatal(err.Error(), l)
		}
		if token := client.Publish(fmt.Sprintf("bloob/%s/collections/list", deviceId), bloobQOS, true, listCollectionsJson); token.Wait() && token.Error() != nil {
			bLogFatal(token.Error().Error(), l)
		}
		broker.SetWill(fmt.Sprintf("bloob/%s/collections/list", deviceId), "", bloobQOS, true)

	}

}

var intentHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {

}
