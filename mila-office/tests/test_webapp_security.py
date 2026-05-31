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
        "vasya", "lera", "manager", "producer", "webapp",
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
