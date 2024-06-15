package gobloob

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

const PlayAudioFileTopic string = "bloob/%s/cores/audio_playback_util/play_file"
const RecordSpeechTopic string = "bloob/%s/cores/audio_recorder_util/record_speech"
const TranscribeAudioTopic string = "bloob/%s/cores/stt_util/transcribe"
const IntentParseTopic string = "bloob/%s/cores/intent_parser_util/run"
const TtsTopic string = "bloob/%s/cores/tts_util/run"
const CoreTopic string = "bloob/%s/cores/%s/run"
const InstantIntentTopic string = "bloob/%s/instant_intents"

const thinkingTopic string = "bloob/%s/thinking"
const recordingTopic string = "bloob/%s/recording"

const BloobQOS byte = 1

type Core struct {
	DeviceId     string
	Id           string
	FriendlyName string
	// Config   CoreConfig
	Intents     []string
	Collections []string
	MqttClient  mqtt.Client
	MqttHost    string
	MqttPort    int
	MqttAuth    map[string]string
}

type Intent struct {
	Id                 string                 `json:"id"`
	CoreId             string                 `json:"core_id"`
	AdvancedKeyphrases []map[string]string    `json:"adv_keyphrases"`
	Keyphrases         [][]string             `json:"keyphrases"`
	Prefixes           []string               `json:"prefixes"`
	Suffixes           []string               `json:"suffixes"`
	Variables          map[string]interface{} `json:"variables"`
	Numbers            map[string]string      `json:"numbers"`
	Wakewords          []string               `json:"wakewords"`
}

type Collection struct {
	Id                 string                 `json:"id"`
	AdvancedKeyphrases map[string]string      `json:"adv_keyphrases"`
	Keyphrases         []string               `json:"keyphrases"`
	Variables          map[string]interface{} `json:"variables"`
}

type ParseRequest struct {
	Id   string
	Text string
}

type ParseResponse struct {
	Id       string `json:"id"`
	Text     string `json:"text"`
	IntentId string `json:"intent_id"`
	CoreId   string `json:"core_id"`
}

type IntentParse struct {
	IntentId   string
	CoreId     string
	CheckDepth int
	ParsedText string
}

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

func TextMatches(text string, checks []string) map[int]string {
	matches := make(map[int]string)
	for _, check := range checks {
		// If the check is one word, check for whole-word matches, multi-word gets regular .Contains
		if len(strings.Split(check, " ")) == 1 {
			// Replace matches & for loop so indices preserved for multiple checks, catches multiple of same word
			for _, word := range strings.Split(text, " ") {
				if word == check {
					matches[strings.Index(text, check)] = check
					text = strings.Replace(text, check, strings.Repeat("_", len(check)), 1)
				}
			}
		} else {
			for strings.Contains(text, check) {
				matches[strings.Index(text, check)] = check
				text = strings.Replace(text, check, strings.Repeat("_", len(check)), 1)
			}
		}
	}

	return matches
}

func TextReplace(text string, oldPhrase string, newPhrase string) (string, bool) {
	changeMade := false
	// If the check is one word, check for whole-word matches, multi-word gets regular .Contains
	untouchedText := text
	if len(strings.Split(oldPhrase, " ")) == 1 {
		var tempText string
		for _, word := range strings.Split(text, " ") {
			if word == oldPhrase {
				tempText = strings.Join([]string{tempText, newPhrase}, " ")
			} else {
				tempText = strings.Join([]string{tempText, word}, " ")
			}
		}
		text = tempText
	} else {
		text = strings.Replace(text, oldPhrase, newPhrase, -1)
	}

	if untouchedText != text {
		changeMade = true
	}

	return text, changeMade
}

func (core Core) Log(text string) {
	logMessage := fmt.Sprintf("[%s] %s", core.FriendlyName, text)
	if core.MqttClient != nil && core.DeviceId != "" {
		core.MqttClient.Publish(fmt.Sprintf("bloob/%s/logs", core.DeviceId), BloobQOS, false, logMessage)
	} else {
		logMessage = fmt.Sprintf("[NO MQTT LOGS] %s", logMessage)
	}

	log.Print(logMessage)
}

func (core Core) LogFatal(text string) {
	logMessage := fmt.Sprintf("!FATAL! [%s] %s", core.FriendlyName, text)

	if core.MqttClient != nil {
		core.MqttClient.Publish(fmt.Sprintf("bloob/%s/logs", core.DeviceId), BloobQOS, false, logMessage)
	}
	log.Fatal(logMessage)
}

func (core Core) PlayAudioFile(audio string, requestId string) {
	audioPlaybackMessage := map[string]string{
		"id":    requestId,
		"audio": audio,
	}
	audioPlaybackJson, err := json.Marshal(audioPlaybackMessage)
	if err != nil {
		core.LogFatal(err.Error())

	}

	core.MqttClient.Publish(fmt.Sprintf(PlayAudioFileTopic, core.DeviceId), BloobQOS, false, audioPlaybackJson)
}

func (core Core) StartRecordingAudio(requestId string) {
	audioRecordMessage := map[string]string{
		"id": requestId,
	}
	audioRecordJson, err := json.Marshal(audioRecordMessage)
	if err != nil {
		core.LogFatal(err.Error())
	}
	core.MqttClient.Publish(fmt.Sprintf(RecordSpeechTopic, core.DeviceId), BloobQOS, false, audioRecordJson)
}

func (core Core) TranscribeAudioFile(audio string, requestId string) {
	audioTranscribeMessage := map[string]string{
		"id":    requestId,
		"audio": audio,
	}
	audioTranscribeJson, err := json.Marshal(audioTranscribeMessage)
	if err != nil {
		core.LogFatal(err.Error())

	}

	core.MqttClient.Publish(fmt.Sprintf(TranscribeAudioTopic, core.DeviceId), BloobQOS, false, audioTranscribeJson)
}

func (core Core) IntentParseText(text string, requestId string) {
	intentParseMessage := map[string]string{
		"id":   requestId,
		"text": text,
	}
	intentParseJson, err := json.Marshal(intentParseMessage)
	if err != nil {
		core.LogFatal(err.Error())

	}
	core.MqttClient.Publish(fmt.Sprintf(IntentParseTopic, core.DeviceId), BloobQOS, false, intentParseJson)
}

func (core Core) SendIntentToCore(intent string, text string, coreId string, requestId string) {
	coreMessage := map[string]string{
		"id":      requestId,
		"intent":  intent,
		"core_id": coreId,
		"text":    text,
	}
	coreMessageJson, err := json.Marshal(coreMessage)
	if err != nil {
		core.LogFatal(err.Error())
	}
	core.MqttClient.Publish(fmt.Sprintf(CoreTopic, core.DeviceId, coreId), BloobQOS, false, coreMessageJson)
}

func (core Core) SpeakText(text string, requestId string) {
	ttsMessage := map[string]string{
		"id":   requestId,
		"text": text,
	}
	ttsMessageJson, err := json.Marshal(ttsMessage)
	if err != nil {
		core.LogFatal(err.Error())
	}
	core.MqttClient.Publish(fmt.Sprintf(TtsTopic, core.DeviceId), BloobQOS, false, ttsMessageJson)
}

func (core Core) SetThinking(state bool) {
	thinkMessage := map[string]bool{
		"is_thinking": state,
	}
	thinkMessageJson, err := json.Marshal(thinkMessage)
	if err != nil {
		core.LogFatal(err.Error())
	}
	core.MqttClient.Publish(fmt.Sprintf(thinkingTopic, core.DeviceId), BloobQOS, true, thinkMessageJson)
}

func (core Core) SetRecording(state bool) {
	recordingMessage := map[string]bool{
		"is_recording": state,
	}
	recordingMessageJson, err := json.Marshal(recordingMessage)
	if err != nil {
		core.LogFatal(err.Error())
	}
	core.MqttClient.Publish(fmt.Sprintf(recordingTopic, core.DeviceId), BloobQOS, true, recordingMessageJson)
}
