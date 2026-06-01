#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_bridge.py — local HTTP API for n8n (replaces disabled Execute Command nodes in n8n 2.x).

n8n 2.0+ blocks n8n-nodes-base.executeCommand by default → workflows show "?" icons.
This bridge runs on 127.0.0.1 only; n8n calls it via standard HTTP Request nodes.

Start:
    cd mila-office
    python n8n_bridge.py

Env (optional, root .env or tools/.env):
    N8N_BRIDGE_PORT=5051
    N8N_BRIDGE_TOKEN=...   # if set, requires Authorization: Bearer <token>
"""
import os
import sys
import json
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from flask import Flask, request, jsonify
from dotenv import load_dotenv

import memory
import policies

ROOT = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "tools" / ".env")

OFFICE = ROOT / "mila-office"
TOOLS = ROOT / "tools"
PORT = int(os.getenv("N8N_BRIDGE_PORT", "5051"))
TOKEN = (os.getenv("N8N_BRIDGE_TOKEN") or "").strip()
# LLM pipelines can run 10–30+ minutes
TIMEOUT_OFFICE = int(os.getenv("N8N_BRIDGE_OFFICE_TIMEOUT", "3600"))
TIMEOUT_TOOLS = int(os.getenv("N8N_BRIDGE_TOOLS_TIMEOUT", "600"))

# Allowlist скриптов, которые мост вправе запускать. Имя приходит из кода
# самого моста (не из запроса), но держим явный список — защита от того, что
# новый endpoint случайно прокинет произвольный путь, и явная карта рабочих папок.
_OFFICE_SCRIPTS = {"pipeline.py", "n8n_context.py"}
_TOOLS_SCRIPTS = {"pipeline.py", "get_analytics.py", "weekly_kpi.py",
                  "weekly_digest.py", "alert_errors.py", "n8n_notify.py",
                  "lead_capture.py", "healthcheck.py", "log_rotate.py",
                  "gumroad_webhook.py"}

app = Flask(__name__)


def _auth():
    """Мост слушает только 127.0.0.1, но всё равно требует Bearer-токен —
    n8n и любой локальный процесс должны его предъявить. Без заданного
    N8N_BRIDGE_TOKEN мост вообще не стартует (см. __main__), так что TOKEN тут
    всегда непустой."""
    hdr = request.headers.get("Authorization", "")
    if hdr == f"Bearer {TOKEN}":
        return None
    return jsonify({"ok": False, "error": "Unauthorized"}), 401


def _run(argv: list, cwd: Path, timeout: int) -> dict:
    """Запускает python-скрипт БЕЗ shell (argv-список) — инъекция в аргументах
    невозможна. Возвращает {ok, stdout, stderr, returncode}."""
    try:
        r = subprocess.run(
            [sys.executable, *argv], shell=False, cwd=str(cwd),
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stdout": (r.stdout or "")[-8000:],
            "stderr": (r.stderr or "")[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _office(*args: str, timeout: int = TIMEOUT_OFFICE) -> dict:
    if not args or args[0] not in _OFFICE_SCRIPTS:
        return {"ok": False, "error": f"script not allowed: {args[0] if args else '(none)'}"}
    return _run(list(args), OFFICE, timeout)


def _tools(*args: str, timeout: int = TIMEOUT_TOOLS) -> dict:
    if not args or args[0] not in _TOOLS_SCRIPTS:
        return {"ok": False, "error": f"script not allowed: {args[0] if args else '(none)'}"}
    return _run(list(args), TOOLS, timeout)


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "mila-n8n-bridge", "port": PORT})


@app.post("/v1/context")
def write_context():
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    event = body.get("event", "n8n")
    data = body.get("data", {})
    # Write via n8n_context.py (loads memory.py)
    payload_file = ROOT / "reports" / "_n8n_context_payload.json"
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    res = _office("n8n_context.py", "write", "--event", event,
                  "--file", str(payload_file), timeout=60)
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/pipeline/<chain>")
def run_pipeline(chain: str):
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    notify = request.args.get("notify", "").lower() in ("1", "true", "yes")
    direct = request.args.get("direct", "").lower() in ("1", "true", "yes")
    if direct:
        if not policies.can_run_direct(chain):
            return jsonify({"ok": False, "error": f"direct run disabled by policy for {chain}"}), 403
        args = ["pipeline.py", chain, "--direct"]
        if notify:
            args.append("--notify")
        res = _office(*args)
        return jsonify({"chain": chain, "notify": notify, "direct": True, **res}), (200 if res.get("ok") else 500)

    data = body.get("data") or {}
    if notify:
        data["notify"] = True
    dedupe_key = body.get("dedupe_key") or data.get("dedupe_key") or policies.default_dedupe_key(chain, data)
    priority = body.get("priority")
    if priority is None:
        priority = policies.default_priority(chain)
    rec = memory.enqueue_task(chain, priority=int(priority or 5), data=data, dedupe_key=dedupe_key)
    return jsonify({"ok": bool(rec.get("id")), "queued": True, "chain": chain, "task": rec}), (200 if rec.get("id") else 400)


@app.post("/v1/tasks")
def enqueue_task():
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    pipeline = body.get("pipeline")
    priority = body.get("priority")
    if priority is None:
        priority = policies.default_priority(pipeline)
    priority = int(priority or 5)
    data = body.get("data") or {}
    dedupe_key = body.get("dedupe_key") or data.get("dedupe_key") or policies.default_dedupe_key(pipeline, data)
    rec = memory.enqueue_task(pipeline, priority=priority, data=data, dedupe_key=dedupe_key)
    return jsonify(rec), (200 if rec.get("id") else 400)


@app.get("/v1/tasks")
def list_tasks():
    err = _auth()
    if err:
        return err
    status = request.args.get("status") or None
    return jsonify({"ok": True, "tasks": memory.list_tasks(status)})


@app.get("/v1/tasks/<task_id>")
def get_task(task_id: str):
    err = _auth()
    if err:
        return err
    rec = memory.get_task(task_id)
    return jsonify(rec), (200 if rec.get("id") else 404)


@app.post("/v1/tasks/<task_id>/retry")
def retry_task(task_id: str):
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    rec = memory.retry_task(task_id, reset_attempts=bool(body.get("reset_attempts")))
    return jsonify(rec), (200 if rec.get("id") else 400)


@app.post("/v1/tasks/<task_id>/cancel")
def cancel_task(task_id: str):
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    rec = memory.cancel_task(task_id, reason=body.get("reason", ""))
    return jsonify(rec), (200 if rec.get("id") else 400)


@app.post("/v1/tasks/<task_id>/unblock")
def unblock_task(task_id: str):
    err = _auth()
    if err:
        return err
    rec = memory.unblock_task(task_id)
    return jsonify(rec), (200 if rec.get("id") else 400)


@app.post("/v1/tasks/worker")
def run_worker():
    err = _auth()
    if err:
        return err
    res = _office("pipeline.py", "worker")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.get("/v1/status")
def office_status():
    err = _auth()
    if err:
        return err
    return jsonify(memory.office_status())


@app.post("/v1/tools/publish_due")
def publish_due():
    err = _auth()
    if err:
        return err
    res = _tools("pipeline.py", "publish_due")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/get_analytics/<kind>")
def get_analytics(kind: str):
    err = _auth()
    if err:
        return err
    if kind not in ("account", "posts", "comments"):
        return jsonify({"ok": False, "error": f"unknown kind: {kind}"}), 400
    res = _tools("get_analytics.py", kind)
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/measure_due")
def measure_due():
    """48ч-петля: дописать охват постам старше 48ч (см. tools/pipeline.py measure_due)."""
    err = _auth()
    if err:
        return err
    res = _tools("pipeline.py", "measure_due")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/healthcheck")
def healthcheck():
    """Утренний health-check: 6 проверок + одна строка Людмиле в Telegram."""
    err = _auth()
    if err:
        return err
    res = _tools("healthcheck.py")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/log_rotate")
def log_rotate():
    """Ротация логов, чтобы файлы не росли бесконечно (tools/log_rotate.py)."""
    err = _auth()
    if err:
        return err
    res = _tools("log_rotate.py")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/weekly_kpi")
def weekly_kpi():
    err = _auth()
    if err:
        return err
    res = _tools("weekly_kpi.py")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/weekly_digest")
def weekly_digest():
    err = _auth()
    if err:
        return err
    res = _tools("weekly_digest.py")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/tools/alert_errors")
def alert_errors():
    err = _auth()
    if err:
        return err
    res = _tools("alert_errors.py")
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/notify")
def notify():
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    payload_file = ROOT / "reports" / "n8n_last_webhook.json"
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    res = _tools("n8n_notify.py", "--file", str(payload_file), timeout=60)
    return jsonify(res), (200 if res.get("ok") else 500)


@app.post("/v1/lead")
def new_lead():
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    payload_file = ROOT / "reports" / "n8n_new_lead.json"
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    # shell=False уже исключает инъекцию команд; дополнительно гасим ведущие
    # дефисы, чтобы значение из вебхука не подменило argparse-флаг, и режем длину.
    def _arg(v, default):
        s = str(v if v is not None else default)[:500]
        return s.lstrip("-").strip() or default

    name = _arg(body.get("name") or body.get("tg_name"), "lead")
    telegram = _arg(body.get("telegram") or body.get("tg_username"), "webhook")
    message = _arg(body.get("message") or body.get("last_message"), "ХОЧУ")

    steps = {}
    steps["capture"] = _tools(
        "lead_capture.py", "--name", name, "--telegram", telegram,
        "--message", message, "--source", "n8n",
    )
    steps["context"] = _office(
        "n8n_context.py", "write", "--event", "new_lead",
        "--file", str(payload_file), timeout=60,
    )
    lead_data = {
        "notify": True,
        "source": "lead",
        "name": name,
        "telegram": telegram,
    }
    task = memory.enqueue_task(
        "new_client",
        priority=policies.default_priority("new_client"),
        data=lead_data,
        dedupe_key=policies.default_dedupe_key("new_client", lead_data),
    )
    steps["pipeline"] = {"ok": bool(task.get("id")), "queued": True, "task": task}
    ok = steps["pipeline"].get("ok")
    return jsonify({"ok": ok, "steps": steps}), (200 if ok else 500)


@app.post("/v1/gumroad/sale")
def gumroad_sale():
    """Вебхук продажи Gumroad. Аутентификацию (общий секрет / HMAC / seller_id)
    делает сам gumroad_webhook.py — чужой POST без секрета будет отклонён там.
    Тело вебхука передаём файлом; HMAC-подпись (если есть) — флагом."""
    err = _auth()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    payload_file = ROOT / "reports" / "n8n_gumroad_sale.json"
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    sig = request.headers.get("X-Gumroad-Signature", "")
    args = ["gumroad_webhook.py", "--file", str(payload_file)]
    if sig:
        args += ["--signature", sig]
    res = _tools(*args, timeout=60)
    return jsonify(res), (200 if res.get("ok") else 500)


if __name__ == "__main__":
    if not TOKEN:
        sys.exit(
            "ОТКАЗ: N8N_BRIDGE_TOKEN не задан. Мост исполняет команды — без токена "
            "не запускаюсь. Добавь в tools/.env:\n"
            "    N8N_BRIDGE_TOKEN=<сгенерируй: python -c \"import secrets;print(secrets.token_urlsafe(32))\">\n"
            "и пропиши его в n8n (HTTP Request → Header Authorization: Bearer <token>)."
        )
    print(f"MILA n8n bridge → http://127.0.0.1:{PORT}/health  (auth: Bearer required)")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
