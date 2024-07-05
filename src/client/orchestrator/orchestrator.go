package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	bloob "blueberry/gobloob"

	mqtt "github.com/eclipse/paho.mqtt.golang"
)

var beginListeningAudio string
var stopListeningAudio string
var errorAudio string
var instantIntentAudio string
var bloobConfig map[string]interface{}

var instantIntents map[string]string = make(map[string]string)

var mqttConfig bloob.MqttConfig
var broker *mqtt.ClientOptions

var friendlyName string = "Orchestrator"

var c bloob.Core = bloob.Core{FriendlyName: friendlyName}

func main() {

	//// Set up directories
	c.Log("Setting up directories")
	pathToExecutable, err := os.Executable()
	if err != nil {
		c.LogFatal(err.Error())
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
			c.LogFatal(err.Error())
		}
	}

	//// Create bloobinfo.txt so that others can gain info about the install
	installInfo := map[string]string{
		"version":      "0.1",
		"install_path": installDir,
	}
	installInfoJsonBytes, err := json.Marshal(installInfo)
	if err != nil {
		c.LogFatal(err.Error())
	}
	installInfoFile, err := os.Create(bloobInfoPath)
	if err != nil {
		c.LogFatal(fmt.Sprintf("Failed to create %v, maybe check permissions. %v", bloobInfoPath, err))
	}
	installInfoFile.Write(installInfoJsonBytes)
	installInfoFile.Close()

	//// Load Config
	c.Log("Loading config")

	bloobConfigRaw, err := os.ReadFile(bloobConfigPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			c.Log(fmt.Sprintf("You don't seem to have a config, so we're making a default one at %s", bloobConfigPath))
			bloobConfigFile, err := os.Create(bloobConfigPath)
			if err != nil {
				c.LogFatal(err.Error())
			}
			bloobConfigDefaultValues := map[string]interface{}{
				"instance_name": "Default Name",
				"uuid":          "test",
				"stt_util": map[string]interface{}{
					"mode":  "local",
					"model": "base.en",
				},
				"tts_util": map[string]interface{}{
					"model": "en_GB-southern_english_female-low",
				},
				"orchestrator": map[string]interface{}{
					"show_remote_logs": false,
				},
				"mqtt": map[string]interface{}{
					"host":     "localhost",
					"port":     1883,
					"user":     "",
					"password": "",
				},
			}
			bloobConfigDefaultJSON, err := json.Marshal(bloobConfigDefaultValues)
			if err != nil {
				c.LogFatal(err.Error())
			}
			bloobConfigFile.Write(bloobConfigDefaultJSON)
			bloobConfigFile.Close()
			bloobConfigRaw = bloobConfigDefaultJSON
		} else {
			c.LogFatal(fmt.Sprintf("Error while JSON encoding the default config: %s", err.Error()))
		}
	}
	err = json.Unmarshal(bloobConfigRaw, &bloobConfig)
	if err != nil {
		c.LogFatal(fmt.Sprintf("Failed to JSON decode your config at %s, error: %s", bloobConfigPath, err.Error()))
	}

	// All necessary fields for the config can be added here, and the Orchestrator won't launch without them
	// TODO: Just struct this and disallow unfilled fields when unmarshalling the JSON
	for _, field := range []string{"instance_name", "uuid", "stt_util", "tts_util", "orchestrator", "mqtt"} {
		if _, ok := bloobConfig[field]; !ok {
			c.LogFatal(fmt.Sprintf("Your config is missing the %s field", field))
		}
	}

	// Though it seems quite roundabout, this seemed like the simplest way to take the MQTT interface and put it into a proper struct
	// with proper types again. Keep tempMqttConfig in its own scope to prevent it appearing elsewhere.
	{
		tempMqttConfig, err := json.Marshal(bloobConfig["mqtt"].(map[string]interface{}))
		if err != nil {
			c.LogFatal(fmt.Sprintf("Issue with your MQTT config prevented it from being loaded: %s", err.Error()))
		}
		json.Unmarshal(tempMqttConfig, &mqttConfig)
	}

	// Load sounds into memory

	{
		beginListeningAudioBytes, err := os.ReadFile(beginListeningAudioPath)
		if err != nil {
			c.LogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err))
		}
		beginListeningAudio = base64.StdEncoding.EncodeToString(beginListeningAudioBytes)
	}

	{
		stopListeningAudioBytes, err := os.ReadFile(stopListeningAudioPath)
		if err != nil {
			c.LogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err))
		}
		stopListeningAudio = base64.StdEncoding.EncodeToString(stopListeningAudioBytes)
	}

	{
		errorAudioBytes, err := os.ReadFile(errorAudioPath)
		if err != nil {
			c.LogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err))
		}
		errorAudio = base64.StdEncoding.EncodeToString(errorAudioBytes)
	}

	{
		instantIntentAudioBytes, err := os.ReadFile(instantIntentAudioPath)
		if err != nil {
			c.LogFatal(fmt.Sprintf("Failed to read listening audio file (%v): %v", beginListeningAudioPath, err))
		}
		instantIntentAudio = base64.StdEncoding.EncodeToString(instantIntentAudioBytes)
	}

	//// Set up MQTT
	c.Log("Setting up MQTT")
	broker = mqtt.NewClientOptions()
	broker.AddBroker(fmt.Sprintf("tcp://%s:%v", mqttConfig.Host, mqttConfig.Port))

	c.Log(fmt.Sprintf("Broker at: tcp://%s:%v\n", mqttConfig.Host, mqttConfig.Port))

	broker.SetClientID(fmt.Sprintf("%v - %s", bloobConfig["instance_name"], friendlyName))

	c.Log(fmt.Sprintf("MQTT client name: %v - %s\n", bloobConfig["instance_name"], friendlyName))

	broker.OnConnect = onConnect
	if mqttConfig.Password != "" && mqttConfig.Username != "" {
		broker.SetPassword(mqttConfig.Password)
		broker.SetUsername(mqttConfig.Username)
		c.Log("Using MQTT authenticated")
	} else {
		c.Log("Using MQTT unauthenticated")
	}
	client := mqtt.NewClient(broker)
	//for loop to go here with a list of the topics that need subbing to.
	// Maybe better than the subscribemultiple
	subscribeMqttTopics := map[string]byte{
		fmt.Sprintf("bloob/%s/cores/+/finished", bloobConfig["uuid"]): bloob.BloobQOS,
	}

	if token := client.Connect(); token.Wait() && token.Error() != nil {
		c.LogFatal(token.Error().Error())
	}
	if token := client.SubscribeMultiple(subscribeMqttTopics, pipelineMessageHandler); token.Wait() && token.Error() != nil {
		c.LogFatal(token.Error().Error())
	}

	if token := client.Subscribe(fmt.Sprintf(bloob.InstantIntentTopic, bloobConfig["uuid"].(string)), bloob.BloobQOS, instantIntentRegister); token.Wait() && token.Error() != nil {
		c.LogFatal(token.Error().Error())
	}

	if bloobConfig["orchestrator"].(map[string]interface{})["show_remote_logs"].(bool) {
		if token := client.Subscribe(fmt.Sprintf("bloob/%s/logs", bloobConfig["uuid"].(string)), bloob.BloobQOS, remoteLogDisplay); token.Wait() && token.Error() != nil {
			c.LogFatal(token.Error().Error())
		}
	}

	// c.Log now has access to MQTT logging
	c.MqttClient = client
	c.DeviceId = bloobConfig["uuid"].(string)

	//// Load Cores
	c.Log(fmt.Sprintf("User Cores dir: %s", userCoresDir))
	c.Log(fmt.Sprintf("Install Cores dir: %s", installCoresDir))

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
			c.LogFatal(err.Error())
		}
		runningCores = append(runningCores, receivedCore)
		c.Log(fmt.Sprintf("Started %s", receivedCore.Id))
	}

	// Add external cores too (cores that weren't started by the Orchestrator, but _are_ running somewhere else and connected over MQTT)
	if _, ok := bloobConfig["orchestrator"].(map[string]interface{})["external_cores"]; ok {
		for _, externalCore := range bloobConfig["orchestrator"].(map[string]interface{})["external_cores"].([]interface{}) {
			c.Log(fmt.Sprintf("Registered external Core %s", externalCore.(map[string]interface{})["id"].(string)))
			runningCores = append(runningCores, Core{Id: externalCore.(map[string]interface{})["id"].(string), Exec: nil})
		}
	}

	// Publish Central Configs if they exist, or an empty object if not. Set a will that empties these configs on accidental disconnect.
	// Which must be the case to ensure that old MQTT configs aren't used from previous runs.
	var configToPublish []byte
	var listOfCores []string
	var topicToPublish string = "bloob/%s/cores/%s/central_config"
	for _, core := range runningCores {

		value, ok := bloobConfig[core.Id]
		if ok {
			configToPublish, err = json.Marshal(value.(map[string]interface{}))
			if err != nil {
				c.LogFatal(fmt.Sprintf("Failed to parse central config for core %v", core.Id))
			}

		} else {
			configToPublish, _ = json.Marshal(make(map[string]interface{}))
		}

		if token := client.Publish(fmt.Sprintf(topicToPublish, bloobConfig["uuid"], core.Id), bloob.BloobQOS, true, configToPublish); token.Wait() && token.Error() != nil {
			c.LogFatal(fmt.Sprintf("Failed publishing Central Config: %s", token.Error()))
		}

		listOfCores = append(listOfCores, core.Id)

	}

	// Publish a list of all running Cores
	var listOfCoresJson []byte
	listOfCoresJson, _ = json.Marshal(map[string]interface{}{
		"loaded_cores": listOfCores,
	})
	if token := client.Publish(fmt.Sprintf("bloob/%s/cores/list", bloobConfig["uuid"]), bloob.BloobQOS, true, listOfCoresJson); token.Wait() && token.Error() != nil {
		c.LogFatal(token.Error().Error())
	}

	// Block until CTRL+C'd
	doneChannel := make(chan os.Signal, 1)
	// the syscall.SIGINT, syscall.SIGTERM is necessary or it exits with "child exited"
	signal.Notify(doneChannel, syscall.SIGINT, syscall.SIGTERM)
	c.Log(fmt.Sprintf("Exit Signal Received: %v, exiting gracefully", <-doneChannel))

	exitCleanup(runningCores, client)
}

func exitCleanup(runningCores []Core, client mqtt.Client) {
	// Go through all Cores, publish blank central configs, and exit them
	for _, runningCore := range runningCores {

		// Kill local cores (not external ones, as they have a nil Exec field)
		if runningCore.Exec != nil {
			c.Log(fmt.Sprintf("Killing Core: %s (%s)", runningCore.Id, runningCore.Exec.Args[0]))
			err := runningCore.Exec.Process.Signal(syscall.SIGINT)
			if err != nil {
				c.LogFatal(err.Error())
			}
		}

	}
	// Subscribe to _all_ bloob/device-id topics to find retained ones, then publish blank messages to clean them up
	// Less ideal, but also MUCH less effort to do this in a garbage-collection style way, rather than "freeing" each topic manually
	c.Log(fmt.Sprintf("Finding all remaining non-empty MQTT topics for this instance (uuid \"%s\") and clearing them", bloobConfig["uuid"]))
	if token := client.Subscribe(fmt.Sprintf("bloob/%s/#", bloobConfig["uuid"]), bloob.BloobQOS, clearTopics); token.Wait() && token.Error() != nil {
		c.LogFatal(token.Error().Error())
	}
	time.Sleep(300 * time.Millisecond)

	client.Disconnect(0)
}
