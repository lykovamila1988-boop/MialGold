# n8n Webhook Integration — Complete Documentation Index

Complete bi-directional n8n ↔ MILA Office integration for agent chain execution, monitoring, and status tracking.

## Files Delivered

### 1. **n8n_webhook.py** (662 lines, 28 KB)
The main Flask application with 10 RESTful endpoints.

**Features:**
- POST /api/n8n/trigger-chain — Start chains from n8n
- GET /api/n8n/chain/{id} — Get chain status in real-time
- POST /api/n8n/chain/{id}/cancel — Abort running chains
- POST /api/n8n/chain/{id}/retry — Retry failed chains
- GET /api/n8n/executions — List all executions
- POST /api/n8n/schedule-trigger — Handle cron-based triggers
- POST /api/n8n/notify — Receive status from n8n
- POST /api/n8n/error-callback — Log errors from n8n
- GET /api/n8n/logs/{id} — Retrieve chain interaction logs
- GET /health — Health check endpoint

**Key Capabilities:**
- Async chain monitoring (background threads)
- Periodic status webhooks every 5 seconds
- Retry logic with exponential backoff
- Per-chain JSON logging
- Bearer token authentication
- Integrates with memory.py task queue

---

### 2. **N8N_WEBHOOK_API.md** (11 KB)
Complete API reference for all 10 endpoints.

**Sections:**
- Overview & startup
- Configuration options
- Authentication (Bearer token)
- Full endpoint documentation with request/response examples
- Status update webhook format
- Logging system
- Complete flow example (n8n → Office → n8n)
- Timeout & cleanup behavior
- Security guarantees
- Troubleshooting guide

**Use this when:** Building n8n workflows, debugging requests, understanding response formats.

---

### 3. **N8N_INTEGRATION_EXAMPLES.md** (17 KB)
10 practical n8n workflow patterns with copy-paste code.

**Patterns included:**
1. Simple chain trigger (async)
2. Trigger + poll until complete
3. Schedule-based trigger (cron)
4. Error handling with retry
5. Monitor chain in separate workflow
6. Multi-agent chain (agent sequencing)
7. Get detailed logs after completion
8. List all running chains (dashboard)
9. Cancel chain from n8n UI
10. Error callback from agent code

**Use this when:** Setting up new n8n workflows, integrating specific use cases.

---

### 4. **N8N_WEBHOOK_SUMMARY.md** (8.8 KB)
Implementation summary, architecture, and deployment guide.

**Sections:**
- Features summary (all 10 features explained)
- Architecture diagram
- Response flow example
- Integration patterns
- Security properties
- Performance characteristics
- Testing commands
- Deployment checklist
- Endpoints summary table
- Future extensions

**Use this when:** Understanding system design, planning deployment, capacity planning.

---

### 5. **N8N_WEBHOOK_QUICK_REFERENCE.md** (6.2 KB)
Cheat sheet with curl commands for every operation.

**Includes:**
- Startup command
- Environment setup
- Bearer token format
- cURL commands for:
  - Health check
  - Trigger chain
  - Get status
  - Cancel/retry
  - List executions
  - Schedule trigger
  - Get logs
- Common chain examples (new_client, content_week, weekly_report, weekly_kpi)
- Status values reference
- n8n HTTP Request node template
- Quick troubleshooting

**Use this when:** Testing manually, building quick integrations, debugging issues.

---

## Quick Start

### 1. Generate Token
```bash
python -c "import secrets;print(secrets.token_urlsafe(32))"
```

### 2. Set Environment
In `tools/.env`:
```env
N8N_WEBHOOK_PORT=5052
N8N_WEBHOOK_TOKEN=<generated_token>
N8N_STATUS_WEBHOOK_URL=http://localhost:5678/webhook/office-status
N8N_WEBHOOK_TIMEOUT=300
```

### 3. Start Service
```bash
cd mila-office
python n8n_webhook.py
```

### 4. Verify
```bash
curl http://127.0.0.1:5052/health
```

### 5. Trigger Test
```bash
curl -X POST http://127.0.0.1:5052/api/n8n/trigger-chain \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_config": {
      "chain_name": "new_client",
      "input_data": {"name": "Test"}
    }
  }'
```

---

## Architecture Overview

```
n8n Workflow
    ↓
POST /api/n8n/trigger-chain
    ↓
[Validate token] → [Enqueue in memory.py] → [Return 202 immediately]
    ↓
[Spawn background monitor thread]
    ↓
Monitor Loop (every 1 second):
  • Check task status from memory.py
  • Update progress (0-100%)
  • Every 5 seconds: send webhook to N8N_STATUS_WEBHOOK_URL
  ↓
[On completion: send final status, log all interactions]
    ↓
n8n receives webhook, triggers next step(s)
```

---

## Documentation Navigation

**By Role:**

- **n8n Workflow Builder** → Start with **N8N_WEBHOOK_QUICK_REFERENCE.md** (curl examples) + **N8N_INTEGRATION_EXAMPLES.md** (patterns)
- **System Administrator** → Read **N8N_WEBHOOK_SUMMARY.md** (architecture), then **N8N_WEBHOOK_API.md** (all options)
- **Developer** → Read **n8n_webhook.py** directly (well-commented), refer to **N8N_WEBHOOK_SUMMARY.md** for architecture
- **DevOps / Deployment** → Use **N8N_WEBHOOK_SUMMARY.md** (deployment checklist) + **N8N_WEBHOOK_API.md** (configuration)

**By Task:**

| Task | Read |
|------|------|
| Set up service for first time | SUMMARY + QUICK_REFERENCE |
| Build n8n workflow | EXAMPLES + QUICK_REFERENCE |
| Debug workflow failure | QUICK_REFERENCE + API |
| Understand system design | SUMMARY + n8n_webhook.py |
| Configure security/auth | API (Authentication section) |
| View chain logs | QUICK_REFERENCE or API |
| Handle errors | EXAMPLES (Pattern 4) |
| Monitor running chains | EXAMPLES (Pattern 8) |

---

## Key Concepts

### Chain
An orchestrated sequence of agent actions triggered by n8n or scheduled. Defined in `pipeline.py` CHAINS dict.

### Execution
A single run of a chain from trigger to completion. Tracked with unique `chain_id`.

### Task
The underlying work unit queued in `memory.py` task system. Each execution has a `task_id`.

### Status
Current state: `pending` → `running` → (`success`|`failed`|`cancelled`|`timeout`)

### Webhook
HTTP POST callback sent to n8n (or any URL) with execution status updates.

### Monitor Thread
Background thread that polls task status every 1 second and sends webhooks every 5 seconds.

---

## Supported Chains

### new_client
Alina (intake) → Lera (sales)
- Input: client data, contact info
- Output: offer recommendation, follow-up message

### content_week
Olya (trends) → Marina (ideas) → Victoria (editing) → Vasya (scheduling)
- Input: week date, focus topic
- Output: scheduled posts/reels

### weekly_report
Dima (analytics) → Marina (insights) → reporting
- Input: week date
- Output: KPI summary

### weekly_kpi
Automated KPI dashboard
- Input: (schedule-triggered)
- Output: analytics snapshot

Add more in `pipeline.py` CHAINS dict.

---

## Endpoint Reference Table

| Endpoint | Method | Purpose | Auth | Response |
|----------|--------|---------|------|----------|
| `/health` | GET | Service health | No | 200: {ok, executions_active} |
| `/api/n8n/trigger-chain` | POST | Start chain | Yes | 202: {chain_id, task_id, status} |
| `/api/n8n/chain/{id}` | GET | Get status | Yes | 200: {execution} |
| `/api/n8n/chain/{id}/cancel` | POST | Abort chain | Yes | 200: {status: "cancelled"} |
| `/api/n8n/chain/{id}/retry` | POST | Retry failed | Yes | 202: {new_chain_id, task_id} |
| `/api/n8n/executions` | GET | List all | Yes | 200: {executions[], count, total} |
| `/api/n8n/schedule-trigger` | POST | Cron trigger | Yes | 202: {chain_id, scheduled: true} |
| `/api/n8n/notify` | POST | Receive from n8n | Yes | 200: {received: true} |
| `/api/n8n/error-callback` | POST | Log n8n error | Yes | 200: {logged: true} |
| `/api/n8n/logs/{id}` | GET | Get logs | Yes | 200: {log_entries[]} |

---

## Logging

All interactions logged to disk:

```
E:\MILA GOLD\reports\n8n_logs\
  ├── n8n_webhook.log                 # Global service log
  └── chain_<chain_id>.log            # Per-chain JSON lines
```

Example log entry:
```json
{
  "timestamp": "2026-06-08T14:01:23.456Z",
  "chain_id": "content_week-abc123",
  "event": "TRIGGER_REQUEST",
  "details": {
    "chain_name": "content_week",
    "from_agent": "n8n",
    "priority": 5
  }
}
```

Events: `TRIGGER_REQUEST`, `CHAIN_ENQUEUED`, `STATUS_UPDATE`, `FINAL_STATUS`, `CHAIN_CANCELLED`, `N8N_ERROR`

---

## Security

✓ Bearer token required (except /health)
✓ Localhost-only (127.0.0.1)
✓ No shell injection (subprocess.run with shell=False)
✓ Constant-time token comparison
✓ Request validation (type casting, required fields)
✓ Token never logged

---

## Performance

| Operation | Time |
|-----------|------|
| Trigger response | <100ms |
| Monitor polling | 1s |
| Webhook delivery | ~500ms (with retries) |
| Default timeout | 300s |

---

## Troubleshooting Flowchart

```
Service won't start?
  ↓ Yes → N8N_WEBHOOK_TOKEN not set → Generate and add to tools/.env
  ↓ No

401 Unauthorized?
  ↓ Yes → Token mismatch in header → Verify N8N_WEBHOOK_TOKEN
  ↓ No

Chain stuck in "pending"?
  ↓ Yes → GET /api/n8n/chain/<id> → Check status
  ↓ No → GET /api/n8n/logs/<id> → View events

Webhook not reaching n8n?
  ↓ → Check N8N_STATUS_WEBHOOK_URL is reachable
  ↓ → View n8n_webhook.log for delivery errors
  ↓ → Verify n8n webhook listener is active
```

---

## Files Cross-Reference

| File | Purpose | Read When |
|------|---------|-----------|
| n8n_webhook.py | Main service | Troubleshooting, extending |
| N8N_WEBHOOK_API.md | Full API reference | Building workflows, debugging |
| N8N_INTEGRATION_EXAMPLES.md | n8n patterns | Setting up new workflows |
| N8N_WEBHOOK_SUMMARY.md | Architecture | Understanding design, deployment |
| N8N_WEBHOOK_QUICK_REFERENCE.md | Cheat sheet | Testing manually, quick lookups |
| N8N_WEBHOOK_INDEX.md | This file | Finding documentation |

---

## Next Steps

1. **Set up token** in `tools/.env`
2. **Start service** with `python n8n_webhook.py`
3. **Test endpoint** with `/health` curl
4. **Create first workflow** using an example pattern
5. **Monitor logs** in `reports/n8n_logs/`
6. **Extend** with custom chains as needed

---

**Status:** Production-ready
**Created:** 2026-06-08
**Lines of code:** 662 (main) + 700+ (documentation)
**Dependencies:** Flask, requests, dotenv (already in project)
