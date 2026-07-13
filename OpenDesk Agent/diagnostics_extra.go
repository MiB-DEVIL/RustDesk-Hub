package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

var (
	kernel32Extra         = syscall.NewLazyDLL("kernel32.dll")
	procGetLogicalDrives  = kernel32Extra.NewProc("GetLogicalDrives")
	procGetDriveTypeW     = kernel32Extra.NewProc("GetDriveTypeW")
)

const driveFixed = 3

func DiskDetails() (map[string]any, error) {
	mask, _, _ := procGetLogicalDrives.Call()
	drives := make([]map[string]any, 0)

	for index := 0; index < 26; index++ {
		if mask&(1<<index) == 0 {
			continue
		}

		letter := string(rune('A' + index))
		root := letter + `:\`
		rootPtr, err := syscall.UTF16PtrFromString(root)
		if err != nil {
			continue
		}

		driveType, _, _ := procGetDriveTypeW.Call(
			uintptr(unsafe.Pointer(rootPtr)),
		)

		if driveType != driveFixed {
			continue
		}

		var freeAvailable uint64
		var totalBytes uint64
		var totalFree uint64

		result, _, _ := procGetDiskFreeSpaceEx.Call(
			uintptr(unsafe.Pointer(rootPtr)),
			uintptr(unsafe.Pointer(&freeAvailable)),
			uintptr(unsafe.Pointer(&totalBytes)),
			uintptr(unsafe.Pointer(&totalFree)),
		)

		if result == 0 {
			continue
		}

		usedBytes := totalBytes - totalFree
		usedPercent := float64(0)

		if totalBytes > 0 {
			usedPercent = (float64(usedBytes) / float64(totalBytes)) * 100
		}

		drives = append(drives, map[string]any{
			"drive":        root,
			"total_bytes":  totalBytes,
			"free_bytes":   totalFree,
			"used_bytes":   usedBytes,
			"used_percent": fmt.Sprintf("%.1f", usedPercent),
		})
	}

	return map[string]any{
		"fixed_drives": drives,
		"count":        len(drives),
	}, nil
}

func WindowsInfo() (map[string]any, error) {
	output, err := runHiddenCommand(
		"cmd.exe",
		"/C",
		"ver",
	)

	version := strings.TrimSpace(output)
	if err != nil {
		version = "Indisponible"
	}

	return map[string]any{
		"os":              runtime.GOOS,
		"architecture":    runtime.GOARCH,
		"windows_version": version,
		"computer_name":   Hostname(),
		"user_name":       os.Getenv("USERNAME"),
		"user_domain":     os.Getenv("USERDOMAIN"),
		"system_root":     os.Getenv("SystemRoot"),
	}, nil
}

func DNSConfiguration() (map[string]any, error) {
	output, err := runHiddenCommand(
		"ipconfig.exe",
		"/all",
	)
	if err != nil {
		return nil, err
	}

	dnsServers := make([]string, 0)
	scanner := bufio.NewScanner(strings.NewReader(output))
	collectingDNS := false

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		lower := strings.ToLower(line)

		if strings.Contains(lower, "dns servers") ||
			strings.Contains(lower, "serveurs dns") {
			collectingDNS = true
			if parts := strings.SplitN(line, ":", 2); len(parts) == 2 {
				value := strings.TrimSpace(parts[1])
				if value != "" {
					dnsServers = append(dnsServers, value)
				}
			}
			continue
		}

		if collectingDNS {
			if line == "" {
				collectingDNS = false
				continue
			}

			if strings.Contains(line, ":") {
				collectingDNS = false
				continue
			}

			if net.ParseIP(line) != nil {
				dnsServers = append(dnsServers, line)
			}
		}
	}

	return map[string]any{
		"dns_servers": dnsServers,
		"count":       len(dnsServers),
	}, nil
}

func RecentSystemErrors() (map[string]any, error) {
	output, err := runHiddenCommand(
		"wevtutil.exe",
		"qe",
		"System",
		"/q:*[System[(Level=1 or Level=2)]]",
		"/c:10",
		"/rd:true",
		"/f:text",
	)
	if err != nil {
		return nil, err
	}

	lines := strings.Split(output, "\n")
	cleaned := make([]string, 0, len(lines))

	for _, line := range lines {
		value := strings.TrimSpace(line)
		if value == "" {
			continue
		}
		cleaned = append(cleaned, value)
	}

	return map[string]any{
		"lines": cleaned,
		"count": len(cleaned),
	}, nil
}

func parseUint(value string) uint64 {
	number, _ := strconv.ParseUint(strings.TrimSpace(value), 10, 64)
	return number
}
