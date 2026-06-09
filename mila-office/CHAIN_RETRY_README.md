# Chain Retry System

Robust chain management, retry, and error handling system for multi-agent workflows in MILA Office.

## What It Does

`chain_retry.py` manages complex workflows where multiple agents work sequentially or in parallel:

- **Sequential chains**: Victoria → Alina → Dima, with automatic retry on failure
- **Escalation**: Switch to a different agent when one gets stuck
- **Parallel processing**: Split a task to 3 agents, merge their results
- **Full traceability**: Every event is logged; access chain history anytime
- **Error handling**: Integrated with error_monitor for critical alerts
- **Thread-safe**: Safe to call from multiple threads

## Files

### Core Module
- **`chain_retry.py`** (700+ lines)
  - Main implementation
  - 5 primary functions: retry, escalate, split, merge, complete
  - State management and logging
  - Thread-safe with RLock

### Guides & Examples
- **`CHAIN_RETRY_GUIDE.md`** (500+ lines)
  - Complete API reference
  - 5+ integration patterns
  - Troubleshooting guide
  - Design notes

- **`chain_retry_integration.py`** (400+ lines)
  - Ready-to-use patterns:
    - Sequential execution
    - Parallel split + merge
    - Error handling with context
    - Fallback chains
    - Background monitoring

### Tests
- **`test_chain_retry.py`** (500+ lines)
  - 29 unit tests
  - Tests for all features
  - Thread safety tests
  - All tests pass ✓

## Quick Example

```python
from chain_retry import (
    create_chain, update_node_status, retry_chain,
    escalate_chain, complete_chain
)

# Create a workflow
chain = create_chain(
    "doc_edit_2026_06_08",
    agents=["victoria", "alina", "dima"],
    context={"document": "post.md"}
)

# Victoria edits
update_node_status("doc_edit_2026_06_08", "victoria", "running")
# ... victoria does work ...
update_node_status("doc_edit_2026_06_08", "victoria", "success",
                   reply="Edited!")

# Alina processes (fails!)
update_node_status("doc_edit_2026_06_08", "alina", "running")
update_node_status("doc_edit_2026_06_08", "alina", "failed",
                   error="Timeout from Instagram API")

# Retry Alina
result = retry_chain("doc_edit_2026_06_08", "alina", "timeout", max_retries=3)
if result:
    print(f"Retrying (attempt {result['retry_count']}/3)")
else:
    print("Max retries exceeded")
    escalate_chain("doc_edit_2026_06_08", "manager",
                   reason="Alina failed after retries")

# At the end
complete_chain("doc_edit_2026_06_08", final_result="Ready to publish")
```

## Features

### 1. Retry Chains
**Function**: `retry_chain(chain_id, failed_agent, reason, max_retries=3)`

Restart from a failed agent. Automatically:
- Tracks retry count (default max: 3)
- Resets downstream agents to "pending"
- Logs to error_monitor if limit exceeded
- Sends Telegram alert on critical failure

```python
result = retry_chain("chain_123", "alina", "timeout", max_retries=2)
if result:
    # Retrying...
    print(f"Attempt {result['retry_count']} of 2")
else:
    # Max retries exceeded
    print("Failed after 2 retries")
```

### 2. Escalate Chains
**Function**: `escalate_chain(chain_id, new_agent, reason="")`

Redirect to a different agent (for complex tasks, stuck agents, etc).

```python
# Victoria can't handle this, try Rita (more senior)
escalate_chain("chain_123", "rita", reason="Task too complex for Victoria")
```

### 3. Split Chains
**Function**: `split_chain(chain_id, to_agents[])`

Send to multiple agents in parallel for consensus or diverse perspectives.

```python
# Get analysis from 3 agents
split_chain("report_123", to_agents=["olya", "rita", "manager"])
```

### 4. Merge Results
**Function**: `merge_results(chain_id, results[], merge_strategy)`

Combine parallel results using one of 3 strategies:

- **"union"** — Collect all successful results
- **"consensus"** — Pick the one with highest confidence
- **"first_success"** — Use the first non-error result

```python
results = [
    {"agent_key": "olya", "result": "Analysis A", "confidence": 0.95},
    {"agent_key": "rita", "result": "Analysis B", "confidence": 0.70},
]

merge_results("report_123", results, merge_strategy="consensus")
# → Uses "Analysis A" (0.95 > 0.70)
```

### 5. Full Logging
All events logged to:
- **`logs/chain_events.jsonl`** — Every event (start, retry, merge, etc.)
- **`logs/chain_retries.jsonl`** — Just retry attempts
- **`logs/chain_retry.log`** — Text log
- **`logs/chains/`** — JSON snapshots (on export)

```python
# Get full event history
history = get_chain_history("chain_123")
for event in history:
    print(f"{event['timestamp']}: {event['event_type']}")

# Get stats
stats = get_chain_stats(hours=24)
print(f"Chains completed: {stats['total_chains']}")
print(f"By status: {stats['by_status']}")
```

## Integration with MILA Office

### Pattern 1: Inside an Agent
```python
from chain_retry import create_chain, update_node_status

def my_agent(session_id, message):
    # Create a sub-chain if this agent needs to delegate
    chain = create_chain(f"agent_{session_id}", ["alina", "dima"])
    
    update_node_status(f"agent_{session_id}", "alina", "running")
    response = run_agent("alina", message)
    update_node_status(f"agent_{session_id}", "alina", "success", reply=response)
    
    return response
```

### Pattern 2: In webapp.py
```python
# In a Flask route
@app.route("/api/chain/run", methods=["POST"])
def run_chain():
    from chain_retry_integration import execute_chain_sequential, ChainExecutionConfig
    
    config = ChainExecutionConfig(
        chain_id=request.json["chain_id"],
        agents=request.json["agents"],
        max_retries=3
    )
    
    result = execute_chain_sequential(config, run_agent)
    return jsonify(result)
```

### Pattern 3: Monitoring
```python
from chain_retry_integration import ChainMonitor

monitor = ChainMonitor(cleanup_hours=24)

# In a background task
def periodic_cleanup():
    monitor.maybe_cleanup()
    status = monitor.get_status()
    print(f"Active chains: {status['total']}")
    
    # Export failed chains for analysis
    monitor.export_failed_chains(Path("logs/chains"))
```

## State Management

### Chain Object Structure
```python
{
    "id": "chain_123",
    "status": "running" | "success" | "failed" | "escalated" | "split" | "merged",
    "agents": ["victoria", "alina", "dima"],
    "nodes": {
        "victoria": ChainNode(status="success", reply="...", duration_seconds=12.5),
        "alina": ChainNode(status="failed", error="Timeout", retry_count=1),
        "dima": ChainNode(status="pending", ...)
    },
    "retry_count": 1,
    "created_at": "2026-06-08T10:15:23Z",
    "completed_at": "2026-06-08T10:17:45Z",
    "history": [
        {"timestamp": "...", "event_type": "start", "agent_key": "victoria", ...},
        {"timestamp": "...", "event_type": "node_done", "agent_key": "victoria", ...},
        ...
    ],
    "split_branches": {
        "olya": {"status": "success", "result": "..."},
        "rita": {"status": "failed", "error": "..."}
    },
    "merged_results": {
        "strategy": "consensus",
        "merged_data": "..."
    }
}
```

## Error Handling

### Critical Failures
When `retry_chain()` exceeds `max_retries`:

1. Chain marked `FAILED`
2. Error logged via `error_monitor.log_error()`
3. Telegram alert sent (if configured)
4. Context includes: chain_id, failed_agent, reason, retry_count

### Example Error Context
```json
{
    "timestamp": "2026-06-08T10:30:15Z",
    "level": "CRITICAL",
    "error_type": "Exception",
    "error_message": "Chain retry limit exceeded: timeout",
    "context": {
        "chain_id": "chain_123",
        "failed_agent": "alina",
        "reason": "timeout",
        "retry_count": 3,
        "max_retries": 3
    }
}
```

## Performance Notes

- **Memory**: Chains live in memory during session. Call `clear_old_chains()` regularly
- **Thread safety**: All state protected by RLock; safe to call from multiple threads
- **Logging**: JSON lines (JSONL) format for easy parsing and streaming
- **Export**: Chain state can be exported to JSON for analysis/archival

## Testing

Run the test suite:
```bash
cd e:\MILA GOLD\mila-office
python test_chain_retry.py
```

Output:
```
Ran 29 tests in 0.092s
OK
```

Tests cover:
- Chain creation and retrieval
- Node status updates
- Retry logic and limits
- Escalation
- Split/merge with all strategies
- Completion and cancellation
- Statistics and history
- Export/load
- Thread safety

## Usage Checklist

- [ ] Import: `from chain_retry import create_chain, ...`
- [ ] Create chain: `create_chain(chain_id, agents, context)`
- [ ] Update nodes: `update_node_status(chain_id, agent_key, status, reply, error)`
- [ ] On error: `retry_chain()` or `escalate_chain()`
- [ ] On success: `complete_chain()`
- [ ] Monitor: `get_chain_stats()`, `get_chain_history()`
- [ ] Maintain: `clear_old_chains()` periodically
- [ ] Debug: Check `logs/chain_events.jsonl` and error_monitor logs

## API Reference

### Primary Functions

| Function | Purpose |
|----------|---------|
| `create_chain(id, agents, context)` | Start a new chain |
| `update_node_status(chain_id, agent, status, reply, error)` | Update progress |
| `retry_chain(chain_id, agent, reason, max_retries)` | Retry from failed agent |
| `escalate_chain(chain_id, new_agent, reason)` | Switch agents |
| `split_chain(chain_id, to_agents, context)` | Parallel processing |
| `merge_results(chain_id, results, strategy)` | Combine parallel results |
| `complete_chain(chain_id, final_result)` | Mark as done |
| `cancel_chain(chain_id, reason)` | Cancel workflow |

### Query Functions

| Function | Returns |
|----------|---------|
| `get_chain(chain_id)` | Chain object or None |
| `get_chain_history(chain_id)` | List of events |
| `get_chain_stats(hours)` | Aggregated stats |
| `get_all_chains()` | All chains dict |

### Utilities

| Function | Purpose |
|----------|---------|
| `clear_old_chains(hours)` | Delete old chains from memory |
| `export_chain_to_json(chain_id, filepath)` | Save to JSON |
| `load_chain_from_json(filepath)` | Restore from JSON |

## Enums

### ChainStatus
- `RUNNING` — Chain is executing
- `SUCCESS` — All agents completed
- `FAILED` — Exceeded retry limit
- `RETRYING` — Currently retrying
- `ESCALATED` — Switched to different agent
- `SPLIT` — Running in parallel
- `MERGED` — Results combined
- `CANCELLED` — User stopped workflow

### RetryReason
- `AGENT_ERROR` — Agent crashed
- `TIMEOUT` — API call timed out
- `API_FAILURE` — External API returned error
- `VALIDATION_FAILED` — Output didn't pass validation
- `MANUAL_RETRY` — Human requested retry
- `TASK_COMPLEXITY` — Task too complex, try different approach
- `ESCALATION` — Escalating to different agent

## See Also

- `error_monitor.py` — Error logging and alerts
- `job_queue.py` — Async job management
- `agent_manager.py` — Agent registry
- `CHAIN_RETRY_GUIDE.md` — Extended guide with patterns
- `chain_retry_integration.py` — Ready-to-use implementations

## Design Philosophy

1. **Explicit over implicit** — Every action is a function call, traceable
2. **Resilient by default** — Retries and escalation built-in
3. **Observable** — All events logged; full history accessible
4. **Simple integration** — Minimal dependencies; works with any agent system
5. **Thread-safe** — No race conditions; safe for concurrent use

---

**Version**: 1.0 | **Last updated**: 2026-06-08 | **Status**: Production-ready
