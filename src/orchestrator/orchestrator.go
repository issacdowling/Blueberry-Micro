package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

func main() {
	pathToExecutable, _ := os.Executable()

	// Gets the repo directory by going three levels up from the Orchestrator directory (there must be a better way than this)
	var installDir string = filepath.Dir(filepath.Dir(filepath.Dir(pathToExecutable)))
	var installCoresDir string = filepath.Join(installDir, "src", "cores")
	var installUtilsDir string = filepath.Join(installDir, "src", "utils")
	var homeDir string = os.Getenv("HOME")
	var bloobConfigDir = filepath.Join(homeDir, ".config", "bloob")
	var userCoresDir string = filepath.Join(bloobConfigDir, "cores")
	var shmDir string = filepath.Join("/dev", "shm", "bloob")

	err := os.MkdirAll(shmDir, 0755)
	if err != nil {
		log.Panic(err)
	}

	// Create bloobinfo.txt so that others can gain info about the install
	installInfo := map[string]string{
		"version":      "0.1",
		"install_path": installDir,
	}
	installInfoJsonBytes, err := json.Marshal(installInfo)
	if err != nil {
		log.Panic(err)
	}
	installInfoFile, _ := os.Create(filepath.Join(shmDir, "bloobinfo.txt"))
	installInfoFile.Write(installInfoJsonBytes)

	fmt.Println(string(installInfoJsonBytes))

	fmt.Println("User Cores dir:", userCoresDir)
	fmt.Println("Install Cores dir:", installCoresDir)

	var corePaths []string = scanForCores([]string{userCoresDir, installCoresDir, installUtilsDir})

	fmt.Println(corePaths)

	runningCores, _ := startCores(corePaths)

	// For now, we'll just launch everything, wait a few seconds, then kill it
	time.Sleep(5 * time.Second)

	for _, runningCore := range runningCores {
		err := runningCore.Process.Kill()
		if err != nil {
			fmt.Println(err)
		}

	}

}
