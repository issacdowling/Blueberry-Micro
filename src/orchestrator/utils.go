package main

import (
	"encoding/json"
	"fmt"
	"log"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

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
		log.Panicln(err)

	}

	client.Publish(fmt.Sprintf(playAudioFileTopic, uuid), bloobQOS, false, audioPlaybackJson)
}

func startRecordingAudio(uuid string, id string, client mqtt.Client) {
	audioRecordMessage := map[string]string{
		"id": id,
	}
	audioRecordJson, err := json.Marshal(audioRecordMessage)
	if err != nil {
		log.Panic(err)
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
		log.Panicln(err)

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
		log.Panicln(err)

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
		log.Panic(err)
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
		log.Panic(err)
	}
	client.Publish(fmt.Sprintf(ttsTopic, uuid), bloobQOS, false, ttsMessageJson)
}
