"""Тесты безопасности n8n_bridge.py — мост исполняет команды, поэтому проверяем:
auth обязателен, allowlist скриптов работает, запуск без shell, аргументы из
вебхука обезвреживаются. См. историю: раньше был shell=True + auth опционален."""
import importlib
import sys


def _fresh_bridge(monkeypatch, tmp_path, token="testtoken"):
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    monkeypatch.setenv("N8N_BRIDGE_TOKEN", token)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sys.modules.pop("n8n_bridge", None)
    sys.modules.pop("memory", None)
    sys.modules.pop("policies", None)
    return importlib.import_module("n8n_bridge")


def test_auth_rejects_without_token(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path)
    app = br.app
    app.testing = True
    client = app.test_client()
    # без заголовка Authorization
    r = client.post("/v1/pipeline/content_week")
    assert r.status_code == 401


def test_auth_accepts_bearer(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path, token="abc123")
    client = br.app.test_client()
    r = client.post("/v1/pipeline/content_week",
                    headers={"Authorization": "Bearer abc123"})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("queued") is True
    assert body["task"]["pipeline"] == "content_week"


def test_pipeline_enqueue_is_idempotent(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path, token="abc123")
    client = br.app.test_client()
    headers = {"Authorization": "Bearer abc123"}
    payload = {"dedupe_key": "content_week:test"}
    first = client.post("/v1/pipeline/content_week", headers=headers, json=payload).get_json()["task"]
    second = client.post("/v1/pipeline/content_week", headers=headers, json=payload).get_json()["task"]
    assert second["id"] == first["id"]
    assert second["deduped"] is True


def test_pipeline_direct_override_obeys_policy(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path, token="abc123")
    calls = []
    monkeypatch.setattr(br, "_office", lambda *a, **k: calls.append(a) or {"ok": True, "stub": True})
    client = br.app.test_client()
    r = client.post("/v1/pipeline/content_week?direct=1",
                    headers={"Authorization": "Bearer abc123"})
    assert r.status_code == 403
    assert r.get_json().get("ok") is False
    assert calls == []


def test_status_endpoint_returns_queue(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path, token="abc123")
    client = br.app.test_client()
    r = client.get("/v1/status", headers={"Authorization": "Bearer abc123"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert "tasks" in body


def test_task_operator_endpoints(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path, token="abc123")
    task = br.memory.enqueue_task("content_week", priority=2)
    br.memory.complete_task(task["id"], "failed", {"error": "boom"})
    client = br.app.test_client()
    headers = {"Authorization": "Bearer abc123"}

    r = client.get(f"/v1/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["status"] == "failed"

    r = client.post(f"/v1/tasks/{task['id']}/retry", headers=headers, json={"reset_attempts": True})
    assert r.status_code == 200
    assert r.get_json()["status"] == "pending"

    r = client.get("/v1/tasks", headers=headers)
    assert r.status_code == 200
    assert r.get_json()["tasks"][0]["id"] == task["id"]

    r = client.post(f"/v1/tasks/{task['id']}/cancel", headers=headers, json={"reason": "manual"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "cancelled"


def test_office_allowlist_blocks_unknown_script(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path)
    res = br._office("evil.py", "--rm", "-rf")
    assert res["ok"] is False
    assert "not allowed" in res["error"]


def test_tools_allowlist_blocks_unknown_script(monkeypatch, tmp_path):
    br = _fresh_bridge(monkeypatch, tmp_path)
    res = br._tools("../../etc/passwd")
    assert res["ok"] is False
    assert "not allowed" in res["error"]


def test_run_uses_no_shell(monkeypatch, tmp_path):
    """_run должен звать subprocess.run с shell=False и списком argv."""
    br = _fresh_bridge(monkeypatch, tmp_path)
    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["shell"] = kwargs.get("shell")
        return _FakeCompleted()

    monkeypatch.setattr(br.subprocess, "run", fake_run)
    br._run(["pipeline.py", "content_week"], tmp_path, 10)
    assert captured["shell"] is False
    assert isinstance(captured["argv"], list)
    # argv[0] — интерпретатор python, дальше наши аргументы
    assert captured["argv"][1:] == ["pipeline.py", "content_week"]


def test_lead_args_strip_leading_dashes(monkeypatch, tmp_path):
    """Значение из вебхука не должно подменять argparse-флаг."""
    br = _fresh_bridge(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(br, "_tools", lambda *a, **k: calls.append(a) or {"ok": True})
    monkeypatch.setattr(br, "_office", lambda *a, **k: {"ok": True})
    client = br.app.test_client()
    client.post("/v1/lead",
                headers={"Authorization": "Bearer testtoken"},
                json={"name": "--telegram", "telegram": "--source", "message": "ХОЧУ"})
    # первый _tools-вызов — lead_capture.py; флаги-значения должны быть очищены
    args = calls[0]
    assert "--telegram" not in args[2]  # name больше не начинается с дефиса
    assert args[2] == "telegram"        # дефисы срезаны
