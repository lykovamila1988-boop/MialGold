#!/usr/bin/env python3
"""
get_threads.py — аналитика Threads для MILA GOLD.

⚠️  Threads API — ОТДЕЛЬНЫЙ от Instagram: своё приложение и токен
    (THREADS_ACCESS_TOKEN, THREADS_USER_ID в .env), хост graph.threads.net.

Использование:
    python get_threads.py posts          # последние треды + метрики
    python get_threads.py replies        # ответы к тредам, помечает заявки
    python get_threads.py account        # профиль + число подписчиков
    python get_threads.py posts --limit 50

Результат печатается в консоль И сохраняется в reports/ как JSON.
"""
import argparse
from _common import (load_threads_config, graph_get, graph_get_all, save_report,
                     GraphError, run_cli, TRIGGER_WORDS)


def _metric_value(item):
    """Достаёт число из элемента insights (формат values[] или total_value)."""
    if "total_value" in item:
        return item["total_value"].get("value")
    vals = item.get("values") or [{}]
    return vals[-1].get("value")


def get_posts(cfg, limit):
    """Последние треды + их метрики (views/likes/replies/reposts/quotes)."""
    fields = "id,media_type,permalink,text,timestamp,is_quote_post"
    posts = graph_get_all(
        cfg, f"{cfg['user_id']}/threads",
        params={"fields": fields, "limit": 25}, max_items=limit,
    )

    results = []
    for m in posts:
        row = {
            "id": m.get("id"),
            "type": m.get("media_type"),
            "date": m.get("timestamp", "")[:10],
            "text": (m.get("text") or "")[:200],
            "link": m.get("permalink"),
            "views": None, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0,
        }
        # Метрики по треду. Для разных тредов набор метрик может
        # отличаться, поэтому ошибки тихо пропускаем.
        try:
            ins = graph_get(
                cfg, f"{m['id']}/insights",
                params={"metric": "views,likes,replies,reposts,quotes"},
            )
            for item in ins.get("data", []):
                row[item.get("name")] = _metric_value(item)
        except GraphError:
            pass
        row["engagement"] = ((row.get("likes") or 0) + (row.get("replies") or 0)
                             + (row.get("reposts") or 0) + (row.get("quotes") or 0))
        results.append(row)

    results.sort(key=lambda x: x["engagement"], reverse=True)
    return results


def get_replies(cfg, limit):
    """Ответы к последним тредам, с пометкой 'заявка'."""
    posts = graph_get_all(
        cfg, f"{cfg['user_id']}/threads",
        params={"fields": "id,permalink,timestamp", "limit": 25},
        max_items=limit,
    )
    all_replies = []
    for m in posts:
        replies = graph_get_all(
            cfg, f"{m['id']}/replies",
            params={"fields": "id,text,username,timestamp", "limit": 50},
        )
        for c in replies:
            text = c.get("text") or ""
            is_lead = any(w in text.lower() for w in TRIGGER_WORDS)
            all_replies.append({
                "reply_id": c.get("id"),
                "post_link": m.get("permalink"),
                "username": c.get("username"),
                "text": text,
                "date": c.get("timestamp", "")[:16],
                "is_lead": is_lead,
            })
    leads = [c for c in all_replies if c["is_lead"]]
    return {"replies": all_replies, "leads": leads}


def get_account(cfg):
    """Профиль Threads + число подписчиков."""
    info = graph_get(
        cfg, cfg["user_id"],
        params={"fields": "username,name,threads_biography"},
    )
    try:
        ins = graph_get(cfg, f"{cfg['user_id']}/threads_insights",
                        params={"metric": "followers_count"})
        for item in ins.get("data", []):
            if item.get("name") == "followers_count":
                info["followers_count"] = _metric_value(item)
    except GraphError:
        info["followers_count"] = None
    return info


def main():
    p = argparse.ArgumentParser(description="Аналитика Threads MILA GOLD")
    p.add_argument("mode", choices=["posts", "replies", "account"],
                   help="что выгружать")
    p.add_argument("--limit", type=int, default=20,
                   help="сколько последних тредов обработать (по умолч. 20)")
    args = p.parse_args()

    cfg = load_threads_config()

    if args.mode == "posts":
        data = get_posts(cfg, args.limit)
        path = save_report("threads_posts", data)
        print(f"\n🧵 Топ тредов по вовлечённости (всего {len(data)}):\n")
        for i, r in enumerate(data[:10], 1):
            views = f", 👁 {r['views']}" if r.get("views") else ""
            print(f"{i}. [{r['date']}] ❤️ {r['likes']}  💬 {r['replies']}  "
                  f"🔁 {r['reposts']}{views}")
            print(f"   {r['text'][:80]}")
            print(f"   {r['link']}\n")

    elif args.mode == "replies":
        data = get_replies(cfg, args.limit)
        path = save_report("threads_replies", data)
        print(f"\n💬 Ответов: {len(data['replies'])}  |  "
              f"Заявок (триггер-слова): {len(data['leads'])}\n")
        for c in data["leads"]:
            print(f"  🔥 @{c['username']}: {c['text'][:90]}")
            print(f"     {c['post_link']}\n")

    elif args.mode == "account":
        data = get_account(cfg)
        path = save_report("threads_account", data)
        print(f"\n🧵 @{data.get('username')}  ({data.get('name')})")
        print(f"   Подписчиков: {data.get('followers_count')}\n")

    print(f"✅ Сохранено: {path}")


if __name__ == "__main__":
    run_cli(main)
