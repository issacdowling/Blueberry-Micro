package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

func main() {

	//// Set up directories
	pathToExecutable, _ := os.Executable()

	// Gets the repo directory by going three levels up from the Orchestrator directory (there must be a better way than this)
	var installDir string = filepath.Dir(filepath.Dir(filepath.Dir(pathToExecutable)))
	var installCoresDir string = filepath.Join(installDir, "src", "cores")
	var installUtilsDir string = filepath.Join(installDir, "src", "utils")
	var homeDir string = os.Getenv("HOME")
	var bloobConfigDir = filepath.Join(homeDir, ".config", "bloob")
	var userCoresDir string = filepath.Join(bloobConfigDir, "cores")
	var shmDir string = filepath.Join("/dev", "shm", "bloob")

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
	installInfoFile, _ := os.Create(bloobInfoPath)
	installInfoFile.Write(installInfoJsonBytes)
	installInfoFile.Close()

	//// Load Config
	var bloobConfig map[string]string

	bloobConfigRaw, err := os.ReadFile(bloobConfigPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			log.Println("You don't seem to have a config, so we're making a default one at ", bloobConfigPath)
			bloobConfigFile, err := os.Create(bloobConfigPath)
			if err != nil {
				log.Panic(err)
			}
			var bloobConfigDefaultValues map[string]interface{} = map[string]interface{}{
				"instance_name": "Default Name",
				"uuid":          "test",
				"stt_model":     "Systran/faster-distil-whisper-small.en",
				"tts_model":     "en_US-lessac-high",
				"mqtt": map[string]string{
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
	for _, field := range []string{"instance_name", "uuid", "stt_model", "tts_model", "mqtt"} {
		if _, ok := bloobConfig[field]; !ok {
			log.Fatal("Your config is missing the ", field, " field")
		}
	}

	//// Load Cores
	log.Println("User Cores dir:", userCoresDir)
	log.Println("Install Cores dir:", installCoresDir)

	var corePaths []string = scanForCores([]string{userCoresDir, installCoresDir, installUtilsDir})
	runningCores, err := startCores(corePaths)
	if err != nil {
		log.Panic(err)
	}

	// For now, we'll just launch everything, wait a few seconds, then kill it
	time.Sleep(5 * time.Second)

	exitCleanup(runningCores)
}

func exitCleanup(runningCores []Core) {
	// Go through all Cores and exit them
	for _, runningCore := range runningCores {
		log.Printf("Killing Core: %s (%s)", runningCore.id, runningCore.exec.Args[0])
		err := runningCore.exec.Process.Kill()
		if err != nil {
			fmt.Println(err)
		}

	}
}
