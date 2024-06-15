package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"strings"

	bloob "blueberry/gobloob"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var wakewordReceived bloob.WakewordResponse

var recordedAudio string
var audioRecorderReceived bloob.AudioRecorderResponse

var transcription string
var transcriptionReceived bloob.TranscriptionResponse

var intentParserReceived bloob.IntentParseResponse

var coreFinishedReceived bloob.CoreResponse

var ttsReceived bloob.TTSResponse

// var collectionIds []string

var currentId string = ""

var onConnect mqtt.OnConnectHandler = func(client mqtt.Client) {
	c.Log("Connected to MQTT broker")
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
	if strings.Contains(message.Topic(), "wakeword_util/finished") {
		// If a current request isn't ongoing
		if currentId == "" {
			newId := fmt.Sprintf("%d", rand.Uint32())
			currentId = newId
			json.Unmarshal(message.Payload(), &wakewordReceived)
			// TODO: Add Instant Intent support
			c.Log(fmt.Sprintf("Wakeword Received - %v (confidence %v) - recording audio", wakewordReceived.WakewordId, wakewordReceived.Confidence))

			if _, ok := instantIntents[wakewordReceived.WakewordId]; ok {
				c.PlayAudioFile(instantIntentAudio, newId)
				c.IntentParseText(fmt.Sprintf("$instant:%s", wakewordReceived.WakewordId), newId)
				c.SetThinking(true)
			} else {
				c.PlayAudioFile(beginListeningAudio, newId)
				c.StartRecordingAudio(newId)
				c.SetRecording(true)
			}
		}

	}

	if strings.Contains(message.Topic(), "audio_recorder_util/finished") {
		json.Unmarshal(message.Payload(), &audioRecorderReceived)

		if currentId == audioRecorderReceived.Id {
			c.SetRecording(false)
			c.PlayAudioFile(stopListeningAudio, audioRecorderReceived.Id)
			c.SetThinking(true)
			c.Log("Received recording, starting transcription")
			recordedAudio = audioRecorderReceived.Audio
			c.TranscribeAudioFile(recordedAudio, audioRecorderReceived.Id)
		}
	}

	if strings.Contains(message.Topic(), "stt_util/finished") {
		json.Unmarshal(message.Payload(), &transcriptionReceived)

		if currentId == transcriptionReceived.Id {
			transcription = transcriptionReceived.Text
			c.Log(fmt.Sprintf("Transcription received - %v - starting intent parsing", transcription))
			c.IntentParseText(transcription, transcriptionReceived.Id)
		}

	}

	// This won't work until Core Configs and collections and intents are done.
	if strings.Contains(message.Topic(), "intent_parser_util/finished") {
		json.Unmarshal(message.Payload(), &intentParserReceived)

		if currentId == intentParserReceived.Id {
			// We need an Error core instead
			if strings.TrimSpace(intentParserReceived.IntentId) != "" {
				c.Log(fmt.Sprintf("Intent Parsed - %s - sending to core %s", intentParserReceived.IntentId, intentParserReceived.CoreId))
				// Get the core from the intent and send it there, then wait for the response by using a wildcard in the core topic,
				// and using the ID to ensure that we're looking at the right response.
				c.SendIntentToCore(intentParserReceived.IntentId, intentParserReceived.Text, intentParserReceived.CoreId, intentParserReceived.Id)
			} else {
				c.PlayAudioFile(errorAudio, intentParserReceived.Id)
				c.Log("No Intent Found in speech")
				currentId = ""
				c.Log("Waiting for wakeword...")
				// speakText("I'm sorry, I don't understand what you said", intentParserReceived.Id)
			}

		}

	}

	// Specifically, here, I do not want responses from Utils, only regular Cores
	if strings.Contains(message.Topic(), "/cores") && strings.Contains(message.Topic(), "/finished") && !strings.Contains(message.Topic(), "util") {
		json.Unmarshal(message.Payload(), &coreFinishedReceived)

		if currentId == coreFinishedReceived.Id {
			c.Log(fmt.Sprintf("Core ran with the output: %v", coreFinishedReceived.Text))

			c.SpeakText(coreFinishedReceived.Text, coreFinishedReceived.Id)
		}

	}

	if strings.Contains(message.Topic(), "/tts_util/finished") {
		json.Unmarshal(message.Payload(), &ttsReceived)

		if currentId == ttsReceived.Id {
			c.SetThinking(false)
			c.Log("Text Spoken")

			c.PlayAudioFile(ttsReceived.Audio, ttsReceived.Id)

			// Reset the currentId to 0 so that we'll accept another wakeword
			currentId = ""
			c.Log("Waiting for wakeword...")

		}

	}

}

var instantIntentRegister mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	var receivedInstantIntents map[string]interface{}
	if string(message.Payload()) != "" {
		err := json.Unmarshal(message.Payload(), &receivedInstantIntents)
		if err != nil {
			c.LogFatal(fmt.Sprintf("Failed to parse received list of Instant Intents: %s", err.Error()))
		}
		c.Log(fmt.Sprintf("Received instant intents: %s", receivedInstantIntents))
		for wakeword, intentId := range receivedInstantIntents {
			instantIntents[wakeword] = intentId.(map[string]interface{})["id"].(string)
		}
	} else {
		c.Log("Received blank Instant Intent message (maybe topics are being cleaned up?)")
	}

}

var clearTopics mqtt.MessageHandler = func(client mqtt.Client, message mqtt.Message) {
	if !strings.Contains(message.Topic(), "logs") && string(message.Payload()) != "" {
		c.Log(fmt.Sprintf("Clearing latent topic: %s", message.Topic()))
		// !!!!!!!! CLEARING THE RETAINED MESSAGES ONLY WORKED WITH QOS 0 !!!!!!!!!!! (i don't know why)
		if token := client.Publish(message.Topic(), 0, true, []byte{}); token.Wait() && token.Error() != nil {
			c.LogFatal(token.Error().Error())
		}
	}

}
