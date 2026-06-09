# Real-World Chain Management Examples

Practical scenarios for orchestrating agent chains in Стас (Manager).

---

## Scenario 1: Monday Morning Standup

**Time**: Every Monday 11:00 AM  
**Chains**: monday_brief → content_week → weekly_report  
**Duration**: ~60 minutes total  
**Outcome**: Full operational update + content plan + financial health check

### n8n Workflow (Triggered at 11:00)
```json
{
  "name": "Monday Morning Standup",
  "trigger": "Cron: 0 11 * * 1",
  "steps": [
    {
      "type": "Execute Command",
      "command": "cd E:\\MILA GOLD\\mila-office && python manager.py run_chain monday_brief --wait"
    },
    {
      "type": "Execute Command",
      "command": "cd E:\\MILA GOLD\\mila-office && python manager.py run_chain content_week --wait"
    },
    {
      "type": "Execute Command",
      "command": "cd E:\\MILA GOLD\\mila-office && python manager.py run_chain weekly_report --wait"
    },
    {
      "type": "Telegram",
      "message": "📊 Понедельник: метрики + контент + финансы готовы. Проверь отчёты в reports/"
    }
  ]
}
```

### Manual Equivalent (Chat with Стас)
```
User: /понедельник-макрос

Стас:
1. Запускаю monday_brief (Стас собирает метрики)...
2. Ждём завершения контент_недели (Оля → Марина → Виктория → Вася)...
3. Параллельно weekly_report (Дима финансовый обзор)...

Результат: 3 отчёта готовы в reports/
```

---

## Scenario 2: Urgent Client Onboarding

**Time**: When new lead arrives  
**Chains**: new_client (alina → lera)  
**Duration**: ~15 minutes  
**Outcome**: Client profile + personalized follow-up ready

### Trigger 1: From Telegram (Алина sees intake form)
```
# Алина читает форму из Telegram → вызывает:

context = {
  "client_name": "Мария",
  "age": "32",
  "problem": "Созависимость, трудность с границами",
  "intake_form": "... полный текст...",
  "channel": "telegram",
  "received_at": "2024-06-08T15:30:00"
}

python manager.py run_chain new_client --context-json '{...}' --wait
```

### Chain Execution
```
STEP 1: Алина analyzes
├─ Reads intake → identifies pattern (Pleaser)
├─ Flags red flags (perfectionism, self-blame)
└─ Recommends: 8-session package + trauma-informed approach

STEP 2: Лера follows up
├─ Reads Алина's recommendation
├─ Writes personalized message (warm, no pressure)
├─ Proposes: bесплатная диагностика → 8-session package
└─ Outputs: draft DM ready for Людмила's review

Output: MILA-BUSINESS/03-clients/new_client_maria_20240608.md
```

### Result
```markdown
# Новая клиентка: Мария

## Профиль (Алина)
- Pattern: Угодница (Pleaser) со слабыми границами
- Red flags: Перфекционизм, self-blame, anxiety
- Recommendation: 8 sessions, trauma-informed, focus on boundaries

## Follow-up (Лера)
Привет, Мария! 

Я посмотрела твою историю и вижу, что ты давно ищешь способ 
восстановить уважение к себе и создать здоровые границы...

Предлагаю начать с бесплатной консультации (20 минут), 
где мы поймём твой точный путь выздоровления...

[CALL TO ACTION]
```

---

## Scenario 3: Content Week Planning (Parallel Content + Other Work)

**Time**: Monday 11:30 AM (after monday_brief)  
**Chains**: content_week (Olya → Marina → Victoria → Vasya)  
**Duration**: ~35 minutes  
**Other work**: Meanwhile, Алина onboarding, Дима financials, Тёма telegram  
**Outcome**: 7 posts + 2 reels scheduled for week

### Parallel Orchestration
```python
# Стас starts content_week, but OTHER chains run in parallel
manage_parallel(
  chain_names="content_week,new_client,weekly_report",
  mode="parallel",
  max_parallel=2  # content_week + new_client run together
)

# Timeline:
# 11:30 - content_week starts (step 1: Olya finds trends)
#       - new_client starts (step 1: Alina analyzes intake)
# 11:35 - Olya done, Marina takes over
# 11:40 - Alina done, Lera takes over
# 11:45 - Marina done, Victoria takes over
# 11:50 - Lera done, follow-up ready
# 12:00 - Victoria done, Vasya schedules
# 12:05 - Vasya done, all content scheduled
# 12:10 - new_client done, follow-up sent
```

### No Conflict Because:
- ✅ Different agents (Olya/Marina/Victoria/Vasya vs Alina/Lera)
- ✅ Different files (content/ vs clients/)
- ✅ Different APIs (Instagram vs Gmail)
- ✅ No shared database writes

---

## Scenario 4: Detecting & Resolving Write Conflict

**Problem**: Two chains writing to same file  
**Example**: Victoria (content_week) and Marina (another_chain) both editing `content-plan.md`

### Detection
```python
# Manager notices:
# ERROR: Victoria trying to write content-plan.md
# ERROR: Marina also trying to write content-plan.md

# Calls:
resolve_chain_conflict(
  conflict_type="write",
  agent1="victoria",
  agent2="marina",
  resource="MILA-BUSINESS/02-content/content-plan.md"
)
```

### Resolution Recommendation
```json
{
  "type": "write",
  "resolution": "Lock для victoria, очередь: marina",
  "recommendation": "Запустить victoria первым (wait=True, timeout=600), затем marina. 
                     Или использовать atomic writes через lock-файл в reports/locks/content-plan.lock."
}
```

### Applied Fix (Sequential)
```python
# Manager re-runs chains sequentially
manage_parallel(
  chain_names="content_week,another_chain",
  mode="sequential"  # one after another, no overlap
)

# Timeline:
# 11:30 - content_week starts (Victoria gets lock on content-plan.md)
# 11:35 - content_week completes (Victoria releases lock)
# 11:36 - another_chain starts (Marina gets lock)
# 11:41 - another_chain completes
```

---

## Scenario 5: Read-Race Condition with Snapshot

**Problem**: Olya reading reports while Dima modifies them  
**Symptom**: Olya sees incomplete/stale data

### Detection & Fix
```python
resolve_chain_conflict(
  conflict_type="read",
  agent1="olya",
  agent2="dima",
  resource="reports/posts_*.json"
)
```

### Recommendation
```
Take snapshot of reports/posts_*.json BEFORE Dima modifies.
Olya reads snapshot, not live data.
Dima modifies original.
Next iteration: use updated snapshot.
```

### Implementation
```python
# Before running weekly_report (Dima step)
def weekly_report_chain():
    # Step 1: Snapshot current posts_*.json
    snapshot_file = create_snapshot("reports/posts_*.json")
    
    # Step 2: Run Dima (modifies live files)
    run_agent("dima", context={"snapshot": snapshot_file})
    
    # Step 3: Olya reads snapshot (not live)
    # run_agent("olya", context={"data_file": snapshot_file})
    
    # Step 4: Later iterations use updated snapshot
```

---

## Scenario 6: Resource Contention (API Rate Limits)

**Problem**: Both Dima and Lera querying Gumroad API simultaneously  
**Symptom**: 429 Too Many Requests

### Detection
```python
resolve_chain_conflict(
  conflict_type="resource",
  agent1="dima",
  agent2="lera",
  resource="GUMROAD_API"
)
```

### Recommendation
```
Add rate limiting:
- Dima: sleep(5) between API calls
- Lera: sleep(3) between calls
- Or: sequential execution (Dima → Lera)
- Or: global semaphore in memory.py (max 1 concurrent request to GUMROAD)
```

### Implementation Option 1: Sequential
```python
# Run weekly_report (includes Dima) FIRST
run_chain("weekly_report", wait=True)

# Run new_client (includes Lera) AFTER
run_chain("new_client", wait=True)
```

### Implementation Option 2: Global Semaphore
```python
# In memory.py:
import threading

GUMROAD_LOCK = threading.Semaphore(1)

def gumroad_api_call(endpoint, **kwargs):
    with GUMROAD_LOCK:
        # Only one agent can call Gumroad at a time
        return requests.get(f"https://api.gumroad.com/{endpoint}", **kwargs)

# In dima.py and lera.py:
from memory import gumroad_api_call
result = gumroad_api_call("products")
```

---

## Scenario 7: Error Investigation Chain

**Time**: When error alert fires  
**Chains**: error_investigation (Manager → Producer)  
**Duration**: ~10-20 minutes  
**Outcome**: Root cause identified + fix deployed

### Triggered by Error Monitor
```python
# error_monitor.py detects:
# [ERROR] OAuth token expired: scope insufficient

# Calls:
run_chain(
  "error_investigation",
  context_json={
    "error": "OAuth token expired",
    "scope": "instagram_business_account",
    "log": "... full traceback ...",
    "timestamp": "2024-06-08T16:45:00"
  },
  wait=True,
  timeout_seconds=900  # 15 min for troubleshooting
)
```

### Chain Execution
```
STEP 1: Стас (Manager) analyzes
├─ Reads error log
├─ Checks token status (tools/.env)
├─ Identifies: IG_ACCESS_TOKEN expired
└─ Message to Producer: "Token needs refresh, docs: ..."

STEP 2: Кирилл (Producer) fixes
├─ Regenerates token via Instagram Graph
├─ Updates tools/.env
├─ Tests with check_setup.py
└─ Reports: "Token refreshed, status: OK"

Output: error_investigation_20240608_164500.json
```

---

## Scenario 8: Custom Chain (User-Defined)

**Use Case**: Weekly competitor analysis (not in builtin chains)  
**Steps**: Olya (trends) → Кирилл (producer) → Марина (strategy)  
**Duration**: ~25 minutes

### Define Custom Chain
```python
# In manager.py, extend _BUILTIN_CHAINS:

_CUSTOM_CHAINS = {
    "competitor_analysis": {
        "steps": ["olya", "producer", "marina"],
        "description": "Еженедельный анализ конкурентов: тренды → анализ → стратегия",
        "requires_context": False,
    }
}
```

### Register & Run
```bash
# Option 1: Via chat
/цепи  # shows competitor_analysis

# Option 2: Direct call
python manager.py run_chain competitor_analysis --wait
```

### Result
```
STEP 1: Оля
├─ Scans top 10 competitors for this week's content
├─ Identifies: "Vulnerability sharing is viral (700+ likes avg)"
└─ Message: "Trend: авторское раскрытие, 3 competitors leading"

STEP 2: Кирилл
├─ Deep-dives: engagement rate, audience demographics
├─ Competitors' story strategies
└─ Message: "Competitors using 3x more stories, avg 45% completion"

STEP 3: Марина
├─ Proposes: increase story posting (2x/day) + vulnerability angles
├─ Expected impact: +20% reach based on historical data
└─ Recommends: A/B test for 2 weeks

Output: reports/competitor_analysis_20240608.json
```

---

## Scenario 9: Monitoring Dashboard

**Real-time view** of all running chains in webapp.py:

```
═══════════════════════════════════════════════════════════════
                    CHAIN STATUS DASHBOARD
═══════════════════════════════════════════════════════════════

ACTIVE (1):
  ✓ content_week_20240608_143022  [Step 2/4: marina]
    └─ Started: 14:30 | Elapsed: 3m 22s | ETA: 30m

COMPLETED (8):
  ✓ new_client_20240608_145500 (12m)
  ✓ monday_brief_20240608_110000 (8m)
  ✓ weekly_report_20240608_110500 (22m)
  ... 5 more

FAILED (1):
  ✗ competitor_analysis_20240607_230000
    └─ Error: Olya timeout (Instagram rate limit)
    └─ Retry: /retry competitor_analysis --timeout 900

═══════════════════════════════════════════════════════════════

RECENT CONFLICTS RESOLVED:
  • write: victoria + marina → sequential execution
  • read: olya + dima → snapshot strategy
  • resource: dima + lera → Gumroad semaphore

═══════════════════════════════════════════════════════════════
```

---

## Scenario 10: Recovery from Chain Failure

**Problem**: content_week failed on step 3 (Victoria timeout)  
**Solution**: Resume from checkpoint

### Step 1: Check Status
```python
get_chain_status("content_week_20240608_143022")
# → status="failed", error="Victoria timeout at 14:45"
```

### Step 2: Analyze
```python
# Is Victoria's input (Marina's ideas) still valid?
# Did Marina complete successfully?
# 
# Answer: Yes, Marina finished at 14:40, ideas are ready.
# Victoria timed out trying to edit (API call failed).
```

### Step 3: Resume
```python
# Option 1: Re-run entire chain with longer timeout
run_chain(
  "content_week",
  wait=True,
  timeout_seconds=900  # 15 min instead of 5
)

# Option 2: Manual retry just Victoria + Vasya
# (requires direct agent invocation, handled by pipeline.py)
```

### Result
```
Pipeline detects checkpoint:
  ✓ Olya: DONE (trends found)
  ✓ Marina: DONE (ideas generated)
  ⏸ Victoria: FAILED (timeout)
  ⏸ Vasya: NOT RUN

Resume from checkpoint → Victoria retries with prev step output
  ✓ Victoria: DONE (rerun)
  ✓ Vasya: DONE (schedule content)

Full chain now complete.
```

---

## Summary: When to Use Each Pattern

| Scenario | Pattern | Why |
|----------|---------|-----|
| Monday standup | Sequential (monday_brief → content_week → weekly_report) | Each depends on previous insights |
| New client arrives | Sync run_chain (alina → lera) | Fast turnaround, watch live |
| Multiple independent tasks | Parallel (content_week + new_client) | No conflicts, faster overall |
| Write to same file | Sequential or lock | Prevent data corruption |
| Read stale data | Snapshot | Olya gets consistent data while Dima modifies |
| API rate limits | Semaphore or sequential | Respect service quotas |
| Urgent error | error_investigation with short timeout | Fast diagnosis |
| Custom workflows | Extend _BUILTIN_CHAINS | Reuse orchestration framework |

All examples use Стас (Manager) as the orchestration layer. Each pattern is idempotent and recoverable.
