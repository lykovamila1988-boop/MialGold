# Orchestration API Technical Reference

**For**: Python developers extending manager.py orchestration  
**Audience**: Pipeline.py, webapp.py, custom chain builders  
**Version**: 1.0 (June 8, 2024)

---

## Core Data Structures

### Chain State Object
```python
chain_state = {
    "id": "content_week_20240608_143022",     # <chain_name>_<YYYYMMDD>_<HHMMSS>
    "name": "content_week",
    "started": "2024-06-08T14:30:22",
    "status": "running|completed|failed|timeout",
    "context": "{...first 500 chars of JSON...}",  # input data
    "current_step": 2,                             # (optional, running only)
    "agent": "marina",                             # current agent (optional)
    "completed": "2024-06-08T15:05:00",           # (optional, completed only)
    "failed": "2024-06-08T14:45:30",              # (optional, failed only)
    "error": "Victoria timeout: requests.Timeout", # error message
}
```

### Checkpoint State Object
```python
checkpoint = {
    "chain_id": "content_week_20240608_143022",
    "current_step": 2,         # 0-indexed step in chain
    "agent": "marina",         # agent currently executing
    "input": {...},            # input to current agent
    "output": "ideas: ...",    # output from agent (truncated)
    "timestamp": "2024-06-08T14:40:00",
    "elapsed_seconds": 600,
    "estimated_remaining": 480,
}
```

### Chain Registry Entry
```python
chain_def = {
    "name": "content_week",
    "steps": ["olya", "marina", "victoria", "vasya"],
    "description": "Еженедельный контент: тренды → идеи → редактура → расписание",
    "requires_context": False,
    "timeout_seconds": 2400,  # 40 min
    "max_retries": 3,
    "tags": ["content", "weekly", "critical"],
}
```

### Conflict Record Object
```python
conflict = {
    "timestamp": "2024-06-08T14:35:00",
    "type": "write|read|resource",
    "agent1": "victoria",
    "agent2": "marina",
    "resource": "MILA-BUSINESS/02-content/content-plan.md",
    "resolution": "Lock для victoria, очередь: marina",
    "recommendation": "Запустить victoria первым (wait=True)...",
    "resolved": True,
}
```

---

## State Files Layout

### `/reports/chain_states/running.json`
Master registry of all chains (active, completed, failed).

```python
{
  "active": [
    {
      "id": "content_week_20240608_143022",
      "name": "content_week",
      "started": "2024-06-08T14:30:22",
      "status": "running",
      "context": "{input data...}"
    }
  ],
  "completed": [
    {
      "id": "new_client_20240608_100000",
      "name": "new_client",
      "started": "2024-06-08T10:00:00",
      "completed": "2024-06-08T10:12:45"
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

### `/reports/chain_states/<chain_id>_state.json`
Per-chain checkpoint (written by pipeline.py after each step).

```python
{
  "chain_id": "content_week_20240608_143022",
  "current_step": 2,
  "agent": "marina",
  "input": {"prev": "Olya findings..."},
  "output": "7 content ideas with hooks",
  "timestamp": "2024-06-08T14:40:00",
  "elapsed_seconds": 600,
  "estimated_remaining": 480
}
```

### `/reports/chain_states/custom_chains.json`
User-defined chains (if extended).

```python
{
  "chains": [
    {
      "name": "competitor_analysis",
      "steps": ["olya", "producer", "marina"],
      "description": "Еженедельный анализ конкурентов",
      "requires_context": False,
      "created_at": "2024-06-01",
      "created_by": "manager"
    }
  ]
}
```

### `/reports/chain_states/conflicts.json`
Conflict log (last 20 unresolved).

```python
[
  {
    "timestamp": "2024-06-08T14:35:00",
    "type": "write",
    "agent1": "victoria",
    "agent2": "marina",
    "resource": "02-content/content-plan.md",
    "resolution": "Lock для victoria, очередь: marina",
    "recommended_fix": "manage_parallel(..., mode='sequential')",
    "resolved": True
  }
]
```

### `/reports/chain_states/<chain_id>_context.json`
Input context file (created by manager.py, cleaned up after chain completes).

```python
{
  "client_name": "Мария",
  "age": 32,
  "problem": "Созависимость",
  "intake_form": "...",
  "channel": "telegram"
}
```

---

## Function Signatures

### `list_chains(status="all") → str (JSON)`
```python
def list_chains(status="all"):
    """
    Args:
        status: "all" | "running" | "idle"
    
    Returns:
        JSON string with structure:
        {
            "total": int,
            "chains": [
                {
                    "name": str,
                    "type": "builtin" | "custom",
                    "steps": int,
                    "step_names": [str],
                    "status": "running" | "completed" | "idle",
                    "active_id": str | None,
                    "runs": {"completed": int, "failed": int}
                }
            ]
        }
    """
```

### `run_chain(chain_name, context_json="", wait=False, timeout_seconds=300) → str (JSON)`
```python
def run_chain(chain_name, context_json="", wait=False, timeout_seconds=300):
    """
    Launches a chain via subprocess (pipeline.py).
    
    Args:
        chain_name: "new_client" | "content_week" | ... (must be in _BUILTIN_CHAINS)
        context_json: JSON string with input data (passed via temp file)
        wait: True → block until completion; False → return chain_id immediately
        timeout_seconds: Max execution time (ignored if wait=False)
    
    Returns:
        JSON string with structure:
        
        If wait=True and success:
        {
            "id": str,
            "chain_name": str,
            "status": "completed",
            "result": str (first 1000 chars of output),
            "errors": null | str
        }
        
        If wait=True and failed:
        {
            "id": str,
            "chain_name": str,
            "status": "failed" | "timeout",
            "errors": str (stderr output)
        }
        
        If wait=False:
        {
            "id": str,
            "chain_name": str,
            "status": "started",
            "note": "Запущена в фоне. Статус: get_chain_status(id)."
        }
    
    Exceptions:
        - ValueError: if chain_name not in _BUILTIN_CHAINS
        - subprocess.TimeoutExpired: if wait=True and timeout exceeded
        - OSError: if pipeline.py not found or exec fails
    """
```

### `get_chain_status(chain_id) → str (JSON)`
```python
def get_chain_status(chain_id):
    """
    Polls status of a chain (running, completed, or failed).
    
    Args:
        chain_id: Chain ID (format: <name>_<YYYYMMDD>_<HHMMSS>)
    
    Returns:
        JSON string with one of:
        
        If running:
        {
            "id": str,
            "status": "running",
            "started": ISO8601,
            "chain_name": str,
            "checkpoint": {
                "current_step": int,
                "agent": str,
                "input": {...},
                "output": str,
                "elapsed_seconds": int
            }
        }
        
        If completed:
        {
            "id": str,
            "status": "completed",
            "chain_name": str,
            "completed": ISO8601
        }
        
        If failed:
        {
            "id": str,
            "status": "failed",
            "chain_name": str,
            "failed": ISO8601,
            "error": str
        }
        
        If not found:
        {
            "error": "Цепочка <id> не найдена"
        }
    """
```

### `manage_parallel(chain_names, mode="sequential", max_parallel=2) → str (JSON)`
```python
def manage_parallel(chain_names, mode="sequential", max_parallel=2):
    """
    Orchestrates multiple chains with concurrency control.
    
    Args:
        chain_names: Comma-separated chain names: "new_client,content_week,weekly_report"
        mode: "sequential" (one-by-one) | "parallel" (concurrent, respecting max_parallel)
        max_parallel: Max simultaneous chains (only used if mode="parallel")
    
    Returns:
        JSON string with structure:
        {
            "mode": str,
            "total": int,
            "completed": int,
            "failed": int,
            "chains": [
                {
                    "id": str,
                    "chain_name": str,
                    "status": "completed" | "failed",
                    "result": str | null,
                    "error": str | null
                }
            ]
        }
    
    Blocking: Always blocks until all chains complete (no async for parallel).
    
    Exceptions:
        - ValueError: if any chain_name invalid
        - concurrent.futures.TimeoutError: if chain exceeds timeout
    """
```

### `resolve_chain_conflict(conflict_type, agent1="", agent2="", resource="") → str (JSON)`
```python
def resolve_chain_conflict(conflict_type, agent1="", agent2="", resource=""):
    """
    Detects and suggests resolution for conflicts between parallel chains.
    
    Args:
        conflict_type: "write" | "read" | "resource"
        agent1: First agent (e.g., "victoria")
        agent2: Second agent (e.g., "marina")
        resource: Conflicting resource (e.g., "content-plan.md")
    
    Returns:
        JSON string with structure:
        {
            "timestamp": ISO8601,
            "type": str,
            "agent1": str,
            "agent2": str,
            "resource": str,
            "resolution": str (human-readable recommendation),
            "recommendation": str (detailed fix steps)
        }
    
    Side Effects:
        - Appends to /reports/chain_states/conflicts.json (last 20)
        - Logged to improvement_log.md
    
    Notes:
        - Does NOT automatically apply fix (only recommends)
        - Manager calls this when conflict detected
        - Use manage_parallel(..., mode='sequential') to apply fix
    """
```

---

## Integration with pipeline.py

### Subprocess Call
```python
# manager.py calls:
cmd = [
    sys.executable,
    "pipeline.py",
    chain_name,  # "content_week"
    "--context-file", "<path>/<chain_id>_context.json"  # if context_json provided
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)

# pipeline.py expected behavior:
# 1. Reads <chain_id>_context.json (optional)
# 2. Loads chain steps from CHAINS dict
# 3. Runs each step (agent) sequentially with retry
# 4. Writes checkpoint after each step: <chain_id>_state.json
# 5. Returns 0 on success, 1 on failure
# 6. Cleans up temp files on exit
```

### Checkpoint Protocol
```python
# After each agent completes, pipeline.py writes:
# reports/chain_states/<chain_id>_state.json

checkpoint = {
    "chain_id": chain_id,
    "current_step": step_index,
    "agent": agent_name,
    "input": {...},           # input to agent
    "output": agent_result[:500],  # truncated
    "timestamp": datetime.now().isoformat(),
    "elapsed_seconds": total_elapsed,
    "estimated_remaining": estimated_total - elapsed,
}
```

### Return Protocol
```python
# On success:
print(json.dumps({"status": "success", "result": "..."}))
sys.exit(0)

# On failure:
print(f"ERROR: {error_message}")
sys.exit(1)
```

---

## Integration with webapp.py

### Dashboard Endpoint (Future)
```python
# Add to webapp.py routes.py:

@app.get("/api/chains")
def get_chains():
    """List all chains and their status."""
    from manager import list_chains
    return json.loads(list_chains(status="all"))

@app.get("/api/chains/<chain_id>/status")
def get_chain_status(chain_id):
    """Poll status of specific chain."""
    from manager import get_chain_status
    return json.loads(get_chain_status(chain_id))

@app.post("/api/chains/<chain_name>/run")
def run_chain_endpoint(chain_name):
    """Trigger chain execution."""
    from manager import run_chain
    context = request.json.get("context", {})
    wait = request.json.get("wait", False)
    return json.loads(run_chain(chain_name, json.dumps(context), wait=wait))
```

### Real-time Dashboard Component
```javascript
// JavaScript polling every 5s:
setInterval(async () => {
    const response = await fetch("/api/chains");
    const data = await response.json();
    
    // Update UI:
    data.chains.forEach(chain => {
        if (chain.status === "running") {
            updateProgress(chain.name, chain.progress);
        }
    });
}, 5000);
```

---

## Integration with n8n

### n8n Webhook Trigger
```json
{
  "name": "Start Chain from Webhook",
  "trigger": "HTTP Request",
  "method": "POST",
  "steps": [
    {
      "type": "Execute Python",
      "script": "python manager.py run_chain new_client --context-json '{...}' --wait"
    }
  ]
}
```

### n8n Cron Trigger
```json
{
  "name": "Weekly Content Planning",
  "trigger": "Cron",
  "cron": "0 11 * * 1",  // Every Monday at 11:00
  "steps": [
    {
      "type": "Execute Python",
      "script": "cd E:\\MILA GOLD\\mila-office && python pipeline.py content_week"
    }
  ]
}
```

---

## Error Handling Best Practices

### Try-Except Pattern
```python
try:
    result = run_chain("content_week", wait=True, timeout_seconds=600)
    data = json.loads(result)
    if data.get("status") == "failed":
        log(f"Chain failed: {data.get('errors')}")
        # Retry or escalate
except subprocess.TimeoutExpired:
    log("Chain exceeded timeout (600s)")
    # Kill process, retry with longer timeout
except Exception as e:
    log(f"Chain error: {e}")
    # Log to sentry, alert
```

### Retry Logic
```python
def run_chain_with_retry(chain_name, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = json.loads(run_chain(chain_name, wait=True))
            if result.get("status") == "completed":
                return result
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
    raise Exception(f"Chain {chain_name} failed after {max_retries} attempts")
```

---

## Performance Optimization

### Chain Parallelization
```python
# Instead of:
run_chain("new_client", wait=True)  # 12 min
run_chain("content_week", wait=True)  # 35 min
# Total: 47 min

# Use:
manage_parallel("new_client,content_week", mode="parallel", max_parallel=2)
# Total: 35 min (faster by 12 min)
```

### Async Execution Pattern
```python
# Start chains asynchronously:
id1 = json.loads(run_chain("new_client", wait=False)).get("id")
id2 = json.loads(run_chain("content_week", wait=False)).get("id")

# Poll in background:
while True:
    status1 = get_chain_status(id1)
    status2 = get_chain_status(id2)
    if both_complete(status1, status2):
        break
    time.sleep(10)
```

---

## Security Considerations

### Context Passing
```python
# ✗ UNSAFE: Passing sensitive data via argv
subprocess.run(["python", "pipeline.py", "--context", sensitive_json])

# ✓ SAFE: Passing via temporary file (manager.py does this)
ctx_file = Path("/reports/chain_states/temp_context.json")
ctx_file.write_text(sensitive_json)
subprocess.run(["python", "pipeline.py", "--context-file", str(ctx_file)])
ctx_file.unlink()  # cleanup
```

### Environment Variables
```python
# ✓ Tokens in .env, not in context_json
# ✓ Context can contain plain text, not secrets
# ✓ Temp context files cleaned up immediately
# ✓ All chain runs logged for audit
```

---

## Testing Checklist

```python
# Unit tests for orchestration functions:

def test_list_chains():
    result = json.loads(list_chains())
    assert "chains" in result
    assert result["total"] > 0

def test_run_chain_invalid():
    result = run_chain("invalid_chain")
    assert "Неизвестная цепочка" in result

def test_run_chain_sync():
    # Requires pipeline.py available
    result = json.loads(run_chain("new_client", wait=True, timeout_seconds=30))
    assert result["status"] in ["completed", "failed", "timeout"]

def test_manage_parallel():
    result = json.loads(manage_parallel("new_client,content_week", mode="sequential"))
    assert result["total"] == 2
    assert result["completed"] + result["failed"] == 2

def test_resolve_conflict():
    result = json.loads(resolve_chain_conflict("write", "victoria", "marina", "file.md"))
    assert result["type"] == "write"
    assert "resolution" in result
```

---

## Debugging Tips

### Check State Files
```bash
# View current state
cat reports/chain_states/running.json

# View chain checkpoint
cat "reports/chain_states/content_week_20240608_143022_state.json"

# View conflict log
cat reports/chain_states/conflicts.json
```

### Enable Verbose Logging
```python
# In manager.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Then:
logger.debug(f"Running chain: {chain_name}")
logger.debug(f"Checkpoint: {checkpoint}")
```

### Manual Chain Execution
```bash
# Run pipeline.py directly for debugging:
cd E:\MILA GOLD\mila-office
python pipeline.py content_week
# See full output, not captured

# Run with context:
python pipeline.py new_client --context-file reports/chain_states/test_context.json
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-06-08 | Initial implementation |
| — | — | Planned: DAG execution, conditional branching |

---

## Related Documentation

- **ORCHESTRATION_GUIDE.md** — User guide + examples
- **CHAIN_EXAMPLES.md** — Real-world scenarios
- **mila-office/manager.py** — Implementation source code
- **mila-office/pipeline.py** — Chain executor (sibling system)
