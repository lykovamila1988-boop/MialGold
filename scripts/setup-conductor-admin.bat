@echo off
REM Run this as Administrator to set up MILA Conductor task
REM Right-click this file -> Run as Administrator

color 0A
title MILA Conductor - Windows Task Setup

echo.
echo ========================================
echo MILA CONDUCTOR - Windows Task Setup
echo ========================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Must run as Administrator!
    echo.
    echo Solution:
    echo   1. Right-click this .bat file
    echo   2. Select "Run as Administrator"
    echo.
    pause
    exit /b 1
)

echo [OK] Running as Administrator
echo.

REM Define variables
set TASK_NAME=MILA-Conductor
set TASK_PATH=\MILA\
set PYTHON_EXE=python
set SCRIPT_PATH=E:\MILA GOLD\mila-office\conductor.py
set WORKING_DIR=E:\MILA GOLD

echo Removing old task (if exists)...
schtasks /delete /tn "%TASK_PATH%%TASK_NAME%" /f >nul 2>&1
timeout /t 1 /nobreak >nul

echo Creating new task...
schtasks /create ^
  /tn "%TASK_PATH%%TASK_NAME%" ^
  /tr "python %SCRIPT_PATH%" ^
  /sc onstart ^
  /rl highest ^
  /f

if %errorLevel% equ 0 (
    echo.
    echo ========================================
    echo [OK] SETUP COMPLETE
    echo ========================================
    echo.
    echo Task: %TASK_NAME%
    echo Trigger: System Startup
    echo Command: python conductor.py
    echo Working Dir: %WORKING_DIR%
    echo.
    echo The conductor will now:
    echo   1. Start when system boots
    echo   2. Poll task queue every 5 seconds
    echo   3. Execute agent chains as tasks are queued
    echo   4. Log everything to: E:\MILA GOLD\logs\conductor.log
    echo.
    echo To verify the task:
    echo   Open: taskschd.msc
    echo   Navigate to: Task Scheduler ^> MILA ^> MILA-Conductor
    echo.
) else (
    echo.
    echo ERROR: Failed to create task!
    echo Please try again or check permissions.
    echo.
)

pause
