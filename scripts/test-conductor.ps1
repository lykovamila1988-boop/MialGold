# Test script: Queue a task and run conductor
# Usage: .\test-conductor.ps1

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "MILA CONDUCTOR - End-to-End Test" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$OfficeDir = "E:\MILA GOLD\mila-office"
$LogFile = "E:\MILA GOLD\logs\conductor.log"
$QueuesDir = "E:\MILA GOLD\logs"

# Change to office directory
Set-Location $OfficeDir

# Step 1: Clear old logs
Write-Host "Step 1: Clearing old logs..." -ForegroundColor Yellow
if (Test-Path $LogFile) {
    Clear-Content $LogFile
    Write-Host "[OK] Logs cleared`n" -ForegroundColor Green
}

# Step 2: Queue a test task
Write-Host "Step 2: Queueing test task (content_week)..." -ForegroundColor Yellow
try {
    $QueueResult = & python pipeline.py content_week 2>&1
    Write-Host $QueueResult

    if ($QueueResult -match '"ok": true') {
        Write-Host "[OK] Task queued successfully`n" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to queue task`n" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Exception during queue: $_`n" -ForegroundColor Red
    exit 1
}

# Step 3: Run conductor for 60 seconds
Write-Host "Step 3: Running conductor for 60 seconds..." -ForegroundColor Yellow
Write-Host "(Conductor will pick up the queued task and execute it)`n" -ForegroundColor Yellow

$ConductorPid = $null
try {
    # Start conductor in background
    $ConductorProcess = Start-Process python -ArgumentList "conductor.py" -PassThru -NoNewWindow -RedirectStandardOutput "$QueuesDir\conductor_test.out" -RedirectStandardError "$QueuesDir\conductor_test.err"
    $ConductorPid = $ConductorProcess.Id

    Write-Host "Conductor started (PID: $ConductorPid)`n" -ForegroundColor Green

    # Wait 60 seconds
    for ($i = 60; $i -gt 0; $i--) {
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 1

        # Show new log lines every 10 seconds
        if ($i % 10 -eq 0) {
            Write-Host " [$i seconds remaining]" -ForegroundColor Gray
        }
    }

    Write-Host "`n[OK] Test period complete`n" -ForegroundColor Green

} finally {
    # Kill conductor
    if ($ConductorPid) {
        Write-Host "Stopping conductor..." -ForegroundColor Yellow
        Stop-Process -Id $ConductorPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        Write-Host "[OK] Conductor stopped`n" -ForegroundColor Green
    }
}

# Step 4: Show conductor logs
Write-Host "Step 4: Conductor Logs" -ForegroundColor Yellow
Write-Host "=" * 60
if (Test-Path $LogFile) {
    $LogContent = Get-Content $LogFile -Tail 30
    Write-Host $LogContent
} else {
    Write-Host "[No log file found]" -ForegroundColor Yellow
}
Write-Host "=" * 60
Write-Host ""

# Step 5: Check queue status
Write-Host "Step 5: Queue Status" -ForegroundColor Yellow
try {
    $QueueStatus = & python pipeline.py queue 2>&1
    Write-Host $QueueStatus
} catch {
    Write-Host "[Error checking queue]" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "What happened:" -ForegroundColor Cyan
Write-Host "  1. Queued content_week task" -ForegroundColor Gray
Write-Host "  2. Conductor polled every 5 seconds" -ForegroundColor Gray
Write-Host "  3. Picked up task and ran via pipeline.py worker" -ForegroundColor Gray
Write-Host "  4. Agents executed (Olya -> Marina -> Victoria -> Vasya)" -ForegroundColor Gray
Write-Host "  5. Task completed and logged" -ForegroundColor Gray
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review logs above to verify execution" -ForegroundColor Gray
Write-Host "  2. If successful, set up Windows Task:" -ForegroundColor Gray
Write-Host "     .\setup-conductor-task.ps1" -ForegroundColor Gray
Write-Host "  3. System will auto-run conductor on startup" -ForegroundColor Gray
Write-Host ""
