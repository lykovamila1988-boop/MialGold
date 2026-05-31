"""Доп. покрытие пайплайна: get_posts/get_account, enrich, KPI-форматтер, состояние алертов."""
import json
import get_analytics as ga
import weekly_digest as wd
import weekly_kpi as kpi
import alert_errors as al


def test_get_posts_sorts_and_pulls_reach(monkeypatch):
    media = [
        {"id": "1", "timestamp": "2026-01-01T00:00:00", "like_count": 10, "comments_count": 2,
         "caption": "low", "permalink": "p1", "media_product_type": "REELS"},
        {"id": "2", "timestamp": "2026-01-02T00:00:00", "like_count": 100, "comments_count": 5,
         "caption": "high", "permalink": "p2", "media_product_type": "REELS"},
    ]
    monkeypatch.setattr(ga, "graph_get_all", lambda cfg, path, params=None, max_items=None: media)
    monkeypatch.setattr(ga, "graph_get",
                        lambda cfg, path, params=None: {"data": [{"name": "reach", "values": [{"value": 500}]}]})
    rows = ga.get_posts({"node": "n"}, 10)
    assert rows[0]["likes"] == 100          # отсортировано по вовлечённости
    assert rows[0]["reach"] == 500
    assert rows[0]["engagement"] == 105


def test_get_posts_reach_none_on_blocked_insights(monkeypatch):
    media = [{"id": "1", "timestamp": "t", "like_count": 1, "comments_count": 0,
              "caption": "x", "permalink": "p", "media_product_type": "REELS"}]
    monkeypatch.setattr(ga, "graph_get_all", lambda cfg, path, params=None, max_items=None: media)

    def boom(cfg, path, params=None):
        raise ga.GraphError("insights blocked")

    monkeypatch.setattr(ga, "graph_get", boom)
    rows = ga.get_posts({"node": "n"}, 10)
    assert rows[0]["reach"] is None          # ошибка инсайтов проглочена, не падаем


def test_get_account(monkeypatch):
    monkeypatch.setattr(ga, "graph_get",
                        lambda cfg, path, params=None: {"username": "u", "followers_count": 100})
    info = ga.get_account({"node": "n", "flow": "instagram_login"})
    assert info["followers_count"] == 100


def test_digest_enrich_er_and_tag():
    row = wd.enrich({"reach": 200_000, "likes": 1000, "comments": 0, "type": "REELS"})
    assert "вирал" in row["tag"]
    assert row["er_pct"] == 0.5
    zero = wd.enrich({"reach": 0, "likes": 5, "comments": 0})
    assert zero["er_pct"] is None            # деление на ноль не ломает


def test_kpi_fmt():
    assert kpi._fmt(1419) == "1 419"
    assert kpi._fmt(None) == "None"


def test_alert_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(al, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(al, "REPORTS", tmp_path)
    al._write_state({"last_count": 42})
    assert al._read_state()["last_count"] == 42


def test_alert_record_file(tmp_path, monkeypatch):
    monkeypatch.setattr(al, "REPORTS", tmp_path)
    p = al._record_file(["ERROR boom"], ["KeyError: 'title'"])
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data[-1]["errors"] == ["ERROR boom"]
