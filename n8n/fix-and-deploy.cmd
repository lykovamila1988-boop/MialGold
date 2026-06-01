@echo off
setlocal EnableDelayedExpansion
set "MILA_ROOT=E:\MILA GOLD"
set "N8N_CMD=C:\Users\SdetArt\AppData\Roaming\npm\n8n.cmd"

if not exist "%N8N_CMD%" (
  echo n8n not found. Run: npm install -g n8n
  exit /b 1
)

echo === MILA n8n fix ===
echo Removing broken MILA workflows from ALL n8n data folders...
cd /d "%MILA_ROOT%\n8n"
python clean_mila_workflows.py

echo.
echo Importing HTTP-based workflows to project folder (n8n-data)...
set "N8N_USER_FOLDER=%MILA_ROOT%\n8n-data"
"%N8N_CMD%" import:workflow --separate --input="%MILA_ROOT%\n8n\workflows"
if errorlevel 1 exit /b 1

echo.
echo Importing HTTP-based workflows to default folder (~/.n8n)...
set "N8N_USER_FOLDER=%USERPROFILE%\.n8n"
"%N8N_CMD%" import:workflow --separate --input="%MILA_ROOT%\n8n\workflows"
if errorlevel 1 exit /b 1

echo.
echo === Done ===
echo RESTART n8n so it reloads workflows:
echo   1. Close any running n8n window
echo   2. tools\start-n8n-bridge.cmd
echo   3. tools\start-n8n-local.cmd
echo.
echo Open http://127.0.0.1:5678 — nodes should show globe icons, NOT ?
echo Full guide: n8n\SKILL.md
