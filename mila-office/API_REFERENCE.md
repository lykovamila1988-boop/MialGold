# MILA OFFICE API Reference

Complete documentation for MILA Office REST API endpoints for agent communication, chain orchestration, and n8n integration.

## Table of Contents

1. [Base Information](#base-information)
2. [Agent Chat API](#agent-chat-api)
3. [Chain Management API](#chain-management-api)
4. [n8n Integration API](#n8n-integration-api)
5. [Error Handling](#error-handling)
6. [Authentication](#authentication)

---

## Base Information

### Endpoints

- **Webapp API (main)**: `http://127.0.0.1:5000/api/`
- **n8n Webhook Service**: `http://127.0.0.1:5052/api/n8n/` (requires Bearer token)
- **Chain Dashboard**: `http://127.0.0.1:5000/chains/`

### Environment Variables

```bash
# In tools/.env or root .env:
N8N_BASE_URL=http://127.0.0.1:5678              # n8n instance URL
N8N_WEBHOOK_PORT=5052                           # Webhook listener port
N8N_WEBHOOK_TOKEN=<random-secret>               # Bearer token for webhook auth
N8N_STATUS_WEBHOOK_URL=http://n8n:5678/webhook/status
N8N_ERROR_WEBHOOK_URL=http://n8n:5678/webhook/error
N8N_WEBHOOK_TIMEOUT=300                         # Max seconds to wait for chain
```

### Health Check

```http
GET /api/meta
```

Returns metadata about available agents and their commands.

**Response (200 OK)**
```json
{
  "version": "2.0",
  "agents": [
    { "key": "marina", "commands": ["/аналитика", "/контент", ...] },
    { "key": "victoria", "commands": ["/редактура", ...] }
  ],
  "timestamp": "2026-06-08T14:00:00Z"
}
```

---

## Agent Chat API

### 1. POST /api/chat

Send a message to an agent. Creates an asynchronous job. Returns immediately with a `job_id`.

**URL**: `POST http://127.0.0.1:5000/api/chat`

**Request Headers**
```
Content-Type: application/json
```

**Request Body**
```json
{
  "agent": "marina",
  "message": "Какие посты давно не публиковались?",
  "from_agent": "user",
  "to_agent": null,
  "chain_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters**
- `agent` (string, required): Agent key (marina, victoria, alina, dima, tyoma, olya, vasya, lera)
- `message` (string, required): Text to send to the agent
- `from_agent` (string, optional): Who initiated this message (default: "user")
  - Used in agent chains to track message origin
  - Example: "olya", "marina", "n8n"
- `to_agent` (string, optional): Override target agent (for delegation)
- `chain_id` (string, optional): UUID linking related messages in a processing chain

**Response (202 Accepted)**
```json
{
  "ok": true,
  "job": "a1b2c3d4e5f6g7h8",
  "agent": "marina",
  "from_agent": "user",
  "chain_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Fields**
- `job`: Unique job ID to poll for results
- `agent`: Target agent key
- `from_agent`: Originating agent or "user"
- `chain_id`: Chain ID for tracking multi-step workflows

**Example: JavaScript**
```javascript
async function chatWithAgent(agent, message, chainId = null) {
  const body = {
    agent,
    message,
    from_agent: "user",
    chain_id: chainId,
  };

  const res = await fetch("http://127.0.0.1:5000/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  if (!data.ok) throw new Error(data.error);
  return data.job; // Return job ID for polling
}
```

**Example: Python**
```python
import requests

def chat_with_agent(agent: str, message: str, chain_id: str = None):
    payload = {
        "agent": agent,
        "message": message,
        "from_agent": "user",
        "chain_id": chain_id,
    }
    resp = requests.post(
        "http://127.0.0.1:5000/api/chat",
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()["job"]
```

**Example: cURL**
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "marina",
    "message": "Напиши анализ комментариев за неделю",
    "from_agent": "user",
    "chain_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

---

### 2. GET /api/result

Poll for the result of a completed job. Returns `{"status": "pending"}` while running.

**URL**: `GET http://127.0.0.1:5000/api/result?job=a1b2c3d4e5f6g7h8`

**Query Parameters**
- `job` (string, required): The job ID from `/api/chat` response

**Response (200 OK) - While Pending**
```json
{
  "status": "pending"
}
```

**Response (200 OK) - When Complete**
```json
{
  "job": "a1b2c3d4e5f6g7h8",
  "agent_key": "marina",
  "reply": "Проанализировал последние комментарии...",
  "verdict": "ready_next",
  "next_agent": "victoria",
  "from_agent": "user",
  "to_agent": null,
  "chain_id": "550e8400-e29b-41d4-a716-446655440000",
  "chain_context": {
    "current_agent": "marina",
    "from_agent": "user",
    "original_to_agent": null,
    "chain_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response Fields**
- `reply`: Agent's response text
- `verdict`: Processing state
  - `ready_next`: Agent suggests next agent in chain
  - `done`: Processing complete, don't continue chain
  - Other verdicts are agent-specific
- `next_agent`: Suggested next agent (if verdict is `ready_next`)
- `chain_context`: Context to pass to next agent in chain
- **Note**: Job is deleted from memory after retrieval

**Example: Polling Loop (JavaScript)**
```javascript
async function pollResult(jobId, maxWait = 60000) {
  const startTime = Date.now();
  const pollInterval = 1000; // Poll every 1 second

  while (Date.now() - startTime < maxWait) {
    const res = await fetch(`http://127.0.0.1:5000/api/result?job=${jobId}`);
    const data = await res.json();

    if (data.status === "pending") {
      await new Promise(resolve => setTimeout(resolve, pollInterval));
      continue;
    }

    return data; // Result ready
  }

  throw new Error(`Job ${jobId} timed out after ${maxWait}ms`);
}

// Usage
const jobId = await chatWithAgent("marina", "Анализ...");
const result = await pollResult(jobId);
console.log("Reply:", result.reply);
```

**Example: Polling Loop (Python)**
```python
import time
import requests

def poll_result(job_id: str, max_wait: int = 60):
    start_time = time.time()
    poll_interval = 1

    while time.time() - start_time < max_wait:
        resp = requests.get(
            "http://127.0.0.1:5000/api/result",
            params={"job": job_id},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "pending":
            time.sleep(poll_interval)
            continue

        return data

    raise TimeoutError(f"Job {job_id} timed out after {max_wait}s")

# Usage
job_id = chat_with_agent("marina", "Анализ...")
result = poll_result(job_id)
print("Reply:", result["reply"])
```

---

## Chain Management API

### 3. POST /api/n8n/trigger-chain

Trigger an agent chain from n8n or external service. Requires Bearer token authentication.

**URL**: `POST http://127.0.0.1:5052/api/n8n/trigger-chain`

**Request Headers**
```
Content-Type: application/json
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

**Request Body**
```json
{
  "chain_config": {
    "chain_name": "content_publication",
    "input_data": {
      "post_id": "12345",
      "approval_status": "ready",
      "publication_time": "2026-06-09T10:00:00Z"
    }
  },
  "from_agent": "olya",
  "to_agent": "marina",
  "chain_id": "content-pub-550e8400",
  "n8n_webhook_url": "http://n8n:5678/webhook/chain-status",
  "priority": 5
}
```

**Parameters**
- `chain_config` (object, required)
  - `chain_name` (string): Name of chain to execute
  - `input_data` (object): Data to pass to the chain
- `from_agent` (string, optional): Originating agent (default: "n8n")
- `to_agent` (string, optional): Initial target agent (default: "auto")
- `chain_id` (string, optional): Custom chain ID for tracking (auto-generated if omitted)
- `n8n_webhook_url` (string, optional): URL for status callbacks
- `priority` (integer, optional): Task priority 1-10 (default: 5)

**Response (202 Accepted)**
```json
{
  "ok": true,
  "chain_id": "content-pub-550e8400",
  "task_id": "task-abc123",
  "status": "pending",
  "message": "Chain triggered and monitoring started"
}
```

**Response Fields**
- `chain_id`: Unique chain identifier
- `task_id`: Internal task queue ID
- `status`: Current execution status

**Status Updates via Webhook**

The service will POST to `n8n_webhook_url` periodically with status updates:

```json
{
  "ok": true,
  "chain_id": "content-pub-550e8400",
  "chain_name": "content_publication",
  "status": "running",
  "progress": 45,
  "started_at": "2026-06-08T14:00:00Z",
  "completed_at": null,
  "result": null,
  "error": null,
  "timestamp": "2026-06-08T14:00:05Z"
}
```

**Example: n8n HTTP Request Node**
```
Method: POST
URL: http://127.0.0.1:5052/api/n8n/trigger-chain
Headers:
  Content-Type: application/json
  Authorization: Bearer <token from env>

Body:
{
  "chain_config": {
    "chain_name": "weekly_report",
    "input_data": {
      "week_start": "{{ $now.toISO().split('T')[0] }}"
    }
  },
  "from_agent": "n8n_scheduler",
  "n8n_webhook_url": "{{ $env.N8N_WEBHOOK_STATUS_URL }}"
}
```

**Example: Python**
```python
import requests
from datetime import datetime

def trigger_chain(chain_name: str, input_data: dict, webhook_url: str, token: str):
    payload = {
        "chain_config": {
            "chain_name": chain_name,
            "input_data": input_data,
        },
        "from_agent": "n8n",
        "n8n_webhook_url": webhook_url,
        "priority": 5,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    
    resp = requests.post(
        "http://127.0.0.1:5052/api/n8n/trigger-chain",
        json=payload,
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()

# Usage
result = trigger_chain(
    "content_publication",
    {"post_id": "12345", "approval_status": "ready"},
    webhook_url="http://n8n:5678/webhook/status",
    token="<your-token>",
)
print(f"Chain triggered: {result['chain_id']}")
```

---

### 4. GET /api/chains/active

List all currently executing chains (requires Bearer token).

**URL**: `GET http://127.0.0.1:5000/chains/api/active`

**Query Parameters** (optional)
- `limit` (integer): Max results (default: 50)
- `agent` (string): Filter by agent name

**Response (200 OK)**
```json
{
  "ok": true,
  "active": [
    {
      "chain_id": "content-pub-550e8400",
      "agent": "marina",
      "started": "2026-06-08T14:00:00Z",
      "elapsed_ms": 5000,
      "progress": 45,
      "status": "running"
    },
    {
      "chain_id": "report-weekly-abc123",
      "agent": "olya",
      "started": "2026-06-08T13:55:00Z",
      "elapsed_ms": 65000,
      "progress": 90,
      "status": "running"
    }
  ],
  "count": 2
}
```

**Example: JavaScript**
```javascript
async function getActiveChains(token) {
  const res = await fetch("http://127.0.0.1:5000/chains/api/active");
  const data = await res.json();
  return data.active;
}
```

---

### 5. GET /api/chains/<chain_id>

Get current status of a specific chain execution.

**URL**: `GET http://127.0.0.1:5052/api/n8n/chain/<chain_id>`

**Request Headers**
```
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

**Response (200 OK)**
```json
{
  "ok": true,
  "execution": {
    "chain_id": "content-pub-550e8400",
    "chain_name": "content_publication",
    "from_agent": "olya",
    "to_agent": "marina",
    "status": "running",
    "progress": 65,
    "started_at": "2026-06-08T14:00:00Z",
    "completed_at": null,
    "result": null,
    "error": null,
    "task_id": "task-abc123",
    "input_data": {
      "post_id": "12345",
      "approval_status": "ready"
    }
  }
}
```

**Possible Status Values**
- `pending` — Waiting to start
- `running` — Currently executing
- `success` — Completed successfully
- `failed` — Failed with error
- `cancelled` — Cancelled by user
- `timeout` — Exceeded timeout limit

**Example: Python**
```python
def get_chain_status(chain_id: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"http://127.0.0.1:5052/api/n8n/chain/{chain_id}",
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()["execution"]
```

---

### 6. GET /api/chains/<chain_id>/logs

Retrieve all logged interactions for a chain.

**URL**: `GET http://127.0.0.1:5052/api/n8n/logs/<chain_id>`

**Request Headers**
```
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

**Response (200 OK)**
```json
{
  "ok": true,
  "chain_id": "content-pub-550e8400",
  "log_entries": [
    {
      "timestamp": "2026-06-08T14:00:00Z",
      "chain_id": "content-pub-550e8400",
      "event": "TRIGGER_REQUEST",
      "details": {
        "chain_name": "content_publication",
        "from_agent": "olya",
        "to_agent": "marina"
      }
    },
    {
      "timestamp": "2026-06-08T14:00:01Z",
      "chain_id": "content-pub-550e8400",
      "event": "CHAIN_ENQUEUED",
      "details": {
        "task_id": "task-abc123",
        "priority": 5
      }
    },
    {
      "timestamp": "2026-06-08T14:00:02Z",
      "chain_id": "content-pub-550e8400",
      "event": "STATUS_UPDATE",
      "details": {
        "status": "running",
        "progress": 25
      }
    },
    {
      "timestamp": "2026-06-08T14:00:10Z",
      "chain_id": "content-pub-550e8400",
      "event": "FINAL_STATUS",
      "details": {
        "status": "success",
        "result": {
          "publication_id": "post-67890",
          "published_at": "2026-06-09T10:00:00Z"
        }
      }
    }
  ]
}
```

**Log Events**
- `TRIGGER_REQUEST` — Chain triggered by n8n
- `CHAIN_ENQUEUED` — Task added to queue
- `STATUS_UPDATE` — Progress update
- `CHAIN_RETRY` — Chain retry initiated
- `CHAIN_CANCELLED` — Chain cancelled
- `N8N_ERROR` — Error from n8n workflow
- `FINAL_STATUS` — Chain completion

**Example: Python**
```python
def get_chain_logs(chain_id: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"http://127.0.0.1:5052/api/n8n/logs/{chain_id}",
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()["log_entries"]
```

---

### 7. POST /api/chains/<chain_id>/retry

Retry a failed chain with the same configuration.

**URL**: `POST http://127.0.0.1:5052/api/n8n/chain/<chain_id>/retry`

**Request Headers**
```
Content-Type: application/json
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

**Request Body** (optional)
```json
{
  "reason": "Retry after fixing dependency"
}
```

**Response (202 Accepted)**
```json
{
  "ok": true,
  "new_chain_id": "content-pub-550e8400-retry-1",
  "task_id": "task-def456",
  "status": "pending",
  "original_chain": "content-pub-550e8400",
  "message": "Retry chain created and monitoring started"
}
```

**Requirements**
- Original chain must have status `failed` or `timeout`
- Only one retry per original chain ID
- Retry uses same `input_data` as original

**Example: cURL**
```bash
curl -X POST "http://127.0.0.1:5052/api/n8n/chain/content-pub-550e8400/retry" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"reason": "Dependency became available"}'
```

**Example: Python**
```python
def retry_chain(chain_id: str, token: str, reason: str = None):
    body = {}
    if reason:
        body["reason"] = reason
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    
    resp = requests.post(
        f"http://127.0.0.1:5052/api/n8n/chain/{chain_id}/retry",
        json=body,
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()

# Usage
result = retry_chain("content-pub-550e8400", token, reason="Fixed upstream error")
print(f"New chain: {result['new_chain_id']}")
```

---

## n8n Integration API

### Additional n8n Endpoints

#### POST /api/n8n/schedule-trigger

Handle schedule-based triggers (cron-activated workflows).

**Request Body**
```json
{
  "chain_name": "weekly_report",
  "schedule": {
    "cron": "0 9 * * 1",
    "timezone": "America/Toronto",
    "trigger_time": "2026-06-08T14:00:00Z"
  },
  "n8n_webhook_url": "http://n8n:5678/webhook/status"
}
```

**Response (202 Accepted)**
```json
{
  "ok": true,
  "chain_id": "weekly_report-0-9-*-*-1-1717939200",
  "task_id": "task-ghi789",
  "status": "pending",
  "scheduled": true
}
```

#### GET /api/n8n/executions

List all chain executions with optional filtering.

**Query Parameters**
- `status` (string): Filter by status (pending, running, success, failed, cancelled, timeout)
- `limit` (integer): Max results (default: 100)

**Example**
```http
GET /api/n8n/executions?status=running&limit=20
Authorization: Bearer <token>
```

**Response (200 OK)**
```json
{
  "ok": true,
  "count": 2,
  "total": 15,
  "executions": [
    {
      "chain_id": "content-pub-550e8400",
      "status": "running",
      "progress": 65,
      "started_at": "2026-06-08T14:00:00Z"
    }
  ]
}
```

#### POST /api/n8n/notify

Receive status updates FROM n8n (reverse webhook).

**Request Body**
```json
{
  "workflow_id": "abc123",
  "execution_id": "exec456",
  "status": "success",
  "message": "Workflow completed",
  "result": {
    "posts_published": 5
  }
}
```

#### POST /api/n8n/error-callback

Receive and log errors from n8n workflows.

**Request Body**
```json
{
  "chain_id": "content-pub-550e8400",
  "workflow_id": "abc123",
  "error_code": "INSTAGRAM_API_ERROR",
  "error_message": "Rate limit exceeded",
  "stack_trace": "..."
}
```

---

## Error Handling

### Common HTTP Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | Success | Job complete, metadata retrieved |
| 202 | Accepted | Async job created, chain triggered |
| 400 | Bad Request | Missing required field, invalid agent |
| 401 | Unauthorized | Missing or invalid Bearer token |
| 404 | Not Found | Job/chain ID not found |
| 500 | Server Error | Internal processing error |

### Error Response Format

```json
{
  "ok": false,
  "error": "Human-readable error message"
}
```

### Example Error Responses

**Invalid agent**
```json
{
  "ok": false,
  "error": "Invalid agent key: unknown_agent"
}
```

**Missing required field**
```json
{
  "ok": false,
  "error": "message is required"
}
```

**Timeout waiting for result**
```json
{
  "status": "pending"
}
```

---

## Authentication

### Bearer Token Generation

For n8n webhook endpoints, generate a secure random token:

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Bash
openssl rand -base64 32
```

### Token Configuration

1. Generate token (once):
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Store in `tools/.env`:
   ```
   N8N_WEBHOOK_TOKEN=<generated-token>
   ```

3. Configure n8n to send token in all requests:
   ```
   Authorization: Bearer <same-token>
   ```

### Rotating Tokens

1. Generate new token
2. Update `N8N_WEBHOOK_TOKEN` in `tools/.env`
3. Update n8n workflow HTTP requests with new token
4. Restart `n8n_webhook.py` service

---

## Complete Example: Multi-Step Chain

This example shows a complete workflow: user initiates a content review chain that passes through multiple agents.

### 1. Start Chain (User → /api/chat)

```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "victoria",
    "message": "Отредактируй этот пост для Инстаграма",
    "chain_id": "content-review-6789"
  }'
```

Response:
```json
{
  "ok": true,
  "job": "job-xyz123",
  "agent": "victoria",
  "chain_id": "content-review-6789"
}
```

### 2. Poll for Victoria Result

```bash
curl http://127.0.0.1:5000/api/result?job=job-xyz123
```

When complete (Victoria suggests next agent):
```json
{
  "job": "job-xyz123",
  "agent_key": "victoria",
  "reply": "✓ Отредактировано. Готово к публикации.",
  "verdict": "ready_next",
  "next_agent": "marina",
  "chain_id": "content-review-6789",
  "chain_context": {
    "current_agent": "victoria",
    "chain_id": "content-review-6789"
  }
}
```

### 3. Pass to Next Agent (Marina)

```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "marina",
    "message": "Пост отредактирован. Предложи оптимальное время публикации.",
    "from_agent": "victoria",
    "chain_id": "content-review-6789"
  }'
```

### 4. Poll Marina Result

```bash
curl http://127.0.0.1:5000/api/result?job=job-abc456
```

Response:
```json
{
  "job": "job-abc456",
  "agent_key": "marina",
  "reply": "Рекомендую публиковать в 10:00 по Toronto времени.",
  "verdict": "done",
  "chain_id": "content-review-6789"
}
```

### 5. Alternative: Trigger Chain from n8n

```bash
curl -X POST http://127.0.0.1:5052/api/n8n/trigger-chain \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "chain_config": {
      "chain_name": "content_review_pipeline",
      "input_data": {
        "post_text": "...",
        "target_audience": "relationship coaches"
      }
    },
    "from_agent": "n8n_scheduler",
    "n8n_webhook_url": "http://n8n:5678/webhook/status"
  }'
```

Response:
```json
{
  "ok": true,
  "chain_id": "content-review-6789",
  "task_id": "task-n8n-001",
  "status": "pending"
}
```

Then check status:

```bash
curl http://127.0.0.1:5052/api/n8n/chain/content-review-6789 \
  -H "Authorization: Bearer <token>"
```

---

## Implementation Checklist

- [x] POST /api/chat with context parameters
- [x] GET /api/result with chain_context
- [x] POST /api/n8n/trigger-chain
- [x] GET /api/chains/active
- [x] GET /api/chains/<chain_id>
- [x] GET /api/chains/<chain_id>/logs
- [x] POST /api/chains/<chain_id>/retry
- [x] Request/response examples for all endpoints
- [x] Error handling documentation
- [x] Authentication (Bearer token)
- [x] Complete multi-step chain example

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-06-08 | Chain management & n8n integration added |
| 1.0 | 2026-05-01 | Initial agent chat API |

---

## Support

For issues with the API:

1. Check logs in `reports/webapp.log` (webapp) or `reports/n8n_logs/` (n8n)
2. Verify Bearer token is correct for n8n endpoints
3. Ensure environment variables are set (see [Base Information](#base-information))
4. Contact: getai.pro@gmail.com
