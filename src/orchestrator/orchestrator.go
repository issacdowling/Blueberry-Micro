package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"
)

func main() {

	//// Get a list of Cores, both in the src dir and the user's config dir.
	pathToExecutable, _ := os.Executable()

	// Gets the repo directory by going three levels up from the Orchestrator directory (there must be a better way than this)
	var installDir string = filepath.Dir(filepath.Dir(filepath.Dir(pathToExecutable)))
	var installCoresDir string = filepath.Join(installDir, "src", "cores")

	var homeDir string = os.Getenv("HOME")
	var userCoresDir string = filepath.Join(homeDir, ".config", "bloob", "cores")

	fmt.Println("User Cores dir:", userCoresDir)
	fmt.Println("Install Cores dir:", installCoresDir)

	var corePaths []string = scanForCores([]string{userCoresDir, installCoresDir})

	_, err := startCores(corePaths)
	if err != nil {
		log.Panic(err)
	}

	// For now, we'll just launch everything, wait a few seconds, then kill it
	// Which seems to actually happen automatically, which is super nice.
	time.Sleep(2 * time.Second)

}
