@echo off
rem MILA Telegram poller — поток «ХОЧУ» (getUpdates). Долгоживущий процесс.
set "MILA_ROOT=E:\MILA GOLD"
cd /d "%MILA_ROOT%\tools"
set PYTHONIOENCODING=utf-8
if not exist "%MILA_ROOT%\logs" mkdir "%MILA_ROOT%\logs"
python telegram_poller.py >> "%MILA_ROOT%\logs\telegram-poller.out.log" 2>> "%MILA_ROOT%\logs\telegram-poller.err.log"
