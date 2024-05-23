package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
)

type Core struct {
	Id    string
	Roles []string
	Exec  *exec.Cmd
}

type Identification struct {
	Id    string
	Roles []string
}

func scanForCores(paths []string) []string {
	var foundCores []string

	for _, path := range paths {
		filepath.WalkDir(path, func(path string, _ fs.DirEntry, _ error) error {
			iscore, err := pathIsCore(path)
			if err != nil {
				fmt.Println(err)
			}

			if iscore {
				foundCores = append(foundCores, path)
				// runningCores = append(runningCores, exec.Command(path))
			}
			return nil
		})
	}

	return foundCores

}

func pathIsCore(path string) (bool, error) {
	fileStats, err := os.Stat(path)
	if err != nil {
		return false, err
	}
	// fileStats.Mode() should return something like -rw-r--r--, and I'm checking whether the 4th value is x to see if it's executable
	if strings.Contains(path, "bb_core") {
		if fmt.Sprint(fileStats.Mode())[3] == '-' {
			return false, fmt.Errorf("core %v was found, but is not executable by its owner", path)
		} else if fmt.Sprint(fileStats.Mode())[3] == 'x' {
			return true, nil
		}
	}
	return false, nil
}

func startCores(corePaths []string) ([]Core, error) {
	var runningCores []Core
	var currentIdent map[string]interface{}
	orchestratorProvidedArgs := []string{"--device-id", bloobConfig["uuid"].(string), "--host", mqttConfig.Host, "--port", mqttConfig.Port}
	if mqttConfig.Username != "" && mqttConfig.Password != "" {
		orchestratorProvidedArgs = append(orchestratorProvidedArgs, "--user", mqttConfig.Username, "--pass", mqttConfig.Password)
	}
	for _, corePath := range corePaths {
		log.Println("Loading Core:", corePath)

		coreIdentRaw, err := exec.Command(corePath, "--identify", "true").Output()
		if err != nil {
			return nil, err
		}

		json.Unmarshal(coreIdentRaw, &currentIdent)

		roles := make([]string, len(currentIdent["roles"].([]interface{})))
		for _, role := range currentIdent["roles"].([]interface{}) {
			roles = append(roles, role.(string))
		}

		runningCores = append(runningCores, Core{Id: currentIdent["id"].(string), Exec: exec.Command(corePath, orchestratorProvidedArgs...), Roles: roles})
	}
	for _, coreToRun := range runningCores {
		err := coreToRun.Exec.Start()
		if err != nil {
			return nil, err
		}
	}
	return runningCores, nil
}

// Returns a list of collections (each collection is a map[string]interface{}, a JSON object) from the core that this was called on.
func (core Core) getCollections() ([]map[string]interface{}, error) {
	if !slices.Contains(core.Roles, "collection_handler") {
		return nil, errors.New("Core is not a collection handler")
	}
	collectionsBytes, err := exec.Command(core.Exec.Path, "--collections", "true").Output()
	if err != nil {
		return nil, err
	}
	var collectionsJson map[string]interface{}
	json.Unmarshal(collectionsBytes, &collectionsJson)

	var coreCollections []map[string]interface{}
	for _, collection := range collectionsJson["collections"].([]interface{}) {
		coreCollections = append(coreCollections, collection.(map[string]interface{}))
	}
	return coreCollections, nil
}
