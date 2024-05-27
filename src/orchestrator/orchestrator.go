package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var beginListeningAudio string
var stopListeningAudio string
var errorAudio string
var instantIntentAudio string
var bloobConfig map[string]interface{}

var mqttConfig MqttConfig
var broker *mqtt.ClientOptions

var l logData = logData{name: "Orchestrator"}

func main() {

	//// Set up directories
	bLog("Setting up directories", l)
	pathToExecutable, err := os.Executable()
	if err != nil {
		bLogFatal(err.Error(), l)
	}

	// Gets the repo directory by going three levels up from the Orchestrator directory (there must be a better way than this)
	var installDir string = filepath.Dir(filepath.Dir(filepath.Dir(pathToExecutable)))
	var installCoresDir string = filepath.Join(installDir, "src", "cores")
	var installUtilsDir string = filepath.Join(installDir, "src", "utils")
	var homeDir string = os.Getenv("HOME")
	var bloobConfigDir = filepath.Join(homeDir, ".config", "bloob")
	var userCoresDir string = filepath.Join(bloobConfigDir, "cores")
	var shmDir string = filepath.Join("/dev", "shm", "bloob")

	var beginListeningAudioPath string = filepath.Join(installDir, "src", "resources", "audio", "begin_listening.wav")
	var stopListeningAudioPath string = filepath.Join(installDir, "src", "resources", "audio", "stop_listening.wav")
	var errorAudioPath string = filepath.Join(installDir, "src", "resources", "audio", "error.wav")
	var instantIntentAudioPath string = filepath.Join(installDir, "src", "resources", "audio", "instant_intent.wav")

	var bloobInfoPath string = filepath.Join(shmDir, "bloobinfo.txt")
	var bloobConfigPath string = filepath.Join(bloobConfigDir, "config.json")

	// Just add all directories that the Orchestrator needs to this list (makes parents, hence userCores rather than bloobConfig)
	for _, dir := range []string{userCoresDir, shmDir} {
		err := os.MkdirAll(dir, 0755)
		if err != nil {
			bLogFatal(err.Error(), l)
		}
	}

	//// Create bloobinfo.txt so that others can gain info about the install
	installInfo := map[string]string{
		"version":      "0.1",
		"install_path": installDir,
	}
	installInfoJsonBytes, err := json.Marshal(installInfo)
	if err != nil {
		bLogFatal(err.Error(), l)
	}
	installInfoFile, err := os.Create(bloobInfoPath)
	if err != nil {
		bLogFatal(fmt.Sprintf("Failed to create %v, maybe check permissions. %v", bloobInfoPath, err), l)
	}
	installInfoFile.Write(installInfoJsonBytes)
	installInfoFile.Close()

	//// Load Config
	bLog("Loading config", l)

	bloobConfigRaw, err := os.ReadFile(bloobConfigPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			bLog(fmt.Sprintf("You don't seem to have a config, so we're making a default one at %s", bloobConfigPath), l)
			bloobConfigFile, err := os.Create(bloobConfigPath)
			if err != nil {
				bLogFatal(err.Error(), l)
			}
			bloobConfigDefaultValues := map[string]interface{}{
				"instance_name": "Default Name",
				"uuid":          "test",
				"stt_util": map[string]interface{}{
					"model": "Systran/faster-distil-whisper-small.en",
				},
				"tts_util": map[string]interface{}{
					"model": "en_US-lessac-high",
				},
				"orchestrator": map[string]interface{}{
					"show_remote_logs": false,
				},
				"mqtt": map[string]interface{}{
					"host":     "localhost",
					"port":     "1883",
					"user":     "",
					"password": "",
				},
			}
			bloobConfigDefaultJSON, err := json.Marshal(bloobConfigDefaultValues)
			if err != nil {
				bLogFatal(err.Error(), l)
			}
			bloobConfigFile.Write(bloobConfigDefaultJSON)
			bloobConfigFile.Close()
			bloobConfigRaw = bloobConfigDefaultJSON
		} else {
			bLogFatal(fmt.Sprintf("Error while JSON encoding the default config: %s", err.Error()), l)
		}
	}
	err = json.Unmarshal(bloobConfigRaw, &bloobConfig)
	if err != nil {
		bLogFatal(fmt.Sprintf("Failed to JSON decode your config at %s, error: %s", bloobConfigPath, err.Error()), l)
	}

	// All necessary fields for the config can be added here, and the Orchestrator won't launch without them
	// TODO: Just struct this and disallow unfilled fields when unmarshalling the JSON
	for _, field := range []string{"instance_name", "uuid", "stt_util", "tts_util", "orchestrator", "mqtt"} {
		if _, ok := bloobConfig[field]; !ok {
			bLogFatal(fmt.Sprintf("Your config is missing the %s field", field), l)
		}
	}

	// Though it seems quite roundabout, this seemed like the simplest way to take the MQTT interface and put it into a proper struct
	// with proper types again. Keep tempMqttConfig in its own scope to prevent it appearing elsewhere.
	{
		tempMqttConfig, err := json.Marshal(bloobConfig["mqtt"].(map[string]interface{}))
		if err != nil {
			bLogFatal(fmt.Sprintf("Issue with your MQTT config prevented it from being loaded: %s", err.Error()), l)
		}
		json.Unmarshal(tempMqttConfig, &mqttConfig)
	}

	// Load sounds into memory

	{
		beginListeningAudioBytes, err := os.ReadFile(beginListeningAudioPath)
		if err != nil {
			bLogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err), l)
		}
		beginListeningAudio = base64.StdEncoding.EncodeToString(beginListeningAudioBytes)
	}

	{
		stopListeningAudioBytes, err := os.ReadFile(stopListeningAudioPath)
		if err != nil {
			bLogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err), l)
		}
		stopListeningAudio = base64.StdEncoding.EncodeToString(stopListeningAudioBytes)
	}

	{
		errorAudioBytes, err := os.ReadFile(errorAudioPath)
		if err != nil {
			bLogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err), l)
		}
		errorAudio = base64.StdEncoding.EncodeToString(errorAudioBytes)
	}

	{
		instantIntentAudioBytes, err := os.ReadFile(instantIntentAudioPath)
		if err != nil {
			bLogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err), l)
		}
		instantIntentAudio = base64.StdEncoding.EncodeToString(instantIntentAudioBytes)
	}

	//// Set up MQTT
	bLog("Setting up MQTT", l)
	broker = mqtt.NewClientOptions()
	broker.AddBroker(fmt.Sprintf("tcp://%s:%v", mqttConfig.Host, mqttConfig.Port))

	bLog(fmt.Sprintf("Broker at: tcp://%s:%v\n", mqttConfig.Host, mqttConfig.Port), l)

	broker.SetClientID(fmt.Sprintf("%v - Orchestrator", bloobConfig["instance_name"]))

	bLog(fmt.Sprintf("MQTT client name: %v - Orchestrator\n", bloobConfig["instance_name"]), l)

	broker.OnConnect = onConnect
	if mqttConfig.Password != "" && mqttConfig.Username != "" {
		broker.SetPassword(mqttConfig.Password)
		broker.SetUsername(mqttConfig.Username)
		bLog("Using MQTT authenticated", l)
	} else {
		bLog("Using MQTT unauthenticated", l)
	}
	client := mqtt.NewClient(broker)
	//for loop to go here with a list of the topics that need subbing to.
	// Maybe better than the subscribemultiple
	subscribeMqttTopics := map[string]byte{
		fmt.Sprintf("bloob/%s/cores/+/finished", bloobConfig["uuid"]): bloobQOS,
	}

	if token := client.Connect(); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.SubscribeMultiple(subscribeMqttTopics, pipelineMessageHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}

	if token := client.Subscribe(fmt.Sprintf("bloob/%s/cores/+/collections", bloobConfig["uuid"]), bloobQOS, collectionHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}

	if bloobConfig["orchestrator"].(map[string]interface{})["show_remote_logs"].(bool) {
		if token := client.Subscribe(fmt.Sprintf("bloob/%s/logs", bloobConfig["uuid"].(string)), bloobQOS, remoteLogDisplay); token.Wait() && token.Error() != nil {
			bLogFatal(token.Error().Error(), l)
		}
	}

	// bLog now has access to MQTT logging
	l.client = client
	l.uuid = bloobConfig["uuid"].(string)

	//// Load Cores
	bLog(fmt.Sprintf("User Cores dir: %s", userCoresDir), l)
	bLog(fmt.Sprintf("Install Cores dir: %s", installCoresDir), l)

	var corePaths []string = scanForCores([]string{userCoresDir, installCoresDir, installUtilsDir})
	var runningCores []Core
	coreReceiver := make(chan Core)
	for _, corePath := range corePaths {
		go createCore(corePath, coreReceiver)
	}

	for i := 0; i < len(corePaths); i++ {
		receivedCore := <-coreReceiver
		err := receivedCore.Exec.Start()
		if err != nil {
			bLogFatal(err.Error(), l)
		}
		runningCores = append(runningCores, receivedCore)
		bLog(fmt.Sprintf("Started %s", receivedCore.Id), l)
	}

	// Add external cores too (cores that weren't started by the Orchestrator, but _are_ running somewhere else and connected over MQTT)
	if _, ok := bloobConfig["orchestrator"].(map[string]interface{})["external_cores"]; ok {
		for _, externalCore := range bloobConfig["orchestrator"].(map[string]interface{})["external_cores"].([]interface{}) {
			bLog(fmt.Sprintf("Registered external Core %s", externalCore.(map[string]interface{})["id"].(string)), l)
			runningCores = append(runningCores, Core{Id: externalCore.(map[string]interface{})["id"].(string), Exec: nil})
		}
	}

	// Publish Central Configs if they exist, or an empty object if not. Set a will that empties these configs on accidental disconnect.
	// Which must be the case to ensure that old MQTT configs aren't used from previous runs.
	var configToPublish []byte
	var listOfCores []string
	var listOfCollections []string
	var topicToPublish string = "bloob/%s/cores/%s/central_config"
	for _, core := range runningCores {

		value, ok := bloobConfig[core.Id]
		if ok {
			configToPublish, err = json.Marshal(value.(map[string]interface{}))
			if err != nil {
				bLogFatal(fmt.Sprintf("Failed to parse central config for core %v", core.Id), l)
			}

		} else {
			configToPublish, _ = json.Marshal(make(map[string]interface{}))
		}

		if token := client.Publish(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), bloobQOS, true, configToPublish); token.Wait() && token.Error() != nil {
			bLogFatal(fmt.Sprintf("Failed publishing Central Config: %s", token.Error()), l)
		}
		broker.SetWill(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), "", bloobQOS, true)

		listOfCores = append(listOfCores, core.Id)

	}

	// Publish a list of all running Cores
	var listOfCoresJson []byte
	listOfCoresJson, _ = json.Marshal(map[string]interface{}{
		"loaded_cores": listOfCores,
	})
	if token := client.Publish(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), bloobQOS, true, listOfCoresJson); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	broker.SetWill(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), "", bloobQOS, true)

	// For now, we'll just launch everything, wait a few seconds, then kill it
	time.Sleep(5 * time.Second)

	exitCleanup(runningCores, listOfCollections, client)
}

func exitCleanup(runningCores []Core, listOfCollections []string, client mqtt.Client) {
	// Go through all Cores, publish blank central configs, and exit them
	for _, runningCore := range runningCores {
		// Clear central configs
		bLog(fmt.Sprintf("Publishing a blank central config for %v", runningCore.Id), l)
		if token := client.Publish(fmt.Sprintf("bloob/%s/cores/%s/central_config", bloobConfig["uuid"], runningCore.Id), bloobQOS, true, ""); token.Wait() && token.Error() != nil {
			bLogFatal(token.Error().Error(), l)
		}

		// Kill local cores (not external ones, as they have a nil Exec field)
		if runningCore.Exec != nil {
			bLog(fmt.Sprintf("Killing Core: %s (%s)", runningCore.Id, runningCore.Exec.Args[0]), l)
			err := runningCore.Exec.Process.Signal(syscall.SIGINT)
			if err != nil {
				bLogFatal(err.Error(), l)
			}
		}

	}

	// Publish empty message to all collection IDs
	for _, collectionId := range listOfCollections {
		topicToPublish := "bloob/%s/collections/%s"
		if token := client.Publish(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], collectionId), bloobQOS, true, ""); token.Wait() && token.Error() != nil {
			bLogFatal(token.Error().Error(), l)
		}
	}

	// Clear list of Cores
	if token := client.Publish(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), bloobQOS, true, ""); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}

	// Clear list of Collections
	if token := client.Publish(fmt.Sprintf("bloob/%s/collections/list", bloobConfig["uuid"]), bloobQOS, true, ""); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
}
