# n8n Integration Guide: Triggering MILA Office Chains

This guide explains how to set up n8n workflows to trigger and monitor mila-office agent chains, with comprehensive examples for content generation, scheduling, and error handling.

## Overview

The integration works via **two bridge services**:

1. **n8n_bridge.py** (port 5051) — HTTP API for executing commands and enqueuing tasks
2. **n8n_webhook.py** (port 5052) — Bi-directional webhook server for chain monitoring and status callbacks

Both listen only on `127.0.0.1` and require Bearer token authentication.

---

## 1. Setup: Prerequisites and Configuration

### 1.1 Environment Variables

Add these to `tools/.env` or `E:\MILA GOLD\.env`:

```env
# Bridge service tokens
N8N_BRIDGE_PORT=5051
N8N_BRIDGE_TOKEN=<generate: python -c "import secrets;print(secrets.token_urlsafe(32))">
N8N_BRIDGE_OFFICE_TIMEOUT=3600
N8N_BRIDGE_TOOLS_TIMEOUT=600

# Webhook service (for chain monitoring)
N8N_WEBHOOK_PORT=5052
N8N_WEBHOOK_TOKEN=<same or different token>
N8N_STATUS_WEBHOOK_URL=http://127.0.0.1:5678/webhook/status
N8N_ERROR_WEBHOOK_URL=http://127.0.0.1:5678/webhook/errors
N8N_WEBHOOK_TIMEOUT=300

# n8n callback (optional, for n8n to notify us on its own completion)
N8N_DONE_WEBHOOK=http://127.0.0.1:5678/webhook/office-done
```

Generate tokens:
```bash
python -c "import secrets;print(secrets.token_urlsafe(32))"
```

### 1.2 Starting the Bridge Services

**Option A: Batch files (Windows)**

Create `tools/start-mila-automation.cmd`:

```batch
@echo off
REM Start n8n bridge
start "n8n_bridge" cmd /k "cd mila-office && python n8n_bridge.py"
REM Start n8n webhook
start "n8n_webhook" cmd /k "cd mila-office && python n8n_webhook.py"
REM Start local n8n
start "n8n" cmd /k "npx n8n start"
```

**Option B: Manual startup**

```bash
# Terminal 1: n8n bridge
cd mila-office
python n8n_bridge.py

# Terminal 2: n8n webhook
cd mila-office
python n8n_webhook.py

# Terminal 3: n8n (if local)
npx n8n start
```

### 1.3 Verify Setup

```bash
# Check n8n bridge
curl -H "Authorization: Bearer <token>" http://127.0.0.1:5051/health

# Check n8n webhook
curl -H "Authorization: Bearer <token>" http://127.0.0.1:5052/health
```

---

## 2. Webhook URL Configuration in n8n

In n8n UI, use **HTTP Request** nodes to call the bridges. Configure as follows:

### For n8n_bridge.py endpoints:

```
Method: POST
URL: http://127.0.0.1:5051/v1/...
Authentication: Header
  Key: Authorization
  Value: Bearer <N8N_BRIDGE_TOKEN>
Headers:
  Content-Type: application/json
```

### For n8n_webhook.py endpoints:

```
Method: POST / GET
URL: http://127.0.0.1:5052/api/n8n/...
Authentication: Header
  Key: Authorization
  Value: Bearer <N8N_WEBHOOK_TOKEN>
Headers:
  Content-Type: application/json
```

---

## 3. Core Endpoints Reference

### n8n_bridge.py Endpoints

#### 3.1 Enqueue Task (Queue-based, with auto-retry)

**Endpoint:** `POST /v1/pipeline/<chain>`

Enqueues a pipeline chain into the task memory (job queue). Returns immediately; task runs asynchronously via the worker.

**Request:**
```json
{
  "data": {
    "keyword": "свежие тренды",
    "format": "brief",
    "notify": true
  },
  "priority": 5,
  "dedupe_key": "weekly_brief_2026-06-08"
}
```

**Query params:**
- `notify=1` — Send result to Telegram after completion
- `direct=1` — Run immediately (if policy allows)

**Response:**
```json
{
  "ok": true,
  "queued": true,
  "chain": "monday_brief",
  "task": {
    "id": "task-uuid",
    "chain": "monday_brief",
    "status": "pending",
    "priority": 5
  }
}
```

**Use case:** Daily or weekly scheduled tasks, content generation pipelines.

---

#### 3.2 Run Pipeline Directly

**Endpoint:** `POST /v1/pipeline/<chain>?direct=1`

Execute a chain immediately (blocks until completion). Only available for chains allowed by `policies.can_run_direct()`.

**Request:**
```json
{
  "data": {
    "topic": "relations",
    "depth": "deep"
  }
}
```

**Response (blocks):**
```json
{
  "ok": true,
  "chain": "content_week",
  "direct": true,
  "notify": false,
  "returncode": 0,
  "stdout": "Chain completed..."
}
```

**Use case:** Real-time content generation on demand (e.g., webhook from Telegram customer).

---

#### 3.3 Get Task Status

**Endpoint:** `GET /v1/tasks/<task_id>`

Retrieve current status of an enqueued task.

**Response:**
```json
{
  "id": "task-uuid",
  "chain": "monday_brief",
  "status": "running|pending|completed|failed",
  "priority": 5,
  "progress": 45,
  "result": { ... },
  "error": null,
  "started_at": "2026-06-08T14:00:00Z",
  "completed_at": null
}
```

---

#### 3.4 List All Tasks

**Endpoint:** `GET /v1/tasks?status=running&limit=10`

**Response:**
```json
{
  "ok": true,
  "tasks": [ { task object }, ... ]
}
```

---

#### 3.5 Retry a Task

**Endpoint:** `POST /v1/tasks/<task_id>/retry`

Requeue a failed task.

**Request (optional):**
```json
{
  "reset_attempts": false
}
```

---

#### 3.6 Cancel a Task

**Endpoint:** `POST /v1/tasks/<task_id>/cancel`

**Request (optional):**
```json
{
  "reason": "User cancelled from n8n"
}
```

---

#### 3.7 Unblock a Blocked Task

**Endpoint:** `POST /v1/tasks/<task_id>/unblock`

Unblock a task that is waiting on external input.

---

### n8n_webhook.py Endpoints

#### 3.8 Trigger Chain with Monitoring

**Endpoint:** `POST /api/n8n/trigger-chain`

Start a chain and monitor its execution. Returns immediately; monitoring happens asynchronously.

**Request:**
```json
{
  "chain_config": {
    "chain_name": "content_week",
    "input_data": {
      "theme": "self-care",
      "posts_count": 7
    }
  },
  "from_agent": "olya",
  "to_agent": "marina",
  "chain_id": "content-week-2026-06-08",
  "n8n_webhook_url": "http://127.0.0.1:5678/webhook/status",
  "priority": 5
}
```

**Response (202 Accepted):**
```json
{
  "ok": true,
  "chain_id": "content-week-2026-06-08",
  "task_id": "task-uuid",
  "status": "pending",
  "message": "Chain triggered and monitoring started"
}
```

**Status updates sent to `n8n_webhook_url`:**
```json
{
  "ok": true,
  "chain_id": "content-week-2026-06-08",
  "chain_name": "content_week",
  "status": "pending|running|success|failed|timeout",
  "progress": 0-100,
  "started_at": "...",
  "completed_at": "...",
  "result": { ... },
  "error": null,
  "timestamp": "2026-06-08T14:05:00Z"
}
```

---

#### 3.9 Get Chain Execution Status

**Endpoint:** `GET /api/n8n/chain/<chain_id>`

Retrieve full details of a chain execution.

**Response:**
```json
{
  "ok": true,
  "execution": {
    "chain_id": "...",
    "chain_name": "content_week",
    "from_agent": "olya",
    "to_agent": "marina",
    "status": "success",
    "progress": 100,
    "started_at": "...",
    "completed_at": "...",
    "result": { ... },
    "error": null,
    "n8n_webhook_url": "...",
    "task_id": "...",
    "input_data": { ... }
  }
}
```

---

#### 3.10 Cancel Chain Execution

**Endpoint:** `POST /api/n8n/chain/<chain_id>/cancel`

**Request (optional):**
```json
{
  "reason": "Cancelled by user"
}
```

---

#### 3.11 Retry Failed Chain

**Endpoint:** `POST /api/n8n/chain/<chain_id>/retry`

Creates a new execution with the same input. Returns new `chain_id` and `task_id`.

**Response:**
```json
{
  "ok": true,
  "new_chain_id": "new-uuid",
  "task_id": "task-uuid",
  "status": "pending"
}
```

---

#### 3.12 List All Chain Executions

**Endpoint:** `GET /api/n8n/executions?status=running&limit=10`

**Query params:**
- `status` — filter by `pending`, `running`, `success`, `failed`, `cancelled`, `timeout`
- `limit` — max results (default 100)

**Response:**
```json
{
  "ok": true,
  "count": 3,
  "total": 15,
  "executions": [ { execution object }, ... ]
}
```

---

#### 3.13 Schedule-Based Trigger

**Endpoint:** `POST /api/n8n/schedule-trigger`

Handle cron-scheduled workflows from n8n.

**Request:**
```json
{
  "chain_name": "weekly_report",
  "schedule": {
    "cron": "0 17 * * 0",
    "timezone": "America/Toronto",
    "trigger_time": "2026-06-08T21:00:00Z"
  },
  "n8n_webhook_url": "http://127.0.0.1:5678/webhook/status"
}
```

**Response (202 Accepted):**
```json
{
  "ok": true,
  "chain_id": "...",
  "task_id": "...",
  "status": "pending",
  "scheduled": true
}
```

---

#### 3.14 Receive n8n Status Notification

**Endpoint:** `POST /api/n8n/notify`

Reverse webhook: n8n notifies us about its own workflow execution.

**Request:**
```json
{
  "workflow_id": "...",
  "execution_id": "...",
  "status": "success|error",
  "message": "Workflow completed",
  "result": { ... }
}
```

---

#### 3.15 Error Callback from n8n

**Endpoint:** `POST /api/n8n/error-callback`

Log errors from n8n workflows directly.

**Request:**
```json
{
  "chain_id": "...",
  "workflow_id": "...",
  "error_code": "TIMEOUT",
  "error_message": "Chain did not complete within 300s",
  "stack_trace": "..."
}
```

---

#### 3.16 Retrieve Chain Logs

**Endpoint:** `GET /api/n8n/logs/<chain_id>`

Get all logged interactions for a chain.

**Response:**
```json
{
  "ok": true,
  "chain_id": "...",
  "log_entries": [
    {
      "timestamp": "2026-06-08T14:00:00Z",
      "event": "TRIGGER_REQUEST",
      "details": { ... }
    },
    {
      "timestamp": "2026-06-08T14:00:05Z",
      "event": "CHAIN_ENQUEUED",
      "details": { "task_id": "...", "priority": 5 }
    },
    ...
  ]
}
```

---

## 4. Example Workflows

### 4.1 Daily Content Generation (Queue-Based)

**n8n workflow: `01-daily-content-gen`**

Trigger: Cron `0 9 * * MON` (Monday 9 AM)

**Workflow steps:**

1. **Cron trigger** — Every Monday at 9 AM

2. **Write context** (HTTP Request, POST)
   ```
   URL: http://127.0.0.1:5051/v1/context
   Body:
   {
     "event": "weekly_content_kick",
     "data": {
       "week": "2026-W24",
       "theme": "{{ $node."Set week theme".json.theme }}",
       "priority": "high"
     }
   }
   ```

3. **Enqueue content_week chain** (HTTP Request, POST)
   ```
   URL: http://127.0.0.1:5051/v1/pipeline/content_week?notify=1
   Body:
   {
     "data": {
       "week": "{{ $node."Set week theme".json.week }}",
       "theme": "{{ $node."Set week theme".json.theme }}"
     },
     "priority": 5,
     "dedupe_key": "content_week_{{ $node."Set week theme".json.week }}"
   }
   ```

4. **Save task ID** (Set node)
   ```
   task_id = {{ $node."Enqueue content_week chain".json.task.id }}
   ```

5. **Poll for completion** (Loop, until task status = "completed")
   ```
   GET http://127.0.0.1:5051/v1/tasks/{{ $node."Save task ID".json.task_id }}
   Every 10 seconds, timeout 30 minutes
   ```

6. **On completion** — Notification sent automatically (chain triggered with `notify=1`)

---

### 4.2 Post Publishing with Real-Time Monitoring

**n8n workflow: `02-publish-due-realtime`**

Trigger: Manual webhook or hourly cron

**Workflow steps:**

1. **Trigger chain via webhook** (HTTP Request, POST)
   ```
   URL: http://127.0.0.1:5052/api/n8n/trigger-chain
   Body:
   {
     "chain_config": {
       "chain_name": "publish_due",
       "input_data": {
         "batch_size": 5,
         "include_reels": true
       }
     },
     "from_agent": "vasya",
     "to_agent": "marina",
     "chain_id": "publish-{{ now().format('YYYY-MM-DD-HHmmss') }}",
     "n8n_webhook_url": "http://127.0.0.1:5678/webhook/publish-status",
     "priority": 8
   }
   ```

2. **Receive webhook notification** (incoming status webhook)
   ```
   Listen on: POST http://127.0.0.1:5678/webhook/publish-status
   
   When status = "success":
     - Log result
     - Send Telegram notification
     - Archive to reports/
   
   When status = "failed" or "timeout":
     - Alert Telegram
     - Trigger retry
   ```

3. **Conditional retry** (if failed)
   ```
   IF status = "failed" THEN
     POST http://127.0.0.1:5052/api/n8n/chain/<chain_id>/retry
     WITH { "reason": "Automated retry" }
   ```

**Incoming webhook receives:**
```json
{
  "ok": true,
  "chain_id": "publish-2026-06-08-090000",
  "chain_name": "publish_due",
  "status": "running|success|failed",
  "progress": 45,
  "started_at": "2026-06-08T09:00:00Z",
  "completed_at": null,
  "result": { "posts_published": 5 },
  "error": null,
  "timestamp": "2026-06-08T09:05:00Z"
}
```

---

### 4.3 Customer Response Chain (Direct + Monitoring)

**n8n workflow: `03-customer-response-realtime`**

Trigger: Webhook from Telegram or form submission

**Workflow steps:**

1. **Receive customer message** (webhook trigger)
   ```
   POST http://127.0.0.1:5678/webhook/customer-query
   Body:
   {
     "customer_id": "tg_123456",
     "message": "Цена практикума?",
     "source": "telegram"
   }
   ```

2. **Create context** (HTTP Request, POST)
   ```
   URL: http://127.0.0.1:5051/v1/context
   Body:
   {
     "event": "customer_query",
     "data": {
       "customer_id": "{{ $node.Webhook.json.customer_id }}",
       "message": "{{ $node.Webhook.json.message }}",
       "source": "{{ $node.Webhook.json.source }}"
     }
   }
   ```

3. **Trigger response chain** (HTTP Request, POST to webhook)
   ```
   URL: http://127.0.0.1:5052/api/n8n/trigger-chain
   Body:
   {
     "chain_config": {
       "chain_name": "customer_reply",
       "input_data": {
         "customer_id": "{{ $node.Webhook.json.customer_id }}",
         "query": "{{ $node.Webhook.json.message }}"
       }
     },
     "from_agent": "n8n",
     "to_agent": "lera",
     "chain_id": "reply-{{ $node.Webhook.json.customer_id }}-{{ now().unix() }}",
     "priority": 9
   }
   ```

4. **Monitor and respond** (incoming webhook)
   ```
   Listen on: http://127.0.0.1:5678/webhook/reply-status
   
   When status = "success":
     - Extract response from result
     - Send to customer via Telegram/email
     - Log to CRM (03-clients)
   
   When status = "failed":
     - Fallback to template response
     - Flag for manual review
   ```

---

### 4.4 Scheduled Weekly Automation

**n8n workflow: `04-weekly-schedule`**

Trigger: Cron schedule (multiple)

**Workflow steps:**

1. **Monday 6:00 AM** — Content week planning
   ```
   POST http://127.0.0.1:5052/api/n8n/schedule-trigger
   Body:
   {
     "chain_name": "content_week",
     "schedule": {
       "cron": "0 6 * * 1",
       "timezone": "America/Toronto",
       "trigger_time": "{{ now().toISO() }}"
     },
     "n8n_webhook_url": "http://127.0.0.1:5678/webhook/content-status"
   }
   ```

2. **Monday 7:00 AM** — Brief/trends
   ```
   POST http://127.0.0.1:5052/api/n8n/schedule-trigger
   Body:
   {
     "chain_name": "monday_brief",
     "schedule": {
       "cron": "0 7 * * 1",
       "timezone": "America/Toronto",
       "trigger_time": "{{ now().toISO() }}"
     }
   }
   ```

3. **Sunday 5:00 PM** — Analytics + KPI
   ```
   POST http://127.0.0.1:5051/v1/pipeline/sunday_analytics?notify=1
   (or POST to trigger-chain with schedule info)
   ```

4. **Sunday 6:00 PM** — Weekly report
   ```
   POST http://127.0.0.1:5051/v1/pipeline/weekly_report?notify=1
   ```

All incoming webhooks update shared dashboards or feed into the next week's planning.

---

## 5. Error Handling & Notifications

### 5.1 Chain Timeout Handling

**Webhook config:**
```json
{
  "N8N_WEBHOOK_TIMEOUT": 300,  // 5 minutes
  "N8N_ERROR_WEBHOOK_URL": "http://127.0.0.1:5678/webhook/errors"
}
```

**If chain does not complete within timeout:**
```json
{
  "ok": false,
  "chain_id": "...",
  "status": "timeout",
  "error": "Chain did not complete within 300s",
  "timestamp": "..."
}
```

**n8n response flow:**
1. Receive `status: "timeout"` on webhook
2. Log to file
3. POST to error webhook (if configured)
4. Option: Auto-retry with longer timeout, or flag for manual review

---

### 5.2 Task Retry Logic

**Automatic retry (n8n_bridge.py):**

Tasks in the queue can be retried via:
```
POST http://127.0.0.1:5051/v1/tasks/<task_id>/retry
```

**In n8n workflow:**
```
IF task.status = "failed" AND retry_count < 3 THEN
  POST /v1/tasks/<task_id>/retry
  WAIT 30 seconds
  GET /v1/tasks/<task_id>
```

**Backoff strategy:**
- Retry 1: Immediate
- Retry 2: 30 seconds
- Retry 3: 2 minutes
- Max 3 retries, then flag for manual intervention

---

### 5.3 Error Webhook Callback

**Sending errors back to n8n:**

From mila-office (e.g., chain fails), post to:
```
POST http://127.0.0.1:5678/webhook/office-errors
Body:
{
  "chain_id": "...",
  "workflow_id": "...",
  "error_code": "CHAIN_FAILED",
  "error_message": "Agent returned None",
  "stack_trace": "...",
  "timestamp": "..."
}
```

**In n8n, handle error webhook:**
```
Listen on: POST http://127.0.0.1:5678/webhook/office-errors

Actions:
  - Log to n8n execution history
  - Increment error counter
  - Send admin alert (Telegram/email)
  - Trigger incident investigation chain (if critical)
```

---

## 6. Monitoring Chain Results

### 6.1 Dashboard: Active Chains

**Query endpoint:**
```
GET http://127.0.0.1:5052/api/n8n/executions?status=running
```

**n8n dashboard node (Set node):**
```javascript
{
  "active_chains": $node."Get executions".json.executions,
  "count": $node."Get executions".json.count,
  "total": $node."Get executions".json.total
}
```

**Display in n8n UI:**
- Table: chain_id, chain_name, progress, started_at
- Color-code by status (running = blue, success = green, failed = red)

---

### 6.2 Periodic Status Check

**n8n workflow: `monitoring-check`**

Trigger: Every 5 minutes

**Steps:**
1. **Get all running chains**
   ```
   GET http://127.0.0.1:5052/api/n8n/executions?status=running&limit=20
   ```

2. **For each running chain, check logs**
   ```
   FOR EACH execution IN executions:
     GET http://127.0.0.1:5052/api/n8n/logs/<execution.chain_id>
   ```

3. **Alert if blocked for >10 minutes**
   ```
   IF execution.progress = (last_progress) AND
      (now() - execution.started_at) > 10 minutes THEN
     SEND Telegram alert: "Chain {{ execution.chain_id }} appears stuck"
   ```

4. **Update web dashboard**
   - Write to file: `reports/n8n_executions_summary.json`
   - Include: active count, recent completions, failure rate

---

### 6.3 Log Retrieval and Analysis

**Get logs for a specific chain:**
```
GET http://127.0.0.1:5052/api/n8n/logs/content-week-2026-06-08
```

**Log file location on disk:**
```
E:\MILA GOLD\reports\n8n_logs\chain_<chain_id>.log
```

**Each log entry:**
```json
{
  "timestamp": "2026-06-08T14:00:05Z",
  "chain_id": "...",
  "event": "TRIGGER_REQUEST|CHAIN_ENQUEUED|STATUS_UPDATE|FINAL_STATUS|CHAIN_CANCELLED|N8N_ERROR",
  "details": { ... }
}
```

**In n8n, parse logs for debugging:**
```javascript
// Extract last 3 errors from chain logs
$node."Get logs".json.log_entries
  .filter(e => e.event.includes("ERROR"))
  .slice(-3)
```

---

### 6.4 Results File Output

**After chain completion:**

```
reports/
  chain_<chain_id>_result.json      // Final result from chain
  n8n_executions_summary.json        // Active/recent executions
  n8n_logs/
    chain_<chain_id>.log             // Full interaction log
```

**Example result file:**
```json
{
  "chain_id": "content-week-2026-06-08",
  "chain_name": "content_week",
  "status": "success",
  "result": {
    "posts_generated": 7,
    "reels_planned": 3,
    "content_calendar": [ ... ],
    "estimated_reach": 12500
  },
  "completed_at": "2026-06-08T14:45:00Z",
  "execution_time_seconds": 2700
}
```

---

## 7. Common Patterns & Best Practices

### 7.1 Pattern: Fire-and-Forget (Queue-Based)

Use `POST /v1/pipeline/<chain>` for background tasks.

**When to use:**
- Scheduled content generation (Monday mornings)
- Weekly analytics reports (Sunday evenings)
- Batch operations (cleanup, archival)

**Advantages:**
- Returns immediately
- Auto-retry on failure
- Task memory persists across restarts
- Configurable priority

**Example:**
```
POST http://127.0.0.1:5051/v1/pipeline/weekly_report?notify=1
Body: { "data": { "week": "2026-W24" }, "priority": 5 }
→ Returns task_id, continues in background
→ Telegram notification when done
```

---

### 7.2 Pattern: Monitored Execution (Webhook-Based)

Use `POST /api/n8n/trigger-chain` for tasks requiring real-time feedback.

**When to use:**
- Customer-facing responses (fast feedback expected)
- Content publishing (need to know when live)
- Dashboards (progress updates)

**Advantages:**
- Bi-directional webhook communication
- Progress updates every 5 seconds
- Per-chain log files
- Chainable: chain output feeds next chain

**Example:**
```
POST http://127.0.0.1:5052/api/n8n/trigger-chain
Body:
{
  "chain_config": {
    "chain_name": "customer_reply",
    "input_data": { "customer_id": "tg_123" }
  },
  "n8n_webhook_url": "http://127.0.0.1:5678/webhook/reply-status"
}
→ Returns immediately with chain_id
→ Status webhook called: pending → running → success
→ n8n workflow receives status updates and acts on them
```

---

### 7.3 Pattern: Direct Execution (Synchronous)

Use `POST /v1/pipeline/<chain>?direct=1` for immediate results.

**When to use:**
- Real-time API endpoints
- Synchronous request/response
- Small chains (<1 minute)

**Advantages:**
- Immediate result in response
- No webhook needed
- Blocks until completion

**Disadvantages:**
- Timeout if >TIMEOUT_OFFICE (3600s)
- Ties up HTTP connection
- No retry/queue support

**Example:**
```
POST http://127.0.0.1:5051/v1/pipeline/instant_summary?direct=1
Body: { "data": { "topic": "sales" } }
→ Blocks 30 seconds
→ Returns with result in response
```

---

### 7.4 Pattern: Scheduled Automation

Use `POST /api/n8n/schedule-trigger` for cron-based workflows.

**When to use:**
- Daily/weekly/monthly automations
- Timezone-aware scheduling
- Predictable, repeating tasks

**Advantages:**
- Timestamp tracking
- Timezone support
- Schedule metadata in logs
- No external cron needed

**Example:**
```
POST http://127.0.0.1:5052/api/n8n/schedule-trigger
Body:
{
  "chain_name": "analytics_daily",
  "schedule": {
    "cron": "0 18 * * *",
    "timezone": "America/Toronto",
    "trigger_time": "2026-06-08T22:00:00Z"
  }
}
```

---

## 8. Troubleshooting

### 8.1 Bridge Not Starting

**Error:** `ОТКАЗ: N8N_BRIDGE_TOKEN не задан`

**Fix:**
```bash
# Generate token
python -c "import secrets;print(secrets.token_urlsafe(32))"

# Add to tools/.env
N8N_BRIDGE_TOKEN=<generated-token>

# Restart bridge
python n8n_bridge.py
```

---

### 8.2 "Unauthorized" (401) Errors

**Issue:** n8n requests return 401

**Debug:**
```bash
# Verify token in HTTP Request node matches N8N_BRIDGE_TOKEN
Authorization: Bearer <token>

# Test with curl
curl -H "Authorization: Bearer <token>" http://127.0.0.1:5051/health
```

---

### 8.3 Chain Timeout

**Issue:** Status = "timeout"

**Causes:**
- Chain execution exceeded `N8N_WEBHOOK_TIMEOUT` (default 300s)
- Network issue, bridge crashed
- Agent blocked waiting for input

**Fix:**
1. Check chain logs: `GET /api/n8n/logs/<chain_id>`
2. Increase timeout: `N8N_WEBHOOK_TIMEOUT=600` (in .env)
3. Manually retry: `POST /api/n8n/chain/<chain_id>/retry`

---

### 8.4 Task Stuck in "pending"

**Issue:** Task never starts

**Debug:**
```bash
# Check task status
GET http://127.0.0.1:5051/v1/tasks/<task_id>

# Check worker is running
python mila-office/pipeline.py worker
```

**Fix:**
- Ensure `pipeline.py worker` is running (or n8n calls `/v1/tasks/worker`)
- Check policies: `policies.can_run_direct(chain)` must be true
- Check agent availability (memory.py lock contention)

---

### 8.5 Webhook Not Received

**Issue:** n8n webhook not called on chain completion

**Debug:**
```bash
# Verify webhook URL is reachable from local network
curl -X POST http://127.0.0.1:5678/webhook/status \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Check n8n webhook logs
# In n8n UI: Workflows > <workflow> > Executions > click execution
```

**Fix:**
- Ensure `N8N_STATUS_WEBHOOK_URL` is set correctly
- Ensure n8n webhook endpoint exists and is active
- Check firewall (unlikely on 127.0.0.1, but check if n8n on different host)
- Try manual webhook test from curl

---

## 9. Quick Reference: Common Chains

| Chain | Endpoint | Trigger | Monitor |
|-------|----------|---------|---------|
| `content_week` | `POST /v1/pipeline/content_week` | Monday 6 AM | Optional webhook |
| `monday_brief` | `POST /v1/pipeline/monday_brief` | Monday 7 AM | Optional webhook |
| `publish_due` | `POST /v1/tools/publish_due` | Hourly | Via bridge |
| `weekly_report` | `POST /v1/pipeline/weekly_report` | Sunday 5 PM | Notify=1 |
| `customer_reply` | `POST /api/n8n/trigger-chain` | Webhook | Required webhook |
| `new_client` | `POST /v1/lead` | Lead form | Via bridge |
| `sunday_analytics` | `POST /v1/pipeline/sunday_analytics` | Sunday 4 PM | Optional |

---

## 10. Advanced: Custom Chain Integration

### Adding a New Chain

**Step 1: Define pipeline in `mila-office/pipeline.py`**
```python
def run_custom_analysis():
    """Custom analysis chain: Rita → Dima → Marina."""
    state = _load_state("custom_analysis")
    ...
    _save_state("custom_analysis", state)
```

**Step 2: Add to `_OFFICE_SCRIPTS` in `n8n_bridge.py`**
```python
_OFFICE_SCRIPTS = {"pipeline.py", "n8n_context.py"}
# Already includes pipeline.py, so custom_analysis runs via:
# POST /v1/pipeline/custom_analysis
```

**Step 3: Configure policy in `mila-office/policies.py`**
```python
def default_priority(chain):
    if chain == "custom_analysis":
        return 6  # Higher than default (5)
    ...

def can_run_direct(chain):
    return chain in ("instant_summary", "custom_analysis")
```

**Step 4: Test in n8n**
```
POST http://127.0.0.1:5051/v1/pipeline/custom_analysis
Body: { "data": { ... } }
```

---

## Summary

| Feature | Endpoint | Blocking | Use Case |
|---------|----------|----------|----------|
| Enqueue + Auto-Retry | `POST /v1/pipeline/<chain>` | No | Scheduled tasks, batch |
| Direct Execution | `POST /v1/pipeline/<chain>?direct=1` | Yes | Real-time, small chains |
| Monitor + Webhook | `POST /api/n8n/trigger-chain` | No (async monitor) | Customer-facing, dashboards |
| Schedule Trigger | `POST /api/n8n/schedule-trigger` | No | Cron-based automation |
| List Tasks | `GET /v1/tasks` | No | Dashboard, status check |
| Chain Logs | `GET /api/n8n/logs/<chain_id>` | No | Debugging, audit trail |
| Error Callback | `POST /api/n8n/error-callback` | No | Error logging, alerts |

Both bridges run on `127.0.0.1` and require Bearer token auth. Start both services, set `N8N_BRIDGE_TOKEN` + `N8N_WEBHOOK_TOKEN` in `.env`, and configure n8n HTTP Request nodes with the token header.
