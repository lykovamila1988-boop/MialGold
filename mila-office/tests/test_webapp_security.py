import importlib
import sys


class InlinePool:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


def _fresh_webapp(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    for name in (
        "base", "agent", "victoria", "alina", "dima", "tyoma", "olya",
        "vasya", "lera", "manager", "producer", "memory", "policies", "webapp",
    ):
        sys.modules.pop(name, None)
    appmod = importlib.import_module("webapp")
    appmod.app.config.update(TESTING=True)
    monkeypatch.setattr(appmod, "_pool", InlinePool())
    appmod.AGENTS["marina"]["responder"] = lambda msg, hist: ("ok: " + msg, hist + [
        {"role": "user", "content": msg},
        {"role": "assistant", "content": "ok: " + msg},
    ])
    return appmod


def _client_with_csrf(appmod):
    client = appmod.app.test_client()
    meta = client.get("/api/meta").get_json()
    return client, meta["csrf"]


def test_post_without_csrf_is_rejected(monkeypatch, tmp_path):
    appmod = _fresh_webapp(monkeypatch, tmp_path)
    client = appmod.app.test_client()

    response = client.post("/api/reset", json={"agent": "marina"})

    assert response.status_code == 403


def test_chat_job_is_bound_to_creating_session(monkeypatch, tmp_path):
    appmod = _fresh_webapp(monkeypatch, tmp_path)
    client, csrf = _client_with_csrf(appmod)

    created = client.post(
        "/api/chat",
        json={"agent": "marina", "message": "hello"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 202
    job = created.get_json()["job"]

    stranger = appmod.app.test_client()
    assert stranger.get(f"/api/result?job={job}").status_code == 404

    result = client.get(f"/api/result?job={job}")
    assert result.status_code == 200
    assert result.get_json()["reply"] == "ok: hello"


def test_settings_token_save_requires_csrf(monkeypatch, tmp_path):
    appmod = _fresh_webapp(monkeypatch, tmp_path)
    client = appmod.app.test_client()

    response = client.post("/api/settings/instagram-token", json={"token": "fake"})

    assert response.status_code == 403


def test_operator_page_and_actions(monkeypatch, tmp_path):
    appmod = _fresh_webapp(monkeypatch, tmp_path)
    task = appmod.memory.enqueue_task("content_week", priority=2, dedupe_key="cw:test")
    appmod.memory.complete_task(task["id"], "failed", {"error": "boom"})
    client, csrf = _client_with_csrf(appmod)

    page = client.get("/operator")
    assert page.status_code == 200
    # Страница операторской очереди переведена на русский («Управление очередью»).
    assert "Управление очередью".encode("utf-8") in page.data

    data = client.get("/api/operator").get_json()
    assert data["ok"] is True
    assert data["tasks"][0]["dedupe_key"] == "cw:test"
    assert "events" in data
    assert "supervisor" in data

    response = client.post(
        f"/api/operator/task/{task['id']}/retry",
        json={"reset_attempts": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.get_json()["task"]["status"] == "pending"
