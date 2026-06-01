@echo off
setlocal
set "MILA_ROOT=E:\MILA GOLD"
set "N8N_CMD=C:\Users\SdetArt\AppData\Roaming\npm\n8n.cmd"

if not exist "%N8N_CMD%" (
  echo n8n not found at %N8N_CMD%
  echo Install: npm install -g n8n
  exit /b 1
)

echo Deploying to BOTH n8n data folders...
cd /d "%MILA_ROOT%\n8n"
python clean_mila_workflows.py

set "N8N_USER_FOLDER=%MILA_ROOT%\n8n-data"
echo Import -^> %N8N_USER_FOLDER%
"%N8N_CMD%" import:workflow --separate --input="%MILA_ROOT%\n8n\workflows"
if errorlevel 1 exit /b 1

set "N8N_USER_FOLDER=%USERPROFILE%\.n8n"
echo Import -^> %N8N_USER_FOLDER%
"%N8N_CMD%" import:workflow --separate --input="%MILA_ROOT%\n8n\workflows"
if errorlevel 1 exit /b 1

echo.
echo OK. Start: tools\start-n8n-bridge.cmd then tools\start-n8n-local.cmd
echo See n8n\SKILL.md
