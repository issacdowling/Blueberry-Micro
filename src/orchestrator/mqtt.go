package main

import (
	"encoding/json"
	"log"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const bloobQOS byte = 2

var id string = "1000"

var wakewordReceivedJson map[string]interface{}

var recordedAudio string
var audioRecorderReceivedJson map[string]interface{}

var transcription string
var transcriptionReceivedJson map[string]interface{}

var intentParserReceivedJson map[string]interface{}

type MqttConfig struct {
	Host     string
	Port     string
	Username string
	Password string
}

var onConnect mqtt.OnConnectHandler = func(client mqtt.Client) {
	log.Println("Connected to MQTT broker")
}

var pipelineMessageHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var instanceUUID string = bloobConfig["uuid"].(string)

	if strings.Contains(message.Topic(), "wakeword/detected") {
		json.Unmarshal(message.Payload(), &wakewordReceivedJson)
		log.Printf("Wakeword Received - %v - recording audio", wakewordReceivedJson["wakeword_id"].(string))
		playAudioFile(beginListeningAudio, instanceUUID, id, client)
		startRecordingAudio(instanceUUID, id, client)
	}

	if strings.Contains(message.Topic(), "audio_recorder/finished") {
		playAudioFile(stopListeningAudio, instanceUUID, id, client)
		json.Unmarshal(message.Payload(), &audioRecorderReceivedJson)

		if audioRecorderReceivedJson["id"].(string) == id {
			log.Printf("Received recording, starting transcription")
			recordedAudio = audioRecorderReceivedJson["audio"].(string)
			transcribeAudio(recordedAudio, instanceUUID, id, client)
		}
	}

	if strings.Contains(message.Topic(), "stt/finished") {
		json.Unmarshal(message.Payload(), &transcriptionReceivedJson)

		if transcriptionReceivedJson["id"].(string) == id {
			transcription = transcriptionReceivedJson["text"].(string)
			log.Printf("Transcription received - %v - starting intent parsing", transcription)
			intentParseText(transcription, instanceUUID, id, client)
		}

	}

	// This won't work until Core Configs and collections and intents are done.
	if strings.Contains(message.Topic(), "intent_parser/finished") {
		json.Unmarshal(message.Payload(), &intentParserReceivedJson)

		if intentParserReceivedJson["id"].(string) == id {
			log.Printf("Intent Parsed - %v - sending to core", intentParserReceivedJson["intent"].(string))
			// Get the core from the intent and send it there, then wait for the response by using a wildcard in the core topic,
			// and using the ID to ensure that we're looking at the right response.
		}

	}

}
