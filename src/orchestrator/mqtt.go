package main

import (
	"encoding/json"
	"fmt"
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

var coreFinishedReceivedJson map[string]interface{}

var ttsReceivedJson map[string]interface{}

type MqttConfig struct {
	Host     string
	Port     string
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

	if strings.Contains(message.Topic(), "wakeword_util/detected") {
		json.Unmarshal(message.Payload(), &wakewordReceivedJson)
		bLog(fmt.Sprintf("Wakeword Received - %v - recording audio", wakewordReceivedJson["wakeword_id"].(string)), l)
		playAudioFile(beginListeningAudio, instanceUUID, id, client)
		startRecordingAudio(instanceUUID, id, client)
	}

	if strings.Contains(message.Topic(), "audio_recorder_util/finished") {
		playAudioFile(stopListeningAudio, instanceUUID, id, client)
		json.Unmarshal(message.Payload(), &audioRecorderReceivedJson)

		if audioRecorderReceivedJson["id"].(string) == id {
			bLog("Received recording, starting transcription", l)
			recordedAudio = audioRecorderReceivedJson["audio"].(string)
			transcribeAudio(recordedAudio, instanceUUID, id, client)
		}
	}

	if strings.Contains(message.Topic(), "stt_util/finished") {
		json.Unmarshal(message.Payload(), &transcriptionReceivedJson)

		if transcriptionReceivedJson["id"].(string) == id {
			transcription = transcriptionReceivedJson["text"].(string)
			bLog(fmt.Sprintf("Transcription received - %v - starting intent parsing", transcription), l)
			intentParseText(transcription, instanceUUID, id, client)
		}

	}

	// This won't work until Core Configs and collections and intents are done.
	if strings.Contains(message.Topic(), "intent_parser_util/finished") {
		json.Unmarshal(message.Payload(), &intentParserReceivedJson)

		if intentParserReceivedJson["id"].(string) == id {
			// We need an Error core instead
			if _, ok := intentParserReceivedJson["intent"].(string); ok {
				bLog(fmt.Sprintf("Intent Parsed - %v - sending to core", intentParserReceivedJson["intent"].(string)), l)
				// Get the core from the intent and send it there, then wait for the response by using a wildcard in the core topic,
				// and using the ID to ensure that we're looking at the right response.
				sendIntentToCore(intentParserReceivedJson["intent"].(string), intentParserReceivedJson["text"].(string), intentParserReceivedJson["core_id"].(string), instanceUUID, id, client)
			} else {
				bLog("No Intent Found in speech", l)
				speakText("I'm sorry, I don't understand what you said", instanceUUID, id, client)
			}

		}

	}

	// Specifically, here, I do not want responses from Utils, only regular Cores
	if strings.Contains(message.Topic(), "/cores") && strings.Contains(message.Topic(), "/finished") && !strings.Contains(message.Topic(), "util") {
		json.Unmarshal(message.Payload(), &coreFinishedReceivedJson)

		if coreFinishedReceivedJson["id"].(string) == id {
			bLog(fmt.Sprintf("Core ran with the output: %v", coreFinishedReceivedJson["text"].(string)), l)

			speakText(coreFinishedReceivedJson["text"].(string), instanceUUID, id, client)
		}

	}

	if strings.Contains(message.Topic(), "/tts/finished") {
		json.Unmarshal(message.Payload(), &ttsReceivedJson)

		if ttsReceivedJson["id"].(string) == id {
			bLog("Text Spoken", l)

			playAudioFile(ttsReceivedJson["audio"].(string), instanceUUID, id, client)
		}

	}

}
