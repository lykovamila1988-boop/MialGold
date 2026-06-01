# -*- coding: utf-8 -*-
"""Small health loop for MILA Office.

It keeps local services visible, starts missing Python services when possible,
runs one queue worker per tick, and writes memory/supervisor_status.json.
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

import memory

OFFICE_DIR = Path(__file__).resolve().parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _probe(url: str, timeout: float = 3.0) -> dict:
    try:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:
            return {"up": 200 <= resp.status < 500, "status": resp.status, "url": url}
    except error.HTTPError as e:
        return {"up": e.code < 500, "status": e.code, "url": url}
    except Exception as e:
        return {"up": False, "error": type(e).__name__, "url": url}


def _start_python(script: str) -> dict:
    try:
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=str(OFFICE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return {"started": True, "pid": proc.pid, "cmd": f"{sys.executable} {script}"}
    except Exception as e:
        return {"started": False, "error": str(e)[:200], "cmd": f"{sys.executable} {script}"}


def _start_command(command: str) -> dict:
    if not command.strip():
        return {"started": False, "reason": "not_configured"}
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(OFFICE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return {"started": True, "pid": proc.pid, "cmd": command}
    except Exception as e:
        return {"started": False, "error": str(e)[:200], "cmd": command}


def _run_worker(timeout: int) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "pipeline.py", "worker"],
            cwd=str(OFFICE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "duration_seconds": round(time.time() - started, 2),
            "stdout_tail": (proc.stdout or "")[-1200:],
            "stderr_tail": (proc.stderr or "")[-1200:],
            "ts": _now(),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 2),
            "error": "timeout",
            "stdout_tail": (e.stdout or "")[-1200:] if isinstance(e.stdout, str) else "",
            "stderr_tail": (e.stderr or "")[-1200:] if isinstance(e.stderr, str) else "",
            "ts": _now(),
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 2),
            "error": str(e)[:300],
            "ts": _now(),
        }


def tick(start_missing: bool, run_worker: bool, worker_timeout: int,
         previous: dict | None = None) -> dict:
    previous = previous or {}
    bridge_port = os.getenv("N8N_BRIDGE_PORT", "5051")
    n8n_url = os.getenv("N8N_BASE_URL", "http://127.0.0.1:5678").rstrip("/")
    services = {
        "webapp": _probe("http://127.0.0.1:5000/api/meta"),
        "bridge": _probe(f"http://127.0.0.1:{bridge_port}/health"),
        "n8n": _probe(f"{n8n_url}/healthz"),
    }

    starts = {}
    if start_missing:
        if not services["webapp"].get("up"):
            starts["webapp"] = _start_python("webapp.py")
        if not services["bridge"].get("up"):
            starts["bridge"] = _start_python("n8n_bridge.py")
        if not services["n8n"].get("up"):
            starts["n8n"] = _start_command(os.getenv("N8N_CMD", ""))

    last_worker = previous.get("last_worker")
    if run_worker:
        last_worker = _run_worker(worker_timeout)

    status = {
        "status": "ok" if all(s.get("up") for s in services.values()) else "degraded",
        "pid": os.getpid(),
        "services": services,
        "starts": starts,
        "last_worker": last_worker,
    }
    memory.write_supervisor_status(status)
    memory.log_event("supervisor:tick", {
        "status": status["status"],
        "worker_ok": bool((last_worker or {}).get("ok")),
        "started": sorted(starts.keys()),
    })
    return status


def main():
    parser = argparse.ArgumentParser(description="MILA Office supervisor")
    parser.add_argument("--once", action="store_true", help="run one health tick and exit")
    parser.add_argument("--no-start", action="store_true", help="do not start missing services")
    parser.add_argument("--interval", type=int, default=_env_int("SUPERVISOR_INTERVAL", 30))
    parser.add_argument("--worker-interval", type=int, default=_env_int("SUPERVISOR_WORKER_INTERVAL", 30))
    parser.add_argument("--worker-timeout", type=int, default=_env_int("SUPERVISOR_WORKER_TIMEOUT", 7200))
    args = parser.parse_args()

    last_worker_ts = 0.0
    previous = memory.read_supervisor_status()
    while True:
        now = time.time()
        should_run_worker = args.once or (now - last_worker_ts >= max(1, args.worker_interval))
        status = tick(
            start_missing=not args.no_start,
            run_worker=should_run_worker,
            worker_timeout=args.worker_timeout,
            previous=previous,
        )
        previous = status
        if should_run_worker:
            last_worker_ts = now
        print(status["status"], status["ts"] if "ts" in status else _now(), flush=True)
        if args.once:
            break
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
