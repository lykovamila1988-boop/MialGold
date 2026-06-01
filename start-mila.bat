@echo off
setlocal
REM ============================================================
REM  start-mila.bat - launch the whole MILA system in one click.
REM  Idempotent: a service starts only if its port is free.
REM    n8n        :5678   n8n_bridge :5051   webapp :5000
REM    telegram_poller (HOCHU flow, no port)
REM  Put a shortcut in shell:startup for autostart on login.
REM ============================================================
set "MILA=E:\MILA GOLD"
set "PATH=C:\Program Files\nodejs;%PATH%"
set "N8NCMD=C:\Users\SdetArt\AppData\Roaming\npm\n8n.cmd"
set "PYTHONIOENCODING=utf-8"

echo === MILA: starting services ===

call :startport 5678 "MILA n8n"     "%N8NCMD% start"
call :startport 5051 "MILA bridge"  "cd /d ""%MILA%\mila-office"" ^& python n8n_bridge.py"
call :startport 5000 "MILA webapp"  "cd /d ""%MILA%\mila-office"" ^& python webapp.py"

REM poller has no port - kill old one by title, then start fresh
taskkill /fi "WINDOWTITLE eq MILA poller*" /t /f >nul 2>&1
echo [poller] starting...
start "MILA poller" /min cmd /c "cd /d ""%MILA%\tools"" & python telegram_poller.py"

echo.
echo Done. In ~30s open:
echo   n8n     http://localhost:5678
echo   webapp  http://localhost:5000   (agents)   /dashboard (approve)
echo Stop everything: stop-mila.bat
timeout /t 5 >nul
goto :eof

REM ---- :startport PORT TITLE COMMAND ----
:startport
netstat -ano | findstr ":%~1 " | findstr LISTENING >nul
if errorlevel 1 (
  echo [%~2] starting...
  start "%~2" /min cmd /c "%~3"
) else (
  echo [%~2] already running on :%~1
)
goto :eof
