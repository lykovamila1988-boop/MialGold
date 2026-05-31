#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_kpi.py — еженедельный KPI-отчёт по аккаунту (markdown) для MILA GOLD.

Берёт последний account_*.json (+ предыдущий для Δ подписчиков) и последний
posts_*.json, считает: подписчики и Δ, число постов, суммарный охват, средний ER,
топ-3 поста. Сохраняет markdown в MILA-BUSINESS/05-analytics/kpi_week_YYYY-MM-DD.md.

Использование:
    python weekly_kpi.py

Заменяет ручной сбор цифр (~30 мин/нед). Δ подписчиков появляется, когда есть
≥2 снимка account_*.json в разные моменты; иначе показывается «н/д».
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
OUTDIR = ROOT / "MILA-BUSINESS" / "05-analytics"


def _latest(pattern, n=1):
    files = sorted(REPORTS.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-n:] if files else []


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _fmt(n):
    try:
        return f"{int(round(n)):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


def main():
    accounts = _latest("account_*.json", 2)
    posts_files = _latest("posts_*.json", 1)
    if not accounts or not posts_files:
        sys.exit("Нужны account_*.json и posts_*.json в reports/ "
                 "(запусти get_analytics.py account и posts).")

    acc = _load(accounts[-1])
    prev = _load(accounts[0]) if len(accounts) == 2 else None
    posts = _load(posts_files[-1])

    followers = acc.get("followers_count")
    delta = None
    if prev is not None and prev.get("followers_count") is not None and followers is not None:
        delta = followers - prev["followers_count"]

    reaches = [p.get("reach") or 0 for p in posts]
    total_reach = sum(reaches)
    ers = []
    for p in posts:
        r = p.get("reach") or 0
        eng = p.get("engagement")
        if eng is None:
            eng = (p.get("likes") or 0) + (p.get("comments") or 0)
        if r:
            ers.append(eng / r * 100)
    avg_er = round(sum(ers) / len(ers), 2) if ers else None
    top3 = sorted(posts, key=lambda p: p.get("reach") or 0, reverse=True)[:3]

    delta_str = "н/д" if delta is None else (f"+{delta}" if delta >= 0 else str(delta))
    today = datetime.datetime.now()
    lines = [
        f"# KPI за неделю — @{acc.get('username', '?')}",
        f"_сгенерировано {today:%Y-%m-%d %H:%M} · источник: {Path(posts_files[-1]).name}_",
        "",
        "| Метрика | Значение | Δ к прошлому замеру |",
        "|---|---|---|",
        f"| Подписчики | {_fmt(followers)} | {delta_str} |",
        f"| Постов в выгрузке | {len(posts)} | |",
        f"| Суммарный охват | {_fmt(total_reach)} | |",
        f"| Средний ER | {avg_er}% | |",
        "",
        "## Топ-3 поста по охвату",
    ]
    for i, p in enumerate(top3, 1):
        r = p.get("reach") or 0
        eng = p.get("engagement") or 0
        er = round(eng / r * 100, 1) if r else "—"
        cap = (p.get("caption") or "").replace("\n", " ")[:70]
        lines.append(f"{i}. **{_fmt(r)}** охват · ER {er}% · ❤️{p.get('likes', 0)} 💬{p.get('comments', 0)}")
        lines.append(f"   {cap}")
        if p.get("link"):
            lines.append(f"   {p['link']}")
    if delta is None:
        lines += ["", "_Δ подписчиков появится, когда накопится ≥2 снимка account_*.json._"]

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"kpi_week_{today:%Y-%m-%d}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n📈 KPI: подписчики {_fmt(followers)} ({delta_str}) · "
          f"охват {_fmt(total_reach)} · ER {avg_er}% · постов {len(posts)}")
    print(f"✅ Отчёт: {out}")


if __name__ == "__main__":
    main()
