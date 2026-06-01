@echo off
set "MILA_ROOT=E:\MILA GOLD"
cd /d "%MILA_ROOT%\mila-office"
if not exist "E:\MILA GOLD\logs" mkdir "E:\MILA GOLD\logs"
python n8n_bridge.py >> "E:\MILA GOLD\logs\n8n-bridge.out.log" 2>> "E:\MILA GOLD\logs\n8n-bridge.err.log"
