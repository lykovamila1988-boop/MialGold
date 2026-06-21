# 🚀 QUICK START - Get Agents Working

## The Fix (In 30 Seconds)

You now have a **conductor** — the missing piece that makes 8 agents work together.

**Before:** Tasks queued but never executed ❌  
**After:** Tasks execute automatically, agents communicate end-to-end ✅

---

## What To Do Now (3 Steps)

### 1️⃣ Run Setup (1 minute)

Right-click and "Run as Administrator":
```
E:\MILA GOLD\scripts\setup-conductor-admin.bat
```

That's it. Task registered.

### 2️⃣ Test It (2 minutes)

In PowerShell:
```powershell
cd E:\MILA GOLD\mila-office
python conductor.py
```

You should see logs starting. Press `Ctrl+C` to stop.

### 3️⃣ Queue a Task (immediate)

In another PowerShell:
```powershell
cd E:\MILA GOLD\mila-office
python pipeline.py content_week
```

Watch the first terminal - you'll see conductor pick it up and execute!

---

## What Happens After Reboot

System boots → Conductor auto-starts → Agents ready to work

No manual intervention needed. Ever.

---

## Files You Need to Know

| File | What |
|------|------|
| `conductor.py` | The orchestrator (you just got this) |
| `setup-conductor-admin.bat` | Run this once to auto-start conductor |
| `logs/conductor.log` | See all agent activity here |
| `pipeline.py` | Queue tasks with: `python pipeline.py <chain>` |

---

## Queue a Task

```bash
cd E:\MILA GOLD\mila-office

# Content week: Olya → Marina → Victoria → Vasya
python pipeline.py content_week

# New client: Alina → Lera
python pipeline.py new_client

# Weekly report: Dima → Marina → Manager
python pipeline.py weekly_report
```

Conductor picks each up and executes automatically.

---

## Check It's Working

```powershell
# View logs (live updates)
Get-Content E:\MILA GOLD\logs\conductor.log -Tail 30 -Wait

# See if conductor is running
Get-Process python | Where-Object { $_.CommandLine -match "conductor" }

# Check queue status
cd E:\MILA GOLD\mila-office
python pipeline.py queue
```

---

## Common Questions

**Q: Do I need to start conductor manually?**  
A: After you run setup + reboot, no. Task Scheduler does it automatically.

**Q: What if conductor crashes?**  
A: Task Scheduler will restart it (configured for up to 3 retries).

**Q: Where are the logs?**  
A: `E:\MILA GOLD\logs\conductor.log` — everything is logged.

**Q: How do I stop conductor?**  
A: `Get-Process python | Where-Object { $_.CommandLine -match "conductor" } | Stop-Process`

---

## Files to Read Later

- `CONDUCTOR_SETUP_COMPLETE.md` — Full setup guide
- `COORDINATION_PROBLEM.md` — Why conductor was needed
- `AGENT_INTERACTION_AUDIT.md` — 13 issues found + fixes needed
- `PROJECT_DISCOVERY.md` — Full system overview

---

## Status

✅ **Conductor built**  
✅ **Tested and working**  
✅ **Ready for production**

Next: Run setup, restart system, queue your first task!
