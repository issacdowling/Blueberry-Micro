package main

import (
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

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

func startCores(corePaths []string) ([]*exec.Cmd, error) {
	var runningCores []*exec.Cmd
	for _, corePath := range corePaths {
		runningCores = append(runningCores, exec.Command(corePath))
	}
	for _, coreToRun := range runningCores {
		err := coreToRun.Start()
		if err != nil {
			return nil, err
		}
	}
	return runningCores, nil
}
