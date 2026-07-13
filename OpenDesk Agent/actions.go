package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type PendingAction struct {
	UUID string `json:"uuid"`
	Type string `json:"type"`
}

type PendingActionResponse struct {
	Status string         `json:"status"`
	Action *PendingAction `json:"action"`
}

func PollAndExecuteAction(config Config, logger *Logger) error {
	machineUUID := MachineUUID()
	endpoint := strings.TrimRight(config.Server, "/") +
		"/api/agent/actions/next?machine_uuid=" + url.QueryEscape(machineUUID)

	req, err := http.NewRequest(http.MethodGet, endpoint, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-Agent-Key", config.AgentAPIKey)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("lecture des actions : %s", resp.Status)
	}

	var payload PendingActionResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return err
	}
	if payload.Action == nil {
		return nil
	}

	logger.Info("Action reçue : " + payload.Action.Type)
	success, message, data, actionErr := executeSafeAction(config, payload.Action.Type)
	errText := ""
	if actionErr != nil {
		errText = actionErr.Error()
	}

	return sendActionResult(config, payload.Action.UUID, success, message, data, errText)
}

func executeSafeAction(config Config, actionType string) (bool, string, map[string]any, error) {
	switch actionType {
	case "agent_status":
		return true, "Agent opérationnel", map[string]any{
			"agent_version": AgentVersion,
			"hostname":      Hostname(),
			"machine_uuid":  MachineUUID(),
			"local_ip":      LocalIP(),
		}, nil

	case "inventory_now":
		if err := SendInventory(config); err != nil {
			return false, "Inventaire en échec", nil, err
		}
		return true, "Inventaire envoyé", map[string]any{"sent": true}, nil

	case "rustdesk_refresh":
		id := RustDeskID()
		if id == "" {
			return false, "ID RustDesk introuvable", nil, fmt.Errorf("RustDesk non détecté")
		}
		return true, "Informations RustDesk actualisées", map[string]any{
			"rustdesk_id":      id,
			"rustdesk_version": RustDeskVersion(),
		}, nil

	case "network_test":
		start := time.Now()
		endpoint := strings.TrimRight(config.Server, "/") + "/"
		client := &http.Client{Timeout: 15 * time.Second}
		resp, err := client.Get(endpoint)
		if err != nil {
			return false, "Hub inaccessible", nil, err
		}
		resp.Body.Close()
		return true, "Connexion au Hub réussie", map[string]any{
			"http_status": resp.StatusCode,
			"duration_ms": time.Since(start).Milliseconds(),
			"local_ip":    LocalIP(),
		}, nil

	case "system_health":
		data, err := SystemHealth()
		if err != nil {
			return false, "Diagnostic système en échec", nil, err
		}
		return true, "Santé système collectée", data, nil

	case "network_details":
		data, err := NetworkDetails()
		if err != nil {
			return false, "Collecte réseau en échec", nil, err
		}
		return true, "Informations réseau collectées", data, nil

	case "process_check":
		data, err := ProcessCheck()
		if err != nil {
			return false, "Vérification des processus en échec", nil, err
		}
		return true, "Processus vérifiés", data, nil

	case "disk_details":
		data, err := DiskDetails()
		if err != nil {
			return false, "Collecte des disques en échec", nil, err
		}
		return true, "Informations disques collectées", data, nil

	case "windows_info":
		data, err := WindowsInfo()
		if err != nil {
			return false, "Collecte Windows en échec", nil, err
		}
		return true, "Informations Windows collectées", data, nil

	case "dns_configuration":
		data, err := DNSConfiguration()
		if err != nil {
			return false, "Collecte DNS en échec", nil, err
		}
		return true, "Configuration DNS collectée", data, nil

	case "recent_system_errors":
		data, err := RecentSystemErrors()
		if err != nil {
			return false, "Lecture des erreurs système en échec", nil, err
		}
		return true, "Erreurs système récentes collectées", data, nil

	default:
		return false, "Action refusée", nil, fmt.Errorf("type d’action non autorisé : %s", actionType)
	}
}

func sendActionResult(
	config Config,
	actionUUID string,
	success bool,
	message string,
	data map[string]any,
	errorText string,
) error {
	encoded, _ := json.Marshal(data)
	form := url.Values{}
	form.Set("machine_uuid", MachineUUID())
	form.Set("success", fmt.Sprintf("%t", success))
	form.Set("message", message)
	form.Set("data_json", string(encoded))
	form.Set("error", errorText)

	endpoint := strings.TrimRight(config.Server, "/") +
		"/api/agent/actions/" + url.PathEscape(actionUUID) + "/result"
	req, err := http.NewRequest(
		http.MethodPost,
		endpoint,
		bytes.NewBufferString(form.Encode()),
	)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("X-Agent-Key", config.AgentAPIKey)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("envoi du résultat : %s", resp.Status)
	}
	return nil
}
