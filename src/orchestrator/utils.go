package main

import (
	"encoding/json"
	"fmt"
	"log"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

type logData struct {
	uuid   string
	client mqtt.Client
	name   string
}

const playAudioFileTopic string = "bloob/%s/audio_playback/play_file"
const recordSpeechTopic string = "bloob/%s/audio_recorder/record_speech"
const transcribeAudioTopic string = "bloob/%s/stt/transcribe"
const intentParseTopic string = "bloob/%s/intent_parser/run"
const coreTopic string = "bloob/%s/cores/%s/run"
const ttsTopic string = "bloob/%s/tts/run"

func playAudioFile(audio string, uuid string, id string, client mqtt.Client) {
	audioPlaybackMessage := map[string]string{
		"id":    id,
		"audio": audio,
	}
	audioPlaybackJson, err := json.Marshal(audioPlaybackMessage)
	if err != nil {
		bLogFatal(err.Error(), l)

	}

	client.Publish(fmt.Sprintf(playAudioFileTopic, uuid), bloobQOS, false, audioPlaybackJson)
}

func startRecordingAudio(uuid string, id string, client mqtt.Client) {
	audioRecordMessage := map[string]string{
		"id": id,
	}
	audioRecordJson, err := json.Marshal(audioRecordMessage)
	if err != nil {
		bLogFatal(err.Error(), l)
	}
	client.Publish(fmt.Sprintf(recordSpeechTopic, uuid), bloobQOS, false, audioRecordJson)
}

func transcribeAudio(audio string, uuid string, id string, client mqtt.Client) {
	audioTranscribeMessage := map[string]string{
		"id":    id,
		"audio": audio,
	}
	audioTranscribeJson, err := json.Marshal(audioTranscribeMessage)
	if err != nil {
		bLogFatal(err.Error(), l)

	}

	client.Publish(fmt.Sprintf(transcribeAudioTopic, uuid), bloobQOS, false, audioTranscribeJson)
}

func intentParseText(text string, uuid string, id string, client mqtt.Client) {
	intentParseMessage := map[string]string{
		"id":   id,
		"text": text,
	}
	intentParseJson, err := json.Marshal(intentParseMessage)
	if err != nil {
		bLogFatal(err.Error(), l)

	}
	client.Publish(fmt.Sprintf(intentParseTopic, uuid), bloobQOS, false, intentParseJson)
}

func sendIntentToCore(intent string, text string, coreId string, uuid string, id string, client mqtt.Client) {
	coreMessage := map[string]string{
		"id":      id,
		"intent":  intent,
		"core_id": coreId,
		"text":    text,
	}
	coreMessageJson, err := json.Marshal(coreMessage)
	if err != nil {
		bLogFatal(err.Error(), l)
	}
	client.Publish(fmt.Sprintf(coreTopic, uuid, coreId), bloobQOS, false, coreMessageJson)
}

func speakText(text string, uuid string, id string, client mqtt.Client) {
	ttsMessage := map[string]string{
		"id":   id,
		"text": text,
	}
	ttsMessageJson, err := json.Marshal(ttsMessage)
	if err != nil {
		bLogFatal(err.Error(), l)
	}
	client.Publish(fmt.Sprintf(ttsTopic, uuid), bloobQOS, false, ttsMessageJson)
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
