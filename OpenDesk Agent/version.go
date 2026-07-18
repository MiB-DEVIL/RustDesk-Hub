package main

import "runtime"

var BuildDate = "Developpement"

func AgentBuildDate() string {
	return BuildDate
}

func AgentArchitecture() string {
	return runtime.GOARCH
}