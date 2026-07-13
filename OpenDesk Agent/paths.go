package main

import (
	"os"
	"path/filepath"
)

func AppDirectory() string {
	exe, err := os.Executable()
	if err != nil {
		dir, _ := os.Getwd()
		return dir
	}
	return filepath.Dir(exe)
}
