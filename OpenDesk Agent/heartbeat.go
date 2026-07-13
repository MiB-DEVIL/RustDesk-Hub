package main

import (
	"bytes"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const AgentVersion = "1.2.0"

func SendHeartbeat(config Config) error {
	rustdeskID := config.RustDeskID
	if strings.EqualFold(rustdeskID, "AUTO") || rustdeskID == "" {
		rustdeskID = RustDeskID()
	}
	if rustdeskID == "" {
		return fmt.Errorf("ID RustDesk introuvable : vérifier que RustDesk est installé et lancé au moins une fois")
	}

	machineUUID := MachineUUID()
	if machineUUID == "" {
		return fmt.Errorf("impossible de créer l'identité permanente de la machine")
	}

	form := url.Values{}
	form.Set("machine_uuid", machineUUID)
	form.Set("rustdesk_id", rustdeskID)
	form.Set("hostname", Hostname())
	form.Set("os", OSVersion())
	form.Set("ip", LocalIP())
	form.Set("version", RustDeskVersion())
	form.Set("bios_serial", BIOSSerial())
	form.Set("motherboard_serial", MotherboardSerial())
	form.Set("primary_mac", primaryMAC())
	form.Set("agent_version", AgentVersion)

	endpoint := strings.TrimRight(config.Server, "/") + "/api/agent/heartbeat"
	req, err := http.NewRequest(http.MethodPost, endpoint, bytes.NewBufferString(form.Encode()))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if config.AgentAPIKey != "" {
		req.Header.Set("X-Agent-Key", config.AgentAPIKey)
	}

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("réponse serveur : %s", resp.Status)
	}
	return nil
}
