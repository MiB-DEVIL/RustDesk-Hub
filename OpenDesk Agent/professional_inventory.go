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

func compactJSON(raw string, fallback string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return fallback
	}

	var value any
	if err := json.Unmarshal([]byte(raw), &value); err != nil {
		return fallback
	}

	output, err := json.Marshal(value)
	if err != nil {
		return fallback
	}

	return string(output)
}

func CollectProfessionalInventory() map[string]string {
	softwareCommand := `
$paths = @(
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$items = Get-ItemProperty $paths -ErrorAction SilentlyContinue |
  Where-Object { $_.DisplayName } |
  ForEach-Object {
    [PSCustomObject]@{
      name = $_.DisplayName
      version = $_.DisplayVersion
      publisher = $_.Publisher
      architecture = if ($_.PSPath -like '*WOW6432Node*') {'x86'} else {'x64'}
    }
  } |
  Sort-Object name, version -Unique
@($items) | ConvertTo-Json -Compress -Depth 4
`

	hotfixCommand := `
$items = Get-HotFix -ErrorAction SilentlyContinue |
  Sort-Object InstalledOn -Descending |
  Select-Object -First 50 |
  ForEach-Object {
    [PSCustomObject]@{
      hotfix_id = $_.HotFixID
      description = $_.Description
      installed_on = if ($_.InstalledOn) {$_.InstalledOn.ToString('dd/MM/yyyy')} else {''}
    }
  }
@($items) | ConvertTo-Json -Compress -Depth 4
`

	securityCommand := `
$defender = Get-MpComputerStatus -ErrorAction SilentlyContinue
$bitlocker = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue
$tpm = Get-Tpm -ErrorAction SilentlyContinue
$secureBoot = try { Confirm-SecureBootUEFI -ErrorAction Stop } catch { $null }
$firewall = Get-NetFirewallProfile -ErrorAction SilentlyContinue |
  Where-Object Enabled |
  Select-Object -ExpandProperty Name
[PSCustomObject]@{
  antivirus = if ($defender) {'Microsoft Defender'} else {'Indisponible'}
  realtime_protection = if ($defender) {[string]$defender.RealTimeProtectionEnabled} else {'Indisponible'}
  bitlocker = if ($bitlocker) {[string]$bitlocker.ProtectionStatus} else {'Indisponible'}
  tpm = if ($tpm) {[string]$tpm.TpmReady} else {'Indisponible'}
  secure_boot = if ($null -ne $secureBoot) {[string]$secureBoot} else {'Indisponible'}
  firewall = if ($firewall) {($firewall -join ', ')} else {'Indisponible'}
} | ConvertTo-Json -Compress -Depth 4
`

	firmwareCommand := `
$bios = Get-CimInstance Win32_BIOS -ErrorAction SilentlyContinue
$board = Get-CimInstance Win32_BaseBoard -ErrorAction SilentlyContinue
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
[PSCustomObject]@{
  bios_manufacturer = $bios.Manufacturer
  bios_version = $bios.SMBIOSBIOSVersion
  bios_date = if ($bios.ReleaseDate) {$bios.ReleaseDate.ToString('dd/MM/yyyy')} else {''}
  firmware_type = if ($env:firmware_type) {$env:firmware_type} else {'UEFI/BIOS'}
  baseboard = (($board.Manufacturer, $board.Product) -join ' ').Trim()
  windows_build = $os.BuildNumber
} | ConvertTo-Json -Compress -Depth 4
`

	devicesCommand := `
$monitors = Get-CimInstance Win32_DesktopMonitor -ErrorAction SilentlyContinue |
  Where-Object Name |
  Select-Object -ExpandProperty Name -Unique
$printers = Get-CimInstance Win32_Printer -ErrorAction SilentlyContinue |
  Where-Object Name |
  Select-Object -ExpandProperty Name -Unique
[PSCustomObject]@{
  monitors = @($monitors)
  printers = @($printers)
} | ConvertTo-Json -Compress -Depth 4
`

	return map[string]string{
		"software_json": compactJSON(
			runPowerShell(softwareCommand),
			"[]",
		),
		"hotfixes_json": compactJSON(
			runPowerShell(hotfixCommand),
			"[]",
		),
		"security_json": compactJSON(
			runPowerShell(securityCommand),
			"{}",
		),
		"firmware_json": compactJSON(
			runPowerShell(firmwareCommand),
			"{}",
		),
		"devices_json": compactJSON(
			runPowerShell(devicesCommand),
			"{}",
		),
	}
}

func SendProfessionalInventory(config Config) error {
	data := CollectProfessionalInventory()

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

	endpoint := strings.TrimRight(
		config.Server,
		"/",
	) + "/api/agent/professional-inventory"

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

	if config.AgentAPIKey != "" {
		request.Header.Set(
			"X-Agent-Key",
			config.AgentAPIKey,
		)
	}

	client := &http.Client{
		Timeout: 180 * time.Second,
	}

	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf(
			"réponse inventaire professionnel : %s",
			response.Status,
		)
	}

	return nil
}
