@echo off
rem MILA OFFICE webapp — фоновый запуск (для start-mila-automation.cmd).
set "MILA_ROOT=E:\MILA GOLD"
cd /d "%MILA_ROOT%\mila-office"
set PYTHONIOENCODING=utf-8
if not exist "%MILA_ROOT%\logs" mkdir "%MILA_ROOT%\logs"
python webapp.py >> "%MILA_ROOT%\logs\webapp.out.log" 2>> "%MILA_ROOT%\logs\webapp.err.log"
