# 🚀 SETUP INSTRUCTIONS - Complete Guide

## You Are Here

✅ Conductor built and tested  
⏳ Windows Task setup (IN PROGRESS)  
⬜ System running autonomously

---

## Complete Setup in 3 Minutes

### Step 1: Run Setup (1 minute)

**Easiest Option - Batch File:**

1. Open File Explorer
2. Navigate to: `E:\MILA GOLD\scripts\`
3. Find: `setup-conductor-admin.bat`
4. **Right-click** on it
5. Select: **"Run as administrator"**
6. Wait for completion (should say "SETUP COMPLETE")

---

### Step 2: Restart System (1 minute)

Option A: Restart now (quick)
```powershell
Restart-Computer
```

Option B: Manual (take your time)
- Windows key → Power icon → Restart

---

### Step 3: Verify It Works (1 minute)

After restart, open PowerShell and run:

```powershell
# Check if conductor is running
Get-Process python | Where-Object { $_.CommandLine -match "conductor" }
```

If you see output with `conductor.py`, you're done! ✅

---

## Alternative Setup Options

If batch file doesn't work, try these:

### Option A: PowerShell as Administrator

1. Right-click PowerShell → "Run as administrator"
2. Run these commands:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
cd E:\MILA GOLD\scripts
.\setup-conductor-task.ps1
```

---

### Option B: Manual Task Scheduler

1. Press `Win+R` (Windows key + R)
2. Type: `taskschd.msc`
3. Press Enter

Then in Task Scheduler:

1. Right-click "Task Scheduler Library"
2. Click "New Folder..."
3. Name it: `MILA`
4. Right-click "MILA" folder
5. Click "Create Basic Task..."

Fill in:

- **Name:** `MILA-Conductor`
- **Description:** Auto-runs conductor.py
- **When you click Next:** Select "At startup"
- **Next:** Select "Start a program"
- **Program:** `python`
- **Arguments:** `E:\MILA GOLD\mila-office\conductor.py`
- **Start in:** `E:\MILA GOLD`
- **Click:** "Finish"

Then:

1. Right-click the task
2. Select "Properties"
3. Check: "Run with highest privileges"
4. Click "OK"

---

## Verify Setup Worked

After you've completed setup and restarted:

### Check 1: Task Exists

```powershell
Get-ScheduledTask -TaskName "MILA-Conductor" -TaskPath "\MILA\"
```

Should show task details. ✓

### Check 2: Conductor Running

```powershell
Get-Process python | Where-Object { $_.CommandLine -match "conductor" }
```

Should show python process. ✓

### Check 3: Try a Task

Open PowerShell:

```powershell
cd E:\MILA GOLD\mila-office
python pipeline.py content_week
```

Then check logs:

```powershell
Get-Content E:\MILA GOLD\logs\conductor.log -Tail 20
```

Should show task being picked up and executed. ✓

---

## Troubleshooting

### "Run as administrator" option doesn't appear

This sometimes happens on older Windows. Use Option A or B instead.

### Python not found error

1. Open PowerShell
2. Run: `python --version`
3. If it fails, Python might not be in PATH
4. Install Python or add it to PATH

### Task shows but conductor doesn't start

1. Check logs:
```powershell
Get-Content E:\MILA GOLD\logs\conductor.log
```

2. Look for error messages

3. Try starting manually:
```powershell
Start-ScheduledTask -TaskName "MILA-Conductor" -TaskPath "\MILA\"
```

### Conductor runs but doesn't execute tasks

1. Verify queue is working:
```powershell
cd E:\MILA GOLD\mila-office
python pipeline.py queue
```

2. Check for errors in conductor.log

---

## What Happens After Setup

**On Next Reboot:**
```
Windows starts
  ↓
Task Scheduler sees: MILA-Conductor
  ↓
Launches: python conductor.py
  ↓
Conductor starts polling
  ↓
When you queue tasks → agents execute automatically
```

**Forever After:**
- Conductor runs in background
- Tasks executed as queued
- Logs everything
- Never stops (until you disable task)

---

## Common Commands

```powershell
# View conductor logs (live)
Get-Content E:\MILA GOLD\logs\conductor.log -Tail 50 -Wait

# Check if running
Get-Process python | Where-Object { $_.CommandLine -match "conductor" }

# Queue a task
cd E:\MILA GOLD\mila-office && python pipeline.py content_week

# Stop conductor
Get-Process python | Where-Object { $_.CommandLine -match "conductor" } | Stop-Process

# Start conductor task
Start-ScheduledTask -TaskName "MILA-Conductor" -TaskPath "\MILA\"

# Disable task (stops auto-start)
Disable-ScheduledTask -TaskName "MILA-Conductor" -TaskPath "\MILA\"

# Delete task
Unregister-ScheduledTask -TaskName "MILA-Conductor" -TaskPath "\MILA\" -Confirm:$false
```

---

## Files

- `setup-conductor-admin.bat` ← Run this (easiest)
- `setup-conductor-task.ps1` ← Or this
- `conductor.py` ← What gets executed
- `logs/conductor.log` ← Activity log

---

## Next: Full Documentation

After setup works, read:
- `QUICK_START.md` — Quick reference
- `CONDUCTOR_SETUP_COMPLETE.md` — Full details
- `COORDINATION_PROBLEM.md` — Why this was needed

---

**That's it!** Three minutes and your agents are coordinated. 🎉
