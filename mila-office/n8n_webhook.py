#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_webhook.py — n8n integration layer with chain monitoring and status callbacks.

Manages bi-directional communication between n8n workflows and MILA Office agent chains.
Features:
  1. POST /api/n8n/trigger-chain — start agent chain from n8n
  2. Accept {chain_config, from_agent, to_agent, chain_id}
  3. Monitor chain execution and call n8n with status updates via webhook
  4. Handle n8n schedule-based triggers (cron patterns)
  5. Error callbacks back to n8n with detailed diagnostics
  6. Comprehensive logging of all n8n interactions

Usage:
    cd mila-office
    python n8n_webhook.py

Env (root .env or tools/.env):
    N8N_WEBHOOK_PORT=5052
    N8N_WEBHOOK_TOKEN=...         # Bearer token required
    N8N_STATUS_WEBHOOK_URL=...    # where to send status updates (e.g. n8n webhook)
    N8N_ERROR_WEBHOOK_URL=...     # separate error callback URL (optional)
    N8N_WEBHOOK_TIMEOUT=300       # max seconds to wait for chain completion

The webhook server listens only on 127.0.0.1 and requires Bearer token auth on all endpoints.
Status updates are sent back to n8n with: {ok, chain_id, status, progress, result, timestamp}
"""
import os
import sys
import json
import logging
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import queue

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Local imports
import memory
import policies

# ─── CONFIG ──────────────────────────────────────────────────────
ROOT = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "tools" / ".env")

OFFICE = ROOT / "mila-office"
LOGS_DIR = ROOT / "reports" / "n8n_logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(os.getenv("N8N_WEBHOOK_PORT", "5052"))
TOKEN = (os.getenv("N8N_WEBHOOK_TOKEN") or "").strip()
STATUS_WEBHOOK = (os.getenv("N8N_STATUS_WEBHOOK_URL") or "").strip()
ERROR_WEBHOOK = (os.getenv("N8N_ERROR_WEBHOOK_URL") or STATUS_WEBHOOK).strip()
TIMEOUT_CHAIN = int(os.getenv("N8N_WEBHOOK_TIMEOUT", "300"))

try:
    import requests
except ImportError:
    requests = None

# ─── LOGGING ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "n8n_webhook.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("n8n_webhook")


# ─── DATA MODELS ──────────────────────────────────────────────────
class ChainStatus(Enum):
    """Chain execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ChainExecution:
    """Tracks a single chain execution triggered by n8n."""
    chain_id: str
    chain_name: str
    from_agent: Optional[str] = None
    to_agent: Optional[str] = None
    status: ChainStatus = ChainStatus.PENDING
    progress: int = 0  # 0-100
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    n8n_webhook_url: Optional[str] = None
    task_id: Optional[str] = None  # memory.py task ID
    input_data: Optional[Dict[str, Any]] = None

    def to_dict(self):
        """Serialize to dict, converting enums."""
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def to_webhook_payload(self):
        """Format for sending to n8n webhook."""
        return {
            "ok": self.status in (ChainStatus.SUCCESS,),
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "status": self.status.value,
            "progress": self.progress,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ─── GLOBAL STATE ──────────────────────────────────────────────────
app = Flask(__name__)
executions: Dict[str, ChainExecution] = {}
execution_lock = threading.Lock()
status_queue = queue.Queue()  # Async webhook delivery


def _log_interaction(chain_id: str, event: str, details: Optional[Dict] = None, level: str = "INFO"):
    """Log n8n interaction to file and console."""
    log_file = LOGS_DIR / f"chain_{chain_id}.log"
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        "timestamp": timestamp,
        "chain_id": chain_id,
        "event": event,
        "details": details or {},
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"[{chain_id}] {event}: {details}")


def _auth():
    """Verify Bearer token. All endpoints require it."""
    hdr = request.headers.get("Authorization", "")
    if hdr == f"Bearer {TOKEN}":
        return None
    return jsonify({"ok": False, "error": "Unauthorized"}), 401


def _send_webhook(url: str, payload: Dict, timeout: int = 10, retry: int = 3):
    """Send status/error webhook to n8n with retries."""
    if not url or not requests:
        return False

    for attempt in range(retry):
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code in (200, 201, 204):
                logger.info(f"Webhook sent to {url}: {resp.status_code}")
                return True
            else:
                logger.warning(f"Webhook {url} returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Webhook attempt {attempt + 1}/{retry} failed: {e}")
            if attempt < retry - 1:
                time.sleep(2 ** attempt)  # exponential backoff
    return False


def _send_status_async(chain_id: str, url: str, payload: Dict):
    """Queue webhook for async delivery (doesn't block response)."""
    if url:
        status_queue.put((chain_id, url, payload))


def _webhook_worker():
    """Background thread: drain status_queue and send webhooks."""
    while True:
        try:
            chain_id, url, payload = status_queue.get(timeout=5)
            _send_webhook(url, payload, timeout=10, retry=2)
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Webhook worker error: {e}")


def _start_chain_task(chain_id: str, chain_name: str, input_data: Dict, task_priority: int = 5):
    """Enqueue chain as a memory.py task and return task_id."""
    try:
        dedupe_key = input_data.get("dedupe_key") or policies.default_dedupe_key(chain_name, input_data)
        task = memory.enqueue_task(
            chain_name,
            priority=task_priority,
            data=input_data,
            dedupe_key=dedupe_key,
        )
        return task.get("id"), task
    except Exception as e:
        logger.error(f"Failed to enqueue chain {chain_id}: {e}")
        return None, None


def _monitor_chain(execution: ChainExecution):
    """Monitor chain task and update execution status with periodic webhooks."""
    _log_interaction(
        execution.chain_id,
        "MONITOR_START",
        {"task_id": execution.task_id, "chain": execution.chain_name},
    )

    start_time = time.time()
    last_webhook_time = start_time
    webhook_interval = 5  # Send status every 5 seconds

    while time.time() - start_time < TIMEOUT_CHAIN:
        try:
            # Check task status
            task = memory.get_task(execution.task_id) if execution.task_id else None
            if not task:
                execution.status = ChainStatus.FAILED
                execution.error = "Task not found in memory"
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                break

            # Update progress based on task status
            task_status = task.get("status", "pending")
            if task_status == "running":
                if execution.status != ChainStatus.RUNNING:
                    execution.status = ChainStatus.RUNNING
                    execution.started_at = datetime.now(timezone.utc).isoformat()
                execution.progress = min(50, execution.progress + 5)
            elif task_status == "completed":
                execution.status = ChainStatus.SUCCESS
                execution.progress = 100
                execution.result = task.get("result", {})
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                break
            elif task_status == "failed":
                execution.status = ChainStatus.FAILED
                execution.error = task.get("error", "Chain execution failed")
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                break
            elif task_status == "cancelled":
                execution.status = ChainStatus.CANCELLED
                execution.error = task.get("reason", "Chain was cancelled")
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                break

            # Send periodic status update
            now = time.time()
            if execution.n8n_webhook_url and (now - last_webhook_time) >= webhook_interval:
                payload = execution.to_webhook_payload()
                _send_status_async(execution.chain_id, execution.n8n_webhook_url, payload)
                last_webhook_time = now
                _log_interaction(
                    execution.chain_id,
                    "STATUS_UPDATE",
                    {"status": execution.status.value, "progress": execution.progress},
                )

        except Exception as e:
            logger.error(f"Monitor loop error for {execution.chain_id}: {e}")

        time.sleep(1)  # Poll every second

    # Timeout check
    if execution.status in (ChainStatus.PENDING, ChainStatus.RUNNING):
        execution.status = ChainStatus.TIMEOUT
        execution.error = f"Chain did not complete within {TIMEOUT_CHAIN}s"
        execution.completed_at = datetime.now(timezone.utc).isoformat()

    # Final webhook
    if execution.n8n_webhook_url:
        final_payload = execution.to_webhook_payload()
        _send_status_async(execution.chain_id, execution.n8n_webhook_url, final_payload)
        _log_interaction(
            execution.chain_id,
            "FINAL_STATUS",
            {"status": execution.status.value, "result": execution.result},
        )

    logger.info(f"Monitor complete for {execution.chain_id}: {execution.status.value}")


# ─── ENDPOINTS ────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "ok": True,
        "service": "mila-n8n-webhook",
        "port": PORT,
        "executions_active": len([e for e in executions.values() if e.status == ChainStatus.RUNNING]),
    })


@app.post("/api/n8n/trigger-chain")
def trigger_chain():
    """
    POST /api/n8n/trigger-chain

    Start an agent chain from n8n. Requires Bearer token.

    Request body:
    {
        "chain_config": {
            "chain_name": "content_week",
            "input_data": { ... }
        },
        "from_agent": "olya",
        "to_agent": "marina",
        "chain_id": "uuid-or-custom-id",
        "n8n_webhook_url": "http://n8n:5678/webhook/status",
        "priority": 5
    }

    Response:
    {
        "ok": true,
        "chain_id": "...",
        "task_id": "...",
        "status": "pending"
    }
    """
    err = _auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    chain_config = body.get("chain_config", {})
    chain_name = chain_config.get("chain_name") or body.get("chain")
    input_data = chain_config.get("input_data") or body.get("data", {})
    from_agent = body.get("from_agent", "n8n")
    to_agent = body.get("to_agent", "auto")
    chain_id = body.get("chain_id") or str(uuid.uuid4())
    n8n_webhook_url = body.get("n8n_webhook_url") or STATUS_WEBHOOK
    priority = body.get("priority", 5)

    if not chain_name:
        return jsonify({"ok": False, "error": "chain_name is required"}), 400

    _log_interaction(
        chain_id,
        "TRIGGER_REQUEST",
        {
            "chain_name": chain_name,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "webhook": n8n_webhook_url,
        },
    )

    # Create execution record
    execution = ChainExecution(
        chain_id=chain_id,
        chain_name=chain_name,
        from_agent=from_agent,
        to_agent=to_agent,
        status=ChainStatus.PENDING,
        n8n_webhook_url=n8n_webhook_url,
        input_data=input_data,
    )

    # Enqueue task
    task_id, task = _start_chain_task(chain_id, chain_name, input_data, int(priority))
    if not task_id:
        execution.status = ChainStatus.FAILED
        execution.error = "Failed to enqueue task"
        with execution_lock:
            executions[chain_id] = execution
        return jsonify({"ok": False, "error": "Failed to enqueue task", "chain_id": chain_id}), 500

    execution.task_id = task_id
    execution.status = ChainStatus.PENDING

    with execution_lock:
        executions[chain_id] = execution

    _log_interaction(
        chain_id,
        "CHAIN_ENQUEUED",
        {"task_id": task_id, "priority": priority},
    )

    # Start monitoring thread (doesn't block response)
    monitor_thread = threading.Thread(
        target=_monitor_chain,
        args=(execution,),
        daemon=True,
        name=f"monitor-{chain_id}",
    )
    monitor_thread.start()

    # Immediate response
    return jsonify({
        "ok": True,
        "chain_id": chain_id,
        "task_id": task_id,
        "status": execution.status.value,
        "message": "Chain triggered and monitoring started",
    }), 202


@app.get("/api/n8n/chain/<chain_id>")
def get_chain_status(chain_id: str):
    """
    GET /api/n8n/chain/<chain_id>

    Get current status of a chain execution. Requires Bearer token.

    Response:
    {
        "ok": true,
        "execution": { chain_id, status, progress, result, error, ... }
    }
    """
    err = _auth()
    if err:
        return err

    with execution_lock:
        execution = executions.get(chain_id)

    if not execution:
        return jsonify({"ok": False, "error": f"Chain {chain_id} not found"}), 404

    return jsonify({
        "ok": True,
        "execution": execution.to_dict(),
    }), 200


@app.post("/api/n8n/chain/<chain_id>/cancel")
def cancel_chain(chain_id: str):
    """
    POST /api/n8n/chain/<chain_id>/cancel

    Cancel a running chain. Requires Bearer token.

    Request body (optional):
    {
        "reason": "User cancelled"
    }

    Response:
    {
        "ok": true,
        "chain_id": "...",
        "status": "cancelled"
    }
    """
    err = _auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "Cancelled via webhook")

    with execution_lock:
        execution = executions.get(chain_id)

    if not execution:
        return jsonify({"ok": False, "error": f"Chain {chain_id} not found"}), 404

    # Cancel underlying task
    if execution.task_id:
        memory.cancel_task(execution.task_id, reason=reason)

    execution.status = ChainStatus.CANCELLED
    execution.error = reason
    execution.completed_at = datetime.now(timezone.utc).isoformat()

    _log_interaction(chain_id, "CHAIN_CANCELLED", {"reason": reason})

    # Send cancellation webhook
    if execution.n8n_webhook_url:
        payload = execution.to_webhook_payload()
        _send_status_async(chain_id, execution.n8n_webhook_url, payload)

    return jsonify({
        "ok": True,
        "chain_id": chain_id,
        "status": execution.status.value,
    }), 200


@app.post("/api/n8n/chain/<chain_id>/retry")
def retry_chain(chain_id: str):
    """
    POST /api/n8n/chain/<chain_id>/retry

    Retry a failed chain. Creates a new execution. Requires Bearer token.

    Response:
    {
        "ok": true,
        "new_chain_id": "...",
        "task_id": "...",
        "status": "pending"
    }
    """
    err = _auth()
    if err:
        return err

    with execution_lock:
        execution = executions.get(chain_id)

    if not execution:
        return jsonify({"ok": False, "error": f"Chain {chain_id} not found"}), 404

    if execution.status not in (ChainStatus.FAILED, ChainStatus.TIMEOUT):
        return jsonify({
            "ok": False,
            "error": f"Can only retry failed chains; current status: {execution.status.value}"
        }), 400

    # Create new execution with same config
    new_chain_id = str(uuid.uuid4())
    new_execution = ChainExecution(
        chain_id=new_chain_id,
        chain_name=execution.chain_name,
        from_agent=execution.from_agent,
        to_agent=execution.to_agent,
        n8n_webhook_url=execution.n8n_webhook_url,
        input_data=execution.input_data,
    )

    task_id, task = _start_chain_task(
        new_chain_id,
        execution.chain_name,
        execution.input_data or {},
    )
    if not task_id:
        return jsonify({"ok": False, "error": "Failed to enqueue retry task"}), 500

    new_execution.task_id = task_id
    with execution_lock:
        executions[new_chain_id] = new_execution

    _log_interaction(
        new_chain_id,
        "CHAIN_RETRY",
        {"original_chain": chain_id, "task_id": task_id},
    )

    # Start monitoring
    monitor_thread = threading.Thread(
        target=_monitor_chain,
        args=(new_execution,),
        daemon=True,
        name=f"monitor-{new_chain_id}",
    )
    monitor_thread.start()

    return jsonify({
        "ok": True,
        "new_chain_id": new_chain_id,
        "task_id": task_id,
        "status": new_execution.status.value,
    }), 202


@app.get("/api/n8n/executions")
def list_executions():
    """
    GET /api/n8n/executions?status=running&limit=10

    List all chain executions, optionally filtered by status. Requires Bearer token.

    Query params:
      status: 'pending', 'running', 'success', 'failed', 'cancelled', 'timeout'
      limit: max results (default 100)

    Response:
    {
        "ok": true,
        "executions": [ { chain_id, status, progress, ... }, ... ]
    }
    """
    err = _auth()
    if err:
        return err

    status_filter = request.args.get("status", "").lower()
    limit = int(request.args.get("limit", "100"))

    with execution_lock:
        all_executions = list(executions.values())

    if status_filter:
        all_executions = [
            e for e in all_executions
            if e.status.value.lower() == status_filter
        ]

    all_executions.sort(key=lambda e: e.started_at or "", reverse=True)
    limited = all_executions[:limit]

    return jsonify({
        "ok": True,
        "count": len(limited),
        "total": len(all_executions),
        "executions": [e.to_dict() for e in limited],
    }), 200


@app.post("/api/n8n/schedule-trigger")
def schedule_trigger():
    """
    POST /api/n8n/schedule-trigger

    Handle schedule-based trigger from n8n (e.g. cron-activated workflow).
    Similar to trigger-chain but tracks schedule metadata.

    Request body:
    {
        "chain_name": "weekly_report",
        "schedule": {
            "cron": "0 9 * * 1",
            "timezone": "America/Toronto",
            "trigger_time": "2026-06-08T14:00:00Z"
        },
        "n8n_webhook_url": "..."
    }

    Response:
    {
        "ok": true,
        "chain_id": "...",
        "task_id": "...",
        "scheduled": true
    }
    """
    err = _auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    chain_name = body.get("chain_name")
    schedule_info = body.get("schedule", {})
    n8n_webhook_url = body.get("n8n_webhook_url") or STATUS_WEBHOOK

    if not chain_name:
        return jsonify({"ok": False, "error": "chain_name is required"}), 400

    chain_id = f"{chain_name}-{schedule_info.get('cron', 'manual')}-{int(time.time())}"
    input_data = {
        "from_schedule": True,
        "cron": schedule_info.get("cron"),
        "timezone": schedule_info.get("timezone"),
        "trigger_time": schedule_info.get("trigger_time"),
    }

    _log_interaction(
        chain_id,
        "SCHEDULE_TRIGGER",
        {
            "chain": chain_name,
            "cron": schedule_info.get("cron"),
            "trigger_time": schedule_info.get("trigger_time"),
        },
    )

    execution = ChainExecution(
        chain_id=chain_id,
        chain_name=chain_name,
        from_agent="n8n_schedule",
        to_agent="auto",
        status=ChainStatus.PENDING,
        n8n_webhook_url=n8n_webhook_url,
        input_data=input_data,
    )

    task_id, task = _start_chain_task(chain_id, chain_name, input_data, priority=3)
    if not task_id:
        execution.status = ChainStatus.FAILED
        execution.error = "Failed to enqueue scheduled task"
        with execution_lock:
            executions[chain_id] = execution
        return jsonify({"ok": False, "error": "Failed to enqueue task", "chain_id": chain_id}), 500

    execution.task_id = task_id
    with execution_lock:
        executions[chain_id] = execution

    monitor_thread = threading.Thread(
        target=_monitor_chain,
        args=(execution,),
        daemon=True,
        name=f"monitor-{chain_id}",
    )
    monitor_thread.start()

    return jsonify({
        "ok": True,
        "chain_id": chain_id,
        "task_id": task_id,
        "status": execution.status.value,
        "scheduled": True,
    }), 202


@app.post("/api/n8n/notify")
def receive_n8n_status():
    """
    POST /api/n8n/notify

    Receive status update FROM n8n (e.g. n8n workflow completed).
    Allows n8n to inform us about its own execution state (reverse webhook).

    Request body:
    {
        "workflow_id": "...",
        "execution_id": "...",
        "status": "success|error",
        "message": "...",
        "result": { ... }
    }

    Response:
    {
        "ok": true,
        "received": true
    }
    """
    err = _auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    workflow_id = body.get("workflow_id", "unknown")
    execution_id = body.get("execution_id", "unknown")
    status = body.get("status", "unknown")

    payload_file = ROOT / "reports" / "n8n_last_notification.json"
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    logger.info(f"Received n8n notification: workflow={workflow_id}, status={status}")

    # Could extend: update memory, trigger related chains, etc.
    return jsonify({
        "ok": True,
        "received": True,
        "workflow_id": workflow_id,
    }), 200


@app.post("/api/n8n/error-callback")
def error_callback():
    """
    POST /api/n8n/error-callback

    Receive and log errors from n8n workflows. Alternative to n8n notifying us via
    webhook — can be called directly from n8n error handlers.

    Request body:
    {
        "chain_id": "...",
        "workflow_id": "...",
        "error_code": "...",
        "error_message": "...",
        "stack_trace": "..."
    }

    Response:
    {
        "ok": true,
        "logged": true
    }
    """
    err = _auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    chain_id = body.get("chain_id", "unknown")
    workflow_id = body.get("workflow_id", "unknown")
    error_code = body.get("error_code", "unknown")
    error_msg = body.get("error_message", "")

    _log_interaction(
        chain_id,
        "N8N_ERROR",
        {
            "workflow_id": workflow_id,
            "error_code": error_code,
            "error_message": error_msg,
        },
        level="ERROR",
    )

    # Optionally send to error webhook
    if ERROR_WEBHOOK and ERROR_WEBHOOK != STATUS_WEBHOOK:
        payload = {
            "ok": False,
            "chain_id": chain_id,
            "workflow_id": workflow_id,
            "error_code": error_code,
            "error_message": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _send_webhook(ERROR_WEBHOOK, payload)

    return jsonify({
        "ok": True,
        "logged": True,
        "chain_id": chain_id,
    }), 200


@app.get("/api/n8n/logs/<chain_id>")
def get_chain_logs(chain_id: str):
    """
    GET /api/n8n/logs/<chain_id>

    Retrieve all logged interactions for a chain. Requires Bearer token.

    Response:
    {
        "ok": true,
        "chain_id": "...",
        "log_entries": [ { timestamp, event, details }, ... ]
    }
    """
    err = _auth()
    if err:
        return err

    log_file = LOGS_DIR / f"chain_{chain_id}.log"
    if not log_file.exists():
        return jsonify({
            "ok": True,
            "chain_id": chain_id,
            "log_entries": [],
            "message": "No logs found",
        }), 200

    try:
        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return jsonify({
            "ok": True,
            "chain_id": chain_id,
            "log_entries": entries,
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Failed to read logs: {e}",
        }), 500


# ─── STARTUP ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        sys.exit(
            "ERROR: N8N_WEBHOOK_TOKEN not set. This service executes chains — "
            "it requires Bearer token auth. Set in tools/.env:\n"
            "    N8N_WEBHOOK_TOKEN=<generate: python -c \"import secrets;print(secrets.token_urlsafe(32))\">\n"
            "and configure n8n to send it in the Authorization header."
        )

    # Start background webhook worker
    webhook_thread = threading.Thread(target=_webhook_worker, daemon=True, name="webhook-worker")
    webhook_thread.start()

    logger.info(f"MILA n8n webhook → http://127.0.0.1:{PORT}/health (auth: Bearer required)")
    logger.info(f"Status webhook: {STATUS_WEBHOOK or '(none)'}")
    logger.info(f"Logs directory: {LOGS_DIR}")

    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
