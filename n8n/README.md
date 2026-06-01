# n8n workflows — MILA Office

**Read `SKILL.md` first** — especially if nodes show **?** icons.

n8n **2.x disables Execute Command** by default. These workflows use **HTTP Request**
nodes calling `mila-office/n8n_bridge.py` on `http://127.0.0.1:5051`.

## Quick start

```cmd
n8n\deploy.cmd
tools\start-mila-automation.cmd
```

Or separately:

```cmd
tools\start-n8n-bridge.cmd
tools\start-n8n-local.cmd
```

Activate workflows in http://127.0.0.1:5678 (toggle **Active** on each).

## Env

```
N8N_DONE_WEBHOOK=http://127.0.0.1:5678/webhook/office-done
N8N_BRIDGE_PORT=5051
```

## Workflows

| File | Trigger | Bridge |
|------|---------|--------|
| `01-publish-due-hourly` | Hourly | `/v1/tools/publish_due` |
| `02-monday-content-week` | Mon 06:00 | context + `/v1/pipeline/content_week` |
| `03-monday-brief` | Mon 07:00 | `/v1/pipeline/monday_brief` |
| `04-sunday-analytics` | Sun 16:00 | analytics + KPI + digest |
| `05-sunday-weekly-report` | Sun 17:00 | `/v1/pipeline/weekly_report` |
| `06-webhook-office-done` | POST webhook | `/v1/notify` |
| `07-webhook-new-lead` | POST webhook | `/v1/lead` |
| `08-alerts-webapp` | Every 15 min | `/v1/tools/alert_errors` |
| `09-monthly-competitive` | 1st of month | `/v1/pipeline/competitive_analysis` |

Delete broken old workflows in n8n UI if duplicates remain after re-deploy.
