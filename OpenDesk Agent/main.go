package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func main() {
	c := LoadConfig()
	logger, e := NewLogger(filepath.Join(AppDirectory(), "opendesk-agent.log"))
	if e != nil {
		fmt.Println("Erreur journal :", e)
		os.Exit(1)
	}
	defer logger.Close()
	logger.Info("OpenDesk Agent v1.2.0 démarré")
	_ = SendRemoteLog(c, "INFO", "startup", "Agent démarré")
	if rc, e := FetchRemoteConfig(c); e == nil {
		if rc.Heartbeat > 0 {
			c.Heartbeat = rc.Heartbeat
		}
		if rc.AddressBookSync > 0 {
			c.AddressBookSync = rc.AddressBookSync
		}
		if rc.InventorySync > 0 {
			c.InventorySync = rc.InventorySync
		}
		logger.Info("Configuration distante chargée")
	} else {
		logger.Error("Configuration distante : " + e.Error())
	}
	if e := SendHeartbeat(c); e != nil {
		logger.Error("Heartbeat initial : " + e.Error())
		_ = SendRemoteLog(c, "ERROR", "heartbeat", e.Error())
	} else {
		logger.Info("Heartbeat initial envoyé")
	}
	if e := PollAndExecuteAction(c, logger); e != nil {
		logger.Error("Actions initiales : " + e.Error())
	}
	if e := DownloadAddressBook(c); e != nil {
		logger.Error("Carnet initial : " + e.Error())
		_ = SendRemoteLog(c, "ERROR", "address_book", e.Error())
	} else {
		logger.Info("Carnet partagé téléchargé")
		_ = SendRemoteLog(c, "INFO", "address_book", "Carnet synchronisé")
	}
	if e := SendInventory(c); e != nil {
		logger.Error("Inventaire initial : " + e.Error())
		_ = SendRemoteLog(c, "ERROR", "inventory", e.Error())
	} else {
		logger.Info("Inventaire envoyé")
		_ = SendRemoteLog(c, "INFO", "inventory", "Inventaire mis à jour")
	}
	if e := SendProfessionalInventory(c); e != nil {
		logger.Error("Inventaire professionnel initial : " + e.Error())
		_ = SendRemoteLog(c, "ERROR", "professional_inventory", e.Error())
	} else {
		logger.Info("Inventaire professionnel envoyé")
		_ = SendRemoteLog(c, "INFO", "professional_inventory", "Inventaire professionnel mis à jour")
	}
	ht := time.NewTicker(time.Duration(c.Heartbeat) * time.Second)
	at := time.NewTicker(time.Duration(c.AddressBookSync) * time.Second)
	it := time.NewTicker(time.Duration(c.InventorySync) * time.Second)
	defer ht.Stop()
	defer at.Stop()
	defer it.Stop()
	for {
		select {
		case <-ht.C:
			if e := SendHeartbeat(c); e != nil {
				logger.Error("Heartbeat : " + e.Error())
				_ = SendRemoteLog(c, "ERROR", "heartbeat", e.Error())
			} else {
				logger.Info("Heartbeat envoyé")
			}
			if e := PollAndExecuteAction(c, logger); e != nil {
				logger.Error("Actions : " + e.Error())
			}
		case <-at.C:
			if e := DownloadAddressBook(c); e != nil {
				logger.Error("Carnet : " + e.Error())
				_ = SendRemoteLog(c, "ERROR", "address_book", e.Error())
			} else {
				logger.Info("Carnet partagé téléchargé")
				_ = SendRemoteLog(c, "INFO", "address_book", "Carnet synchronisé")
			}
		case <-it.C:
			if e := SendInventory(c); e != nil {
				logger.Error("Inventaire : " + e.Error())
				_ = SendRemoteLog(c, "ERROR", "inventory", e.Error())
			} else {
				logger.Info("Inventaire envoyé")
				_ = SendRemoteLog(c, "INFO", "inventory", "Inventaire mis à jour")
			}
			if e := SendProfessionalInventory(c); e != nil {
				logger.Error("Inventaire professionnel : " + e.Error())
				_ = SendRemoteLog(c, "ERROR", "professional_inventory", e.Error())
			} else {
				logger.Info("Inventaire professionnel envoyé")
				_ = SendRemoteLog(c, "INFO", "professional_inventory", "Inventaire professionnel mis à jour")
			}
		}
	}
}
