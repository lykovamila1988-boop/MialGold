# 🔍 COMPREHENSIVE AGENT INTERACTION AUDIT

**Date:** 2026-06-17  
**Scope:** Full cross-agent behavior analysis (mila-office/)  
**Finding:** System is **functionally working but has 13 identified issues**

---

## ⚡ EXECUTIVE SUMMARY

### System Architecture: **Hybrid Orchestration Model**

```
┌──────────────────┐
│   Web UI Layer   │  (webapp.py) Blocking calls, single-user
├──────────────────┤
│  Message Broker  │  (memory.py) File-based state + coordination
├──────────────────┤
│ Pipeline Engine  │  (pipeline.py) Sequential chains + checkpoints
├──────────────────┤
│  Agent Registry  │  (agent_manager.py) Module loading system
├──────────────────┤
│  8 Agents        │  (victoria.py, marina.py, etc.) Independent workers
└──────────────────┘
```

### How Agents Talk to Each Other

1. **Via Context Tags** → `[from: marina] [to: victoria] [chain_id: abc123]`
2. **Via Verdict System** → `[VERDICT: ready_next|done|needs_revision]`
3. **Via Handoff Records** → `memory.py` tracks baton passes
4. **Via Shared Memory** → `memory.py` stores context.json, profile.json, approvals.json
5. **Via Pipeline Chains** → Sequential agent execution with checkpoints

---

## 📊 AGENT INTERACTION GRAPH

### Synchronous Pipelines (pipeline.py)

```
new_client:
    Alina → Lera [handoff]

content_week:
    Olya → Marina → Victoria → Vasya
                       ↓
                  (approval gate)

monday_brief:
    Manager → Marina

weekly_report:
    Dima → Marina → Manager

new_product:
    Rita → Marina → Victoria
```

### Message Broker (memory.py + n8n_bridge.py)

```
External Trigger (n8n)
    ↓
POST /v1/context (writes to context.json)
    ↓
All agents read via memory.read_context()
    ↓
Manual routing (operator/n8n decides next agent)
    ↓
Task enqueued, worker runs pipeline.py
    ↓
Completion → Telegram alert
```

### Web UI Routing (webapp.py + routes.py)

```
User Input → POST /api/chat
  (agent, message, from_agent, chain_id)
    ↓
Job enqueued
    ↓
Agent runs (blocking, no timeout)
    ↓
GET /api/result?job=<id>
  (reply, verdict, next_agent, context)
```

---

## 🔧 HOW AGENTS COMMUNICATE IN DETAIL

### 1. Context Passing Mechanism

**Location:** `base.py:537-588`, `message_handler.py:125-166`

Each agent receives context automatically injected into system prompt:

```python
# System prompt for Victoria becomes:
SYSTEM = """Ты Victoria, редактор...
[CONTEXT: Request from marina for content_week pipeline]
[CHAIN_ID: ch_12345]
[PHASE: learning]
"""
```

**Context Tags in Responses:**
```
Пост одобрен. Хук цепляет.
[VERDICT: ready_next]
[→ vasya]
```

### 2. Handoff Pattern (Agent A → Agent B)

**Location:** `memory.py:249-287`, `pipeline.py:306-312`

When Marina finishes, system creates handoff record:

```json
{
  "id": "h1",
  "from": "marina",
  "to": "victoria",
  "payload": {
    "pipeline": "content_week",
    "task": "marina_to_victoria",
    "content": "3 готовых поста...",
    "context": {"chain_id": "ch_12345", "phase": "learning"}
  },
  "status": "pending",
  "ts": "2026-06-17T10:30:00+00:00"
}
```

Status transitions: `pending` → `completed` or `rejected`

### 3. Verdict System

**Valid Verdicts:**
- `ready_next` — work ready, auto-switch to next agent
- `pass` — explicit pass to next agent  
- `done` — work complete, end chain
- `needs_revision` — revert to previous agent

**Verdict Flow** (message_handler.py):
```python
verdict = extract_verdict(agent_reply)  # Parse [VERDICT: xxx]
if verdict in ("ready_next", "pass"):
    next_agent = extract_next_agent(agent_reply)  # Parse [→ agent]
    should_switch = True
```

### 4. Tool Sharing

**Shared Tools** (all agents):
```python
core_tools():
  - read_file(path)
  - write_file(path, content)
  - list_files(path)
```

**Agent-Specific Tools:**

| Agent | Unique Tools |
|-------|------------|
| Marina | instagram_get_analytics, instagram_publish_post, get_dms, instagram_get_comments |
| Victoria | generate_image, approve_post, request_revisions |
| Alina | find_clients_by_pattern, get_client_list, log_client_journey, generate_chain_id |
| Dima | measure_sales_funnel, get_gumroad_data, db_query |
| Manager | office_review, measure_metrics, list_reports, app_review, create_action |
| Rita | analyze_audience |
| Olya | web_search, monitor_competitors |
| Tyoma | telegram_send, telegram_channel_stats |
| Vasya | schedule_post, get_posting_schedule, list_scheduled |
| Lera | track_lead_funnel, get_intake_forms, send_cold_dm |

### 5. Pipeline Checkpoint System

**Location:** `pipeline.py:98-116, 264-270`

Chains can resume from failure:

```
[00:00] Start content_week
[00:05] ✓ Olya completes, state saved
[00:10] ✓ Marina completes, state saved
[00:15] ✗ Victoria fails on API error
        → State checkpoint written
[Operator reruns: python pipeline.py retry ch_12345]
[00:20] ⏭ Skip Olya + Marina, restart Victoria
[00:25] ✓ Victoria succeeds
[00:30] ✓ Vasya publishes
```

---

## ⚠️ CRITICAL ISSUES FOUND (13 Total)

### 🔴 CRITICAL (must fix before production)

#### Issue #1: No Timeout on Web API Blocking Calls
**File:** `routes.py:41-86`  
**Severity:** CRITICAL  
**Impact:** User requests hang indefinitely if Claude API is slow

```python
# Current (broken):
result = run_agent(...)  # No timeout, blocks forever

# Should be:
result = run_agent(..., timeout=30)  # Add fallback to Gemini
```

**Fix:** Add timeout + fallback in `routes.py:64`
```python
try:
    result = base.run_agent(..., timeout=30)
except TimeoutError:
    result = fall_back_to_gemini(...)  # Already exists in base.py
```

---

#### Issue #2: Victoria's Approval Gate Not Enforced in Web UI
**File:** `routes.py:120-125` (missing check)  
**Severity:** CRITICAL  
**Impact:** Unapproved content can bypass Victoria and go to Vasya

**Current Flow:**
```
User: victoria.py (edit)
User: vasya.py (schedule) ← NO approval check!
Unapproved content published
```

**Should Be:**
```
User: victoria.py (edit)
System: Check memory.get_approval("content_week:victoria")
If rejected: show feedback, don't route to Vasya
If approved: proceed to Vasya
```

**Fix:** Add this in `routes.py` before switching agents:
```python
if next_agent == "vasya":
    approval = memory.get_approval(f"{chain_id}:victoria")
    if approval and approval["status"] == "rejected":
        return {"error": f"Victoria rejected: {approval['feedback']}"}
```

---

#### Issue #3: Data Race in Parallel Chains
**File:** `memory.py:145-160` (context.json)  
**Severity:** CRITICAL  
**Impact:** If Alina (CRM) and Olya (trends) run simultaneously, context overwrites occur

**Current:**
```json
// memory/context.json (global, no segregation)
{"event": "new_lead", "data": {...}}
```

If both chains write: last write wins, data loss.

**Fix:** Segregate by chain_id:
```python
# memory/contexts/{chain_id}.json
memory/contexts/ch_lead_001.json
memory/contexts/ch_content_weekly.json
```

---

### 🟠 HIGH PRIORITY

#### Issue #4: No Rate Limiting on Instagram/Telegram
**Files:** `agent.py`, `victoria.py`, `tyoma.py`  
**Severity:** HIGH  
**Impact:** Can trigger Instagram spam detection (rate-limited replies)

**Example Problem:**
```python
# Victoria might generate 20 comment replies, all send at once
queue_comment_replies(replies)  # No rate limiting
→ Instagram flags account as spam
```

**Fix:** Implement rate limiter (framework exists but unused):
```python
# Add to memory.py
def check_rate_limit(agent, action):
    limits = {
        "instagram_comment": 5,  # per minute
        "telegram_send": 10,
        "instagram_publish": 1,  # per hour
    }
    # Check timestamp of last action, enforce limit

# Use in agent calls:
if not memory.check_rate_limit("victoria", "instagram_comment"):
    return "Rate limit exceeded, retry in 30s"
```

---

#### Issue #5: Chain Checkpoint Deduplication Flawed
**File:** `pipeline.py:264-270`  
**Severity:** HIGH  
**Impact:** Rerunning same chain can execute duplicate steps

**Problem:**
```python
# Uses context_ts to dedupe, but:
if ctx_ts == previous_ctx_ts:
    resume_from_failed_step()

# But if context DATA changed (new lead added), ts not updated
# → Rerun executes already-completed steps
```

**Fix:** Hash context data instead:
```python
import hashlib
ctx_hash = hashlib.sha256(json.dumps(ctx).encode()).hexdigest()
checkpoint_key = f"{chain_name}:{ctx_hash}"
```

---

#### Issue #6: No Deadlock Prevention for Cross-Chain Handoffs
**File:** `memory.py:101-141` (_FileLock)  
**Severity:** HIGH  
**Impact:** Circular dependencies can hang system

**Scenario:**
```
Alina waits for Lera's approval
Lera waits for Alina's client list
→ DEADLOCK (both waiting)
```

**Fix:** Add timeout + cycle detection:
```python
# Add to memory.py
def handoff_with_timeout(frm, to, payload, timeout=300):
    start = time.time()
    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"Handoff {frm}→{to} timed out (circular?)")
        # Proceed with handoff
```

---

### 🟡 MEDIUM PRIORITY

#### Issue #7: Approval Workflow Incomplete
**File:** `pipeline.py:317` (logs only, doesn't enforce)  
**Severity:** MEDIUM  
**Impact:** Approval status stored but not checked

**Current:**
```python
# Victoria's reply is logged:
memory.set_approval("content_week:victoria", "approved", reply[:500])
# But next agent doesn't check it

# Vasya just runs, doesn't know if Victoria rejected
```

**Fix:** Implement approval gate (same as Issue #2 above)

---

#### Issue #8: Session History Unbounded
**File:** `session_manager.py:68` (trim_history keeps only last 10)  
**Severity:** MEDIUM  
**Impact:** Long conversations lose early context

**Current:**
```python
history = load_history(session_id, agent_key)  # 10 last messages only
# Earlier messages about context/strategy lost
```

**Fix:** Implement sliding window + summarization:
```python
# Keep last 10, summarize older ones
if len(history) > 10:
    old_msgs = history[:-10]
    summary = summarize_messages(old_msgs)  # Use Claude
    history = [{"role": "system", "content": f"Summary: {summary}"}] + history[-10:]
```

---

#### Issue #9: Error Messages Leak Internal Paths
**File:** `base.py` (all error returns)  
**Severity:** MEDIUM  
**Impact:** Users see Windows paths like `E:\MILA GOLD\...`

**Example:**
```python
except FileNotFoundError as e:
    return f"Ошибка: {e}"  # Shows "E:\MILA GOLD\03-clients\..."
```

**Fix:** Sanitize paths:
```python
except FileNotFoundError as e:
    path = str(e).replace(str(MILA_FOLDER), "[project]")
    return f"Ошибка: {path}"
```

---

#### Issue #10: No Idempotency for Duplicate Requests
**File:** `routes.py:64-65`  
**Severity:** MEDIUM  
**Impact:** Two identical requests create two jobs, might send duplicate Instagram replies

**Current:**
```
User clicks "Send comment" twice (network lag)
→ 2 identical jobs created
→ 2 identical replies sent to Instagram
```

**Fix:** Implement dedupe in job_queue (logic exists in task_queue):
```python
def enqueue_job(agent_key, message, dedup_key=None):
    if dedup_key and job_exists(dedup_key):
        return existing_job
    # Create new job
```

---

### 🟢 LOW PRIORITY (design notes)

#### Issue #11: Context Tag Parsing Fragile
**File:** `message_handler.py:8-12`  
**Severity:** LOW  
**Impact:** Agent names with underscores fail

```python
regex = r'\[→\s*(\w+)\]'  # Matches word chars, ok
# But validates against hardcoded agent list
```

**Fix:** Add whitelist validation:
```python
VALID_AGENTS = {"marina", "victoria", "alina", "dima", "tyoma", "olya", "vasya", "lera", "rita", "manager", "producer"}
if agent not in VALID_AGENTS:
    raise ValueError(f"Unknown agent: {agent}")
```

---

#### Issue #12: No Timeout on File Operations
**File:** `base.py:225-263`  
**Severity:** LOW  
**Impact:** read_file/write_file can hang on network shares

```python
# Only run_command has timeout:
result = subprocess.run(..., timeout=60)

# File ops do not:
content = open(path).read()  # Can hang forever on network
```

**Fix:** Add timeout context manager:
```python
def read_file_safe(path, timeout=10):
    with timeout_handler(timeout):
        return open(path).read()
```

---

#### Issue #13: Memory.py Not Thread-Safe for Multi-User
**File:** `memory.py:101-141` (_FileLock)  
**Severity:** LOW (current single-user, but note for future)  
**Impact:** If 2 operators use webapp simultaneously, lock contention

**Current:** File-based locking with exponential backoff

**Note for Future:** When scaling to multi-user, migrate to Supabase (framework already exists: `db_query()`)

---

## ✅ WHAT'S WORKING WELL

1. **Context Propagation** ✓
   - Context flows correctly through all layers (tags + system injection)
   - `from_agent`, `chain_id` preserved across handoffs

2. **Checkpoint Recovery** ✓
   - Failed chains resume from failed step (atomic temp file + rename)
   - State not lost on crash

3. **Modular Agent Architecture** ✓
   - Agents don't know about each other (low coupling)
   - Easy to add new agent (copy victoria.py, register in agent_manager.py)

4. **Tool Sharing** ✓
   - Core tools (read/write/list) available to all
   - Agent-specific tools cleanly separated

5. **Verdict System** ✓
   - Clear status indicators for approval/rejection
   - Auto-switching based on verdict works

---

## 📋 RECOMMENDED ACTION PLAN

### IMMEDIATE (This Week)

**Priority 1: Add Timeout to Web API** (2 hours)
```python
# routes.py, add to run_agent call:
result = base.run_agent(..., timeout=30)
# + fallback to Gemini
```

**Priority 2: Implement Approval Gate in Web UI** (3 hours)
```python
# routes.py, before next_agent switch:
approval = memory.get_approval(f"{chain_id}:victoria")
if approval["status"] == "rejected":
    return {"error": approval["feedback"]}
```

**Priority 3: Fix Parallel Chain Data Race** (4 hours)
```python
# memory.py, segregate context by chain_id:
memory/contexts/{chain_id}.json instead of memory/context.json
```

### SHORT TERM (Week 1-2)

- [ ] Complete approval workflow (make decisions binding)
- [ ] Implement handoff retry with exponential backoff
- [ ] Add rate limiting (framework exists, just activate it)

### MEDIUM TERM (Sprint)

- [ ] Automatic chain healing (fallback to next agent on failure)
- [ ] Implement idempotency for job_queue
- [ ] Add cycle detection for locks

### LONG TERM (Architecture)

- [ ] Migrate memory to Supabase (multi-user ready)
- [ ] Implement true async (event-driven instead of blocking)
- [ ] Add formal agent-to-agent protocol (JSON-RPC or gRPC)

---

## 📚 KEY FILES FOR REFERENCE

| File | Lines | Purpose | Changes Needed |
|------|-------|---------|-----------------|
| `base.py` | 537-588 | Context injection | Add timeout parameter |
| `routes.py` | 41-86, 120-125 | Web API | Add timeout, approval gate |
| `message_handler.py` | 125-166 | Context routing | Validate agent names |
| `memory.py` | 145-160, 249-287 | Shared state | Segregate by chain_id |
| `pipeline.py` | 264-270, 306-312 | Chain execution | Fix dedup hash |
| `session_manager.py` | 68 | History | Add summarization |
| `agent_manager.py` | 1-42 | Registry | Enforces whitelist (ok) |

---

## 🎯 CONCLUSION

**Current Status:** ⚠️ **Functionally working but incomplete**

The system successfully orchestrates 8 agents through a hybrid blocking-pipeline architecture. Context flows correctly, recovery works, and modular design is sound.

**But:** 3 critical issues block production use:
1. Timeout on web API (hangs user)
2. Approval gate not enforced (bypasses review)
3. Data race in parallel chains (lost context)

**Effort to reach Production Ready:** ~30 hours
- Immediate fixes: 9 hours
- Short-term: 12 hours
- Medium-term: 9 hours

**Current Use Case:** Single-operator autonomous loops (✓ works)  
**Production Use Case:** Multi-user web UI with approval workflows (need fixes above)

---

**Report Date:** 2026-06-17  
**Audit by:** Multi-agent Explore Agent  
**Confidence Level:** High (reviewed 15+ core files, 500+ lines analyzed)
