"""Тесты ядра tools/_common.py — конфиг, HTTP-обёртки, дедуп отчётов, поллинг."""
import json
import pytest
import _common as c


class FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.content = b"x"
        self.text = json.dumps(data, ensure_ascii=False)

    def json(self):
        return self._data


# ─── save_report: дедупликация + уникальность ────────────
def test_save_report_dedup_identical(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "REPORTS_DIR", tmp_path)
    p1 = c.save_report("t", {"a": 1})
    p2 = c.save_report("t", {"a": 1})
    assert p1 == p2
    assert len(list(tmp_path.glob("t_*.json"))) == 1


def test_save_report_distinct_for_different(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "REPORTS_DIR", tmp_path)
    p1 = c.save_report("t", {"a": 1})
    p2 = c.save_report("t", {"a": 2})
    assert p1 != p2
    assert len(list(tmp_path.glob("t_*.json"))) == 2


def test_save_report_writes_content(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "REPORTS_DIR", tmp_path)
    p = c.save_report("t", {"k": "значение"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"k": "значение"}


# ─── wait_until_ready: успех / ошибка / таймаут ──────────
def test_wait_until_ready_finished(monkeypatch):
    monkeypatch.setattr(c, "graph_get", lambda cfg, cid, params=None: {"status_code": "FINISHED"})
    monkeypatch.setattr(c.time, "sleep", lambda s: None)
    assert c.wait_until_ready({}, "id")["status_code"] == "FINISHED"


def test_wait_until_ready_fail_raises(monkeypatch):
    monkeypatch.setattr(c, "graph_get",
                        lambda cfg, cid, params=None: {"status": "ERROR", "error_message": "плохое видео"})
    monkeypatch.setattr(c.time, "sleep", lambda s: None)
    with pytest.raises(c.GraphError):
        c.wait_until_ready({}, "id", status_field="status", fail_codes=("ERROR",))


def test_wait_until_ready_timeout_raises(monkeypatch):
    monkeypatch.setattr(c, "graph_get", lambda cfg, cid, params=None: {"status_code": "IN_PROGRESS"})
    monkeypatch.setattr(c.time, "sleep", lambda s: None)
    with pytest.raises(c.GraphError):
        c.wait_until_ready({}, "id", timeout=2, interval=1)


# ─── run_cli: исключения → чистый exit ───────────────────
def test_run_cli_converts_graph_error():
    with pytest.raises(SystemExit):
        c.run_cli(lambda: (_ for _ in ()).throw(c.GraphError("x")))


def test_run_cli_converts_config_error():
    with pytest.raises(SystemExit):
        c.run_cli(lambda: (_ for _ in ()).throw(c.ConfigError("x")))


def test_run_cli_passthrough_ok():
    flag = {}
    c.run_cli(lambda: flag.setdefault("ran", True))
    assert flag["ran"] is True


# ─── graph_get: разбор ответа ────────────────────────────
_CFG = {"token": "t", "version": "v21.0", "base": "https://graph.example"}


def test_graph_get_ok(monkeypatch):
    monkeypatch.setattr(c._session, "get",
                        lambda url, params=None, timeout=None: FakeResp({"data": [1, 2]}))
    assert c.graph_get(_CFG, "path")["data"] == [1, 2]


def test_graph_get_error_payload_raises(monkeypatch):
    monkeypatch.setattr(c._session, "get",
                        lambda url, params=None, timeout=None: FakeResp({"error": {"message": "no"}}, status=400))
    with pytest.raises(c.GraphError):
        c.graph_get(_CFG, "path")


# ─── load_config: отсутствие .env ────────────────────────
def test_load_config_missing_env(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "ENV_PATH", tmp_path / "nope.env")
    with pytest.raises(c.ConfigError):
        c.load_config()


def test_trigger_words_present():
    assert "хочу" in c.TRIGGER_WORDS and len(c.TRIGGER_WORDS) >= 3
