#!/usr/bin/env python3
"""
get_analytics.py — аналитика Instagram для MILA GOLD.

Использование:
    python get_analytics.py posts        # последние посты + охваты/лайки
    python get_analytics.py comments     # все комментарии к постам
    python get_analytics.py account      # статистика аккаунта
    python get_analytics.py posts --limit 50

Результат печатается в консоль И сохраняется в папку reports/ как JSON,
чтобы Cowork мог потом построить по нему отчёт.
"""
import argparse
from _common import (load_config, graph_get, graph_get_all, save_report,
                     GraphError, run_cli, TRIGGER_WORDS)


def get_posts(cfg, limit):
    """Последние медиа + их базовые метрики."""
    fields = (
        "id,caption,media_type,media_product_type,permalink,timestamp,"
        "like_count,comments_count,thumbnail_url,media_url"
    )
    media = graph_get_all(
        cfg, f"{cfg['node']}/media",
        params={"fields": fields, "limit": 25}, max_items=limit,
    )

    results = []
    for m in media:
        row = {
            "id": m.get("id"),
            "type": m.get("media_product_type") or m.get("media_type"),
            "date": m.get("timestamp", "")[:10],
            "timestamp": m.get("timestamp"),
            "published_time": (m.get("timestamp", "")[11:16] if m.get("timestamp") else ""),
            "likes": m.get("like_count", 0),
            "comments": m.get("comments_count", 0),
            "caption": (m.get("caption") or "")[:200],
            "link": m.get("permalink"),
        }
        # Попробуем получить охваты (insights). Для разных типов медиа
        # доступны разные метрики; ошибки тихо пропускаем.
        try:
            ins = graph_get(
                cfg, f"{m['id']}/insights",
                params={"metric": "reach"},
            )
            for item in ins.get("data", []):
                vals = item.get("values", [{}])
                row["reach"] = vals[0].get("value")
        except GraphError:
            row["reach"] = None
        results.append(row)

    # Сортируем по вовлечённости
    for r in results:
        r["engagement"] = (r["likes"] or 0) + (r["comments"] or 0)
    results.sort(key=lambda x: x["engagement"], reverse=True)
    return results


def get_comments(cfg, limit):
    """Все комментарии к последним постам, с пометкой 'заявка'."""
    media = graph_get_all(
        cfg, f"{cfg['node']}/media",
        params={"fields": "id,caption,permalink,timestamp,comments_count", "limit": 25},
        max_items=limit,
    )
    expected = sum(m.get("comments_count") or 0 for m in media)
    all_comments = []
    for m in media:
        comments = graph_get_all(
            cfg, f"{m['id']}/comments",
            params={"fields": "id,text,username,timestamp,like_count", "limit": 50},
        )
        for c in comments:
            text = (c.get("text") or "")
            is_lead = any(w in text.lower() for w in TRIGGER_WORDS)
            all_comments.append({
                "comment_id": c.get("id"),
                "post_link": m.get("permalink"),
                "username": c.get("username"),
                "text": text,
                "date": c.get("timestamp", "")[:16],
                "likes": c.get("like_count", 0),
                "is_lead": is_lead,
            })
    leads = [c for c in all_comments if c["is_lead"]]
    result = {"comments": all_comments, "leads": leads, "expected_count": expected}
    # comments_count > 0, но API вернул 0 — это не баг скрипта и не «особенность Reels»
    # (проверено: пустыми приходят и FEED-посты). У токена нет доступа на чтение
    # комментариев.
    if expected and not all_comments:
        result["note"] = (
            f"У постов есть комментарии (comments_count={expected}), но API вернул 0. "
            "Токену не хватает разрешения на чтение комментариев: нужен scope "
            "instagram_business_manage_comments + advanced access (App Review). "
            "Перевыпусти токен с этим разрешением и обнови IG_ACCESS_TOKEN в .env."
        )
    return result


def get_account(cfg):
    """Базовая статистика аккаунта."""
    # follows_count есть только в Facebook-flow; в Instagram Login его нет.
    fields = "username,followers_count,media_count,biography"
    if cfg.get("flow") != "instagram_login":
        fields = "username,followers_count,follows_count,media_count,biography"
    info = graph_get(cfg, cfg["node"], params={"fields": fields})
    return info


def main():
    p = argparse.ArgumentParser(description="Аналитика Instagram MILA GOLD")
    p.add_argument("mode", choices=["posts", "comments", "account"],
                   help="что выгружать")
    p.add_argument("--limit", type=int, default=20,
                   help="сколько последних постов обработать (по умолч. 20)")
    args = p.parse_args()

    cfg = load_config()

    if args.mode == "posts":
        data = get_posts(cfg, args.limit)
        path = save_report("posts", data)
        print(f"\n📊 Топ постов по вовлечённости (всего {len(data)}):\n")
        for i, r in enumerate(data[:10], 1):
            reach = f", охват {r['reach']}" if r.get("reach") else ""
            print(f"{i}. [{r['date']}] ❤️ {r['likes']}  💬 {r['comments']}{reach}")
            print(f"   {r['caption'][:80]}")
            print(f"   {r['link']}\n")

    elif args.mode == "comments":
        data = get_comments(cfg, args.limit)
        path = save_report("comments", data)
        print(f"\n💬 Комментариев: {len(data['comments'])}  |  "
              f"Заявок (триггер-слова): {len(data['leads'])}\n")
        if data.get("note"):
            print(f"⚠️  {data['note']}\n")
        for c in data["leads"]:
            print(f"  🔥 @{c['username']}: {c['text'][:90]}")
            print(f"     {c['post_link']}\n")

    elif args.mode == "account":
        data = get_account(cfg)
        path = save_report("account", data)
        print(f"\n👤 @{data.get('username')}")
        print(f"   Подписчиков: {data.get('followers_count')}")
        print(f"   Публикаций:  {data.get('media_count')}")
        bio = data.get("biography")
        if bio:
            print(f"   Bio:\n      " + bio.replace("\n", "\n      "))
        print()

    print(f"✅ Сохранено: {path}")


if __name__ == "__main__":
    run_cli(main)
