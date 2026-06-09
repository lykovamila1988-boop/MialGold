# n8n Webhook — Quick Reference Card

## Start Service

```bash
cd mila-office
python n8n_webhook.py
```

Listens on `http://127.0.0.1:5052`

## Environment Setup

In `tools/.env`:
```env
N8N_WEBHOOK_PORT=5052
N8N_WEBHOOK_TOKEN=<generate via: python -c "import secrets;print(secrets.token_urlsafe(32))">
N8N_STATUS_WEBHOOK_URL=http://localhost:5678/webhook/office-status
N8N_WEBHOOK_TIMEOUT=300
```

## Auth Header (All Requests)

```
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

## Health Check

```bash
curl http://127.0.0.1:5052/health
```

**Response:**
```json
{"ok": true, "service": "mila-n8n-webhook", "port": 5052, "executions_active": 3}
```

---

## Trigger Chain

```bash
curl -X POST http://127.0.0.1:5052/api/n8n/trigger-chain \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_config": {
      "chain_name": "content_week",
      "input_data": {
        "week": "2026-06-08",
        "focus": "trends"
      }
    },
    "n8n_webhook_url": "http://localhost:5678/webhook/status",
    "priority": 5
  }'
```

**Response (202):**
```json
{
  "ok": true,
  "chain_id": "...",
  "task_id": "...",
  "status": "pending"
}
```

---

## Get Chain Status

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:5052/api/n8n/chain/<chain_id>
```

**Response:**
```json
{
  "ok": true,
  "execution": {
    "chain_id": "...",
    "chain_name": "content_week",
    "status": "running",
    "progress": 50,
    "started_at": "2026-06-08T14:01:23Z",
    "result": null,
    "error": null
  }
}
```

---

## Cancel Chain

```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "User cancelled"}' \
  http://127.0.0.1:5052/api/n8n/chain/<chain_id>/cancel
```

---

## Retry Failed Chain

```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:5052/api/n8n/chain/<chain_id>/retry
```

**Response (202):**
```json
{
  "ok": true,
  "new_chain_id": "...",
  "task_id": "...",
  "status": "pending"
}
```

---

## List All Executions

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://127.0.0.1:5052/api/n8n/executions?status=running&limit=10"
```

---

## Schedule-Based Trigger

```bash
curl -X POST http://127.0.0.1:5052/api/n8n/schedule-trigger \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name": "weekly_kpi",
    "schedule": {
      "cron": "0 9 * * 1",
      "timezone": "America/Toronto",
      "trigger_time": "2026-06-08T14:00:00Z"
    }
  }'
```

---

## Get Chain Logs

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:5052/api/n8n/logs/<chain_id>
```

**Response:**
```json
{
  "ok": true,
  "chain_id": "...",
  "log_entries": [
    {
      "timestamp": "2026-06-08T14:01:23Z",
      "event": "TRIGGER_REQUEST",
      "details": {...}
    },
    {
      "timestamp": "2026-06-08T14:01:24Z",
      "event": "CHAIN_ENQUEUED",
      "details": {...}
    }
  ]
}
```

---

## Common Chains

### new_client
Intake interview → profile → recommendations
```json
{"chain_config": {"chain_name": "new_client", "input_data": {"name": "...", "telegram": "..."}}}
```

### content_week
Olya → Marina → Victoria → Vasya (full content pipeline)
```json
{"chain_config": {"chain_name": "content_week", "input_data": {"week": "2026-06-08"}}}
```

### weekly_report
Dima → Marina → analytics
```json
{"chain_config": {"chain_name": "weekly_report"}}
```

### weekly_kpi
Automated KPI dashboard
```json
{"chain_config": {"chain_name": "weekly_kpi"}}
```

---

## Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Queued, not started |
| `running` | Agent executing |
| `success` | Completed successfully |
| `failed` | Agent error |
| `cancelled` | User cancelled |
| `timeout` | Exceeded 5 min (default) |

---

## Webhooks From Service → n8n

Sent to `N8N_STATUS_WEBHOOK_URL` every 5 seconds:

```json
{
  "ok": true,
  "chain_id": "...",
  "chain_name": "content_week",
  "status": "running",
  "progress": 50,
  "started_at": "2026-06-08T14:01:23Z",
  "completed_at": null,
  "result": null,
  "error": null,
  "timestamp": "2026-06-08T14:01:30Z"
}
```

---

## Logs Directory

```
reports/n8n_logs/
  ├── n8n_webhook.log              # Global service log
  ├── chain_<chain_id>.log         # Per-chain JSON lines
  └── chain_<chain_id>.log
```

View logs:
```bash
tail -f "E:\MILA GOLD\reports\n8n_logs\n8n_webhook.log"
cat "E:\MILA GOLD\reports\n8n_logs\chain_<chain_id>.log" | python -m json.tool
```

---

## n8n HTTP Request Node Template

```javascript
// Method: POST
// URL: {{ $env.OFFICE_WEBHOOK_URL }}/api/n8n/trigger-chain
// Headers:
//   Authorization: Bearer {{ $env.OFFICE_TOKEN }}
//   Content-Type: application/json

{
  "chain_config": {
    "chain_name": "{{ $json.chainName }}",
    "input_data": {{ JSON.stringify($json.inputData) }}
  },
  "n8n_webhook_url": "{{ $env.N8N_WEBHOOK_CALLBACK }}"
}
```

---

## Troubleshooting

**Service won't start:**
```
ERROR: N8N_WEBHOOK_TOKEN not set
```
→ Generate and set `N8N_WEBHOOK_TOKEN` in `tools/.env`

**401 Unauthorized:**
```
{"ok": false, "error": "Unauthorized"}
```
→ Check token matches `N8N_WEBHOOK_TOKEN` exactly in header

**Chain stuck in "pending":**
```bash
# Check if task exists
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:5052/api/n8n/chain/<chain_id>

# View logs
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:5052/api/n8n/logs/<chain_id>
```

**Webhook not reaching n8n:**
```bash
# Check logs for delivery failures
tail -f reports/n8n_logs/n8n_webhook.log | grep "Webhook"

# Verify n8n webhook URL is reachable
curl -v <N8N_STATUS_WEBHOOK_URL>
```

---

## Performance Notes

- **Trigger response:** <100ms
- **Status check polling:** 1s intervals
- **Webhook delivery:** ~500ms (with retries)
- **Default timeout:** 300s (5 minutes)
- **Max concurrent chains:** limited by system resources

---

## Documentation Files

- **N8N_WEBHOOK_API.md** — Complete endpoint reference
- **N8N_INTEGRATION_EXAMPLES.md** — 10 workflow patterns
- **N8N_WEBHOOK_SUMMARY.md** — Architecture & implementation
- **n8n_webhook.py** — Source code (662 lines)
