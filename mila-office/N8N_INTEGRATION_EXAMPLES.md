# n8n Integration Examples — How to Call n8n_webhook.py

Practical examples of integrating n8n workflows with MILA Office agent chains.

## Setup

1. **Start the webhook service:**
   ```bash
   cd mila-office
   python n8n_webhook.py
   ```

2. **In n8n Environment Variables**, set:
   ```
   OFFICE_WEBHOOK_URL = http://localhost:5052
   OFFICE_TOKEN = <value from N8N_WEBHOOK_TOKEN in tools/.env>
   ```

3. **In n8n HTTP Request nodes**, use `{{ $env.OFFICE_WEBHOOK_URL }}` and `{{ $env.OFFICE_TOKEN }}`

---

## Pattern 1: Simple Chain Trigger (No Wait)

**Use case:** Start a background task and continue n8n workflow immediately.

**n8n Workflow (3 nodes):**

```
┌─────────────────────┐
│  Trigger: Manual    │
└──────────┬──────────┘
           │
        ┌──▼──────────────────────────────────┐
        │ HTTP Request: Start Chain            │
        │  Method: POST                        │
        │  URL: {{ $env.OFFICE_WEBHOOK_URL }}/api/n8n/trigger-chain
        │  Headers:
        │    Authorization: Bearer {{ $env.OFFICE_TOKEN }}
        │  Body:
        │    {
        │      "chain_config": {
        │        "chain_name": "new_client",
        │        "input_data": {
        │          "client_name": "{{ $json.name }}",
        │          "client_telegram": "{{ $json.telegram }}"
        │        }
        │      },
        │      "from_agent": "n8n",
        │      "priority": 5
        │    }
        └──────────┬─────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │ Notification: Email │
        │  Message: "Chain {{ $json.chain_id }} started" │
        └─────────────────────┘
```

**JavaScript in HTTP Request:**
```javascript
// Parse response
const response = $json;
if (response.ok) {
  return {
    chain_id: response.chain_id,
    task_id: response.task_id,
    status: response.status
  };
} else {
  throw new Error("Failed to trigger chain: " + response.error);
}
```

---

## Pattern 2: Trigger + Poll Until Complete

**Use case:** Wait for chain to complete before continuing (e.g. generate content, then publish).

**n8n Workflow (4 nodes):**

```
┌──────────────────┐
│ Trigger: Manual  │
└────────┬─────────┘
         │
    ┌────▼──────────────────────┐
    │ HTTP: Start Chain          │
    │ Method: POST               │
    │ URL: .../api/n8n/trigger-chain
    └────┬──────────────────────┘
         │
    ┌────▼─────────────────────────┐
    │ Loop: Wait for Completion     │
    │ Max iterations: 60 (5 min)    │
    │ Wait between: 5s              │
    │
    │ Inside loop:                  │
    │  - HTTP: Check Status         │
    │    GET .../api/n8n/chain/{{ $json.chain_id }}
    │    Headers: Bearer {{ $env.OFFICE_TOKEN }}
    │  - Decision: status == "success"?
    │    YES → exit loop, continue  │
    │    NO → wait 5s, retry        │
    └────┬──────────────────────────┘
         │
    ┌────▼─────────────────────────┐
    │ Process Result               │
    │ result = {{ $json.execution.result }}
    └──────────────────────────────┘
```

**JavaScript in "Wait for Completion" condition:**
```javascript
// Return true to continue loop, false to exit
const execution = $json.execution;
const isComplete = ["success", "failed", "cancelled", "timeout"].includes(execution.status);
return !isComplete;  // Keep looping until status is final
```

**On success:**
```javascript
// Extract result for next nodes
const result = $json.execution.result;
return {
  content: result.content || "",
  posts_count: result.posts_count || 0,
  status: result.status || "pending"
};
```

---

## Pattern 3: Schedule-Based Trigger (Cron)

**Use case:** Run chain on schedule (e.g. daily analytics at 9 AM).

**n8n Workflow (2 nodes):**

```
┌──────────────────────────────────┐
│ Trigger: Cron                    │
│ Pattern: 0 9 * * *  (9 AM daily) │
└────────┬─────────────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │ HTTP: Schedule Trigger             │
    │ Method: POST                       │
    │ URL: .../api/n8n/schedule-trigger  │
    │ Headers: Bearer {{ $env.OFFICE_TOKEN }}
    │ Body:
    │   {
    │     "chain_name": "weekly_kpi",
    │     "schedule": {
    │       "cron": "0 9 * * *",
    │       "timezone": "America/Toronto",
    │       "trigger_time": "{{ now() }}"
    │     }
    │   }
    └────────────────────────────────┘
```

**JavaScript:**
```javascript
// Format trigger time as ISO
return {
  chain_name: "weekly_kpi",
  schedule: {
    cron: "0 9 * * *",
    timezone: "America/Toronto",
    trigger_time: new Date().toISOString()
  }
};
```

---

## Pattern 4: Error Handling with Retry

**Use case:** Chain fails → log error → retry up to 3 times.

**n8n Workflow (6 nodes):**

```
┌────────────────────┐
│ Trigger: Manual    │
└────────┬───────────┘
         │
    ┌────▼──────────────────┐
    │ Set Variables          │
    │ retries = 0            │
    │ max_retries = 3        │
    └────┬──────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │ Loop: Retry until success          │
    │ Max iterations: 3                  │
    │
    │ Inside:
    │  - HTTP: Trigger Chain             │
    │  - Decision: status == "success"? │
    │    YES → break loop                │
    │    NO → retry_count++              │
    │         if >= 3 → Error            │
    └────┬──────────────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ Error Handler             │
    │ HTTP: Log Error           │
    │ POST .../api/n8n/error-callback
    │ Body:
    │   {
    │     "chain_id": "{{ chain_id }}",
    │     "error_code": "MAX_RETRIES",
    │     "error_message": "Failed after 3 attempts"
    │   }
    └────────────────────────────┘
```

**Retry logic in Decision node:**
```javascript
// After HTTP request, check response
const response = $json;
const execution = response.execution || {};

if (execution.status === "success") {
  return { success: true };
} else if (execution.status === "failed" || execution.status === "timeout") {
  // Retry or fail
  return { success: false, should_retry: true };
}
```

---

## Pattern 5: Monitor Chain in Separate n8n Workflow

**Use case:** Receive status updates from MILA Office via webhook, act on them.

**n8n Workflow (incoming webhook):**

```
┌─────────────────────────────────┐
│ Trigger: Webhook                │
│ (Listen POST to Slack channel)  │
└────────┬────────────────────────┘
         │
    ┌────▼──────────────────────────┐
    │ Decision: Check Status         │
    │ $json.status == "success"?     │
    │  YES → Success path            │
    │  NO  → $json.status == "failed"?
    │        YES → Error path        │
    │        NO  → Ignore            │
    └────┬──────────────────────────┘
         │
    ├────▼──────────────────────┐
    │ Path: Success             │
    │ 1. Extract result         │
    │ 2. Send to Slack: ✓       │
    │ 3. File: Save JSON        │
    │
    ├────▼──────────────────────┐
    │ Path: Error               │
    │ 1. Send to Slack: ✗       │
    │ 2. Log to DB              │
    │ 3. Notify admin           │
```

**To receive webhooks from MILA Office:**
1. In n8n, create Webhook trigger: "Activate webhook trigger" → copy URL
2. In your MILA Office chain trigger call, pass this URL as `n8n_webhook_url`
3. n8n webhook will receive status updates every 5 seconds

**n8n HTTP Request (to trigger with webhook):**
```json
{
  "chain_config": {
    "chain_name": "content_week"
  },
  "n8n_webhook_url": "https://n8n.yoursite.com/webhook/office-status"
}
```

---

## Pattern 6: Multi-Agent Chain (Agent-to-Agent)

**Use case:** Chain multiple agents with context passing (e.g. Olya → Marina → Victoria).

**n8n Workflow:**

```
┌────────────────────────────┐
│ Trigger: Manual            │
│ Input: week, focus topic   │
└────────┬───────────────────┘
         │
    ┌────▼──────────────────────────┐
    │ HTTP: Trigger content_week     │
    │ POST .../api/n8n/trigger-chain │
    │ Body:
    │   {
    │     "chain_config": {
    │       "chain_name": "content_week",
    │       "input_data": {
    │         "week": "{{ $json.week }}",
    │         "topic": "{{ $json.topic }}"
    │       }
    │     },
    │     "from_agent": "n8n",
    │     "to_agent": "olya",
    │     "chain_id": "content_{{ now() }}"
    │   }
    └────────────────────────────┘
```

The `pipeline.py` CHAINS dict handles agent sequencing:
```python
"content_week": [
    ("olya", "Find 3 viral themes..."),
    ("marina", "Expand themes into 5 content ideas..."),
    ("victoria", "Edit and format ideas..."),
    ("vasya", "Schedule publication..."),
]
```

n8n provides `chain_name` and input; agents automatically sequence.

---

## Pattern 7: Get Detailed Logs After Completion

**Use case:** Chain completed → retrieve full interaction log for audit.

**n8n Workflow (2 nodes):**

```
┌─────────────────────┐
│ Trigger: Manual     │
│ Input: chain_id     │
└────────┬────────────┘
         │
    ┌────▼──────────────────────┐
    │ HTTP: Get Logs             │
    │ GET .../api/n8n/logs/{{ $json.chain_id }}
    │ Headers: Bearer {{ $env.OFFICE_TOKEN }}
    └────┬──────────────────────┘
         │
    ┌────▼──────────────────────┐
    │ File: Write Log            │
    │ Filename: chain_{{ $json.chain_id }}.json
    │ Data: {{ $json.log_entries }}
    └────────────────────────────┘
```

Response includes all interactions (TRIGGER_REQUEST, CHAIN_ENQUEUED, STATUS_UPDATE, etc.).

---

## Pattern 8: List All Running Chains (Dashboard)

**Use case:** n8n dashboard showing all active MILA chains.

**n8n Workflow:**

```
┌────────────────────┐
│ Trigger: Interval  │
│ Every 10 seconds   │
└────────┬───────────┘
         │
    ┌────▼────────────────────────────┐
    │ HTTP: List Executions            │
    │ GET .../api/n8n/executions?status=running
    │ Headers: Bearer {{ $env.OFFICE_TOKEN }}
    └────┬───────────────────────────┘
         │
    ┌────▼────────────────────────────┐
    │ Webhook: Send to Slack           │
    │ Format: Running chains:          │
    │   - {{ $json.executions[0].chain_id }}  ({{ progress }}%)
    └────────────────────────────────┘
```

---

## Pattern 9: Cancel Chain from n8n UI

**Use case:** User clicks "Abort" button in n8n → cancel MILA chain.

**n8n Workflow:**

```
┌─────────────────────────┐
│ Trigger: Manual         │
│ Input: chain_id         │
└────────┬────────────────┘
         │
    ┌────▼────────────────────────────┐
    │ HTTP: Cancel Chain               │
    │ POST .../api/n8n/chain/{{ $json.chain_id }}/cancel
    │ Headers: Bearer {{ $env.OFFICE_TOKEN }}
    │ Body:
    │   {
    │     "reason": "Cancelled by user"
    │   }
    └────┬───────────────────────────┘
         │
    ┌────▼──────────────────────────┐
    │ Notification: Email            │
    │ "Chain {{ chain_id }} cancelled"│
    └───────────────────────────────┘
```

---

## Pattern 10: Error Callback from Agent

**Use case:** Agent encounters error → send detailed error back to n8n for diagnostics.

**In agent code (e.g., `olya.py` or `marina.py`):**

```python
import requests
import os

OFFICE_WEBHOOK_URL = os.getenv("OFFICE_WEBHOOK_URL", "http://localhost:5052")
OFFICE_TOKEN = os.getenv("OFFICE_TOKEN", "")

def report_error_to_n8n(chain_id: str, error_code: str, error_msg: str):
    """Send error callback to n8n."""
    url = f"{OFFICE_WEBHOOK_URL}/api/n8n/error-callback"
    payload = {
        "chain_id": chain_id,
        "workflow_id": "agent-workflow",
        "error_code": error_code,
        "error_message": error_msg,
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {OFFICE_TOKEN}"},
            timeout=5,
        )
        return resp.json()
    except Exception as e:
        print(f"Failed to report error: {e}")
        return {"ok": False}

# Usage in agent:
try:
    result = process_content(data)
except Exception as e:
    report_error_to_n8n(chain_id, "AGENT_ERROR", str(e))
    raise
```

---

## Debugging Tips

**Check webhook is running:**
```bash
curl http://127.0.0.1:5052/health
```

**Verify token works:**
```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://127.0.0.1:5052/api/n8n/executions
```

**View chain logs:**
```bash
cat "E:\MILA GOLD\reports\n8n_logs\chain_<chain_id>.log"
```

**Webhook delivery issues:**
```bash
tail -f "E:\MILA GOLD\reports\n8n_logs\n8n_webhook.log"
```

**Test trigger from command line:**
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

## Next Steps

1. Deploy `n8n_webhook.py` to production alongside n8n
2. Configure `N8N_WEBHOOK_TOKEN` in both `.env` files
3. Create first n8n workflow using one of the patterns above
4. Monitor logs in `reports/n8n_logs/` directory
5. Extend with custom agent chains as needed
