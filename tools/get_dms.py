#!/usr/bin/env python3
"""
get_dms.py — выгрузка личных сообщений (Instagram Direct) для MILA GOLD.

⚠️  ВАЖНО про доступ:
    Чтение Instagram Direct идёт через Messenger Platform (Facebook Page,
    привязанная к Instagram). Для этого нужны разрешения
    'instagram_manage_messages' + 'pages_messaging', и приложение должно
    пройти App Review в Meta. Пока проверка не пройдена, эти запросы
    вернут ошибку прав доступа — это нормально, не баг скрипта.

Использование:
    python get_dms.py                  # все диалоги + последние сообщения
    python get_dms.py --limit 50       # не более 50 диалогов
    python get_dms.py --unread         # только непрочитанные

Результат сохраняется в reports/, чтобы Cowork подготовил черновики ответов.
"""
import sys
import argparse
from _common import load_config, graph_get, graph_get_all, save_report, run_cli


def get_conversations(cfg, limit, unread_only):
    """Список диалогов Instagram через привязанную страницу."""
    page_id = cfg["fb_page_id"] or "me"
    convos = graph_get_all(
        cfg, f"{page_id}/conversations",
        params={
            "platform": "instagram",
            "fields": "id,updated_time,unread_count,participants,"
                      "messages.limit(10){id,from,to,message,created_time}",
            "limit": 25,
        },
        max_items=limit,
    )

    results = []
    for c in convos:
        unread = c.get("unread_count", 0)
        if unread_only and not unread:
            continue
        parts = [p.get("username") or p.get("name") or p.get("id")
                 for p in c.get("participants", {}).get("data", [])]
        msgs = []
        for m in c.get("messages", {}).get("data", []):
            sender = m.get("from", {})
            msgs.append({
                "from": sender.get("username") or sender.get("name") or sender.get("id"),
                "text": m.get("message", ""),
                "time": m.get("created_time", "")[:16],
            })
        msgs.reverse()  # хронологический порядок
        results.append({
            "conversation_id": c.get("id"),
            "with": [p for p in parts],
            "unread": unread,
            "updated": c.get("updated_time", "")[:16],
            "messages": msgs,
        })
    return results


def main():
    p = argparse.ArgumentParser(description="Выгрузка Instagram Direct для MILA GOLD")
    p.add_argument("--limit", type=int, default=30, help="макс. число диалогов")
    p.add_argument("--unread", action="store_true", help="только непрочитанные")
    args = p.parse_args()

    cfg = load_config()
    if not cfg["fb_page_id"]:
        print("[i] FB_PAGE_ID не задан в .env — пробую 'me'. "
              "Если будет ошибка прав, впишите ID страницы.\n", file=sys.stderr)

    convos = get_conversations(cfg, args.limit, args.unread)
    path = save_report("dms", convos)

    total_unread = sum(c["unread"] for c in convos)
    print(f"\n📨 Диалогов: {len(convos)}  |  Непрочитанных сообщений: {total_unread}\n")
    for c in convos:
        flag = f"🔴 {c['unread']}" if c["unread"] else "  "
        who = ", ".join(c["with"]) or c["conversation_id"]
        print(f"{flag} {who}  (обновлён {c['updated']})")
        for m in c["messages"][-2:]:
            print(f"      {m['from']}: {m['text'][:80]}")
        print()

    print(f"✅ Сохранено: {path}")


if __name__ == "__main__":
    run_cli(main)
