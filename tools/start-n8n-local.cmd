@echo off
rem MILA project n8n — always use repo data folder (NOT %USERPROFILE%\.n8n)
set "N8N_USER_FOLDER=E:\MILA GOLD\n8n-data"
set "N8N_PORT=5678"
set "N8N_HOST=127.0.0.1"
set "N8N_RUNNERS_ENABLED=true"

if not exist "E:\MILA GOLD\logs" mkdir "E:\MILA GOLD\logs"
echo n8n data folder: %N8N_USER_FOLDER%
echo UI: http://127.0.0.1:%N8N_PORT%
echo Bridge must run first: tools\start-n8n-bridge.cmd
"C:\Users\SdetArt\AppData\Roaming\npm\n8n.cmd" start >> "E:\MILA GOLD\logs\n8n-start.out.log" 2>> "E:\MILA GOLD\logs\n8n-start.err.log"
