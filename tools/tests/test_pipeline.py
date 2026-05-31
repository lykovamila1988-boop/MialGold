"""Тесты пайплайна: разбор комментариев, классификация дайджеста, форматтер отчёта."""
import get_analytics as ga
import weekly_digest as wd
import make_report as mr


def test_comments_note_when_blocked(monkeypatch):
    """comments_count > 0, но API вернул 0 → в результате должен быть note."""
    media = [{"id": "1", "comments_count": 5, "caption": "c",
              "permalink": "l", "timestamp": "2026-01-01"}]

    def fake_all(cfg, path, params=None, max_items=None):
        return media if path.endswith("/media") else []

    monkeypatch.setattr(ga, "graph_get_all", fake_all)
    res = ga.get_comments({"node": "n"}, 10)
    assert res["expected_count"] == 5
    assert res["comments"] == []
    assert "note" in res


def test_comments_lead_detection(monkeypatch):
    """Комментарий с триггер-словом помечается как лид."""
    media = [{"id": "1", "caption": "c", "permalink": "l", "timestamp": "t"}]

    def fake_all(cfg, path, params=None, max_items=None):
        if path.endswith("/media"):
            return media
        return [{"id": "c1", "text": "хочу купить практикум", "username": "u",
                 "timestamp": "t", "like_count": 0}]

    monkeypatch.setattr(ga, "graph_get_all", fake_all)
    res = ga.get_comments({"node": "n"}, 10)
    assert len(res["leads"]) == 1
    assert res["leads"][0]["is_lead"] is True


def test_digest_classify_thresholds():
    assert "вирал" in wd.classify(100_000)
    assert "средний" in wd.classify(10_000)
    assert "слабый" in wd.classify(100)
    # граница 50 000 — это ещё «средний», > 50 000 — «вирал»
    assert "средний" in wd.classify(50_000)
    assert "вирал" in wd.classify(50_001)


def test_digest_build_top_and_distribution(tmp_path):
    posts = [
        {"id": "a", "reach": 646486, "likes": 100, "comments": 10, "engagement": 110, "type": "REELS", "caption": "x", "link": "L1"},
        {"id": "b", "reach": 100, "likes": 5, "comments": 1, "engagement": 6, "type": "REELS", "caption": "y", "link": "L2"},
    ]
    src = tmp_path / "posts_x.json"
    src.write_text(__import__("json").dumps(posts), encoding="utf-8")
    digest = wd.build(src)
    assert digest["top3"][0]["reach"] == 646486
    assert digest["distribution"]["🔥 вирал"] == 1
    assert digest["distribution"]["⚠️ слабый"] == 1
    assert digest["totals"]["posts"] == 2


def test_make_report_fmt():
    assert mr.fmt(1234567) == "1 234 567"
    assert mr.fmt(0) == "0"
