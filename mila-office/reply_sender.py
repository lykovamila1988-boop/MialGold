# -*- coding: utf-8 -*-
"""
reply_sender.py — paced-отправитель ответов на комментарии Instagram.

Берёт ответы из очереди (memory.reply_queue) и шлёт их ПО ОДНОМУ с паузой между
ответами и под общим ЧАСОВЫМ лимитом (memory.shared_rate_limit) — чтобы всплеск
ответов не выглядел спамом для Instagram. Очередь наполняет Марина по команде
«ответить всем» (инструмент queue_comment_replies).

Запуск:
  python reply_sender.py            # разгрести очередь и выйти (с паузой между ответами)
  python reply_sender.py --watch    # не выходить: ждать новые ответы и слать их
  python reply_sender.py --once     # отправить ровно один ответ и выйти
  python reply_sender.py --status   # показать состояние очереди и выйти (ничего не шлёт)

Темп/лимит (флаги или env REPLY_*):
  --pause-min 30  --pause-max 60  --max-per-hour 25

Токен берётся из tools/.env (facebook-flow EAA-токен → graph.facebook.com).
"""
import os
import sys
import time
import json
import random
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from dotenv import load_dotenv

# Свой процесс → читаем .env заново (root, затем tools/.env поверх — как везде в офисе),
# чтобы подхватить актуальный токен/flow, даже если webapp стартовал со старым.
ROOT = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "tools" / ".env", override=True)

sys.path.insert(0, str(ROOT / "mila-office"))
import memory  # noqa: E402

RATE_KEY = "instagram_comments"


def _token() -> str:
    return (os.getenv("IG_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN") or "").strip()


def _host() -> str:
    flow = (os.getenv("IG_API_FLOW", "facebook") or "facebook").strip().lower()
    # facebook-flow (EAA-токен) ходит через graph.facebook.com; instagram_login — graph.instagram.com
    return "https://graph.instagram.com" if flow == "instagram_login" else "https://graph.facebook.com"


def _ver() -> str:
    return os.getenv("GRAPH_API_VERSION", "v21.0")


def post_reply(comment_id: str, message: str):
    """POST {comment_id}/replies. Возвращает (ok, error, response_id).
    Не используем _common.graph_post — он sys.exit'ит на ошибке, что для долго
    живущего отправителя недопустимо."""
    token = _token()
    if not token:
        return False, "IG token не задан (IG_ACCESS_TOKEN)", None
    url = f"{_host()}/{_ver()}/{comment_id}/replies"
    try:
        r = requests.post(url, data={"message": message, "access_token": token}, timeout=25)
        j = r.json() if r.content else {}
    except Exception as e:
        return False, f"сеть: {e}", None
    if isinstance(j, dict) and j.get("error"):
        return False, (j["error"].get("message") or "API error"), None
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code}", None
    return True, None, (j.get("id") if isinstance(j, dict) else None)


def run(pause_min: float, pause_max: float, max_per_hour: int,
        once: bool = False, watch: bool = False) -> dict:
    sent = failed = 0
    while True:
        if not memory.list_replies("pending"):
            if watch:
                time.sleep(10)
                continue
            break
        # Часовой лимит — общий счётчик, переживает перезапуск процесса.
        rl = memory.shared_rate_limit(RATE_KEY, max_per_hour)
        if not rl.get("ok"):
            wait = min(int(rl.get("retry_after", 60) or 60), 300)
            print(f"[reply] часовой лимит исчерпан ({rl.get('used')}/{max_per_hour}) — пауза {wait}с")
            if once:
                break
            time.sleep(wait)
            continue
        rep = memory.dequeue_reply()
        if not rep:
            continue  # гонка: ответ забрал другой процесс
        ok, err, resp_id = post_reply(rep["comment_id"], rep["message"])
        if ok:
            memory.mark_reply(rep["id"], "sent", response_id=resp_id)
            sent += 1
            print(f"[reply] ✓ {rep['id']} → коммент {rep['comment_id']} (@{rep.get('username') or '?'})")
        else:
            memory.mark_reply(rep["id"], "failed", error=err)
            failed += 1
            print(f"[reply] ✗ {rep['id']} ошибка: {err}")
        if once:
            break
        pause = random.uniform(pause_min, pause_max)  # рандом, чтобы не выглядеть ботом
        print(f"[reply] пауза {pause:.0f}с до следующего…")
        time.sleep(pause)
    print(f"[reply] готово. отправлено: {sent}, ошибок: {failed}")
    return {"sent": sent, "failed": failed}


def main():
    p = argparse.ArgumentParser(description="Paced-отправитель ответов на комментарии")
    p.add_argument("--once", action="store_true", help="отправить один ответ и выйти")
    p.add_argument("--watch", action="store_true", help="не выходить: ждать новые ответы")
    p.add_argument("--status", action="store_true", help="показать очередь и выйти")
    p.add_argument("--pause-min", type=float, default=float(os.getenv("REPLY_PAUSE_MIN", "30")))
    p.add_argument("--pause-max", type=float, default=float(os.getenv("REPLY_PAUSE_MAX", "60")))
    p.add_argument("--max-per-hour", type=int, default=int(os.getenv("REPLY_MAX_PER_HOUR", "25")))
    a = p.parse_args()
    if a.status:
        print(json.dumps(memory.reply_queue_status(), ensure_ascii=False, indent=2))
        return
    pause_max = max(a.pause_max, a.pause_min)
    run(a.pause_min, pause_max, a.max_per_hour, once=a.once, watch=a.watch)


if __name__ == "__main__":
    main()
