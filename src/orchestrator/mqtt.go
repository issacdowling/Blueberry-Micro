package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"slices"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const bloobQOS byte = 2

var wakewordReceivedJson map[string]interface{}

var recordedAudio string
var audioRecorderReceivedJson map[string]interface{}

var transcription string
var transcriptionReceivedJson map[string]interface{}

var intentParserReceivedJson map[string]interface{}

var coreFinishedReceivedJson map[string]interface{}

var ttsReceivedJson map[string]interface{}

var collectionTopic string = "bloob/%s/collections/%s"

var collectionIds []string

var currentIds []string

type MqttConfig struct {
	Host     string
	Port     int
	Username string
	Password string
}

var onConnect mqtt.OnConnectHandler = func(client mqtt.Client) {
	bLog("Connected to MQTT broker", l)
}

var remoteLogDisplay mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	if !strings.Contains(string(message.Payload()), "[Orchestrator]") {
		log.Print(string(message.Payload()))
	}
}

var pipelineMessageHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var instanceUUID string = bloobConfig["uuid"].(string)

	if strings.Contains(message.Topic(), "wakeword_util/finished") {
		newId := fmt.Sprintf("%d", rand.Uint32())
		currentIds = append(currentIds, newId)
		json.Unmarshal(message.Payload(), &wakewordReceivedJson)
		bLog(fmt.Sprintf("Wakeword Received - %v - recording audio", wakewordReceivedJson["wakeword_id"].(string)), l)
		playAudioFile(beginListeningAudio, instanceUUID, newId, client)
		startRecordingAudio(instanceUUID, newId, client)
	}

	if strings.Contains(message.Topic(), "audio_recorder_util/finished") {
		json.Unmarshal(message.Payload(), &audioRecorderReceivedJson)

		if slices.Contains(currentIds, audioRecorderReceivedJson["id"].(string)) {
			playAudioFile(stopListeningAudio, instanceUUID, audioRecorderReceivedJson["id"].(string), client)
			bLog("Received recording, starting transcription", l)
			recordedAudio = audioRecorderReceivedJson["audio"].(string)
			transcribeAudio(recordedAudio, instanceUUID, audioRecorderReceivedJson["id"].(string), client)
		}
	}

	if strings.Contains(message.Topic(), "stt_util/finished") {
		json.Unmarshal(message.Payload(), &transcriptionReceivedJson)

		if slices.Contains(currentIds, transcriptionReceivedJson["id"].(string)) {
			transcription = transcriptionReceivedJson["text"].(string)
			bLog(fmt.Sprintf("Transcription received - %v - starting intent parsing", transcription), l)
			intentParseText(transcription, instanceUUID, transcriptionReceivedJson["id"].(string), client)
		}

	}

	// This won't work until Core Configs and collections and intents are done.
	if strings.Contains(message.Topic(), "intent_parser_util/finished") {
		json.Unmarshal(message.Payload(), &intentParserReceivedJson)

		if slices.Contains(currentIds, intentParserReceivedJson["id"].(string)) {
			// We need an Error core instead
			if _, ok := intentParserReceivedJson["intent"].(string); ok {
				bLog(fmt.Sprintf("Intent Parsed - %v - sending to core", intentParserReceivedJson["intent"].(string)), l)
				// Get the core from the intent and send it there, then wait for the response by using a wildcard in the core topic,
				// and using the ID to ensure that we're looking at the right response.
				sendIntentToCore(intentParserReceivedJson["intent"].(string), intentParserReceivedJson["text"].(string), intentParserReceivedJson["core_id"].(string), instanceUUID, intentParserReceivedJson["id"].(string), client)
			} else {
				bLog("No Intent Found in speech", l)
				speakText("I'm sorry, I don't understand what you said", instanceUUID, intentParserReceivedJson["id"].(string), client)
			}

		}

	}

	// Specifically, here, I do not want responses from Utils, only regular Cores
	if strings.Contains(message.Topic(), "/cores") && strings.Contains(message.Topic(), "/finished") && !strings.Contains(message.Topic(), "util") {
		json.Unmarshal(message.Payload(), &coreFinishedReceivedJson)

		if slices.Contains(currentIds, coreFinishedReceivedJson["id"].(string)) {
			bLog(fmt.Sprintf("Core ran with the output: %v", coreFinishedReceivedJson["text"].(string)), l)

			speakText(coreFinishedReceivedJson["text"].(string), instanceUUID, coreFinishedReceivedJson["id"].(string), client)
		}

	}

	if strings.Contains(message.Topic(), "/tts_util/finished") {
		json.Unmarshal(message.Payload(), &ttsReceivedJson)

		if slices.Contains(currentIds, ttsReceivedJson["id"].(string)) {
			bLog("Text Spoken", l)

			playAudioFile(ttsReceivedJson["audio"].(string), instanceUUID, ttsReceivedJson["id"].(string), client)
		}

	}

}
