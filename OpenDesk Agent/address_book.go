package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type AddressBookEntry struct {
	Name       string `json:"name"`
	RustDeskID string `json:"rustdesk_id"`
	Group      string `json:"group"`
	Hostname   string `json:"hostname"`
	OS         string `json:"os"`
	IP         string `json:"ip"`
	Online     bool   `json:"online"`
	LastSeen   string `json:"last_seen"`
}

type AddressBookResponse struct {
	Version string             `json:"version"`
	Count   int                `json:"count"`
	Entries []AddressBookEntry `json:"entries"`
}

func DownloadAddressBook(config Config) error {
	endpoint := strings.TrimRight(config.Server, "/") + "/api/address-book"

	request, err := http.NewRequest(http.MethodGet, endpoint, nil)
	if err != nil {
		return err
	}

	request.Header.Set("X-API-Key", config.AddressBookAPIKey)

	client := &http.Client{Timeout: 15 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()

	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("réponse carnet : %s", response.Status)
	}

	body, err := io.ReadAll(response.Body)
	if err != nil {
		return err
	}

	var addressBook AddressBookResponse
	if err := json.Unmarshal(body, &addressBook); err != nil {
		return err
	}

	output, err := json.MarshalIndent(addressBook, "", "  ")
	if err != nil {
		return err
	}

	path := filepath.Join(AppDirectory(), "address_book.json")
	return os.WriteFile(path, output, 0644)
}
