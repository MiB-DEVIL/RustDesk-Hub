package main

import (
    "crypto/rand"
    "encoding/hex"
    "fmt"
    "os"
    "path/filepath"
    "strings"
)

func MachineUUID() string {
    dir := filepath.Join(os.Getenv("PROGRAMDATA"), "OpenDesk")
    if dir == "OpenDesk" {
        dir = AppDirectory()
    }
    _ = os.MkdirAll(dir, 0755)
    path := filepath.Join(dir, "machine.id")

    if data, err := os.ReadFile(path); err == nil {
        value := strings.TrimSpace(string(data))
        if value != "" {
            return value
        }
    }

    raw := make([]byte, 16)
    if _, err := rand.Read(raw); err != nil {
        return ""
    }
    raw[6] = (raw[6] & 0x0f) | 0x40
    raw[8] = (raw[8] & 0x3f) | 0x80
    encoded := hex.EncodeToString(raw)
    value := fmt.Sprintf(
        "%s-%s-%s-%s-%s",
        encoded[0:8], encoded[8:12], encoded[12:16], encoded[16:20], encoded[20:32],
    )
    _ = os.WriteFile(path, []byte(value+"\n"), 0600)
    return value
}

func BIOSSerial() string {
    return runPowerShell("(Get-CimInstance Win32_BIOS).SerialNumber")
}

func MotherboardSerial() string {
    return runPowerShell("(Get-CimInstance Win32_BaseBoard).SerialNumber")
}
