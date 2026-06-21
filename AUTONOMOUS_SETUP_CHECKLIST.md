# 🤖 MILA Gold Autonomous Setup — WHAT'S MISSING

## Current Status: ⚠️ INCOMPLETE

**Code exists:** `autonomous_daily_loop.py`, `scheduler_autonomous.py` ✓  
**Running:** NO ✗  
**Persistent:** NO ✗  
**Monitored:** NO ✗

---

## The Gap

The **autonomous loop is DESIGNED but not DEPLOYED**. It's like having a self-driving car with the engine off.

### What Exists (but isn't running)
```python
scheduler_autonomous.py                    # Scheduler code (not active)
autonomous_daily_loop.py                   # Daily loop logic (dormant)
autonomous_deep_content_loop.py            # Deep content variant (dormant)
```

### What's Missing (for true autonomy)
1. **No background process** running the scheduler
2. **No service** to keep it alive
3. **No system restart recovery** (if machine reboots, everything stops)
4. **No monitoring** to alert if it breaks
5. **No deployment procedure** documented

---

## 📋 Autonomous Setup Checklist

### PHASE 1: Prerequisites (Verify)
- [ ] `.env` configured with `ANTHROPIC_KEY` ✓ (found: *****)
- [ ] `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHANNEL_ID` configured ✓ (found)
- [ ] Claude model accessible: `MILA_MODEL` (defaults to claude-opus-4-6)
- [ ] All agents installed: `pip install -r requirements.txt` in `mila-office/`
- [ ] Test one agent manually: `python mila-office/victoria.py` (verify it runs)

### PHASE 2: Manual Test (One-Off)
```bash
# Run the loop ONCE to verify everything works
cd E:\MILA GOLD\mila-office
python scheduler_autonomous.py --mode once

# This should:
# 1. ✓ Olya: analyze metrics
# 2. ✓ Rita: choose topics
# 3. ✓ Marina: create 3 posts
# 4. ✓ Victoria: review posts
# 5. ✓ Tyoma: publish to Telegram
```

**Expected output:** 3 posts created + published to Telegram, logs written to `logs/`

### PHASE 3: Windows Task Scheduler (Persistent)
Create a scheduled task to run the loop every day:

**Option A: PowerShell (Recommended)**
```powershell
# Run as Admin
$taskName = "MILA-Autonomous-Daily-Loop"
$taskPath = "\MILA\"
$scriptPath = "E:\MILA GOLD\mila-office\scheduler_autonomous.py"
$pythonExe = "python"  # or full path: C:\Python310\python.exe

$trigger = New-ScheduledTaskTrigger -Daily -At 00:30
$action = New-ScheduledTaskAction `
  -Execute $pythonExe `
  -Argument $scriptPath `
  -WorkingDirectory "E:\MILA GOLD"

$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances Parallel `
  -StartWhenAvailable `
  -DontStopOnIdleEnd

Register-ScheduledTask `
  -TaskName $taskName `
  -TaskPath $taskPath `
  -Trigger $trigger `
  -Action $action `
  -Settings $settings `
  -RunLevel Highest `
  -Force

Write-Host "✓ Task '$taskName' created"
```

**Option B: Batch Script (Simple)**
Create `E:\MILA GOLD\scripts\start-autonomous.bat`:
```batch
@echo off
cd /d "E:\MILA GOLD"
python mila-office\scheduler_autonomous.py --mode schedule
```

Then use Windows Task Scheduler GUI to run this batch file daily at 00:30.

### PHASE 4: Health Monitoring (Optional but Recommended)
Create `mila-office/supervisor.py`:
```python
"""Monitors the autonomous loop and restarts if needed"""
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime

SCHEDULER = Path(__file__).parent / "scheduler_autonomous.py"
LOG_FILE = Path(__file__).parent.parent / "logs" / "supervisor.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run_scheduler():
    """Run the scheduler in a subprocess and monitor it"""
    log("Starting autonomous loop scheduler...")
    
    proc = subprocess.Popen(
        [sys.executable, str(SCHEDULER), "--mode", "schedule"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    log(f"Scheduler PID: {proc.pid}")
    
    # Keep monitoring
    while True:
        returncode = proc.poll()
        if returncode is not None:
            # Process died
            log(f"❌ Scheduler died (exit code {returncode}). Restarting in 10 seconds...")
            time.sleep(10)
            proc = subprocess.Popen(
                [sys.executable, str(SCHEDULER), "--mode", "schedule"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    run_scheduler()
```

Then schedule THIS instead of the scheduler directly.

### PHASE 5: Error Recovery (Recommended)

Update `scheduler_autonomous.py` to add retry logic:

```python
def run_daily_loop_with_retry(max_retries=3):
    """Run with exponential backoff on failure"""
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                [sys.executable, str(AUTONOMOUS_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                return True
            
            # Non-zero exit, retry
            wait = 2 ** attempt  # 2, 4, 8 seconds
            print(f"[Attempt {attempt}] Failed, retrying in {wait}s...")
            time.sleep(wait)
            
        except Exception as e:
            print(f"[Attempt {attempt}] Exception: {e}")
            if attempt < max_retries:
                wait = 2 ** attempt
                time.sleep(wait)
    
    return False
```

### PHASE 6: Logging & Alerts (Optional)

Add to `autonomous_daily_loop.py`:

```python
import logging

LOG_FILE = MILA_FOLDER / "logs" / "autonomous.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("autonomous")
logger.setLevel(logging.INFO)

handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

# Then replace print() with logger.info()
logger.info("Starting autonomous loop")
logger.info("Step 1: Olya analyzing metrics...")
```

### PHASE 7: Test End-to-End

1. **Kill all running processes:**
   ```powershell
   Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
   ```

2. **Verify task is scheduled:**
   ```powershell
   Get-ScheduledTask -TaskName "MILA-Autonomous-Daily-Loop"
   ```

3. **Wait for next scheduled run (or trigger manually):**
   ```powershell
   Start-ScheduledTask -TaskName "MILA-Autonomous-Daily-Loop"
   ```

4. **Check logs:**
   ```powershell
   Get-Content "E:\MILA GOLD\logs\autonomous.log" -Tail 50
   ```

5. **Verify posts published:**
   - Check Telegram channel
   - Check `logs/autonomous.log`
   - Check `logs/telegram.log`

---

## 🎯 Minimal Viable Autonomous (MVA)

**If you just want it running TODAY:**

```bash
# Terminal 1: Start scheduler (keeps running)
cd E:\MILA GOLD\mila-office
python scheduler_autonomous.py --mode schedule
```

This will:
- Start at 00:30 every day
- Run the full pipeline (Olya → Rita → Marina → Victoria → Tyoma)
- Publish 3 posts to Telegram daily
- Log everything to `logs/`

**BUT:** Dies if the terminal closes, terminal window, or machine reboots.

---

## 🚀 Production Autonomous (Recommended)

1. Use **Windows Task Scheduler** (PHASE 3) for reliability
2. Add **supervisor.py** (PHASE 4) for auto-restart
3. Add **logging** (PHASE 6) for visibility
4. Run **weekly health checks** to verify posts are actually publishing

---

## 🔍 What to Check Daily

```bash
# Telegram posts published?
Get-Content "E:\MILA GOLD\logs\telegram.log" -Tail 20

# Autonomous loop ran?
Get-Content "E:\MILA GOLD\logs\autonomous.log" -Tail 30

# Any errors?
Get-Content "E:\MILA GOLD\logs\error_monitor.log" -Tail 20
```

---

## Why It's Not Auto by Default

1. **API calls cost money** — no built-in rate limiting
2. **Telegram integration** — needs verified bot + channel
3. **Agent availability** — Claude API outages would cause posts to fail
4. **Testing maturity** — code is ~2 months old (commit 73d6cef), likely has edge cases
5. **No production monitoring** — logs exist but no alerting

---

## Next Steps

Pick ONE:
- **Option A (Easy):** Manual test: `python scheduler_autonomous.py --mode once`
- **Option B (Medium):** Windows Task Scheduler setup (PHASE 3)
- **Option C (Best):** Full deployment: Task Scheduler + Supervisor + Logging
