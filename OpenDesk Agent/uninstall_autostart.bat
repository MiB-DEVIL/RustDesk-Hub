@echo off
schtasks /End /TN "OpenDesk Agent" >nul 2>&1
schtasks /Delete /TN "OpenDesk Agent" /F

echo OpenDesk Agent a ete retire du demarrage automatique.
pause
