# PowerShell script to set up MILA Conductor as Windows Task
# RUN AS ADMIN: Right-click PowerShell -> Run as Administrator
# Then: Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
# Then: .\setup-conductor-task.ps1

param(
    [switch]$Remove = $false
)

$ErrorActionPreference = "Stop"

$TaskName = "MILA-Conductor"
$TaskPath = "\MILA\"
$PythonExe = "python"  # Assumes python in PATH; can also use full path like "C:\Python310\python.exe"
$ScriptPath = "E:\MILA GOLD\mila-office\conductor.py"
$WorkingDir = "E:\MILA GOLD"
$LogFile = "E:\MILA GOLD\logs\conductor.log"

Write-Host "╔════════════════════════════════════════════════════════════════╗"
Write-Host "║       MILA CONDUCTOR - Windows Task Scheduler Setup            ║"
Write-Host "╚════════════════════════════════════════════════════════════════╝"
Write-Host ""

# Check if running as admin
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "❌ ERROR: Must run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Running as Administrator" -ForegroundColor Green
Write-Host ""

# Check if python exists
try {
    $PythonVersion = & python --version 2>&1
    Write-Host "✓ Python found: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found in PATH" -ForegroundColor Red
    Write-Host "Either install Python or update PATH, then try again" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

if ($Remove) {
    Write-Host "Removing existing task '$TaskName'..." -ForegroundColor Yellow
    try {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "✓ Task removed" -ForegroundColor Green
    } catch {
        Write-Host "⚠ Task didn't exist or couldn't be removed" -ForegroundColor Yellow
    }
    exit 0
}

# Check if files exist
Write-Host "Checking files..."
if (-not (Test-Path $ScriptPath)) {
    Write-Host "❌ conductor.py not found at $ScriptPath" -ForegroundColor Red
    exit 1
}
Write-Host "✓ conductor.py exists" -ForegroundColor Green

if (-not (Test-Path $WorkingDir)) {
    Write-Host "❌ Working directory not found at $WorkingDir" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Working directory exists" -ForegroundColor Green

Write-Host ""

# Remove existing task if it exists
Write-Host "Removing any existing task '$TaskName'..." -ForegroundColor Yellow
try {
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Write-Host "✓ Old task removed" -ForegroundColor Green
} catch {
    Write-Host "⚠ (No existing task to remove)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Creating new task..."

# Create trigger (on system startup)
$Trigger = New-ScheduledTaskTrigger -AtStartup
Write-Host "✓ Trigger created: At System Startup" -ForegroundColor Green

# Create action (run conductor.py)
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $ScriptPath `
    -WorkingDirectory $WorkingDir
Write-Host "✓ Action created: python conductor.py" -ForegroundColor Green

# Create settings (restart on failure, run with high priority)
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances Parallel `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RunOnlyIfNetworkAvailable:$false `
    -Priority 7
Write-Host "✓ Settings created: Auto-restart on failure, high priority" -ForegroundColor Green

# Register the task
Write-Host ""
Write-Host "Registering task with Task Scheduler..."

try {
    # Ensure task path exists
    $TaskPathObj = Get-ScheduledTask | Where-Object { $_.TaskPath -eq $TaskPath } -ErrorAction SilentlyContinue
    if (-not $TaskPathObj) {
        # Task path may not exist, but Register-ScheduledTask creates it
    }

    $RegisteredTask = Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -RunLevel Highest `
        -Force

    Write-Host "✓ Task registered successfully" -ForegroundColor Green
    Write-Host ""

} catch {
    Write-Host "❌ Failed to register task: $_" -ForegroundColor Red
    exit 1
}

Write-Host "╔════════════════════════════════════════════════════════════════╗"
Write-Host "║                    ✓ SETUP COMPLETE                           ║"
Write-Host "╚════════════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Host "Task Details:" -ForegroundColor Cyan
Write-Host "  Name:          $TaskName"
Write-Host "  Path:          $TaskPath"
Write-Host "  Trigger:       System Startup"
Write-Host "  Command:       python conductor.py"
Write-Host "  Working Dir:   $WorkingDir"
Write-Host "  Log File:      $LogFile"
Write-Host ""
Write-Host "What happens next:" -ForegroundColor Cyan
Write-Host "  1. System starts → conductor task auto-runs"
Write-Host "  2. Conductor polls queue every 5 seconds"
Write-Host "  3. When task queued → conductor executes it"
Write-Host "  4. Agents run: Olya → Marina → Victoria → Vasya"
Write-Host "  5. Log at: $LogFile"
Write-Host ""
Write-Host "Test it now:" -ForegroundColor Yellow
Write-Host "  python $ScriptPath"
Write-Host "  # In another terminal:"
Write-Host "  python mila-office\pipeline.py content_week"
Write-Host "  # Watch conductor.log for execution"
Write-Host ""
Write-Host "View/manage task:" -ForegroundColor Yellow
Write-Host "  taskschd.msc"
Write-Host "  (look under Task Scheduler → MILA → MILA-Conductor)"
Write-Host ""
Write-Host "Remove task later:" -ForegroundColor Yellow
Write-Host "  .\setup-conductor-task.ps1 -Remove"
Write-Host ""
