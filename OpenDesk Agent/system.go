package main

import (
	"os"
	"os/user"
	"runtime"
)

func Hostname() string {
	name, err := os.Hostname()
	if err != nil {
		return "Unknown"
	}
	return name
}

func Username() string {
	u, err := user.Current()
	if err != nil {
		return "Unknown"
	}
	return u.Username
}

func OSVersion() string {
	return runtime.GOOS
}
