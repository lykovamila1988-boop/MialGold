# Orchestration Context & Chain Management Guide

This guide explains how Стас (Manager agent) orchestrates and coordinates parallel agent chains in the MILA Office. Updated in `manager.py` with comprehensive chain management logic.

## Quick Start

### View All Chains
```bash
# Show all available chains and their status
/цепи

# Filter by status: running, idle
/цепи --status running
```

### Run a Single Chain
```bash
# Run synchronously (wait for result, max 5 min)
/запусти-цепь content_week --wait

# Run asynchronously (returns chain_id for monitoring)
/запусти-цепь new_client
```

### Monitor Active Chains
```bash
# See which chains are running, completed, or failed
/монитор

# Check specific chain status
/монитор chain_id_202406081234567
```

### Run Multiple Chains
```bash
# Sequential: one after another
/параллель new_client,content_week,weekly_report --mode sequential

# Parallel: up to 3 simultaneous (respects rate limits)
/параллель new_client,content_week --parallel 3
```

### Resolve Conflicts
```bash
# Detect and solve write-conflicts, race conditions, resource locks
/конфликты write victoria marina content-plan.md
/конфликты read olya marina reports/
```

---

## Built-in Chains

### 1. `new_client` — Client Onboarding
**Steps**: Alina → Lera  
**Duration**: ~10-15 minutes  
**Context Required**: Yes (intake form data)

**Flow**:
1. **Алина** (CRM) — analyzes intake form, identifies attachment pattern (Rescuer/Pleaser/Avoidant), flags risks
2. **Лера** (Sales) — writes warm personalized follow-up, recommends package

**Example**:
```json
{
  "client_name": "Мария",
  "intake_form": "... полная форма с ответами...",
  "channel": "instagram_dm"
}
```

```bash
python manager.py run_chain --chain-name new_client --context-json '{"client_name": "Мария", ...}'
```

---

### 2. `content_week` — Weekly Content Planning
**Steps**: Olya → Marina → Victoria → Vasya  
**Duration**: ~30-40 minutes  
**Context Required**: No

**Flow**:
1. **Оля** (Trends) — finds 3 viral themes in psychology/relationships niche this week
2. **Марина** (Marketing) — generates content ideas + hooks
3. **Виктория** (Editor) — edits for brand voice, refines captions
4. **Вася** (Scheduling) — schedules across all platforms + calendar

**Runs**: Every Monday, ~11:00 (via n8n cron)

```bash
python pipeline.py content_week
```

---

### 3. `monday_brief` — Weekly Report & Planning
**Steps**: Manager (Стас) → Marina  
**Duration**: ~15 minutes  
**Context Required**: No

**Flow**:
1. **Стас** — generates office metrics summary (measure_metrics), flags bottlenecks
2. **Марина** — creates action plan based on metrics

```bash
python pipeline.py monday_brief
```

---

### 4. `weekly_report` — Financial & Analytics
**Steps**: Dima (Finance) → Marina (Marketing) → Manager (Analysis)  
**Duration**: ~20-25 minutes  
**Context Required**: No

**Flow**:
1. **Дима** — correlates Gumroad sales with content performance
2. **Марина** — proposes content adjustments for conversion optimization
3. **Стас** — reviews data quality and suggests improvements

```bash
python pipeline.py weekly_report
```

---

### 5. `error_investigation` — Critical Error Resolution
**Steps**: Manager → Producer  
**Duration**: Varies (urgent)  
**Context Required**: Yes (error logs/trace)

**Flow**:
1. **Стас** — analyzes logs, identifies root cause
2. **Киrill** (Producer) — implements fix or workaround

**Example**:
```bash
python manager.py run_chain \
  --chain-name error_investigation \
  --context-json '{"error": "OAuth scope insufficient", "log": "...traceback..."}'
```

---

## API Reference

### Core Functions

#### `list_chains(status="all")`
Returns inventory of all chains with step counts and status.

**Returns**:
```json
{
  "total": 5,
  "chains": [
    {
      "name": "content_week",
      "type": "builtin",
      "steps": 4,
      "step_names": ["olya", "marina", "victoria", "vasya"],
      "status": "running",
      "active_id": "content_week_20240608_143022",
      "runs": { "completed": 12, "failed": 0 }
    }
  ]
}
```

---

#### `run_chain(chain_name, context_json="", wait=False, timeout_seconds=300)`
Launches a chain via `pipeline.py` (subprocess).

**Parameters**:
- `chain_name` (required): new_client, content_week, monday_brief, weekly_report, error_investigation
- `context_json`: JSON data for chain (passed via temp file for safety)
- `wait`: If True, block until completion (max 5 min); if False, return chain_id immediately
- `timeout_seconds`: Max execution time when wait=True

**Returns** (synchronous):
```json
{
  "id": "content_week_20240608_143022",
  "chain_name": "content_week",
  "status": "completed",
  "result": "Контент на неделю с 7 постов + 2 рилса подготовлено...",
  "errors": null
}
```

**Returns** (asynchronous):
```json
{
  "id": "content_week_20240608_143022",
  "chain_name": "content_week",
  "status": "started",
  "note": "Запущена в фоне. Статус: get_chain_status(id)."
}
```

---

#### `get_chain_status(chain_id)`
Checks status of a running or completed chain.

**Returns**:
```json
{
  "id": "content_week_20240608_143022",
  "status": "running",
  "started": "2024-06-08T14:30:22",
  "chain_name": "content_week",
  "checkpoint": {
    "current_step": 2,
    "agent": "marina",
    "message": "Generating 7 content ideas based on 3 trends..."
  }
}
```

---

#### `manage_parallel(chain_names, mode="sequential", max_parallel=2)`
Orchestrates multiple chains with concurrency control.

**Parameters**:
- `chain_names`: Comma-separated: "new_client,content_week,weekly_report"
- `mode`: "sequential" (one-by-one) or "parallel" (concurrent, respecting max_parallel)
- `max_parallel`: Max simultaneous chains (default 2)

**Example - Sequential**:
```bash
python manager.py manage_parallel \
  --chain-names "new_client,weekly_report" \
  --mode sequential
```

Flow: new_client completes → weekly_report starts → both done

**Example - Parallel with Rate Limiting**:
```bash
python manager.py manage_parallel \
  --chain-names "content_week,new_client" \
  --mode parallel \
  --max-parallel 2
```

Flow: both start simultaneously, manager ensures no resource contention

**Returns**:
```json
{
  "mode": "sequential",
  "total": 2,
  "completed": 2,
  "failed": 0,
  "chains": [
    { "id": "new_client_...", "status": "completed", "result": "..." },
    { "id": "weekly_report_...", "status": "completed", "result": "..." }
  ]
}
```

---

#### `resolve_chain_conflict(conflict_type, agent1, agent2, resource="")`
Detects and resolves conflicts between parallel chains.

**Conflict Types**:

**1. Write Conflict** (two agents writing same file)
```bash
resolve_chain_conflict(
  conflict_type="write",
  agent1="victoria",
  agent2="marina",
  resource="MILA-BUSINESS/02-content/posts/monday.md"
)
```

**Resolution**: Lock for agent1, queue for agent2
```json
{
  "type": "write",
  "agent1": "victoria",
  "agent2": "marina",
  "resource": "monday.md",
  "resolution": "Lock для victoria, очередь: marina",
  "recommendation": "Запустить victoria первым (wait=True), затем marina. Или использовать atomic writes через lock-файл..."
}
```

**2. Read-Race** (agent reading data being modified)
```bash
resolve_chain_conflict(
  conflict_type="read",
  agent1="olya",
  agent2="marina",
  resource="reports/posts_*.json"
)
```

**Resolution**: Snapshot before modification
```json
{
  "type": "read",
  "resolution": "Snapshot данных для olya перед изменением marina",
  "recommendation": "Сохранить снимок reports/posts_*.json перед запуском marina. Olya читает снимок, а не актуальные данные (итерация без гонки)."
}
```

**3. Resource Contention** (API rate limits, tokens, etc)
```bash
resolve_chain_conflict(
  conflict_type="resource",
  agent1="dima",
  agent2="lera",
  resource="GUMROAD_API"
)
```

**Resolution**: Rate limiting or sequential access
```json
{
  "type": "resource",
  "resolution": "Использовать rate-limit или очередь в n8n/pipeline",
  "recommendation": "Добавить sleep/delay между вызовами dima и lera для ресурса GUMROAD_API. Или завести глобальный семафор в memory.py..."
}
```

---

## State Files & Monitoring

### Chain State Directory
```
reports/chain_states/
├── running.json                    # Current active/completed/failed chains
├── custom_chains.json              # User-defined chains
├── conflicts.json                  # Conflict log (last 20)
└── <chain_id>_state.json          # Per-chain checkpoint (step, progress, errors)
```

### Example: `running.json`
```json
{
  "active": [
    {
      "id": "content_week_20240608_143022",
      "name": "content_week",
      "started": "2024-06-08T14:30:22",
      "status": "running",
      "context": "{...first 500 chars of context...}"
    }
  ],
  "completed": [
    {
      "id": "new_client_20240608_100000",
      "name": "new_client",
      "started": "2024-06-08T10:00:00",
      "completed": "2024-06-08T10:12:45",
      "status": "completed"
    }
  ],
  "failed": [
    {
      "id": "weekly_report_20240607_230000",
      "name": "weekly_report",
      "started": "2024-06-07T23:00:00",
      "failed": "2024-06-07T23:05:12",
      "error": "Gumroad API timeout"
    }
  ]
}
```

---

## Common Patterns

### Pattern 1: Parallel Content + Sales
Run content planning and client onboarding simultaneously (no resource conflict).

```bash
manage_parallel(
  chain_names="content_week,new_client",
  mode="parallel",
  max_parallel=2
)
```

**Why it works**: Different files, different agents, no shared resources.

---

### Pattern 2: Sequential Financial Pipeline
Run finance → marketing → analysis (each depends on previous output).

```bash
manage_parallel(
  chain_names="weekly_report",  # includes dima→marina→manager
  mode="sequential"
)
```

**Built-in**: pipeline.py already handles step sequencing within a chain.

---

### Pattern 3: Scheduled Weekly Orchestration
Every Monday at 11:00 (via n8n):

```bash
1. monday_brief (manager overview)
2. content_week (new content)
3. weekly_report (finance review)
```

**Sequential** to ensure data consistency:
```
n8n workflow "Weekly Standup":
  POST /pipeline/run content_week (wait=true)
  POST /pipeline/run weekly_report (wait=true)
  POST /pipeline/run monday_brief (wait=true)
```

---

## Error Handling & Retries

### Automatic Retry
`pipeline.py` includes `run_agent_with_retry()`:
- Max 3 attempts per step
- Exponential backoff (1s → 2s → 4s)
- Logged to improvement_log.md

### Manual Retry
```bash
# Get status
get_chain_status("content_week_20240608_143022")  # → status="failed"

# Re-run specific chain
run_chain("content_week", wait=True, timeout_seconds=600)
```

### Timeout Handling
- Default: 300 seconds (5 min)
- If exceeded → status="timeout", chain marked as failed
- Context file cleaned up automatically

---

## Safety Rules

1. **No Automatic Writes** — chains only write via designated agent tools
2. **RLS Protection** — database writes require service-role key (not publishable)
3. **Checkpoint Recovery** — if chain fails mid-step, next run resumes from checkpoint
4. **Conflict Detection** — resolve_chain_conflict prevents data races
5. **Immutable History** — all chain runs logged in running.json for audit

---

## Integrations

### With pipeline.py
Manager calls `subprocess.run(['pipeline.py', chain_name, ...])` to execute chains independently.

### With n8n
n8n can trigger chains via:
- HTTP POST to manager agent endpoint (if deployed)
- Direct `python pipeline.py chain_name` calls

### With memory.py
Chains store shared context in `memory.py` (coordination between agents).

### With session logs
All chain runs → `logs/sessions/<session_id>/` for audit trail.

---

## Troubleshooting

### Chain Stuck / Not Responding
```bash
# Check status
get_chain_status("chain_id")

# If running > 5 min, kill and re-run with longer timeout
manage_parallel("chain_name", wait=true, timeout=600)
```

### Data Inconsistency
```bash
# Detect conflicts
resolve_chain_conflict("write", "agent1", "agent2", "resource.md")

# Apply fix (lock + sequential)
manage_parallel("chain1,chain2", mode="sequential")
```

### Write Conflict in Shared File
```bash
# Example: both victoria and marina write to content-plan.md
resolve_chain_conflict("write", "victoria", "marina", "02-content/content-plan.md")
# → recommendation: Lock victoria first, queue marina
run_chain("content_week", wait=True)  # victoria runs first in chain
```

---

## Summary Table

| Command | Purpose | Wait? | Returns |
|---------|---------|-------|---------|
| `list_chains()` | View all chains | Instant | JSON inventory |
| `run_chain(name)` | Start chain (async) | No | chain_id |
| `run_chain(name, wait=True)` | Start chain (sync) | Yes | result |
| `get_chain_status(id)` | Monitor running chain | No | status + checkpoint |
| `manage_parallel(names, "sequential")` | Run multiple one-by-one | Yes | summary |
| `manage_parallel(names, "parallel", 2)` | Run 2 simultaneously | Yes | summary |
| `resolve_chain_conflict(...)` | Handle write/read/resource conflict | Instant | recommendation |

---

## Next Steps

1. **Extend chains**: Add custom chains to `_BUILTIN_CHAINS` in `manager.py`
2. **Monitor dashboards**: Build real-time UI in `webapp.py` showing active chains
3. **Smart scheduling**: Implement n8n workflows that call chains based on conditions
4. **Conflict auto-resolution**: Add semaphores/locks in `memory.py` for automatic rate limiting
5. **Chain dependencies**: Extend syntax to support fan-out patterns (one chain triggers multiple children)
