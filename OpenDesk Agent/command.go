package main

import (
	"bytes"
	"os/exec"
)

func runHiddenCommand(name string, args ...string) (string, error) {
	command := exec.Command(name, args...)
	command.SysProcAttr = hiddenWindowAttributes()

	var output bytes.Buffer
	var errorOutput bytes.Buffer

	command.Stdout = &output
	command.Stderr = &errorOutput

	err := command.Run()
	if err != nil {
		if errorOutput.Len() > 0 {
			return output.String(), &commandError{
				command: name,
				message: errorOutput.String(),
			}
		}
		return output.String(), err
	}

	return output.String(), nil
}

type commandError struct {
	command string
	message string
}

func (e *commandError) Error() string {
	return e.command + " : " + e.message
}
