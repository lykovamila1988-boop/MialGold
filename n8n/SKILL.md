# n8n + MILA Office — setup skill

Use this when n8n workflows show **?** icons, fail to activate, or report
`Unrecognized node type: n8n-nodes-base.executeCommand`.

## Root cause (n8n 2.x)

From n8n **2.0**, these nodes are **disabled by default** for security:

- `n8n-nodes-base.executeCommand` (Execute Command)
- `n8n-nodes-base.localFileTrigger`

MILA workflows must **not** use Execute Command. They call a local **HTTP bridge**
instead (`mila-office/n8n_bridge.py`) via standard **HTTP Request** nodes.

## Architecture

```
n8n (schedule / webhook)
    → HTTP Request → http://127.0.0.1:5051/v1/...
        → n8n_bridge.py
            → run-office.cmd / run-tools.cmd
                → pipeline.py, get_analytics.py, …
```

Pipeline completion optionally POSTs to `N8N_DONE_WEBHOOK` (n8n webhook
`MILA — Webhook office-done` → bridge `/v1/notify` → Telegram).

## Start (every session)

Two processes must run:

```cmd
tools\start-n8n-bridge.cmd    REM port 5051 — do this FIRST
tools\start-n8n-local.cmd     REM port 5678
```

Verify:

```cmd
curl http://127.0.0.1:5051/health
curl http://127.0.0.1:5678/healthz
```

## Deploy / update workflows

```cmd
n8n\deploy.cmd
```

Then in n8n UI (http://127.0.0.1:5678): open each **MILA —** workflow → toggle **Active**.

Set in `.env` or `tools/.env`:

```
N8N_DONE_WEBHOOK=http://127.0.0.1:5678/webhook/office-done
N8N_BRIDGE_PORT=5051
```

Optional auth:

```
N8N_BRIDGE_TOKEN=your-secret
```

If set, every HTTP Request node needs header `Authorization: Bearer your-secret`.

## Workflows (repo: `n8n/workflows/`)

| Workflow | Bridge endpoint |
|----------|-----------------|
| Publish due (hourly) | `POST /v1/tools/publish_due` |
| Monday content week | `POST /v1/context` → `POST /v1/pipeline/content_week?notify=1` |
| Monday brief | `POST /v1/pipeline/monday_brief?notify=1` |
| Sunday analytics | `/v1/tools/get_analytics/account` → posts → weekly_kpi → weekly_digest |
| Sunday weekly report | `POST /v1/pipeline/weekly_report?notify=1` |
| Webhook office-done | n8n webhook → `POST /v1/notify` |
| Webhook new lead | n8n webhook → `POST /v1/lead` |
| Webapp alerts | `POST /v1/tools/alert_errors` |
| Monthly competitive | `POST /v1/pipeline/competitive_analysis?notify=1` |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Nodes show **?** | Re-import with `n8n\deploy.cmd` (old Execute Command workflows) |
| HTTP Request fails ECONNREFUSED | Start `tools\start-n8n-bridge.cmd` |
| Pipeline timeout in n8n | HTTP Request node timeout = 3600000 ms (1 h) |
| Telegram notify empty | Set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ADMIN_CHAT_ID` in `tools/.env` |
| LLM pipeline errors | Check `ANTHROPIC_API_KEY` / Gemini keys in `.env` |
| Wrong n8n database | `N8N_USER_FOLDER` must be `E:\MILA GOLD\n8n-data` (see `deploy.cmd`) |

## Optional: re-enable Execute Command (not recommended)

If you insist on shell nodes, add to `tools/start-n8n-local.cmd` before `n8n start`:

```cmd
set "NODES_EXCLUDE=[n8n-nodes-base.localFileTrigger]"
```

Restart n8n. Prefer the HTTP bridge — no unsafe nodes, works on n8n Cloud limits too
(if bridge is reachable).

## Files

- `n8n/workflows/*.json` — workflow definitions (HTTP Request only)
- `n8n/deploy.cmd` — import into `n8n-data`
- `n8n/bin/run-office.cmd`, `run-tools.cmd` — subprocess wrappers
- `mila-office/n8n_bridge.py` — bridge server
- `mila-office/n8n_context.py` — memory/context helper
- `tools/n8n_notify.py` — Telegram from webhook payload
