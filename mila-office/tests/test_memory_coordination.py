import importlib
import sys


def _fresh_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    sys.modules.pop("memory", None)
    return importlib.import_module("memory")


def test_lock_blocks_and_releases(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    first = memory.acquire_lock("content_week", owner="a")
    second = memory.acquire_lock("content_week", owner="b")
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["locked_by"] == "a"
    assert memory.release_lock("content_week", owner="a")["released"] is True
    assert memory.acquire_lock("content_week", owner="b")["ok"] is True


def test_handoff_records_structured_payload(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    rec = memory.handoff("marina", "victoria", {
        "task": "check_post",
        "content": "text",
        "context": "hook tested",
    })
    rows = memory.list_handoffs(to="victoria")
    assert rec["id"] == "h1"
    assert rows[0]["payload"]["context"] == "hook tested"


def test_queue_dequeues_by_priority(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    memory.enqueue_task("content_week", priority=2)
    urgent = memory.enqueue_task("new_client", priority=1)
    task = memory.dequeue_task("pipeline", worker_id="worker:test")
    assert task["id"] == urgent["id"]
    assert task["status"] == "running"
    assert task["worker_id"] == "worker:test"
    assert task["heartbeat_at"]
    assert task["lease_expires_at"]
    memory.complete_task(task["id"], "done")
    assert memory.list_tasks("done")[0]["id"] == urgent["id"]


def test_queue_dedupes_pending_and_running_tasks(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    first = memory.enqueue_task("content_week", priority=2, dedupe_key="content_week:2026-W23")
    second = memory.enqueue_task("content_week", priority=2, dedupe_key="content_week:2026-W23")
    assert second["id"] == first["id"]
    assert second["deduped"] is True

    running = memory.dequeue_task("pipeline")
    third = memory.enqueue_task("content_week", priority=2, dedupe_key="content_week:2026-W23")
    assert third["id"] == running["id"]
    assert third["deduped"] is True

    memory.complete_task(running["id"], "done")
    fourth = memory.enqueue_task("content_week", priority=2, dedupe_key="content_week:2026-W23")
    assert fourth["id"] != first["id"]
    assert fourth["deduped"] is False


def test_queue_skips_tasks_until_next_run(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    delayed = memory.enqueue_task("content_week", priority=1)
    ready = memory.enqueue_task("new_client", priority=2)
    memory.reschedule_task(delayed["id"], delay_seconds=3600, reason="failed")
    task = memory.dequeue_task("pipeline")
    assert task["id"] == ready["id"]
    assert task["attempts"] == 1


def test_heartbeat_extends_running_task_lease(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    task = memory.enqueue_task("content_week", priority=1)
    running = memory.dequeue_task("pipeline", worker_id="w1", lease_seconds=60)
    old_lease = running["lease_expires_ts"]
    updated = memory.heartbeat_task(task["id"], worker_id="w1", lease_seconds=120)
    assert updated["id"] == task["id"]
    assert updated["lease_expires_ts"] >= old_lease
    assert updated["worker_id"] == "w1"


def test_recover_stale_tasks_is_lock_aware(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    now = {"t": 1000.0}
    monkeypatch.setattr(memory.time, "time", lambda: now["t"])

    task = memory.enqueue_task("content_week", priority=1)
    running = memory.dequeue_task("pipeline", worker_id="w1", lease_seconds=60)
    assert running["id"] == task["id"]
    memory.acquire_lock("content_week", owner="pipeline:content_week", ttl_seconds=3600)

    now["t"] = 2000.0
    assert memory.recover_stale_tasks(timeout_seconds=60) == []
    assert memory.get_task(task["id"])["status"] == "running"

    now["t"] = 5000.0
    recovered = memory.recover_stale_tasks(timeout_seconds=60)
    assert recovered[0]["id"] == task["id"]
    assert memory.get_task(task["id"])["status"] == "pending"


def test_operator_retry_cancel_unblock(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    task = memory.enqueue_task("content_week", priority=2)
    memory.complete_task(task["id"], "failed", {"error": "boom"})

    retried = memory.retry_task(task["id"], reset_attempts=True)
    assert retried["status"] == "pending"
    assert retried["attempts"] == 0

    cancelled = memory.cancel_task(task["id"], reason="manual")
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancel_reason"] == "manual"

    unblocked = memory.unblock_task(task["id"])
    assert unblocked["status"] == "pending"


def test_approval_latest_status(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    memory.set_approval("post_mon", "victoria", "rejected", "weak hook")
    memory.set_approval("post_mon", "victoria", "approved", "fixed")
    latest = memory.get_approval("post_mon")
    assert latest["status"] == "approved"
    assert len(latest["history"]) == 2


def test_shared_rate_limit_blocks_after_limit(monkeypatch, tmp_path):
    memory = _fresh_memory(monkeypatch, tmp_path)
    assert memory.shared_rate_limit("instagram_api", 2)["ok"] is True
    assert memory.shared_rate_limit("instagram_api", 2)["ok"] is True
    blocked = memory.shared_rate_limit("instagram_api", 2)
    assert blocked["ok"] is False
    assert blocked["retry_after"] > 0
