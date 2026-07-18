@echo off
setlocal
cd /d "%~dp0"

set CGO_ENABLED=0
set GOOS=windows

if not exist dist mkdir dist

echo Compilation x64...
set GOARCH=amd64
go build -trimpath -ldflags="-s -w -H=windowsgui" -o dist\OpenDesk-Agent-x64.exe .
if errorlevel 1 (
  echo Echec de compilation x64.
  exit /b 1
)

echo Compilation x86...
set GOARCH=386
go build -trimpath -ldflags="-s -w -H=windowsgui" -o dist\OpenDesk-Agent-x86.exe .
if errorlevel 1 (
  echo Echec de compilation x86.
  exit /b 1
)

echo.
echo Compilation terminee avec succes.
echo Fichiers crees :
echo dist\OpenDesk-Agent-x64.exe
echo dist\OpenDesk-Agent-x86.exe