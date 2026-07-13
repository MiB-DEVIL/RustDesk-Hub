@echo off
setlocal
cd /d "%~dp0"
set CGO_ENABLED=0
set GOOS=windows
set GOARCH=amd64
go build -trimpath -ldflags="-s -w -H=windowsgui" -o OpenDesk-Agent.exe .
if errorlevel 1 (
  echo Echec de compilation.
  exit /b 1
)
echo OpenDesk-Agent.exe cree avec succes.
