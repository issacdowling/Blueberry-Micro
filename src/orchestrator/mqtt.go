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

const bloobQOS byte = 1

var wakewordReceived WakewordResponse

var recordedAudio string
var audioRecorderReceived AudioRecorderResponse

var transcription string
var transcriptionReceived TranscriptionResponse

var intentParserReceived IntentParseResponse

var coreFinishedReceived CoreResponse

var ttsReceived TTSResponse

var collectionTopic string = "bloob/%s/collections/%s"

var collectionIds []string

var currentIds []string

type MqttConfig struct {
	Host     string
	Port     int
	Username string
	Password string
}

type WakewordResponse struct {
	WakewordId string `json:"wakeword_id"`
	Confidence string `json:"confidence"`
}

type AudioRecorderResponse struct {
	Id    string `json:"id"`
	Audio string `json:"audio"`
}

type TranscriptionResponse struct {
	Id   string `json:"id"`
	Text string `json:"text"`
}

type IntentParseResponse struct {
	Id       string `json:"id"`
	Text     string `json:"text"`
	IntentId string `json:"intent_id"`
	CoreId   string `json:"core_id"`
}

type CoreResponse struct {
	Id          string `json:"id"`
	Text        string `json:"text"`
	Explanation string `json:"explanation"`
}

type TTSResponse struct {
	Id    string `json:"id"`
	Audio string `json:"audio"`
}

var onConnect mqtt.OnConnectHandler = func(client mqtt.Client) {
	bLog("Connected to MQTT broker", l)
}

var remoteLogDisplay mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	if !strings.Contains(string(message.Payload()), "[Orchestrator]") {
		log.Print(string(message.Payload()))
	}
}

// Need to work on a way to track an ID's progress through the steps and ensure that duplicates aren't recognised.
// Also work on not responding to a new wakeword during the processing of another request. Could use the currentIds array
// if I remove them once done.
var pipelineMessageHandler mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var instanceUUID string = bloobConfig["uuid"].(string)

	if strings.Contains(message.Topic(), "wakeword_util/finished") {
		newId := fmt.Sprintf("%d", rand.Uint32())
		currentIds = append(currentIds, newId)
		json.Unmarshal(message.Payload(), &wakewordReceived)
		// TODO: Add Instant Intent support
		bLog(fmt.Sprintf("Wakeword Received - %v (confidence %v) - recording audio", wakewordReceived.WakewordId, wakewordReceived.Confidence), l)

		if _, ok := instantIntents[wakewordReceived.WakewordId]; ok {
			playAudioFile(instantIntentAudio, instanceUUID, newId, client)
			intentParseText(fmt.Sprintf("$instant:%s", wakewordReceived.WakewordId), instanceUUID, newId, client)
		} else {
			playAudioFile(beginListeningAudio, instanceUUID, newId, client)
			startRecordingAudio(instanceUUID, newId, client)
			setRecording(true, instanceUUID, client)
		}

	}

	if strings.Contains(message.Topic(), "audio_recorder_util/finished") {
		json.Unmarshal(message.Payload(), &audioRecorderReceived)

		if slices.Contains(currentIds, audioRecorderReceived.Id) {
			setRecording(false, instanceUUID, client)
			playAudioFile(stopListeningAudio, instanceUUID, audioRecorderReceived.Id, client)
			setThinking(true, instanceUUID, client)
			bLog("Received recording, starting transcription", l)
			recordedAudio = audioRecorderReceived.Audio
			transcribeAudio(recordedAudio, instanceUUID, audioRecorderReceived.Id, client)
		}
	}

	if strings.Contains(message.Topic(), "stt_util/finished") {
		json.Unmarshal(message.Payload(), &transcriptionReceived)

		if slices.Contains(currentIds, transcriptionReceived.Id) {
			transcription = transcriptionReceived.Text
			bLog(fmt.Sprintf("Transcription received - %v - starting intent parsing", transcription), l)
			intentParseText(transcription, instanceUUID, transcriptionReceived.Id, client)
		}

	}

	// This won't work until Core Configs and collections and intents are done.
	if strings.Contains(message.Topic(), "intent_parser_util/finished") {
		json.Unmarshal(message.Payload(), &intentParserReceived)

		if slices.Contains(currentIds, intentParserReceived.Id) {
			setThinking(false, instanceUUID, client)
			// We need an Error core instead
			if strings.TrimSpace(intentParserReceived.IntentId) != "" {
				bLog(fmt.Sprintf("Intent Parsed - %s - sending to core %s", intentParserReceived.IntentId, intentParserReceived.CoreId), l)
				// Get the core from the intent and send it there, then wait for the response by using a wildcard in the core topic,
				// and using the ID to ensure that we're looking at the right response.
				sendIntentToCore(intentParserReceived.IntentId, intentParserReceived.Text, intentParserReceived.CoreId, instanceUUID, intentParserReceived.Id, client)
			} else {
				playAudioFile(errorAudio, instanceUUID, intentParserReceived.Id, client)
				bLog("No Intent Found in speech", l)
				// speakText("I'm sorry, I don't understand what you said", instanceUUID, intentParserReceived.Id, client)
			}

		}

	}

	// Specifically, here, I do not want responses from Utils, only regular Cores
	if strings.Contains(message.Topic(), "/cores") && strings.Contains(message.Topic(), "/finished") && !strings.Contains(message.Topic(), "util") {
		json.Unmarshal(message.Payload(), &coreFinishedReceived)

		if slices.Contains(currentIds, coreFinishedReceived.Id) {
			bLog(fmt.Sprintf("Core ran with the output: %v", coreFinishedReceived.Text), l)

			speakText(coreFinishedReceived.Text, instanceUUID, coreFinishedReceived.Id, client)
		}

	}

	if strings.Contains(message.Topic(), "/tts_util/finished") {
		json.Unmarshal(message.Payload(), &ttsReceived)

		if slices.Contains(currentIds, ttsReceived.Id) {
			bLog("Text Spoken", l)

			playAudioFile(ttsReceived.Audio, instanceUUID, ttsReceived.Id, client)
		}

	}

}

var instantIntentRegister mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedInstantIntents map[string]interface{}
	fmt.Println(string(message.Payload()))
	err := json.Unmarshal(message.Payload(), &receivedInstantIntents)
	if err != nil {
		bLogFatal(fmt.Sprintf("Failed to parse received list of Instant Intents: %s", err.Error()), l)
	}
	bLog(fmt.Sprintf("Received instant intents: %s", receivedInstantIntents), l)
	for wakeword, intentId := range receivedInstantIntents {
		instantIntents[wakeword] = intentId.(map[string]interface{})["id"].(string)
	}
}

var clearTopics mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	if !strings.Contains(message.Topic(), "logs") && string(message.Payload()) != "" {
		bLog(fmt.Sprintf("Clearing latent topic: %s", message.Topic()), l)
		// !!!!!!!! CLEARING THE RETAINED MESSAGES ONLY WORKED WITH QOS 0 !!!!!!!!!!! (i don't know why)
		if token := client.Publish(message.Topic(), 0, true, []byte{}); token.Wait() && token.Error() != nil {
			bLogFatal(token.Error().Error(), l)
		}
	}

}
