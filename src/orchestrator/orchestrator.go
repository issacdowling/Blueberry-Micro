package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var beginListeningAudio string
var stopListeningAudio string
var errorAudio string
var instantIntentAudio string
var bloobConfig map[string]interface{}

var mqttConfig MqttConfig

func main() {

	//// Set up directories
	log.Println("Setting up directories")
	pathToExecutable, err := os.Executable()
	if err != nil {
		log.Panic(err)
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
			log.Panic(err)
		}
	}

	//// Create bloobinfo.txt so that others can gain info about the install
	installInfo := map[string]string{
		"version":      "0.1",
		"install_path": installDir,
	}
	installInfoJsonBytes, err := json.Marshal(installInfo)
	if err != nil {
		log.Panic(err)
	}
	installInfoFile, err := os.Create(bloobInfoPath)
	if err != nil {
		log.Panicf("Failed to create %v, maybe check permissions. %v", bloobInfoPath, err)
	}
	installInfoFile.Write(installInfoJsonBytes)
	installInfoFile.Close()

	//// Load Config
	log.Println("Loading config")

	bloobConfigRaw, err := os.ReadFile(bloobConfigPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			log.Println("You don't seem to have a config, so we're making a default one at ", bloobConfigPath)
			bloobConfigFile, err := os.Create(bloobConfigPath)
			if err != nil {
				log.Panic(err)
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
				log.Panic(err)
			}
			bloobConfigFile.Write(bloobConfigDefaultJSON)
			bloobConfigFile.Close()
			bloobConfigRaw = bloobConfigDefaultJSON
		} else {
			log.Fatal("Error while JSON decoding your config ", err)
		}
	}
	json.Unmarshal(bloobConfigRaw, &bloobConfig)

	// All necessary fields for the config can be added here, and the Orchestrator won't launch without them
	// TODO: Just struct this and disallow unfilled fields when unmarshalling the JSON
	for _, field := range []string{"instance_name", "uuid", "stt", "tts", "mqtt"} {
		if _, ok := bloobConfig[field]; !ok {
			log.Fatal("Your config is missing the ", field, " field")
		}
	}

	// Though it seems quite roundabout, this seemed like the simplest way to take the MQTT interface and put it into a proper struct
	// with proper types again. Keep tempMqttConfig in its own scope to prevent it appearing elsewhere.
	{
		tempMqttConfig, err := json.Marshal(bloobConfig["mqtt"].(map[string]interface{}))
		if err != nil {
			log.Panic("Issue with your MQTT config prevented it from being loaded: ", err)
		}
		json.Unmarshal(tempMqttConfig, &mqttConfig)
	}

	// Load sounds into memory

	{
		beginListeningAudioBytes, err := os.ReadFile(beginListeningAudioPath)
		if err != nil {
			log.Panicf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err)
		}
		beginListeningAudio = base64.StdEncoding.EncodeToString(beginListeningAudioBytes)
	}

	{
		stopListeningAudioBytes, err := os.ReadFile(stopListeningAudioPath)
		if err != nil {
			log.Panicf("Failed to read listening audio file (%v): %v", stopListeningAudioPath, err)
		}
		stopListeningAudio = base64.StdEncoding.EncodeToString(stopListeningAudioBytes)
	}

	{
		errorAudioBytes, err := os.ReadFile(errorAudioPath)
		if err != nil {
			log.Panicf("Failed to read listening audio file (%v): %v", errorAudioPath, err)
		}
		errorAudio = base64.StdEncoding.EncodeToString(errorAudioBytes)
	}

	{
		instantIntentAudioBytes, err := os.ReadFile(instantIntentAudioPath)
		if err != nil {
			log.Panicf("Failed to read listening audio file (%v): %v", instantIntentAudioPath, err)
		}
		instantIntentAudio = base64.StdEncoding.EncodeToString(instantIntentAudioBytes)
	}

	//// Set up MQTT
	log.Println("Setting up MQTT")
	broker := mqtt.NewClientOptions()
	broker.AddBroker(fmt.Sprintf("tcp://%s:%v", mqttConfig.Host, mqttConfig.Port))

	fmt.Printf("tcp://%s:%v\n", mqttConfig.Host, mqttConfig.Port)

	broker.SetClientID(fmt.Sprintf("%v - Orchestrator", bloobConfig["instance_name"]))

	fmt.Printf("%v - Orchestrator\n", bloobConfig["instance_name"])

	broker.OnConnect = onConnect
	if mqttConfig.Password != "" && mqttConfig.Username != "" {
		broker.SetPassword(mqttConfig.Password)
		broker.SetUsername(mqttConfig.Username)
		log.Println("Using MQTT authenticated")
	} else {
		log.Println("Using MQTT unauthenticated")
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
	}

	if token := client.Connect(); token.Wait() && token.Error() != nil {
		log.Fatal(token.Error())
	}
	if token := client.SubscribeMultiple(subscribeMqttTopics, pipelineMessageHandler); token.Wait() && token.Error() != nil {
		log.Fatal(token.Error())
	}

	//// Load Cores
	log.Println("User Cores dir:", userCoresDir)
	log.Println("Install Cores dir:", installCoresDir)

	var corePaths []string = scanForCores([]string{userCoresDir, installCoresDir, installUtilsDir})
	runningCores, err := startCores(corePaths)
	if err != nil {
		log.Panic("Failed to launch a core, check your environment (if it's a Python Core, do you have the right venv?)", err)
	}

	// Publish Central Configs if they exist, or an empty object if not. Set a will that empties these configs on accidental disconnect.
	// Which must be the case to ensure that old MQTT configs aren't used from previous runs.
	var configToPublish []byte
	var listOfCores []string
	for _, core := range runningCores {
		value, ok := bloobConfig[core.Id]
		if ok {
			configToPublish, err = json.Marshal(value.(map[string]interface{}))
			if err != nil {
				log.Panicf("Failed to parse central config for core %v", core.Id)
			}

		} else {
			configToPublish, _ = json.Marshal(make(map[string]interface{}))
		}

		client.Publish(fmt.Sprintf("bloob/%s/cores/%s/central_config", bloobConfig["uuid"], core.Id), bloobQOS, true, configToPublish)
		broker.SetWill(fmt.Sprintf("bloob/%s/cores/%s/central_config", bloobConfig["uuid"], core.Id), "", bloobQOS, true)

		listOfCores = append(listOfCores, core.Id)
	}

	// Publish a list of all running Cores
	var listOfCoresJson []byte
	listOfCoresJson, _ = json.Marshal(map[string]interface{}{
		"loaded_cores": listOfCores,
	})
	client.Publish(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), bloobQOS, true, listOfCoresJson)
	broker.SetWill(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), "", bloobQOS, true)
	// For now, we'll just launch everything, wait a few seconds, then kill it
	time.Sleep(15 * time.Second)

	exitCleanup(runningCores, client)
}

func exitCleanup(runningCores []Core, client mqtt.Client) {
	// Go through all Cores, publish blank central configs, and exit them
	for _, runningCore := range runningCores {
		// Clear central configs
		log.Printf("Publishing a blank central config for %v", runningCore.Id)
		client.Publish(fmt.Sprintf("bloob/%s/cores/%s/central_config", bloobConfig["uuid"], runningCore.Id), bloobQOS, true, "")

		// Kill cores
		log.Printf("Killing Core: %s (%s)", runningCore.Id, runningCore.Exec.Args[0])
		err := runningCore.Exec.Process.Kill()
		if err != nil {
			fmt.Println(err)
		}

	}

	// Clear list of cores
	client.Publish(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), bloobQOS, true, "")
}
