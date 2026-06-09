@echo off
setlocal
REM ============================================================
REM  stop-mila.bat - gracefully stop MILA services.
REM  Closes windows by title and frees ports 5678 / 5051 / 5000.
REM ============================================================
echo === MILA: stopping services ===

for %%T in ("MILA n8n" "MILA bridge" "MILA webapp" "MILA poller") do (
  taskkill /fi "WINDOWTITLE eq %%~T*" /t /f >nul 2>&1
)

for %%P in (5678 5051 5000) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
    taskkill /pid %%I /f >nul 2>&1
  )
)

echo MILA services stopped.
timeout /t 3 >nul
