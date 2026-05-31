#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py — авто-постинг Instagram для MILA GOLD.

⚠️  У Instagram API (flow instagram_login) НЕТ нативного отложенного постинга —
    нельзя «попросить Instagram опубликовать позже». Поэтому расписание держим у
    себя: очередь в MILA-BUSINESS/02-content/post_queue.json, а раннер публикует
    каждый пост, когда наступило его время. Раннер запускается по расписанию
    (Планировщик задач Windows) — см. README внизу.

Команды:
    python pipeline.py content_week     # собрать очередь на след. неделю (Пн–Пт) из черновиков
    python pipeline.py status           # показать очередь
    python pipeline.py approve <id>     # одобрить пост (Людмила) → попадёт в публикацию
    python pipeline.py publish_due      # опубликовать всё одобренное, чьё время пришло (раннер)

Требования к публикации:
    • токен с правом instagram_content_publish (тот же IG_ACCESS_TOKEN);
    • медиа доступно по ПУБЛИЧНОМУ URL (локальные файлы IG API не принимает) —
      поле media_url у поста. Без него пост помечается needs_media.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _common import load_config, run_cli, GraphError, wait_until_ready, TOOLS_DIR
import post_content as ig  # переиспользуем create_*_container / publish (без дублирования HTTP)

ROOT = TOOLS_DIR.parent
QUEUE = ROOT / "MILA-BUSINESS" / "02-content" / "post_queue.json"
POSTS_DIR = ROOT / "MILA-BUSINESS" / "02-content" / "posts"
POST_HOUR_UTC = 10  # Пн–Пт 10:00 UTC (≈13:00 МСК) — как в content-plan


# ─── очередь ─────────────────────────────────────────────
def _load_queue():
    try:
        return json.loads(QUEUE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


def _save_queue(q):
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(q):
    return max([i.get("id", 0) for i in q], default=0) + 1


def _parse_dt(s):
    try:
        dt = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def enqueue(kind, media_url, caption, when_iso, status="approved", source="manual"):
    """Добавляет пост в очередь. Используется Васей и content_week. Возвращает item."""
    q = _load_queue()
    item = {
        "id": _next_id(q),
        "kind": kind if kind in ("photo", "reel") else "photo",
        "caption": caption or "",
        "media_url": media_url or "",
        "when": when_iso,
        "status": status if (media_url or "").strip() else "needs_media",
        "source": source,
        "published_id": None,
        "error": None,
    }
    q.append(item)
    _save_queue(q)
    return item


# ─── content_week: каркас недели из черновиков ───────────
def _week_slots(hour=POST_HOUR_UTC):
    now = datetime.now(timezone.utc)
    days_to_monday = (7 - now.weekday()) % 7 or 7   # всегда следующий понедельник
    monday = (now + timedelta(days=days_to_monday)).replace(
        hour=hour, minute=0, second=0, microsecond=0)
    return [monday + timedelta(days=i) for i in range(5)]   # Пн..Пт


def _recent_drafts(n=5):
    if not POSTS_DIR.exists():
        return []
    files = [p for p in POSTS_DIR.glob("*")
             if p.suffix.lower() in (".md", ".txt") and p.name.lower() != "readme.txt"]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:n]:
        try:
            out.append((p.name, p.read_text(encoding="utf-8").strip()[:2100]))
        except OSError:
            continue
    return out


def content_week():
    q = _load_queue()
    existing_when = {i["when"] for i in q}
    drafts = _recent_drafts(5)
    slots = _week_slots()
    added = 0
    for i, slot in enumerate(slots):
        when = slot.isoformat()
        if when in existing_when:
            continue
        name, caption = drafts[i] if i < len(drafts) else (f"slot_{i+1}", "")
        q.append({
            "id": _next_id(q), "kind": "photo", "caption": caption, "media_url": "",
            "when": when, "status": "draft", "source": name,
            "published_id": None, "error": None,
        })
        added += 1
    _save_queue(q)
    print(f"📅 Очередь на неделю обновлена: добавлено {added} слотов (Пн–Пт {POST_HOUR_UTC}:00 UTC).")
    print("Людмила: впиши media_url (публичная ссылка) и одобри — "
          "`python pipeline.py approve <id>`.")
    _print_queue(q)


def approve(post_id):
    q = _load_queue()
    for item in q:
        if item["id"] == post_id:
            if not item.get("media_url", "").strip():
                print(f"⚠️ У #{post_id} нет media_url — впиши публичную ссылку, потом одобряй.")
                return
            item["status"] = "approved"
            _save_queue(q)
            print(f"✓ #{post_id} одобрен → опубликуется в {item['when']} (по запуску publish_due).")
            return
    print(f"#{post_id} не найден.")


def status():
    _print_queue(_load_queue())


def _print_queue(q):
    if not q:
        print("Очередь пуста. Запусти `python pipeline.py content_week`.")
        return
    icon = {"draft": "✏️", "approved": "✅", "published": "📤", "failed": "❌", "needs_media": "🖼️"}
    print(f"\nОчередь публикаций ({len(q)}):")
    for i in sorted(q, key=lambda x: x.get("when", "")):
        cap = (i.get("caption") or "").replace("\n", " ")[:50]
        print(f"  #{i['id']:>3} {icon.get(i['status'],'?')} {i['status']:<10} {i.get('when','?')[:16]} "
              f"[{i['kind']}] {cap}")
        if i["status"] == "failed" and i.get("error"):
            print(f"        ↳ {i['error'][:90]}")


# ─── publish_due: раннер (Планировщик задач) ─────────────
def _publish_item(cfg, item):
    if item["kind"] == "reel":
        cid = ig.create_reel_container(cfg, item["media_url"], item.get("caption", ""), "")
        wait_until_ready(cfg, cid, fields="status_code,status")
    else:
        cid = ig.create_photo_container(cfg, item["media_url"], item.get("caption", ""))
    return ig.publish(cfg, cid)


def publish_due():
    q = _load_queue()
    now = datetime.now(timezone.utc)
    cfg = None
    published = changed = 0
    for item in q:
        if item.get("status") != "approved":
            continue
        when = _parse_dt(item.get("when"))
        if when is None or when > now:
            continue
        if not item.get("media_url", "").strip():
            item["status"] = "needs_media"; changed += 1; continue
        if cfg is None:
            cfg = load_config()   # бросит ConfigError → run_cli обработает
        try:
            res = _publish_item(cfg, item)
            item["status"] = "published"
            item["published_id"] = res.get("id")
            item["published_at"] = now.isoformat()
            published += 1
        except GraphError as e:
            item["status"] = "failed"; item["error"] = str(e)[:200]
        changed += 1
    if changed:
        _save_queue(q)
    print(f"📤 Опубликовано: {published}. Обновлено записей: {changed}. (UTC {now:%Y-%m-%d %H:%M})")


def main():
    p = argparse.ArgumentParser(description="Авто-постинг Instagram (MILA GOLD)")
    p.add_argument("mode", choices=["content_week", "status", "approve", "publish_due"])
    p.add_argument("id", nargs="?", type=int, help="id поста для approve")
    args = p.parse_args()
    if args.mode == "content_week":
        content_week()
    elif args.mode == "status":
        status()
    elif args.mode == "approve":
        if args.id is None:
            sys.exit("Укажи id: python pipeline.py approve <id>")
        approve(args.id)
    elif args.mode == "publish_due":
        publish_due()


if __name__ == "__main__":
    run_cli(main)
