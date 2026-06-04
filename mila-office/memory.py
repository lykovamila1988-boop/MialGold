# -*- coding: utf-8 -*-
"""
memory.py — общая память офиса: «язык», на котором n8n и агенты говорят друг
с другом, не зная друг о друге напрямую (Паттерн 3 из концепта).

Хранилище — JSON-файлы в mila-office/memory/. Все записи атомарны (temp+replace)
и под межпроцессным файловым замком, потому что писать сюда будут параллельно
и n8n (через Execute Command / отдельный процесс), и Python-агенты.

Слои:
  context.json       — последнее входящее событие из внешнего мира (n8n → агенты)
  agent_notes.json   — очередь заметок агент→агент (Алина → Лере и т.п.)
  published.json     — реестр публикаций для петли «измерь через 48ч» (Разрыв 1)
  events.jsonl       — append-only журнал всего, что происходило (аудит)

Ничего внешнего не импортирует (только stdlib) — чтобы memory.py могли
безопасно вызывать и агенты, и отдельные скрипты n8n.
"""
import os
import json
import time
import tempfile
import socket
from pathlib import Path
from datetime import datetime, timezone

MEM_DIR = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD")) / "mila-office" / "memory"
CONTEXT = MEM_DIR / "context.json"
NOTES = MEM_DIR / "agent_notes.json"
PUBLISHED = MEM_DIR / "published.json"
PROFILE = MEM_DIR / "profile.json"
COMPETITORS = MEM_DIR / "competitors.json"
EVENTS = MEM_DIR / "events.jsonl"
LOCKS = MEM_DIR / "locks.json"
HANDOFFS = MEM_DIR / "handoffs.json"
TASK_QUEUE = MEM_DIR / "task_queue.json"
APPROVALS = MEM_DIR / "approvals.json"
RATE_LIMITS = MEM_DIR / "rate_limits.json"
SUPERVISOR_STATUS = MEM_DIR / "supervisor_status.json"
REPLY_QUEUE = MEM_DIR / "reply_queue.json"
DOC_WORKFLOWS = MEM_DIR / "doc_workflows.json"
AGENT_HISTORIES = MEM_DIR / "agent_histories.json"
_LOCK = MEM_DIR / ".lock"
ACTIVE_TASK_STATUSES = {"pending", "running"}

# ─── Профиль офиса: стабильные defaults + фаза «холодного старта» ──────────
# ВАЖНО: профиль живёт ОТДЕЛЬНО от context.json. context.json перезаписывается
# целиком при каждом событии из n8n (write_context), поэтому defaults туда класть
# нельзя — их сотрёт первое же событие. profile.json n8n не трогает.
# Если файла нет — read_profile() возвращает эти DEFAULT_PROFILE, так что система
# полезна с первого дня даже без созданного файла (Фаза 0 «работает на defaults»).
DEFAULT_PROFILE = {
    "business": {
        "brand": "@liudmyla.lykova",
        "expert": "Людмила Лыкова, психолог, Канада",
        "audience": "женщины 25–45, болезненные отношения / тревожная привязанность",
        "ig_followers": 1300,
        "phase_override": None,        # null → фаза считается автоматически (см. current_phase)
        "sales_count": 0,             # обновляется вручную/из Gumroad до подключения авто-источника
        "best_content_type": "Reel",
        "best_posting_time": "10:00 UTC",
        "top_topics": [
            "тревожная привязанность",
            "паттерн Спасателя",
            "почему мы выбираем не тех",
        ],
        "products": "практикум $37 → консультация $120 → пакеты $420 / $750",
        "goal": "стабильные $5000/мес",
        "note": "Данных пока мало — это экспертные defaults, а не статистика.",
    }
}

# Пороги перехода фаз (Фаза 0 → 1 → 2). Главный задокументированный триггер —
# «10 постов + 2 продажи» → режим анализа (Стас из стратега запуска становится аналитиком).
_PHASE_LEARNING_POSTS = 5     # первые слабые паттерны
_PHASE_ANALYSIS_POSTS = 10
_PHASE_ANALYSIS_SALES = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now_ts() -> float:
    return time.time()


def _iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _ensure():
    MEM_DIR.mkdir(parents=True, exist_ok=True)


class _FileLock:
    """Простой межпроцессный замок через атомарное создание файла.
    Достаточно для локального однопользовательского офиса.
    Использует exponential backoff для уменьшения contention."""
    def __init__(self, path=_LOCK, timeout=15.0):
        self.path, self.timeout, self.fd = path, timeout, None

    def __enter__(self):
        _ensure()
        start = time.time()
        attempt = 0
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                elapsed = time.time() - start
                if elapsed > self.timeout:
                    # Замок завис (упавший процесс) — забираем силой.
                    try:
                        self.path.unlink()
                        continue
                    except OSError:
                        pass
                    raise TimeoutError(f"Could not acquire lock after {self.timeout}s")
                else:
                    # Exponential backoff с jitter: 10ms → 20ms → 40ms (up to 200ms)
                    delay = min(0.01 * (2 ** attempt) + (time.time() % 0.01), 0.2)
                    time.sleep(delay)
                    attempt += 1

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        try:
            self.path.unlink()
        except OSError:
            pass


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def _write_json(path: Path, data):
    """Атомарная запись: пишем во временный файл и заменяем — читатель никогда
    не увидит наполовину записанный JSON."""
    _ensure()
    fd, tmp = tempfile.mkstemp(dir=str(MEM_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def log_event(kind: str, payload: dict | None = None):
    """Append-only аудит всего, что прошло через память."""
    _ensure()
    rec = {"ts": _now(), "kind": kind, "payload": payload or {}}
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def recent_events(limit: int = 20, prefix: str | None = None) -> list:
    try:
        lines = EVENTS.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if prefix and not str(rec.get("kind", "")).startswith(prefix):
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return list(reversed(out))


# ─── COORDINATION: locks / handoffs / queue / approvals ──────────
def acquire_lock(resource: str, owner: str = "", ttl_seconds: int = 3600,
                 wait: bool = False, timeout: float = 0) -> dict:
    """Take a logical lock for a pipeline/resource."""
    resource = (resource or "").strip()
    if not resource:
        return {"ok": False, "error": "resource is required"}
    owner = (owner or f"pid:{os.getpid()}").strip()
    deadline = time.time() + max(0, float(timeout or 0))
    while True:
        now = time.time()
        with _FileLock():
            locks = _read_json(LOCKS, {})
            for key, rec in list(locks.items()):
                if float(rec.get("expires_at", 0) or 0) <= now:
                    locks.pop(key, None)
            current = locks.get(resource)
            if not current:
                rec = {
                    "resource": resource,
                    "owner": owner,
                    "pid": os.getpid(),
                    "acquired_at": _now(),
                    "expires_at": now + int(ttl_seconds or 3600),
                }
                locks[resource] = rec
                _write_json(LOCKS, locks)
                log_event("lock:acquired", {"resource": resource, "owner": owner})
                return {"ok": True, **rec}
            _write_json(LOCKS, locks)
        if not wait or time.time() >= deadline:
            return {"ok": False, "resource": resource,
                    "locked_by": current.get("owner"), "acquired_at": current.get("acquired_at")}
        time.sleep(0.25)


def release_lock(resource: str, owner: str = "") -> dict:
    """Release a logical lock. If owner is passed, it must match."""
    resource = (resource or "").strip()
    with _FileLock():
        locks = _read_json(LOCKS, {})
        current = locks.get(resource)
        if not current:
            return {"ok": True, "released": False, "resource": resource}
        if owner and current.get("owner") != owner:
            return {"ok": False, "error": "owner mismatch",
                    "resource": resource, "locked_by": current.get("owner")}
        locks.pop(resource, None)
        _write_json(LOCKS, locks)
    log_event("lock:released", {"resource": resource, "owner": owner or current.get("owner")})
    return {"ok": True, "released": True, "resource": resource}


def list_locks() -> dict:
    return _read_json(LOCKS, {})


def handoff(frm: str, to: str, payload: dict, status: str = "pending") -> dict:
    """Structured baton pass between agents."""
    with _FileLock():
        rows = _read_json(HANDOFFS, [])
        rec = {
            "id": f"h{max([int(str(r.get('id', 'h0')).lstrip('h') or 0) for r in rows], default=0) + 1}",
            "from": frm,
            "to": to,
            "payload": payload or {},
            "status": status or "pending",
            "ts": _now(),
        }
        rows.append(rec)
        _write_json(HANDOFFS, rows)
    log_event("handoff", {"from": frm, "to": to, "id": rec["id"], "status": rec["status"]})
    return rec


def list_handoffs(to: str | None = None, status: str | None = None) -> list:
    rows = _read_json(HANDOFFS, [])
    return [
        r for r in rows
        if (to is None or r.get("to") == to)
        and (status is None or r.get("status") == status)
    ]


def update_handoff(handoff_id: str, status: str) -> dict:
    with _FileLock():
        rows = _read_json(HANDOFFS, [])
        for r in rows:
            if r.get("id") == handoff_id:
                r["status"] = status
                r["updated_at"] = _now()
                _write_json(HANDOFFS, rows)
                log_event("handoff:update", {"id": handoff_id, "status": status})
                return r
    return {"ok": False, "error": "handoff not found", "id": handoff_id}


def enqueue_task(pipeline: str, priority: int = 5, data: dict | None = None,
                 dedupe_key: str | None = None) -> dict:
    """Add a pipeline task. Lower priority number runs first."""
    pipeline = (pipeline or "").strip()
    if not pipeline:
        return {"ok": False, "error": "pipeline is required"}
    data = data or {}
    dedupe_key = (dedupe_key or data.get("dedupe_key") or "").strip()
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        if dedupe_key:
            for existing in rows:
                if (
                    existing.get("dedupe_key") == dedupe_key
                    and existing.get("status") in ACTIVE_TASK_STATUSES
                ):
                    existing["deduped"] = True
                    log_event("task:deduped", {
                        "id": existing.get("id"),
                        "pipeline": pipeline,
                        "dedupe_key": dedupe_key,
                    })
                    return existing
        rec = {
            "id": f"t{max([int(str(r.get('id', 't0')).lstrip('t') or 0) for r in rows], default=0) + 1}",
            "pipeline": pipeline,
            "dedupe_key": dedupe_key or None,
            "deduped": False,
            "priority": int(priority or 5),
            "data": data,
            "status": "pending",
            "attempts": 0,
            "next_run_at": None,
            "created_at": _now(),
        }
        rows.append(rec)
        _write_json(TASK_QUEUE, rows)
    log_event("task:queued", {
        "id": rec["id"],
        "pipeline": pipeline,
        "priority": rec["priority"],
        "dedupe_key": rec.get("dedupe_key"),
    })
    return rec


def dequeue_task(agent: str = "pipeline", worker_id: str | None = None,
                 lease_seconds: int = 3600) -> dict | None:
    """Take one pending task by priority and mark it running."""
    worker_id = worker_id or default_worker_id()
    lease_seconds = max(60, int(lease_seconds or 3600))
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        now = _now_ts()
        pending = [
            r for r in rows
            if r.get("status") == "pending"
            and float(r.get("next_run_ts") or 0) <= now
        ]
        if not pending:
            return None
        selected = sorted(pending, key=lambda r: (int(r.get("priority", 5)), r.get("created_at", "")))[0]
        for r in rows:
            if r.get("id") == selected.get("id"):
                r["status"] = "running"
                r["agent"] = agent
                r["worker_id"] = worker_id
                r["started_at"] = _now()
                r["heartbeat_at"] = _now()
                r["heartbeat_ts"] = now
                r["lease_expires_at"] = _iso_from_ts(now + lease_seconds)
                r["lease_expires_ts"] = now + lease_seconds
                r["attempts"] = int(r.get("attempts", 0) or 0) + 1
                r["next_run_at"] = None
                r["next_run_ts"] = None
                selected = r
                break
        _write_json(TASK_QUEUE, rows)
    log_event("task:dequeued", {
        "id": selected["id"],
        "pipeline": selected["pipeline"],
        "agent": agent,
        "worker_id": worker_id,
    })
    return selected


def complete_task(task_id: str, status: str = "done", result: dict | None = None) -> dict:
    result = result or {}
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        for r in rows:
            if r.get("id") == task_id:
                r["status"] = status
                r["finished_at"] = _now()
                r["result"] = result
                r["artifact"] = result.get("artifact") or r.get("artifact") or {}
                r["lease_expires_at"] = None
                r["lease_expires_ts"] = None
                _write_json(TASK_QUEUE, rows)
                log_event("task:complete", {"id": task_id, "status": status})
                return r
    return {"ok": False, "error": "task not found", "id": task_id}


def reschedule_task(task_id: str, delay_seconds: int, reason: str = "",
                    result: dict | None = None) -> dict:
    """Return a running task to pending with a visible next_run_at timestamp."""
    delay_seconds = max(1, int(delay_seconds or 1))
    next_ts = _now_ts() + delay_seconds
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        for r in rows:
            if r.get("id") == task_id:
                r["status"] = "pending"
                r["agent"] = None
                r["worker_id"] = None
                r["finished_at"] = None
                r["lease_expires_at"] = None
                r["lease_expires_ts"] = None
                r["next_run_ts"] = next_ts
                r["next_run_at"] = _iso_from_ts(next_ts)
                r["retry_reason"] = reason
                r["last_result"] = result or {}
                _write_json(TASK_QUEUE, rows)
                log_event("task:rescheduled", {
                    "id": task_id,
                    "delay_seconds": delay_seconds,
                    "reason": reason,
                })
                return r
    return {"ok": False, "error": "task not found", "id": task_id}


def heartbeat_task(task_id: str, worker_id: str | None = None,
                   lease_seconds: int = 3600) -> dict:
    worker_id = worker_id or default_worker_id()
    lease_seconds = max(60, int(lease_seconds or 3600))
    now = _now_ts()
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        for r in rows:
            if r.get("id") == task_id:
                if r.get("status") != "running":
                    return {"ok": False, "error": "task is not running", "id": task_id}
                if r.get("worker_id") and r.get("worker_id") != worker_id:
                    return {"ok": False, "error": "worker mismatch", "id": task_id,
                            "worker_id": r.get("worker_id")}
                r["worker_id"] = worker_id
                r["heartbeat_at"] = _now()
                r["heartbeat_ts"] = now
                r["lease_expires_at"] = _iso_from_ts(now + lease_seconds)
                r["lease_expires_ts"] = now + lease_seconds
                _write_json(TASK_QUEUE, rows)
                return r
    return {"ok": False, "error": "task not found", "id": task_id}


def recover_stale_tasks(timeout_seconds: int = 3600,
                        recover_to: str = "pending") -> list:
    """Recover running tasks whose lease expired and whose pipeline lock is not alive."""
    timeout_seconds = max(60, int(timeout_seconds or 3600))
    now = _now_ts()
    recovered = []
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        locks = _read_json(LOCKS, {})
        for r in rows:
            if r.get("status") != "running":
                continue
            lease_ts = float(r.get("lease_expires_ts") or 0)
            heartbeat_ts = float(r.get("heartbeat_ts") or 0)
            stale_by_heartbeat = heartbeat_ts and (now - heartbeat_ts > timeout_seconds)
            if lease_ts > now and not stale_by_heartbeat:
                continue

            pipeline = r.get("pipeline")
            lock = locks.get(pipeline)
            if lock and float(lock.get("expires_at", 0) or 0) > now:
                continue

            r["status"] = "failed" if recover_to == "failed" else "pending"
            r["agent"] = None
            r["worker_id"] = None
            r["recovered_at"] = _now()
            r["recovery_reason"] = "lease_expired"
            r["lease_expires_at"] = None
            r["lease_expires_ts"] = None
            if r["status"] == "pending":
                r["next_run_at"] = None
                r["next_run_ts"] = None
            recovered.append(r.copy())
        if recovered:
            _write_json(TASK_QUEUE, rows)
    for task in recovered:
        log_event("task:recovered", {
            "id": task.get("id"),
            "pipeline": task.get("pipeline"),
            "status": task.get("status"),
            "attempts": task.get("attempts"),
        })
    return recovered


def get_task(task_id: str) -> dict:
    for task in _read_json(TASK_QUEUE, []):
        if task.get("id") == task_id:
            return task
    return {"ok": False, "error": "task not found", "id": task_id}


def retry_task(task_id: str, reset_attempts: bool = False) -> dict:
    """Operator command: make a failed/blocked/delayed task runnable now."""
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        for r in rows:
            if r.get("id") == task_id:
                if r.get("status") == "running":
                    return {"ok": False, "error": "cannot retry a running task", "id": task_id}
                r["status"] = "pending"
                r["agent"] = None
                r["worker_id"] = None
                r["finished_at"] = None
                r["next_run_at"] = None
                r["next_run_ts"] = None
                r["lease_expires_at"] = None
                r["lease_expires_ts"] = None
                r["retry_reason"] = "operator_retry"
                if reset_attempts:
                    r["attempts"] = 0
                r["operator_updated_at"] = _now()
                _write_json(TASK_QUEUE, rows)
                log_event("task:operator_retry", {"id": task_id, "reset_attempts": reset_attempts})
                return r
    return {"ok": False, "error": "task not found", "id": task_id}


def cancel_task(task_id: str, reason: str = "") -> dict:
    with _FileLock():
        rows = _read_json(TASK_QUEUE, [])
        for r in rows:
            if r.get("id") == task_id:
                if r.get("status") == "running":
                    return {"ok": False, "error": "cannot cancel a running task", "id": task_id}
                r["status"] = "cancelled"
                r["finished_at"] = _now()
                r["lease_expires_at"] = None
                r["lease_expires_ts"] = None
                r["cancel_reason"] = reason or "operator_cancel"
                r["operator_updated_at"] = _now()
                _write_json(TASK_QUEUE, rows)
                log_event("task:cancelled", {"id": task_id, "reason": r["cancel_reason"]})
                return r
    return {"ok": False, "error": "task not found", "id": task_id}


def unblock_task(task_id: str) -> dict:
    """Operator command: clear blocked/locked/delayed state and run on next worker tick."""
    task = get_task(task_id)
    if task.get("ok") is False:
        return task
    if task.get("status") == "running":
        return {"ok": False, "error": "cannot unblock a running task", "id": task_id}
    return retry_task(task_id, reset_attempts=False)


def list_tasks(status: str | None = None) -> list:
    rows = _read_json(TASK_QUEUE, [])
    return [r for r in rows if status is None or r.get("status") == status]


# ─── REPLIES: очередь ответов на комментарии (paced, anti-spam) ──────────
# Марина по команде «ответить всем» кладёт сюда черновики (по одному на коммент).
# Отдельный paced-отправитель (reply_sender.py) шлёт их ПО ОДНОМУ с паузой и под
# общим часовым лимитом (shared_rate_limit), чтобы всплеск ответов не выглядел
# спамом для Instagram. Дедуп по comment_id — на один комментарий один ответ.
REPLY_ACTIVE_STATUSES = {"pending", "sending"}


def enqueue_reply(comment_id: str, message: str, post_id: str = "",
                  username: str = "", comment_text: str = "") -> dict:
    """Поставить ответ на комментарий в очередь. Дедуп по comment_id."""
    comment_id = str(comment_id or "").strip()
    message = (message or "").strip()
    if not comment_id or not message:
        return {"ok": False, "error": "comment_id and message are required"}
    with _FileLock():
        rows = _read_json(REPLY_QUEUE, [])
        for r in rows:  # не отвечаем дважды на один и тот же комментарий
            if r.get("comment_id") == comment_id and r.get("status") in (REPLY_ACTIVE_STATUSES | {"sent"}):
                out = dict(r)
                out["deduped"] = True
                log_event("reply:deduped", {"comment_id": comment_id, "id": r.get("id")})
                return out
        rec = {
            "id": f"r{max([int(str(x.get('id', 'r0')).lstrip('r') or 0) for x in rows], default=0) + 1}",
            "comment_id": comment_id,
            "message": message[:1000],
            "post_id": post_id or None,
            "username": username or None,
            "comment_text": (comment_text or "")[:200],
            "status": "pending",
            "attempts": 0,
            "deduped": False,
            "created_at": _now(),
            "sent_at": None,
            "error": None,
        }
        rows.append(rec)
        _write_json(REPLY_QUEUE, rows)
    log_event("reply:queued", {"id": rec["id"], "comment_id": comment_id, "username": username})
    return rec


def list_replies(status: str | None = None) -> list:
    rows = _read_json(REPLY_QUEUE, [])
    return [r for r in rows if status is None or r.get("status") == status]


def dequeue_reply(worker_id: str | None = None) -> dict | None:
    """Взять один pending-ответ (FIFO) и пометить sending."""
    worker_id = worker_id or default_worker_id()
    with _FileLock():
        rows = _read_json(REPLY_QUEUE, [])
        pending = [r for r in rows if r.get("status") == "pending"]
        if not pending:
            return None
        selected = sorted(pending, key=lambda r: r.get("created_at", ""))[0]
        for r in rows:
            if r.get("id") == selected.get("id"):
                r["status"] = "sending"
                r["worker_id"] = worker_id
                r["started_at"] = _now()
                r["attempts"] = int(r.get("attempts", 0) or 0) + 1
                selected = r
                break
        _write_json(REPLY_QUEUE, rows)
    return selected


def mark_reply(reply_id: str, status: str, error: str | None = None,
               response_id: str | None = None) -> dict:
    with _FileLock():
        rows = _read_json(REPLY_QUEUE, [])
        for r in rows:
            if r.get("id") == reply_id:
                r["status"] = status
                if status == "sent":
                    r["sent_at"] = _now()
                if error is not None:
                    r["error"] = str(error)[:300]
                if response_id is not None:
                    r["response_id"] = response_id
                _write_json(REPLY_QUEUE, rows)
                log_event(f"reply:{status}", {"id": reply_id, "comment_id": r.get("comment_id")})
                return r
    return {"ok": False, "error": "reply not found", "id": reply_id}


def reply_queue_status(limit: int = 50) -> dict:
    rows = _read_json(REPLY_QUEUE, [])
    pending = [r for r in rows if r.get("status") == "pending"]
    sent = [r for r in rows if r.get("status") == "sent"]
    failed = [r for r in rows if r.get("status") == "failed"]
    return {
        "pending": len(pending),
        "sent": len(sent),
        "failed": len(failed),
        "items_pending": pending[:limit],
        "recent_sent": sent[-limit:],
        "items_failed": failed[-limit:],
    }


def write_supervisor_status(status: dict) -> dict:
    rec = {"ok": True, "ts": _now(), **(status or {})}
    with _FileLock():
        _write_json(SUPERVISOR_STATUS, rec)
    return rec


def read_supervisor_status() -> dict:
    return _read_json(SUPERVISOR_STATUS, {"ok": False, "status": "missing"})


def set_approval(item_id: str, agent: str, status: str, comment: str = "") -> dict:
    """Set structured approval for an item."""
    item_id = (item_id or "").strip()
    status = (status or "").strip().lower()
    if status not in {"approved", "rejected", "changes_requested", "pending"}:
        return {"ok": False, "error": "invalid approval status"}
    rec = {"item_id": item_id, "agent": agent, "status": status,
           "comment": comment or "", "ts": _now()}
    with _FileLock():
        rows = _read_json(APPROVALS, {})
        history = rows.get(item_id, [])
        history.append(rec)
        rows[item_id] = history
        _write_json(APPROVALS, rows)
    log_event("approval:set", {"item_id": item_id, "agent": agent, "status": status})
    return rec


def get_approval(item_id: str) -> dict:
    rows = _read_json(APPROVALS, {})
    history = rows.get(item_id, [])
    if not history:
        return {"item_id": item_id, "status": "missing", "history": []}
    latest = history[-1].copy()
    latest["history"] = history
    return latest


def shared_rate_limit(api: str, max_per_hour: int, cost: int = 1) -> dict:
    """Shared rolling-hour rate limit counter for external APIs.

    Returns {"ok": True, ...} and records the request when allowed. Returns
    {"ok": False, "retry_after": seconds, ...} without recording when exhausted.
    """
    api = (api or "").strip().lower()
    if not api:
        return {"ok": False, "error": "api is required"}
    try:
        max_per_hour = int(max_per_hour)
        cost = int(cost or 1)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid max_per_hour/cost"}
    if max_per_hour <= 0 or cost <= 0:
        return {"ok": False, "error": "max_per_hour and cost must be positive"}

    now = time.time()
    window = 3600
    with _FileLock():
        state = _read_json(RATE_LIMITS, {})
        hits = [
            float(ts) for ts in state.get(api, [])
            if now - float(ts) < window
        ]
        remaining = max_per_hour - len(hits)
        if remaining < cost:
            oldest = min(hits) if hits else now
            retry_after = max(1, int(window - (now - oldest)))
            state[api] = hits
            _write_json(RATE_LIMITS, state)
            return {
                "ok": False,
                "api": api,
                "limit": max_per_hour,
                "used": len(hits),
                "remaining": max(0, remaining),
                "retry_after": retry_after,
            }
        hits.extend([now] * cost)
        state[api] = hits
        _write_json(RATE_LIMITS, state)
    return {
        "ok": True,
        "api": api,
        "limit": max_per_hour,
        "used": len(hits),
        "remaining": max_per_hour - len(hits),
        "retry_after": 0,
    }


def rate_limit_status(api: str | None = None) -> dict:
    now = time.time()
    state = _read_json(RATE_LIMITS, {})
    out = {}
    for key, hits in state.items():
        if api and key != api:
            continue
        active = [float(ts) for ts in hits if now - float(ts) < 3600]
        out[key] = {"used_last_hour": len(active)}
    return out


def office_status(limit: int = 20) -> dict:
    """Compact operational status for bridge/CLI dashboards."""
    tasks = list_tasks()
    by_status = {}
    for task in tasks:
        by_status[task.get("status", "unknown")] = by_status.get(task.get("status", "unknown"), 0) + 1

    approvals = _read_json(APPROVALS, {})
    latest_approvals = {}
    for item_id, history in approvals.items():
        if history:
            latest_approvals[item_id] = history[-1]

    return {
        "ok": True,
        "ts": _now(),
        "locks": list_locks(),
        "tasks": {
            "counts": by_status,
            "pending": list_tasks("pending")[:limit],
            "running": list_tasks("running")[:limit],
            "failed": list_tasks("failed")[-limit:],
            "awaiting_approval": list_tasks("awaiting_approval")[-limit:],
            "done_recent": list_tasks("done")[-limit:],
        },
        "handoffs_open": list_handoffs(status="pending")[-limit:],
        "approvals": latest_approvals,
        "rate_limits": rate_limit_status(),
        "supervisor": read_supervisor_status(),
        "recent_events": recent_events(limit),
        "recent_operator_events": [
            e for e in recent_events(limit * 2)
            if str(e.get("kind", "")).startswith("task:operator_")
            or e.get("kind") in {"task:cancelled", "task:deduped"}
        ][-limit:],
    }


# ─── CONTEXT: внешний мир → агенты ───────────────────────
def write_context(event: str, data: dict) -> dict:
    """n8n кладёт сюда входящее событие. Перезаписывает «текущий контекст»."""
    ctx = {"event": event, "ts": _now(), "data": data}
    with _FileLock():
        _write_json(CONTEXT, ctx)
    log_event(f"context:{event}", data)
    return ctx


def read_context() -> dict:
    """Агент читает текущий контекст (или пустой словарь)."""
    return _read_json(CONTEXT, {})


# ─── NOTES: агент → агент (очередь) ──────────────────────
def add_note(frm: str, to: str, note: str, data: dict | None = None) -> dict:
    """Агент оставляет заметку другому агенту. n8n потом увидит её и запустит
    адресата (Паттерн 3)."""
    with _FileLock():
        notes = _read_json(NOTES, [])
        rec = {
            "id": (max([n.get("id", 0) for n in notes], default=0) + 1),
            "from": frm, "to": to, "note": note,
            "data": data or {}, "status": "open", "ts": _now(),
        }
        notes.append(rec)
        _write_json(NOTES, notes)
    log_event("note", {"from": frm, "to": to, "note": note})
    return rec


def pop_notes(to: str, mark: bool = True) -> list:
    """Возвращает открытые заметки для агента. При mark=True помечает их взятыми,
    чтобы n8n не запустил адресата дважды на одно и то же."""
    with _FileLock():
        notes = _read_json(NOTES, [])
        mine = [n for n in notes if n.get("to") == to and n.get("status") == "open"]
        if mark:
            ids = {n["id"] for n in mine}
            for n in notes:
                if n["id"] in ids:
                    n["status"] = "taken"
            _write_json(NOTES, notes)
    return mine


def list_notes(status: str | None = None) -> list:
    notes = _read_json(NOTES, [])
    return [n for n in notes if status is None or n.get("status") == status]


# ─── PUBLISHED: реестр для петли «измерь через 48ч» ──────
def record_published(media_id: str, theme: str, hook: str = "", extra: dict | None = None):
    """pipeline вызывает при публикации поста. measure_due потом найдёт посты
    старше 48ч и допишет им метрики (Разрыв 1 — петля обратной связи)."""
    with _FileLock():
        rows = _read_json(PUBLISHED, [])
        if any(r.get("media_id") == media_id for r in rows):
            return  # уже зарегистрирован
        rows.append({
            "media_id": media_id, "theme": theme, "hook": hook[:80],
            "posted_at": _now(), "measured": False,
            "reach": None, "likes": None, "comments": None,
            **(extra or {}),
        })
        _write_json(PUBLISHED, rows)
    log_event("published", {"media_id": media_id, "theme": theme})


def due_for_measure(hours: int = 48) -> list:
    """Посты, опубликованные ≥hours назад и ещё не измеренные."""
    rows = _read_json(PUBLISHED, [])
    out = []
    now = datetime.now(timezone.utc)
    for r in rows:
        if r.get("measured"):
            continue
        try:
            posted = datetime.fromisoformat(r["posted_at"])
        except (ValueError, KeyError):
            continue
        if (now - posted).total_seconds() >= hours * 3600:
            out.append(r)
    return out


def save_measurement(media_id: str, metrics: dict):
    """Записывает измеренные метрики и помечает пост измеренным."""
    with _FileLock():
        rows = _read_json(PUBLISHED, [])
        for r in rows:
            if r.get("media_id") == media_id:
                r.update(metrics)
                r["measured"] = True
                r["measured_at"] = _now()
                break
        _write_json(PUBLISHED, rows)
    log_event("measured", {"media_id": media_id, **metrics})


# ─── PROFILE: стабильные defaults + фаза ─────────────────
def read_profile() -> dict:
    """Профиль офиса (defaults + настройки фазы). Если файла нет — встроенные
    DEFAULT_PROFILE, чтобы агенты работали с разумными предположениями с первого
    дня, а не с пустотой."""
    return _read_json(PROFILE, DEFAULT_PROFILE)


def write_profile(profile: dict) -> dict:
    """Сохраняет профиль целиком (атомарно)."""
    with _FileLock():
        _write_json(PROFILE, profile)
    log_event("profile:update", {})
    return profile


def read_competitors() -> dict:
    """Список топ-аккаунтов для конкурентной разведки (или пустой каркас).
    Обновляется вручную (Людмила/муж раз в месяц) — Instagram API чужую
    аналитику не отдаёт, поэтому список курируется человеком."""
    return _read_json(COMPETITORS, {"updated": None, "accounts": []})


def published_count() -> int:
    """Сколько постов зарегистрировано в реестре публикаций (для расчёта фазы)."""
    rows = _read_json(PUBLISHED, [])
    return len(rows) if isinstance(rows, list) else 0


def sales_count() -> int:
    """Число завершённых продаж. Первичный источник — таблица purchases в Supabase
    (status='completed'); если БД недоступна (нет supa/ключа/сети) — fallback на
    ручное поле business.sales_count из профиля.

    supa импортируется ЛЕНИВО и под try/except, чтобы memory.py остался без жёстких
    зависимостей (его вызывает и n8n как отдельный stdlib-скрипт)."""
    try:
        import sys
        tools_dir = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD")) / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        import supa
        if supa.available():
            rows = supa.select("purchases", columns="id",
                               filters={"status": "eq.completed"})
            return len(rows)
    except Exception:
        pass  # БД недоступна — падаем на ручное значение из профиля
    profile = read_profile()
    biz = profile.get("business", {}) if isinstance(profile, dict) else {}
    try:
        return int(biz.get("sales_count", 0) or 0)
    except (ValueError, TypeError):
        return 0


def current_phase() -> str:
    """Текущая фаза офиса: 'cold_start' | 'learning' | 'analysis'.

    Считается автоматически: число постов из published.json + число продаж из
    purchases (Supabase; fallback на profile.sales_count). Ручной приоритет —
    поле business.phase_override (если выставлено валидное значение).
    """
    profile = read_profile()
    biz = profile.get("business", {}) if isinstance(profile, dict) else {}
    override = biz.get("phase_override")
    if override in ("cold_start", "learning", "analysis"):
        return override
    posts = published_count()
    sales = sales_count()
    if posts >= _PHASE_ANALYSIS_POSTS and sales >= _PHASE_ANALYSIS_SALES:
        return "analysis"
    if posts >= _PHASE_LEARNING_POSTS:
        return "learning"
    return "cold_start"


# ─── Document Workflow Tracking ──────────────────────────
# Отслеживание пути документа через агентов: оригинал → Виктория → Рита → Марина → ...
# Каждый этап сохраняет input, output, agent, verdict (ready_next / needs_revision / done)

def start_document_workflow(file_name: str, file_content: str) -> dict:
    """Начать workflow документа. Возвращает {doc_id, created_at}."""
    import uuid
    doc_id = str(uuid.uuid4())[:8]
    workflows = _read_json(DOC_WORKFLOWS, {})
    workflows[doc_id] = {
        "id": doc_id,
        "file_name": file_name,
        "original_content": file_content[:2000],  # первые 2000 chars для истории
        "stages": [],
        "current_stage": 0,
        "current_agent": None,
        "created_at": _now(),
        "status": "in_progress",
    }
    with _FileLock():
        _write_json(DOC_WORKFLOWS, workflows)
    log_event(f"doc:workflow:start", {"doc_id": doc_id, "file": file_name})
    return {"doc_id": doc_id, "created_at": workflows[doc_id]["created_at"]}


def add_workflow_stage(doc_id: str, agent: str, input_text: str, output_text: str,
                       verdict: str = "ready_next") -> dict:
    """Добавить этап: агент обработал документ. Возвращает {stage_idx, ...}."""
    workflows = _read_json(DOC_WORKFLOWS, {})
    if doc_id not in workflows:
        return {"ok": False, "error": f"doc {doc_id} not found"}
    doc = workflows[doc_id]
    stage = {
        "agent": agent,
        "input": input_text[:500],  # краткий summary input
        "output": output_text[:500],  # краткий summary output
        "verdict": verdict,  # ready_next / needs_revision / done
        "timestamp": _now(),
    }
    doc["stages"].append(stage)
    doc["current_stage"] = len(doc["stages"])
    doc["current_agent"] = agent
    if verdict == "done":
        doc["status"] = "completed"
    with _FileLock():
        _write_json(DOC_WORKFLOWS, workflows)
    log_event(f"doc:workflow:stage", {"doc_id": doc_id, "agent": agent, "verdict": verdict})
    return {"ok": True, "doc_id": doc_id, "stage_idx": len(doc["stages"]) - 1}


def get_document_workflow(doc_id: str) -> dict:
    """Получить весь workflow документа."""
    workflows = _read_json(DOC_WORKFLOWS, {})
    return workflows.get(doc_id) or {"ok": False, "error": "not found"}


def list_workflows(status: str = None, limit: int = 20) -> list:
    """Список workflows, опционально фильтруя по статусу."""
    workflows = _read_json(DOC_WORKFLOWS, {})
    docs = list(workflows.values())
    if status:
        docs = [d for d in docs if d.get("status") == status]
    return sorted(docs, key=lambda d: d.get("created_at", ""), reverse=True)[:limit]


def add_backward_feedback(doc_id: str, from_agent: str, to_agent: str,
                          feedback: str) -> dict:
    """Отправить правки от одного агента назад к другому агенту.
    Создаёт обратное сообщение в цепочке обработки."""
    workflows = _read_json(DOC_WORKFLOWS, {})
    if doc_id not in workflows:
        return {"ok": False, "error": f"doc {doc_id} not found"}

    doc = workflows[doc_id]
    if "feedback_chain" not in doc:
        doc["feedback_chain"] = []

    feedback_entry = {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "feedback": feedback,
        "timestamp": _now(),
    }
    doc["feedback_chain"].append(feedback_entry)

    with _FileLock():
        _write_json(DOC_WORKFLOWS, workflows)

    log_event(f"doc:feedback:backward", {
        "doc_id": doc_id,
        "from": from_agent,
        "to": to_agent
    })
    return {"ok": True, "doc_id": doc_id, "feedback_count": len(doc["feedback_chain"])}


def archive_document(doc_id: str) -> dict:
    """Архивировать документ (переместить из in_progress в архив)."""
    workflows = _read_json(DOC_WORKFLOWS, {})
    if doc_id not in workflows:
        return {"ok": False, "error": f"doc {doc_id} not found"}

    doc = workflows[doc_id]
    doc["status"] = "archived"
    doc["archived_at"] = _now()

    with _FileLock():
        _write_json(DOC_WORKFLOWS, workflows)

    log_event(f"doc:archived", {"doc_id": doc_id})
    return {"ok": True, "doc_id": doc_id}


def export_document(doc_id: str) -> dict:
    """Экспортировать документ со всей историей (для скачивания)."""
    workflows = _read_json(DOC_WORKFLOWS, {})
    if doc_id not in workflows:
        return {"ok": False, "error": f"doc {doc_id} not found"}

    doc = workflows[doc_id]
    export_data = {
        "id": doc.get("id"),
        "file_name": doc.get("file_name"),
        "created_at": doc.get("created_at"),
        "completed_at": doc.get("archived_at"),
        "status": doc.get("status"),
        "original_content": doc.get("original_content"),
        "stages": doc.get("stages", []),
        "feedback_chain": doc.get("feedback_chain", []),
    }

    log_event(f"doc:exported", {"doc_id": doc_id})
    return {"ok": True, "export": export_data}


# ─── Agent conversation history (persistent storage) ─────────────────
def save_agent_message(agent: str, text: str, is_user: bool, verdict: str = None) -> dict:
    """Сохранить сообщение от пользователя или агента в историю."""
    histories = _read_json(AGENT_HISTORIES, {})

    if agent not in histories:
        histories[agent] = {
            "agent": agent,
            "created_at": _now(),
            "messages": []
        }

    message = {
        "role": "user" if is_user else "assistant",
        "text": text,
        "verdict": verdict,
        "timestamp": _now(),
    }

    histories[agent]["messages"].append(message)

    with _FileLock():
        _write_json(AGENT_HISTORIES, histories)

    return {"ok": True, "agent": agent, "msg_count": len(histories[agent]["messages"])}


def get_agent_history(agent: str) -> dict:
    """Получить полную историю переписки с агентом."""
    histories = _read_json(AGENT_HISTORIES, {})
    if agent not in histories:
        return {"ok": True, "agent": agent, "messages": []}
    return {"ok": True, "agent": agent, "history": histories[agent]}


def list_agent_histories() -> list:
    """Список всех историй переписок с агентами."""
    histories = _read_json(AGENT_HISTORIES, {})
    result = []
    for agent, data in histories.items():
        result.append({
            "agent": agent,
            "created_at": data.get("created_at"),
            "message_count": len(data.get("messages", [])),
            "last_message_at": data.get("messages", [{}])[-1].get("timestamp") if data.get("messages") else None,
        })
    return sorted(result, key=lambda x: x.get("last_message_at", ""), reverse=True)


def clear_agent_history(agent: str) -> dict:
    """Очистить историю переписки с конкретным агентом."""
    histories = _read_json(AGENT_HISTORIES, {})
    if agent in histories:
        del histories[agent]
        with _FileLock():
            _write_json(AGENT_HISTORIES, histories)
        log_event(f"agent:history:cleared", {"agent": agent})
        return {"ok": True, "agent": agent}
    return {"ok": False, "error": f"Agent {agent} not found"}


def clear_all_histories() -> dict:
    """Очистить все истории переписок."""
    with _FileLock():
        _write_json(AGENT_HISTORIES, {})
    log_event(f"agent:histories:cleared_all", {})
    return {"ok": True, "cleared": "all"}


if __name__ == "__main__":
    # Быстрый самотест без сети и без LLM.
    print("MEM_DIR:", MEM_DIR)
    print("phase:", current_phase(), "| posts:", published_count(), "| sales:", sales_count())
    write_context("test", {"hello": "мир"})
    print("context:", read_context())
    n = add_note("alina", "lera", "паттерн Угодницы, предложи пакет 4")
    print("note добавлена id=", n["id"])
    print("для lera:", [x["note"] for x in pop_notes("lera")])
    record_published("TEST_MEDIA_1", "отношения", "Никогда не делай ради мужчины…")
    print("due(0h):", [r["media_id"] for r in due_for_measure(0)])
    save_measurement("TEST_MEDIA_1", {"reach": 12345, "likes": 678, "comments": 9})
    print("due после измерения:", [r["media_id"] for r in due_for_measure(0)])
    print("OK self-test")
