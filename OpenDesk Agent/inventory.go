package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

type DiskInfo struct {
	Name   string  `json:"name"`
	SizeGB float64 `json:"size_gb"`
	FreeGB float64 `json:"free_gb"`
}

func runPowerShell(command string) string {
	cmd := exec.Command(
		"powershell",
		"-NoProfile",
		"-Command",
		command,
	)

	cmd.SysProcAttr = hiddenWindowAttributes()

	output, err := cmd.Output()
	if err != nil {
		return ""
	}

	return strings.TrimSpace(string(output))
}

func CollectInventory() map[string]string {
	ramBytes := runPowerShell(
		"(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
	)

	ramGB := ""

	if value, err := strconv.ParseFloat(ramBytes, 64); err == nil {
		ramGB = fmt.Sprintf("%.1f", value/1024/1024/1024)
	}

	disksRaw := runPowerShell(
		`Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ` +
			`Select-Object DeviceID,Size,FreeSpace | ConvertTo-Json -Compress`,
	)

	disks := normalizeDisks(disksRaw)

	return map[string]string{
		"username":      Username(),
		"os_version":    runPowerShell("(Get-CimInstance Win32_OperatingSystem).Caption"),
		"cpu":           runPowerShell("(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"),
		"ram_gb":        ramGB,
		"manufacturer":  runPowerShell("(Get-CimInstance Win32_ComputerSystem).Manufacturer"),
		"model":         runPowerShell("(Get-CimInstance Win32_ComputerSystem).Model"),
		"serial_number": runPowerShell("(Get-CimInstance Win32_BIOS).SerialNumber"),
		"mac":           primaryMAC(),
		"uptime_seconds": runPowerShell(
			"[int]((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalSeconds",
		),
		"disks_json": disks,
	}
}

func normalizeDisks(raw string) string {
	if raw == "" {
		return "[]"
	}

	var generic any

	if err := json.Unmarshal([]byte(raw), &generic); err != nil {
		return "[]"
	}

	items := []map[string]any{}

	switch value := generic.(type) {
	case map[string]any:
		items = append(items, value)
	case []any:
		for _, item := range value {
			if m, ok := item.(map[string]any); ok {
				items = append(items, m)
			}
		}
	}

	result := []DiskInfo{}

	for _, item := range items {
		name, _ := item["DeviceID"].(string)
		size, _ := item["Size"].(float64)
		free, _ := item["FreeSpace"].(float64)

		result = append(result, DiskInfo{
			Name:   name,
			SizeGB: round1(size / 1024 / 1024 / 1024),
			FreeGB: round1(free / 1024 / 1024 / 1024),
		})
	}

	output, err := json.Marshal(result)
	if err != nil {
		return "[]"
	}

	return string(output)
}

func round1(value float64) float64 {
	return float64(int(value*10+0.5)) / 10
}

func primaryMAC() string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return ""
	}

	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 ||
			iface.Flags&net.FlagLoopback != 0 ||
			len(iface.HardwareAddr) == 0 {
			continue
		}

		return iface.HardwareAddr.String()
	}

	return ""
}

func SendInventory(config Config) error {
	data := CollectInventory()

	rustdeskID := config.RustDeskID
	if strings.EqualFold(rustdeskID, "AUTO") || rustdeskID == "" {
		rustdeskID = RustDeskID()
	}

	form := url.Values{}
	form.Set("machine_uuid", MachineUUID())
	form.Set("rustdesk_id", rustdeskID)

	for key, value := range data {
		form.Set(key, value)
	}

	endpoint := strings.TrimRight(config.Server, "/") + "/api/agent/inventory"

	request, err := http.NewRequest(
		http.MethodPost,
		endpoint,
		bytes.NewBufferString(form.Encode()),
	)

	if err != nil {
		return err
	}

	request.Header.Set(
		"Content-Type",
		"application/x-www-form-urlencoded",
	)

	client := &http.Client{
		Timeout: 45 * time.Second,
	}

	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf(
			"réponse inventaire : %s",
			response.Status,
		)
	}

	return nil
}
