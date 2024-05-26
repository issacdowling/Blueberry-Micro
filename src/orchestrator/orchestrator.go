package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var beginListeningAudio string
var stopListeningAudio string
var errorAudio string
var instantIntentAudio string
var bloobConfig map[string]interface{}

var mqttConfig MqttConfig

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
				"stt": map[string]interface{}{
					"model": "Systran/faster-distil-whisper-small.en",
				},
				"tts": map[string]interface{}{
					"model": "en_US-lessac-high",
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
			bLogFatal(fmt.Sprintf("Error while JSON decoding your config: %s", err.Error()), l)
		}
	}
	json.Unmarshal(bloobConfigRaw, &bloobConfig)

	// All necessary fields for the config can be added here, and the Orchestrator won't launch without them
	// TODO: Just struct this and disallow unfilled fields when unmarshalling the JSON
	for _, field := range []string{"instance_name", "uuid", "stt", "tts", "mqtt"} {
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
	broker := mqtt.NewClientOptions()
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
		fmt.Sprintf("bloob/%s/wakeword/detected", bloobConfig["uuid"]):       bloobQOS,
		fmt.Sprintf("bloob/%s/audio_playback/finished", bloobConfig["uuid"]): bloobQOS,
		fmt.Sprintf("bloob/%s/audio_recorder/finished", bloobConfig["uuid"]): bloobQOS,
		fmt.Sprintf("bloob/%s/stt/finished", bloobConfig["uuid"]):            bloobQOS,
		fmt.Sprintf("bloob/%s/tts/finished", bloobConfig["uuid"]):            bloobQOS,
		fmt.Sprintf("bloob/%s/intent_parser/finished", bloobConfig["uuid"]):  bloobQOS,
		fmt.Sprintf("bloob/%s/cores/+/finished", bloobConfig["uuid"]):        bloobQOS,
	}

	if token := client.Connect(); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	if token := client.SubscribeMultiple(subscribeMqttTopics, pipelineMessageHandler); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}

	if token := client.Subscribe(fmt.Sprintf("bloob/%s/logs", bloobConfig["uuid"].(string)), bloobQOS, remoteLogDisplay); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
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
		receivedCore.Exec.Start()
		runningCores = append(runningCores, receivedCore)
		fmt.Println("Started", receivedCore.Id)
	}

	if err != nil {
		bLogFatal(fmt.Sprintf("Failed to launch a core, check your environment (if it's a Python Core, do you have the right venv?): %s", err.Error()), l)
	}

	// Publish Central Configs if they exist, or an empty object if not. Set a will that empties these configs on accidental disconnect.
	// Which must be the case to ensure that old MQTT configs aren't used from previous runs.
	var configToPublish []byte
	var listOfCores []string
	var listOfCollections []string
	var topicToPublish string
	for _, core := range runningCores {

		// If no_config, we publish a blank config _on behalf_ of the Core. This is different from the central config
		if slices.Contains(core.Roles, "no_config") {
			topicToPublish = "bloob/%s/cores/%s/config"
			blankConfig := map[string]interface{}{
				"metadata": map[string]interface{}{
					"core_id": core.Id,
				},
			}
			blankConfigJson, err := json.Marshal(blankConfig)
			if err != nil {
				bLogFatal(err.Error(), l)
			}
			if token := client.Publish(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), bloobQOS, true, blankConfigJson); token.Wait() && token.Error() != nil {
				bLogFatal(fmt.Sprintf("Failed publishing Config %s", token.Error()), l)
			}
			broker.SetWill(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), "", bloobQOS, true)
		}

		value, ok := bloobConfig[core.Id]
		if ok {
			configToPublish, err = json.Marshal(value.(map[string]interface{}))
			if err != nil {
				bLogFatal(fmt.Sprintf("Failed to parse central config for core %v", core.Id), l)
			}

		} else {
			configToPublish, _ = json.Marshal(make(map[string]interface{}))
		}

		// If it's a util, we omit /cores/ before the Core ID in the topic
		if slices.Contains(core.Roles, "util") {
			topicToPublish = "bloob/%s/%s/central_config"
		} else {
			topicToPublish = "bloob/%s/cores/%s/central_config"
		}

		if token := client.Publish(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), bloobQOS, true, configToPublish); token.Wait() && token.Error() != nil {
			bLogFatal(fmt.Sprintf("Failed publishing Central Config: %s", token.Error()), l)
		}
		broker.SetWill(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), "", bloobQOS, true)

		listOfCores = append(listOfCores, core.Id)

		// If it's a Collection Handler, we get Collections from it and publish them, along with the Will that empties them on exit.
		if slices.Contains(core.Roles, "collection_handler") {
			coreCollections, err := core.getCollections()
			if err != nil {
				bLogFatal(err.Error(), l)
			}
			bLog(fmt.Sprintf("%v has provided %d Collections", core.Id, len(coreCollections)), l)
			for _, collection := range coreCollections {
				topicToPublish = "bloob/%s/collections/%s"
				collectionToPublish, err := json.Marshal(collection)
				if err != nil {
					bLogFatal(err.Error(), l)
				}
				if token := client.Publish(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], collection["id"].(string)), bloobQOS, true, collectionToPublish); token.Wait() && token.Error() != nil {
					bLogFatal(fmt.Sprintf("Failed publishing Collection %s", token.Error()), l)
				}
				broker.SetWill(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], collection["id"].(string)), "", bloobQOS, true)
				listOfCollections = append(listOfCollections, collection["id"].(string))
			}
		}

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

	// Publish a list of all Collections
	var listOfCollectionsJson []byte
	listOfCollectionsJson, _ = json.Marshal(map[string]interface{}{
		"loaded_collections": listOfCollections,
	})
	if token := client.Publish(fmt.Sprintf("bloob/%s/collections/list", bloobConfig["uuid"]), bloobQOS, true, listOfCollectionsJson); token.Wait() && token.Error() != nil {
		bLogFatal(token.Error().Error(), l)
	}
	broker.SetWill(fmt.Sprintf("bloob/%s/collections/list", bloobConfig["uuid"]), "", bloobQOS, true)

	// For now, we'll just launch everything, wait a few seconds, then kill it
	time.Sleep(15 * time.Second)

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

		// Kill cores
		bLog(fmt.Sprintf("Killing Core: %s (%s)", runningCore.Id, runningCore.Exec.Args[0]), l)
		err := runningCore.Exec.Process.Kill()
		if err != nil {
			fmt.Println(err)
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
