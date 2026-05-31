#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_digest.py — авто-дайджест контента для MILA GOLD (top/flop Reels + классификация).

Берёт последнюю выгрузку reports/posts_*.json, считает ER, классифицирует посты по
охвату и формирует топ-3 / антитоп-3. Результат печатается и сохраняется в
reports/digest_week_YYYY-MM-DD.json.

Закрывает задачи офиса #1 (авто-дайджест) и #5 (классификация постов).

Использование:
    python weekly_digest.py                 # последний posts_*.json
    python weekly_digest.py <путь.json>     # конкретная выгрузка

Пороги классификации (по reach):
    > 50 000      → 🔥 вирал
    5 000–50 000  → ✅ средний
    < 5 000       → ⚠️ слабый
ER (engagement / reach) считается отдельно; ER < 3% помечается как low_er.
"""
import sys
# UTF-8 для консоли Windows — иначе финальный print с русским/эмодзи падает на cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

VIRAL_REACH = 50_000
MID_REACH = 5_000
ER_MIN_PCT = 3.0


def latest_posts_json():
    files = sorted(REPORTS.glob("posts_*.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit("Нет файлов reports/posts_*.json — сначала запусти get_analytics.py posts.")
    return files[-1]


def classify(reach):
    if reach > VIRAL_REACH:
        return "🔥 вирал"
    if reach >= MID_REACH:
        return "✅ средний"
    return "⚠️ слабый"


def enrich(post):
    reach = post.get("reach") or 0
    eng = post.get("engagement")
    if eng is None:
        eng = (post.get("likes") or 0) + (post.get("comments") or 0)
    er = round(eng / reach * 100, 2) if reach else None
    return {
        "id": post.get("id"),
        "date": post.get("date"),
        "type": post.get("type"),
        "reach": reach,
        "likes": post.get("likes", 0),
        "comments": post.get("comments", 0),
        "engagement": eng,
        "er_pct": er,
        "low_er": (er is not None and er < ER_MIN_PCT),
        "tag": classify(reach),
        "caption": (post.get("caption") or "")[:80],
        "link": post.get("link"),
    }


def build(json_path):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    posts = [enrich(p) for p in data]
    by_reach = sorted(posts, key=lambda p: p["reach"], reverse=True)

    distribution = {"🔥 вирал": 0, "✅ средний": 0, "⚠️ слабый": 0}
    for p in posts:
        distribution[p["tag"]] += 1

    top3 = by_reach[:3]
    # антитоп — самые слабые по охвату (исключаем посты без охвата = нет данных)
    flop_pool = [p for p in by_reach if p["reach"] > 0]
    flop3 = flop_pool[-3:][::-1] if flop_pool else []

    total_reach = sum(p["reach"] for p in posts)
    ers = [p["er_pct"] for p in posts if p["er_pct"] is not None]
    avg_er = round(sum(ers) / len(ers), 2) if ers else None

    return {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": Path(json_path).name,
        "totals": {
            "posts": len(posts),
            "total_reach": total_reach,
            "avg_er_pct": avg_er,
        },
        "distribution": distribution,
        "top3": top3,
        "flop3": flop3,
        "posts": by_reach,
    }


def main():
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_posts_json()
    digest = build(json_path)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    out = REPORTS / f"digest_week_{stamp}.json"
    out.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")

    t = digest["totals"]
    d = digest["distribution"]
    print(f"\n📊 Дайджест за неделю · источник {digest['source']}")
    print(f"   Постов: {t['posts']}  ·  суммарный охват: {t['total_reach']:,}".replace(",", " ")
          + f"  ·  средний ER: {t['avg_er_pct']}%")
    print(f"   Распределение: 🔥 {d['🔥 вирал']}  ·  ✅ {d['✅ средний']}  ·  ⚠️ {d['⚠️ слабый']}\n")

    print("🏆 Топ-3 по охвату:")
    for i, p in enumerate(digest["top3"], 1):
        print(f"  {i}. {p['tag']}  reach {p['reach']:,}".replace(",", " ")
              + f"  ER {p['er_pct']}%  ❤️{p['likes']} 💬{p['comments']}")
        print(f"     {p['caption']}")
        print(f"     {p['link']}")
    print("\n🧊 Антитоп-3 по охвату:")
    for i, p in enumerate(digest["flop3"], 1):
        print(f"  {i}. {p['tag']}  reach {p['reach']:,}".replace(",", " ") + f"  ER {p['er_pct']}%")
        print(f"     {p['caption']}")

    print(f"\n✅ Сохранено: {out}")


if __name__ == "__main__":
    main()
