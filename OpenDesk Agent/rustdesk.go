package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "regexp"
    "strings"
)

func rustDeskExecutables() []string {
    return []string{
        filepath.Join(os.Getenv("PROGRAMFILES"), "RustDesk", "RustDesk.exe"),
        filepath.Join(os.Getenv("PROGRAMFILES(X86)"), "RustDesk", "RustDesk.exe"),
        filepath.Join(os.Getenv("LOCALAPPDATA"), "RustDesk", "RustDesk.exe"),
        filepath.Join(AppDirectory(), "RustDesk.exe"),
    }
}

func RustDeskID() string {
    // Méthode prioritaire : demander directement son ID au client installé.
    for _, exePath := range rustDeskExecutables() {
        if _, err := os.Stat(exePath); err != nil {
            continue
        }
        cmd := exec.Command(exePath, "--get-id")
        cmd.SysProcAttr = hiddenWindowAttributes()
        if output, err := cmd.Output(); err == nil {
            if id := extractRustDeskID(string(output)); id != "" {
                return id
            }
        }
    }

    // Repli : lecture stricte des fichiers RustDesk. Le motif est ancré au
    // début de ligne afin de ne plus confondre une autre valeur telle que 005.
    possibleFiles := []string{
        filepath.Join(os.Getenv("APPDATA"), "RustDesk", "config", "RustDesk2.toml"),
        filepath.Join(os.Getenv("APPDATA"), "RustDesk", "config", "RustDesk.toml"),
        filepath.Join(os.Getenv("PROGRAMDATA"), "RustDesk", "config", "RustDesk2.toml"),
        filepath.Join(os.Getenv("PROGRAMDATA"), "RustDesk", "config", "RustDesk.toml"),
    }
    re := regexp.MustCompile(`(?m)^\s*(?:id|rustdesk_id)\s*=\s*['"]?([0-9]{6,12})['"]?\s*$`)
    for _, path := range possibleFiles {
        data, err := os.ReadFile(path)
        if err != nil {
            continue
        }
        match := re.FindStringSubmatch(string(data))
        if len(match) == 2 {
            return match[1]
        }
    }
    return ""
}

func extractRustDeskID(raw string) string {
    re := regexp.MustCompile(`[0-9]{6,12}`)
    return strings.TrimSpace(re.FindString(raw))
}

func RustDeskVersion() string {
    for _, path := range rustDeskExecutables() {
        if _, err := os.Stat(path); err == nil {
            version := runPowerShell("(Get-Item '" + strings.ReplaceAll(path, "'", "''") + "').VersionInfo.ProductVersion")
            if version != "" {
                return version
            }
            return "installed"
        }
    }
    return "unknown"
}
