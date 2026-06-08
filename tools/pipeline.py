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

# Общая память офиса (mila-office/memory.py) — для 48ч-петли обратной связи.
# Импортируем по пути, как это делает n8n_bridge; если недоступна — петля просто
# не регистрирует пост (не ломая публикацию).
_OFFICE = ROOT / "mila-office"
if str(_OFFICE) not in sys.path:
    sys.path.insert(0, str(_OFFICE))
try:
    import memory as office_memory
except Exception:
    office_memory = None


# Тема поста — общий источник истины tools/theme.py (тот же, что в make_report),
# чтобы «тема→охват» в published.json и в отчёте не расходились.
from theme import classify as _classify_theme


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
            # 48ч-петля: регистрируем пост, чтобы measure_due через ≥48ч дописал охват.
            if office_memory and item.get("published_id"):
                try:
                    office_memory.record_published(
                        media_id=str(item["published_id"]),
                        theme=_classify_theme(item.get("caption", "")),
                        hook=(item.get("caption", "") or "").splitlines()[0] if item.get("caption") else "",
                    )
                except Exception as e:
                    print(f"[48h] не записал в память: {e}", file=sys.stderr)
        except GraphError as e:
            item["status"] = "failed"; item["error"] = str(e)[:200]
        changed += 1
    if changed:
        _save_queue(q)
    result = {"published": published, "changed": changed}
    print(f"📤 Опубликовано: {published}. Обновлено записей: {changed}. (UTC {now:%Y-%m-%d %H:%M})")
    return result


def measure_due(hours=48):
    """48ч-петля: для постов старше `hours` тянет охват/лайки/комменты из IG и
    пишет в память (save_measurement). Так у Стаса появляются данные «тема→охват»."""
    from _common import graph_get
    if office_memory is None:
        sys.exit("memory.py недоступна — нечего измерять")
    due = office_memory.due_for_measure(hours)
    if not due:
        print(f"📭 Нет постов старше {hours}ч для измерения.")
        return
    cfg = load_config()
    measured = 0
    for row in due:
        mid = row["media_id"]
        metrics = {}
        try:
            base = graph_get(cfg, mid, params={"fields": "like_count,comments_count"})
            metrics["likes"] = base.get("like_count", 0)
            metrics["comments"] = base.get("comments_count", 0)
        except GraphError:
            pass
        try:
            ins = graph_get(cfg, f"{mid}/insights", params={"metric": "reach"})
            for it in ins.get("data", []):
                # values может прийти пустым списком ([]), не только отсутствовать —
                # тогда [{}] как default не спасает (а [][0] кинул бы IndexError).
                values = it.get("values") or []
                first = values[0] if isinstance(values, list) and values else {}
                reach = first.get("value") if isinstance(first, dict) else None
                if reach is not None:
                    metrics["reach"] = reach
        except GraphError as e:
            print(f"  ⚠ {mid}: insights/reach недоступен ({e})")
        if metrics.get("reach") is None:
            metrics.setdefault("reach", None)
            print(f"  ⚠ {mid}: охват не получен (reach=None) — метрика записана неполной.")
        office_memory.save_measurement(mid, metrics)
        measured += 1
        print(f"  ✓ {mid} [{row.get('theme')}] reach={metrics.get('reach')} "
              f"likes={metrics.get('likes')} comments={metrics.get('comments')}")
    print(f"📊 Измерено постов: {measured}. (через ≥{hours}ч после публикации)")


def main():
    p = argparse.ArgumentParser(description="Авто-постинг Instagram (MILA GOLD)")
    p.add_argument("mode", choices=["content_week", "status", "approve",
                                    "publish_due", "measure_due"])
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
    elif args.mode == "measure_due":
        measure_due()


if __name__ == "__main__":
    run_cli(main)
