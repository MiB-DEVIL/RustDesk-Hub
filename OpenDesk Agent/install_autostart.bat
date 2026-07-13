@echo off
setlocal
cd /d "%~dp0"

if not exist "OpenDesk-Agent.exe" (
    echo OpenDesk-Agent.exe introuvable.
    echo Lance d'abord build.bat.
    pause
    exit /b 1
)

echo Installation du demarrage automatique...

schtasks /Create ^
 /TN "OpenDesk Agent" ^
 /TR "\"%CD%\OpenDesk-Agent.exe\"" ^
 /SC ONSTART ^
 /RU SYSTEM ^
 /RL HIGHEST ^
 /F

if errorlevel 1 (
    echo.
    echo ERREUR : lance ce fichier en tant qu'administrateur.
    pause
    exit /b 1
)

schtasks /Run /TN "OpenDesk Agent"

echo.
echo OpenDesk Agent est installe au demarrage de Windows.
pause
