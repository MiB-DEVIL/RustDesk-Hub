package main

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"unsafe"
)

var (
	kernel32Diag           = syscall.NewLazyDLL("kernel32.dll")
	procGetTickCount64     = kernel32Diag.NewProc("GetTickCount64")
	procGetDiskFreeSpaceEx = kernel32Diag.NewProc("GetDiskFreeSpaceExW")
)

func SystemHealth() (map[string]any, error) {
	uptimeMilliseconds, _, _ := procGetTickCount64.Call()
	uptimeSeconds := uint64(uptimeMilliseconds) / 1000

	systemDrive := os.Getenv("SystemDrive")
	if systemDrive == "" {
		systemDrive = "C:"
	}

	root := filepath.Clean(systemDrive + `\`)
	rootPtr, err := syscall.UTF16PtrFromString(root)
	if err != nil {
		return nil, err
	}

	var freeAvailable uint64
	var totalBytes uint64
	var totalFree uint64

	result, _, callErr := procGetDiskFreeSpaceEx.Call(
		uintptr(unsafe.Pointer(rootPtr)),
		uintptr(unsafe.Pointer(&freeAvailable)),
		uintptr(unsafe.Pointer(&totalBytes)),
		uintptr(unsafe.Pointer(&totalFree)),
	)

	if result == 0 {
		return nil, fmt.Errorf("lecture espace disque impossible : %v", callErr)
	}

	usedBytes := totalBytes - totalFree
	usedPercent := float64(0)

	if totalBytes > 0 {
		usedPercent = (float64(usedBytes) / float64(totalBytes)) * 100
	}

	return map[string]any{
		"uptime_seconds":    uptimeSeconds,
		"uptime_hours":      float64(uptimeSeconds) / 3600,
		"system_drive":      root,
		"disk_total_bytes":  totalBytes,
		"disk_free_bytes":   totalFree,
		"disk_used_bytes":   usedBytes,
		"disk_used_percent": fmt.Sprintf("%.1f", usedPercent),
	}, nil
}

func NetworkDetails() (map[string]any, error) {
	interfaces, err := net.Interfaces()
	if err != nil {
		return nil, err
	}

	items := make([]map[string]any, 0)

	for _, iface := range interfaces {
		addresses, addressErr := iface.Addrs()
		if addressErr != nil {
			continue
		}

		addressStrings := make([]string, 0, len(addresses))
		for _, address := range addresses {
			addressStrings = append(addressStrings, address.String())
		}

		sort.Strings(addressStrings)

		items = append(items, map[string]any{
			"name":       iface.Name,
			"mac":        iface.HardwareAddr.String(),
			"mtu":        iface.MTU,
			"flags":      iface.Flags.String(),
			"addresses":  addressStrings,
		})
	}

	sort.Slice(items, func(i, j int) bool {
		return fmt.Sprint(items[i]["name"]) < fmt.Sprint(items[j]["name"])
	})

	return map[string]any{
		"hostname":   Hostname(),
		"local_ip":   LocalIP(),
		"interfaces": items,
	}, nil
}

func ProcessCheck() (map[string]any, error) {
	targets := []string{
		"OpenDesk-Agent.exe",
		"rustdesk.exe",
	}

	running := map[string]bool{}

	processEntries, err := os.ReadDir(`C:\Windows\System32`)
	_ = processEntries
	_ = err

	// Utilise tasklist uniquement en lecture, fenêtre masquée.
	for _, target := range targets {
		isRunning, checkErr := processExists(target)
		if checkErr != nil {
			running[target] = false
			continue
		}
		running[target] = isRunning
	}

	return map[string]any{
		"processes": running,
	}, nil
}

func processExists(processName string) (bool, error) {
	output, err := runHiddenCommand(
		"tasklist.exe",
		"/FI",
		"IMAGENAME eq "+processName,
		"/FO",
		"CSV",
		"/NH",
	)
	if err != nil {
		return false, err
	}

	normalized := strings.ToLower(output)
	return strings.Contains(
		normalized,
		strings.ToLower(processName),
	), nil
}
