# Chain Retry Guide

Complete reference for the `chain_retry.py` module — managing agent chain failures, retries, and complex workflows.

## Overview

`chain_retry.py` provides a robust system for:

1. **Retry chains** — restart from a failed agent with automatic limits
2. **Escalate chains** — redirect to a different agent when stuck
3. **Split chains** — send tasks to multiple agents in parallel
4. **Merge results** — combine outputs from parallel branches
5. **Full logging** — all events and retries tracked in JSON files
6. **Error handling** — integration with `error_monitor.py` for critical alerts

## Quick Start

### 1. Create a Chain

```python
from chain_retry import create_chain, update_node_status, complete_chain

# Define your agent workflow
agents = ["victoria", "alina", "dima"]
context = {"document": "test.md", "user_id": "user_123"}

chain = create_chain("doc_editing_001", agents, context=context)
# Output:
# {
#   "id": "doc_editing_001",
#   "status": "running",
#   "agents": ["victoria", "alina", "dima"],
#   "nodes": {...},
#   "retry_count": 0,
#   ...
# }
```

### 2. Update Node Status as Agents Work

```python
# Start Victoria
update_node_status("doc_editing_001", "victoria", "running")

# Victoria finishes successfully
update_node_status("doc_editing_001", "victoria", "success",
                   reply="Отредактировано и улучшено")

# Alina starts next
update_node_status("doc_editing_001", "alina", "running")

# Alina hits an error
update_node_status("doc_editing_001", "alina", "failed",
                   error="API rate limit exceeded")
```

### 3. Retry on Failure

```python
from chain_retry import retry_chain

# Retry from Alina up to 3 times
result = retry_chain("doc_editing_001", "alina", 
                     reason="api_failure", max_retries=3)

if result is None:
    print("Max retries exceeded!")
else:
    print("Retrying from Alina...")
```

### 4. Complete or Cancel

```python
from chain_retry import complete_chain, cancel_chain

# Success
complete_chain("doc_editing_001", final_result="Document ready for review")

# Or cancel
cancel_chain("doc_editing_001", reason="User requested cancellation")
```

## Detailed API Reference

### Core Functions

#### `create_chain(chain_id, agents, context=None)`

Create a new agent chain.

**Parameters:**
- `chain_id` (str): Unique identifier for this chain
- `agents` (list[str]): List of agent keys in execution order
- `context` (dict, optional): Metadata (document path, user ID, etc.)

**Returns:** Chain object

**Example:**
```python
chain = create_chain(
    "report_gen_2026_06_08",
    agents=["olya", "rita", "dima"],
    context={
        "month": "June 2026",
        "type": "analytics_report",
        "triggered_by": "weekly_schedule"
    }
)
```

---

#### `update_node_status(chain_id, agent_key, status, reply=None, error=None)`

Update the status of an agent node in the chain.

**Parameters:**
- `chain_id` (str): Chain ID
- `agent_key` (str): Agent key (e.g., "victoria", "alina")
- `status` (str): One of `"running"`, `"success"`, `"failed"`, `"skipped"`
- `reply` (str, optional): Agent's response text
- `error` (str, optional): Error description

**Returns:** None (modifies chain in place)

**Example:**
```python
# Node starts working
update_node_status("doc_editing_001", "victoria", "running")

# Node succeeds
update_node_status("doc_editing_001", "victoria", "success",
                   reply="Document edited and formatted")

# Node fails
update_node_status("doc_editing_001", "alina", "failed",
                   error="Instagram API returned 401 Unauthorized")
```

---

#### `retry_chain(chain_id, failed_agent, reason, max_retries=3)`

Restart the chain from a failed agent.

**Parameters:**
- `chain_id` (str): Chain ID
- `failed_agent` (str): Agent key that failed (restart from here)
- `reason` (str): Reason for retry (see `RetryReason` enum below)
- `max_retries` (int): Maximum retry attempts (default: 3)

**Returns:** Updated chain object or `None` if limit exceeded

**Retry Reasons (from `RetryReason` enum):**
- `"agent_error"` — Agent crashed or threw an exception
- `"timeout"` — API call timed out
- `"api_failure"` — External API returned error
- `"validation_failed"` — Output validation failed
- `"manual_retry"` — Human requested retry
- `"task_complexity"` — Task too complex, try different approach
- `"escalation"` — Escalating to different agent

**Behavior:**
1. Increments `chain.retry_count`
2. If `retry_count > max_retries`: marks chain as FAILED and logs to error_monitor
3. Otherwise: resets all nodes from `failed_agent` onward to "pending"
4. Logs retry attempt in `RETRY_LOG`

**Example:**
```python
# Simple retry
result = retry_chain("doc_editing_001", "alina", reason="api_failure")

if result:
    print(f"Retrying (attempt {result['retry_count']}/3)")
else:
    print("Max retries exceeded - escalate to human")
```

---

#### `escalate_chain(chain_id, new_agent, reason="")`

Redirect the chain to a different agent (e.g., if current agent is stuck).

**Parameters:**
- `chain_id` (str): Chain ID
- `new_agent` (str): New agent key
- `reason` (str, optional): Why we're escalating

**Returns:** Updated chain object or `None` if not found

**Behavior:**
1. Marks all remaining agents as "skipped"
2. Inserts the `new_agent` at the current position
3. Sets chain status to `ESCALATED`
4. Logs escalation event

**Example:**
```python
# Victoria fails; escalate to Rita (more senior editor)
escalate_chain("doc_editing_001", "rita",
               reason="Victoria unable to parse complex formatting")
```

---

#### `split_chain(chain_id, to_agents, context=None)`

Send the chain to multiple agents in parallel.

**Parameters:**
- `chain_id` (str): Chain ID
- `to_agents` (list[str]): List of agents to process in parallel
- `context` (dict, optional): Additional context for the split

**Returns:** Updated chain object

**Behavior:**
1. Creates parallel branches for each agent
2. Sets branch status to "pending"
3. Sets chain status to `SPLIT`
4. Stores metadata about the split

**Example:**
```python
# Let three agents analyze the same report in parallel
split_chain("report_001", 
            to_agents=["olya", "rita", "manager"],
            context={"analysis_type": "fact_check"})
```

---

#### `merge_results(chain_id, results, merge_strategy="union")`

Combine results from parallel branches.

**Parameters:**
- `chain_id` (str): Chain ID
- `results` (list[dict]): Results from each agent:
  ```python
  [
    {"agent_key": "olya", "result": "...", "error": None, "confidence": 0.9},
    {"agent_key": "rita", "result": "...", "error": None, "confidence": 0.8},
    {"agent_key": "manager", "result": None, "error": "timeout", "confidence": None}
  ]
  ```
- `merge_strategy` (str): One of `"union"`, `"consensus"`, `"first_success"`

**Returns:** Updated chain object

**Merge Strategies:**
- `"union"` — Combine all successful results into a list
- `"consensus"` — Pick the result with highest confidence score
- `"first_success"` — Use the first non-error result

**Example:**
```python
# Collect results from parallel analysis
results = [
    {"agent_key": "olya", "result": "5 issues found", "confidence": 0.95},
    {"agent_key": "rita", "result": "3 issues found", "confidence": 0.80},
]

merge_results("report_001", results, merge_strategy="consensus")
# → Uses Olya's result (0.95 > 0.80)
```

---

#### `complete_chain(chain_id, final_result=None)`

Mark the chain as successfully completed.

**Parameters:**
- `chain_id` (str): Chain ID
- `final_result` (str, optional): Final output/summary

**Returns:** `True` if successful, `False` if chain not found

**Example:**
```python
complete_chain("doc_editing_001", 
               final_result="Document ready: /path/to/file.md")
```

---

#### `cancel_chain(chain_id, reason="")`

Cancel the chain (user requested, time limit, etc.).

**Parameters:**
- `chain_id` (str): Chain ID
- `reason` (str, optional): Why cancelled

**Returns:** `True` if successful, `False` if chain not found

---

### Querying Functions

#### `get_chain(chain_id)`

Get current chain state.

```python
chain = get_chain("doc_editing_001")
print(f"Status: {chain['status']}")
print(f"Retries: {chain['retry_count']}")
```

---

#### `get_chain_history(chain_id)`

Get all events for a chain.

```python
events = get_chain_history("doc_editing_001")
for event in events:
    print(f"{event['timestamp']}: {event['event_type']} ({event['agent_key']})")
# Output:
# 2026-06-08T10:15:23Z: start (victoria)
# 2026-06-08T10:15:45Z: node_done (victoria)
# 2026-06-08T10:16:02Z: node_running (alina)
# 2026-06-08T10:16:30Z: node_failed (alina)
# 2026-06-08T10:16:32Z: retry (alina)
```

---

#### `get_chain_stats(hours=24)`

Get aggregated statistics.

```python
stats = get_chain_stats(hours=24)
# {
#   "period": "last 24 hours",
#   "total_chains": 42,
#   "by_status": {
#     "success": 38,
#     "failed": 2,
#     "running": 2
#   },
#   "total_retries": 7,
#   "avg_duration_seconds": 45.3,
#   "chains": [...]
# }
```

---

#### `get_all_chains()`

Get all chains currently in memory (for debugging).

---

### Maintenance

#### `clear_old_chains(hours=24)`

Delete chains that completed more than N hours ago.

```python
clear_old_chains(hours=24)  # Clean up daily
```

---

#### `export_chain_to_json(chain_id, filepath=None)`

Export chain to JSON file for analysis/archival.

```python
path = export_chain_to_json("doc_editing_001")
# Writes to: logs/chains/doc_editing_001.json
```

---

#### `load_chain_from_json(filepath)`

Restore chain from exported JSON.

```python
chain = load_chain_from_json(Path("logs/chains/doc_editing_001.json"))
```

---

## Integration with Agents

### Pattern: Basic Chain Execution

**In an agent runner (e.g., `webapp.py` or `office.py`):**

```python
from chain_retry import (
    create_chain, update_node_status, retry_chain,
    escalate_chain, complete_chain, get_chain
)

def run_agent_chain(chain_id, agents, context):
    """Execute a chain of agents sequentially."""
    chain = create_chain(chain_id, agents, context=context)
    
    for agent_key in agents:
        try:
            # Start agent
            update_node_status(chain_id, agent_key, "running")
            
            # Run the agent (pseudo-code)
            response = run_agent(agent_key, context)
            
            # Success
            update_node_status(chain_id, agent_key, "success", reply=response)
            
        except Exception as e:
            # Fail
            update_node_status(chain_id, agent_key, "failed",
                               error=str(e))
            
            # Try to recover
            if should_retry(e):
                result = retry_chain(chain_id, agent_key, reason="agent_error")
                if result:
                    # Retry successful, re-run from this agent
                    continue
                else:
                    # Max retries exceeded
                    escalate_chain(chain_id, "manager",
                                   reason=f"Failed after retries: {e}")
                    break
            else:
                # Don't retry, escalate
                escalate_chain(chain_id, "lera", reason=str(e))
                break
    
    # Mark as done
    final_chain = get_chain(chain_id)
    if final_chain["status"] == "escalated":
        print("Chain was escalated")
    else:
        complete_chain(chain_id, final_result="All agents completed")
```

---

### Pattern: Parallel Processing with Merge

**For tasks that benefit from multiple perspectives:**

```python
from chain_retry import split_chain, merge_results, complete_chain

def analyze_document_parallel(chain_id, doc_path):
    """Get analysis from 3 agents, merge results."""
    
    # Start the split
    split_chain(chain_id, to_agents=["olya", "rita", "manager"])
    
    # Run agents in parallel (using threads or async)
    results = []
    for agent_key in ["olya", "rita", "manager"]:
        try:
            response = run_agent(agent_key, {"document": doc_path})
            results.append({
                "agent_key": agent_key,
                "result": response,
                "error": None,
                "confidence": 0.9  # Adjust based on agent
            })
        except Exception as e:
            results.append({
                "agent_key": agent_key,
                "result": None,
                "error": str(e),
                "confidence": None
            })
    
    # Merge with consensus strategy
    merge_results(chain_id, results, merge_strategy="consensus")
    
    # Get merged data
    chain = get_chain(chain_id)
    final_consensus = chain["merged_results"]["merged_data"]
    
    complete_chain(chain_id, final_result=final_consensus)
```

---

## Error Handling & Alerts

### Critical Failures

When `retry_chain()` exceeds `max_retries`, the chain is marked `FAILED` and:

1. Chain status → `FAILED`
2. Error logged to `errors.jsonl` via `error_monitor.log_error()`
3. Telegram alert sent (if `TELEGRAM_ADMIN_CHAT_ID` set)
4. Context includes: chain_id, failed_agent, reason, retry_count

### Logging Files

All chains are logged to:

- **`logs/chain_events.jsonl`** — Every event (start, node_done, retry, merge, etc.)
- **`logs/chain_retries.jsonl`** — Just retry attempts
- **`logs/chain_retry.log`** — Text log with INFO/ERROR messages
- **`logs/chains/`** — Exported JSON snapshots (if `export_chain_to_json()` called)

### Access Control

Session notes (`MILA-BUSINESS/03-clients/session-notes/`) should NOT be included in chain context.
If needed, sanitize via `data_sanitizer.py` before passing to agents.

---

## Examples

### Example 1: Content Creation Pipeline

```python
# Edit → Post → Analytics
chain = create_chain(
    "content_2026_06_08_post1",
    agents=["victoria", "vasya", "olya"],
    context={
        "post_type": "reel",
        "content": "/path/to/reel.md",
        "channels": ["instagram", "telegram"]
    }
)

# Victoria edits
update_node_status("content_2026_06_08_post1", "victoria", "running")
# ... Victoria works ...
update_node_status("content_2026_06_08_post1", "victoria", "success",
                   reply="Reel script polished")

# Vasya schedules
update_node_status("content_2026_06_08_post1", "vasya", "running")
# ... Vasya hits n8n timeout ...
update_node_status("content_2026_06_08_post1", "vasya", "failed",
                   error="n8n /webhook timeout after 30s")

# Retry scheduling
result = retry_chain("content_2026_06_08_post1", "vasya", "timeout", max_retries=2)
if result:
    print(f"Retrying Vasya (attempt {result['retry_count']}/2)")
else:
    escalate_chain("content_2026_06_08_post1", "manager",
                   reason="Vasya failed after retries")
```

---

### Example 2: Client Intake Processing

```python
# Client fills form → Alina processes → Lera sends intake → Rita archives
chain = create_chain(
    "client_intake_2026_06_08_user_456",
    agents=["alina", "lera", "rita"],
    context={
        "form_id": "user_456",
        "service": "consultation"
    }
)

# Process all agents
for agent in ["alina", "lera", "rita"]:
    try:
        update_node_status(chain_id, agent, "running")
        response = run_agent(agent, context)
        update_node_status(chain_id, agent, "success", reply=response)
    except Exception as e:
        update_node_status(chain_id, agent, "failed", error=str(e))
        retry_chain(chain_id, agent, reason="agent_error", max_retries=2)

complete_chain(chain_id, final_result="Intake processed")
```

---

### Example 3: Report Generation (Parallel + Merge)

```python
# Get analytics from 3 agents, pick best analysis
split_chain("monthly_report_2026_06", ["olya", "rita", "manager"])

results = []
for agent in ["olya", "rita", "manager"]:
    try:
        r = run_agent(agent, {"month": "June 2026"})
        results.append({
            "agent_key": agent,
            "result": r,
            "confidence": get_confidence(agent, r),
            "error": None
        })
    except Exception as e:
        results.append({
            "agent_key": agent,
            "result": None,
            "error": str(e),
            "confidence": None
        })

merge_results("monthly_report_2026_06", results,
              merge_strategy="consensus")

complete_chain("monthly_report_2026_06", 
               final_result="Report ready for review")
```

---

## Troubleshooting

### Chain Not Found

```python
chain = get_chain("non_existent_id")
if chain is None:
    print("Chain not found — create it first with create_chain()")
```

### Stuck in Retry Loop

If a chain keeps retrying:

1. Check `get_chain_history(chain_id)` for pattern
2. Increase `max_retries` if temporary glitch
3. Use `escalate_chain()` to switch agents
4. Use `cancel_chain()` if unrecoverable

### Reviewing Failures

```python
from error_monitor import get_recent_errors

# See all errors from last 24h
errors = get_recent_errors(limit=20)
for err in errors:
    if "chain" in err.get("context", {}):
        print(f"Chain error: {err['error_message']}")
```

---

## Design Notes

### Thread Safety

All state is protected by `_chains_lock` (RLock). Safe to call from multiple threads.

### State Persistence

Chains live in memory (`_chains` dict) during the session. Export important chains:

```python
export_chain_to_json("critical_chain_id")  # Save to logs/chains/
```

For long-running processes, periodically call:

```python
clear_old_chains(hours=24)  # Prevent memory leak
```

### Events vs. Nodes

- **Nodes** = Agents in the workflow (victoria, alina, dima)
- **Events** = What happened (started, succeeded, failed, retried)

A chain has a fixed set of nodes but a growing list of events as it executes.

### Retry Limits

Default `max_retries=3` means:
- 1st attempt (initial failure)
- 2nd attempt (retry #1)
- 3rd attempt (retry #2)
- 4th attempt (retry #3) ← hits limit → FAILED

Adjust per use case:
- Quick operations: `max_retries=1` or `2`
- Long operations: `max_retries=5`
- Critical: `max_retries=0` (fail immediately, escalate)

---

## See Also

- `error_monitor.py` — Error logging and Telegram alerts
- `job_queue.py` — Async job management
- `agent_manager.py` — Agent registry
- `base.py` — Common utilities and Claude client setup
