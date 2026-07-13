package main
import ("encoding/json"; "fmt"; "net/http"; "strings"; "time")
type RemoteConfig struct { Heartbeat int `json:"heartbeat"`; AddressBookSync int `json:"address_book_sync"`; InventorySync int `json:"inventory_sync"`; InventoryEnabled bool `json:"inventory_enabled"`; AddressBookEnabled bool `json:"address_book_enabled"` }
func FetchRemoteConfig(config Config)(RemoteConfig,error){ endpoint:=strings.TrimRight(config.Server,"/")+"/api/agent/config"; c:=&http.Client{Timeout:15*time.Second}; r,e:=c.Get(endpoint); if e!=nil{return RemoteConfig{},e}; defer r.Body.Close(); if r.StatusCode<200||r.StatusCode>=300{return RemoteConfig{},fmt.Errorf("configuration distante : %s",r.Status)}; var out RemoteConfig; e=json.NewDecoder(r.Body).Decode(&out); return out,e }
