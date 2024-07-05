package main

import (
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type Core struct {
	Id   string
	Exec *exec.Cmd
}

func scanForCores(paths []string) []string {
	var foundCores []string

	for _, path := range paths {
		filepath.WalkDir(path, func(path string, _ fs.DirEntry, _ error) error {
			iscore, err := pathIsCore(path)
			if err != nil {
				c.Log(err.Error())
			}

			if iscore {
				foundCores = append(foundCores, path)
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

// Starts a Core that presently only has a path
func createCore(corePath string, coreChannel chan<- Core) {
	orchestratorProvidedArgs := []string{"--device-id", bloobConfig["uuid"].(string), "--host", mqttConfig.Host, "--port", fmt.Sprintf("%v", mqttConfig.Port)}

	if mqttConfig.Username != "" && mqttConfig.Password != "" {
		orchestratorProvidedArgs = append(orchestratorProvidedArgs, "--user", mqttConfig.Username, "--pass", mqttConfig.Password)
	}

	fileName := filepath.Base(corePath)

	// Follows the naming convention where Cores are named {core_id}_bb_core
	coreId := strings.Split(fileName, "_bb_core")[0]

	coreChannel <- Core{Id: coreId, Exec: exec.Command(corePath, orchestratorProvidedArgs...)}
}
