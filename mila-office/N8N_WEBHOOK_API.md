# n8n Webhook API — Chain Execution & Monitoring

Bi-directional integration layer between n8n workflows and MILA Office agent chains.

## Overview

`n8n_webhook.py` provides:
- **Chain triggering** from n8n: start agent chains with input data
- **Status monitoring**: real-time progress tracking with webhook callbacks
- **Schedule support**: handle n8n cron-based triggers
- **Error handling**: detailed error logging and callback routes
- **Task queueing**: integrates with `memory.py` task system

## Startup

```bash
cd mila-office
python n8n_webhook.py
```

Listens on `127.0.0.1:5052` (configurable via `N8N_WEBHOOK_PORT`).

## Configuration

Set in root `.env` or `tools/.env`:

```env
# Service
N8N_WEBHOOK_PORT=5052
N8N_WEBHOOK_TOKEN=<generate: python -c "import secrets;print(secrets.token_urlsafe(32))">

# Webhook callbacks to n8n
N8N_STATUS_WEBHOOK_URL=http://localhost:5678/webhook/office-status
N8N_ERROR_WEBHOOK_URL=http://localhost:5678/webhook/office-error  # optional; defaults to STATUS_WEBHOOK

# Chain monitoring
N8N_WEBHOOK_TIMEOUT=300  # max seconds to wait for chain completion
```

## Authentication

All endpoints require Bearer token:

```
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

**Example cURL:**
```bash
curl -H "Authorization: Bearer abc123..." http://127.0.0.1:5052/api/n8n/executions
```

## Endpoints

### 1. Health Check

```
GET /health
```

No auth required.

**Response:**
```json
{
  "ok": true,
  "service": "mila-n8n-webhook",
  "port": 5052,
  "executions_active": 3
}
```

---

### 2. Trigger Chain

```
POST /api/n8n/trigger-chain
Authorization: Bearer <token>
Content-Type: application/json
```

Start an agent chain from n8n.

**Request:**
```json
{
  "chain_config": {
    "chain_name": "content_week",
    "input_data": {
      "week": "2026-06-08",
      "focus": "relationship trends"
    }
  },
  "from_agent": "n8n",
  "to_agent": "olya",
  "chain_id": "weekly-content-2026-06-08",
  "n8n_webhook_url": "http://localhost:5678/webhook/office-status",
  "priority": 5
}
```

**Field descriptions:**
- `chain_config.chain_name` (required): name of chain (e.g. `new_client`, `content_week`, `weekly_report`)
- `chain_config.input_data`: context data passed to agents
- `from_agent`: originator (e.g. `n8n`, `stasya`)
- `to_agent`: target agent or `auto`
- `chain_id`: custom ID for tracking (generated if omitted)
- `n8n_webhook_url`: where to send status updates
- `priority`: 1–10, lower = higher priority

**Response (202 Accepted):**
```json
{
  "ok": true,
  "chain_id": "weekly-content-2026-06-08",
  "task_id": "task_123abc...",
  "status": "pending",
  "message": "Chain triggered and monitoring started"
}
```

**Flow:**
1. Chain enqueued in `memory.py` as a task
2. Monitoring thread spawned (background)
3. Response returns immediately (async)
4. Monitor sends periodic status updates to `n8n_webhook_url`
5. Final status sent on completion/timeout

---

### 3. Get Chain Status

```
GET /api/n8n/chain/<chain_id>
Authorization: Bearer <token>
```

**Response:**
```json
{
  "ok": true,
  "execution": {
    "chain_id": "weekly-content-2026-06-08",
    "chain_name": "content_week",
    "from_agent": "n8n",
    "to_agent": "olya",
    "status": "running",
    "progress": 35,
    "started_at": "2026-06-08T14:01:23.456Z",
    "completed_at": null,
    "result": null,
    "error": null,
    "task_id": "task_123abc...",
    "n8n_webhook_url": "http://localhost:5678/webhook/office-status"
  }
}
```

**Status values:** `pending`, `running`, `success`, `failed`, `cancelled`, `timeout`

---

### 4. Cancel Chain

```
POST /api/n8n/chain/<chain_id>/cancel
Authorization: Bearer <token>
Content-Type: application/json
```

**Request (optional):**
```json
{
  "reason": "User cancelled from n8n UI"
}
```

**Response:**
```json
{
  "ok": true,
  "chain_id": "weekly-content-2026-06-08",
  "status": "cancelled"
}
```

Sends cancellation webhook to n8n immediately.

---

### 5. Retry Chain

```
POST /api/n8n/chain/<chain_id>/retry
Authorization: Bearer <token>
```

Retry a failed/timed-out chain. Creates a new execution with same config.

**Response (202):**
```json
{
  "ok": true,
  "new_chain_id": "weekly-content-2026-06-08-retry-1",
  "task_id": "task_456def...",
  "status": "pending"
}
```

---

### 6. List Executions

```
GET /api/n8n/executions?status=running&limit=10
Authorization: Bearer <token>
```

List all chain executions with optional filtering.

**Query params:**
- `status`: filter by status (e.g. `running`, `failed`)
- `limit`: max results (default 100)

**Response:**
```json
{
  "ok": true,
  "count": 2,
  "total": 47,
  "executions": [
    {
      "chain_id": "weekly-content-2026-06-08",
      "chain_name": "content_week",
      "status": "running",
      "progress": 50,
      "started_at": "2026-06-08T14:01:23.456Z",
      "completed_at": null
    }
  ]
}
```

---

### 7. Schedule-Based Trigger

```
POST /api/n8n/schedule-trigger
Authorization: Bearer <token>
Content-Type: application/json
```

Handle cron-activated workflows from n8n.

**Request:**
```json
{
  "chain_name": "weekly_report",
  "schedule": {
    "cron": "0 9 * * 1",
    "timezone": "America/Toronto",
    "trigger_time": "2026-06-08T14:00:00Z"
  },
  "n8n_webhook_url": "http://localhost:5678/webhook/office-status"
}
```

**Response (202):**
```json
{
  "ok": true,
  "chain_id": "weekly_report-0_9_*_*_1-1717939200",
  "task_id": "task_789ghi...",
  "status": "pending",
  "scheduled": true
}
```

---

### 8. Receive n8n Status Notification

```
POST /api/n8n/notify
Authorization: Bearer <token>
Content-Type: application/json
```

Receive status updates **from** n8n (reverse webhook — allows n8n to inform office of its own execution state).

**Request:**
```json
{
  "workflow_id": "workflow-abc123",
  "execution_id": "exec-def456",
  "status": "success",
  "message": "Content generated and scheduled",
  "result": {
    "posts_count": 3,
    "reels_count": 1
  }
}
```

**Response:**
```json
{
  "ok": true,
  "received": true,
  "workflow_id": "workflow-abc123"
}
```

---

### 9. Error Callback

```
POST /api/n8n/error-callback
Authorization: Bearer <token>
Content-Type: application/json
```

Log errors from n8n workflows.

**Request:**
```json
{
  "chain_id": "weekly-content-2026-06-08",
  "workflow_id": "workflow-xyz789",
  "error_code": "AGENT_TIMEOUT",
  "error_message": "Agent execution exceeded 5 minutes",
  "stack_trace": "..."
}
```

**Response:**
```json
{
  "ok": true,
  "logged": true,
  "chain_id": "weekly-content-2026-06-08"
}
```

Logs to `reports/n8n_logs/chain_{chain_id}.log` and optionally sends to `N8N_ERROR_WEBHOOK_URL`.

---

### 10. Get Chain Logs

```
GET /api/n8n/logs/<chain_id>
Authorization: Bearer <token>
```

Retrieve all logged interactions for a chain.

**Response:**
```json
{
  "ok": true,
  "chain_id": "weekly-content-2026-06-08",
  "log_entries": [
    {
      "timestamp": "2026-06-08T14:01:23.456Z",
      "chain_id": "weekly-content-2026-06-08",
      "event": "TRIGGER_REQUEST",
      "details": {
        "chain_name": "content_week",
        "from_agent": "n8n",
        "to_agent": "auto"
      }
    },
    {
      "timestamp": "2026-06-08T14:01:24.100Z",
      "event": "CHAIN_ENQUEUED",
      "details": {
        "task_id": "task_123abc...",
        "priority": 5
      }
    }
  ]
}
```

---

## Status Update Webhook Format

Every 5 seconds (or on completion), the service sends this to `N8N_STATUS_WEBHOOK_URL`:

```json
{
  "ok": true,
  "chain_id": "weekly-content-2026-06-08",
  "chain_name": "content_week",
  "status": "running",
  "progress": 50,
  "started_at": "2026-06-08T14:01:23.456Z",
  "completed_at": null,
  "result": null,
  "error": null,
  "timestamp": "2026-06-08T14:01:30.789Z"
}
```

**n8n workflow configuration example:**

1. Create HTTP Request node to listen for webhooks:
   - Method: POST
   - URL: `http://localhost:5678/webhook/office-status` (incoming)

2. In MILA Office, store the webhook URL when triggering:
   ```javascript
   // In your n8n workflow, when calling /api/n8n/trigger-chain:
   {
     "chain_config": {...},
     "n8n_webhook_url": "http://localhost:5678/webhook/office-status"
   }
   ```

3. Parse the incoming JSON and branch on `status`:
   - `success` → next node
   - `failed` → error handler
   - `running` → wait/log

---

## Logging

All interactions logged to:
- **Global log:** `reports/n8n_logs/n8n_webhook.log`
- **Per-chain log:** `reports/n8n_logs/chain_{chain_id}.log` (JSON lines)

Each entry:
```json
{
  "timestamp": "2026-06-08T14:01:23.456Z",
  "chain_id": "...",
  "event": "TRIGGER_REQUEST|CHAIN_ENQUEUED|STATUS_UPDATE|FINAL_STATUS|CHAIN_CANCELLED|N8N_ERROR",
  "details": {...}
}
```

---

## Example: Complete Flow (n8n → Office → n8n)

```
n8n Workflow:
  1. User clicks "Generate Weekly Content"
  2. HTTP Request: POST /api/n8n/trigger-chain
     {
       "chain_config": {"chain_name": "content_week"},
       "n8n_webhook_url": "http://localhost:5678/webhook/office-status"
     }
  3. Get response: chain_id, task_id
  4. HTTP Request listener: wait for POST to webhook/office-status
  5. On "running": log progress
  6. On "success": extract result, continue workflow
  7. On "failed": trigger error handler

MILA Office (background):
  1. Receive POST, validate token
  2. Enqueue task in memory.py
  3. Return 202 immediately
  4. Spawn monitor thread
  5. Every 1s: check task status
  6. Every 5s: POST status to n8n webhook (if progress changed)
  7. On complete: send final status webhook
  8. Log all interactions to chain_{chain_id}.log
```

---

## Timeout & Cleanup

- **Default timeout:** 300s (5 minutes) — configurable via `N8N_WEBHOOK_TIMEOUT`
- **Executions stored in memory** during service uptime
- **Logs persisted** to disk indefinitely (manage via `log_rotate.py` if needed)

When a chain exceeds timeout:
```json
{
  "ok": false,
  "chain_id": "...",
  "status": "timeout",
  "error": "Chain did not complete within 300s"
}
```

---

## Security

- **Bearer token required** on all endpoints except `/health`
- **Localhost-only** (127.0.0.1) — n8n and office must be on same machine
- **No shell injection** — all subprocess calls use `subprocess.run(..., shell=False)`
- **Token in request body** never logged — only in Authorization header

---

## Troubleshooting

**Chain stays in "pending":**
- Check task in `memory.py`: `GET /v1/tasks/<task_id>`
- View chain logs: `GET /api/n8n/logs/<chain_id>`

**Webhook not reaching n8n:**
- Verify `N8N_STATUS_WEBHOOK_URL` is reachable
- Check `reports/n8n_logs/n8n_webhook.log` for failed deliveries
- Service retries 3 times with exponential backoff

**Authorization fails:**
- Confirm token in n8n HTTP Request header: `Authorization: Bearer <token>`
- Token must match `N8N_WEBHOOK_TOKEN` in `.env` exactly

**Chain fails immediately:**
- Check agent chain config in `pipeline.py` (CHAINS dict)
- Verify agent module exists (e.g. `olya.py` for chain step)

---

## Related Files

- `n8n_bridge.py` — legacy bridge (command execution via `/v1/pipeline`)
- `pipeline.py` — chain orchestration & agent wiring
- `memory.py` — task queue & state persistence
- `policies.py` — chain policy & defaults
