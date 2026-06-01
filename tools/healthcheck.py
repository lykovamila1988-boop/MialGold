#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
healthcheck.py — единая утренняя проверка «работает ли система прямо сейчас».

Проверяет 5 вещей:
  1. n8n отвечает            (http://127.0.0.1:5678/healthz)
  2. n8n_bridge отвечает     (http://127.0.0.1:5051/health)
  3. Supabase доступна       (supa.select products)
  4. Instagram токен жив и не истекает <7 дней (debug_token / срок)
  5. memory/context.json — валидный JSON
  6. последний триггер сработал не более 25ч назад (events.jsonl pipeline:*)

Итог — ОДНА строка Людмиле в Telegram:
  «✅ Все системы работают»  или  «⚠️ Проблема: …»

Запуск:
    python healthcheck.py            # проверить и отправить в Telegram
    python healthcheck.py --no-send  # только напечатать (для cron-теста)
    python healthcheck.py --json     # машинный вывод

Вызывается n8n по расписанию (ежедневно утром) через мост: /v1/tools/healthcheck.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from dotenv import load_dotenv

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
load_dotenv(ROOT / ".env")
load_dotenv(TOOLS / ".env")

TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API") or "").strip()
CHAT = (os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_ALERT_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
N8N_URL = os.getenv("N8N_BASE_URL", "http://127.0.0.1:5678").rstrip("/")
BRIDGE_PORT = os.getenv("N8N_BRIDGE_PORT", "5051")
TOKEN_WARN_DAYS = int(os.getenv("TOKEN_WARN_DAYS", "7"))
TRIGGER_MAX_HOURS = int(os.getenv("TRIGGER_MAX_HOURS", "25"))

MEMORY_DIR = ROOT / "mila-office" / "memory"
CONTEXT = MEMORY_DIR / "context.json"
EVENTS = MEMORY_DIR / "events.jsonl"


def _probe(url):
    try:
        r = requests.get(url, timeout=5)
        return r.status_code < 500
    except requests.RequestException:
        return False


def check_n8n():
    return ("n8n", _probe(f"{N8N_URL}/healthz"), "n8n не отвечает (:5678)")


def check_bridge():
    return ("bridge", _probe(f"http://127.0.0.1:{BRIDGE_PORT}/health"),
            "n8n_bridge не отвечает (:5051)")


def check_supabase():
    try:
        if str(TOOLS) not in sys.path:
            sys.path.insert(0, str(TOOLS))
        import supa
        if not supa.available():
            return ("supabase", False, "Supabase не настроена")
        supa.select("products", limit=1)
        return ("supabase", True, "")
    except Exception as e:
        return ("supabase", False, f"Supabase недоступна: {str(e)[:60]}")


def check_ig_token():
    """Жив ли токен и не истекает ли в ближайшие TOKEN_WARN_DAYS дней."""
    try:
        if str(TOOLS) not in sys.path:
            sys.path.insert(0, str(TOOLS))
        from _common import load_config, graph_get, GraphError
        cfg = load_config()
        token = cfg.get("token")
        # debug_token работает на graph.facebook.com; для instagram_login проверяем
        # живость через /me, срок — через данные debug (если доступно).
        flow = cfg.get("flow")
        if flow == "instagram_login":
            # просто проверяем, что токен ещё отвечает
            try:
                graph_get(cfg, cfg.get("node", "me"), params={"fields": "id"})
                return ("ig_token", True, "")
            except GraphError as e:
                return ("ig_token", False, f"Instagram токен не отвечает: {str(e)[:50]}")
        # facebook flow → debug_token со сроком
        dbg = graph_get(cfg, "debug_token", params={"input_token": token}).get("data", {})
        if not dbg.get("is_valid"):
            return ("ig_token", False, "Instagram токен НЕДЕЙСТВИТЕЛЕН")
        exp = dbg.get("data_access_expires_at") or dbg.get("expires_at") or 0
        if exp:
            days = (datetime.fromtimestamp(exp, timezone.utc) - datetime.now(timezone.utc)).days
            if days < 0:
                return ("ig_token", False, "Instagram токен ИСТЁК")
            if days <= TOKEN_WARN_DAYS:
                return ("ig_token", False, f"Instagram токен истекает через {days} дн.! Перевыпусти.")
        return ("ig_token", True, "")
    except SystemExit as e:
        return ("ig_token", False, f"Instagram токен/конфиг: {str(e)[:50]}")
    except Exception as e:
        return ("ig_token", False, f"Проверка токена не удалась: {str(e)[:50]}")


def check_memory():
    try:
        if not CONTEXT.exists():
            return ("memory", True, "")  # пусто — норм (ещё не было событий)
        json.loads(CONTEXT.read_text(encoding="utf-8"))
        return ("memory", True, "")
    except (ValueError, OSError) as e:
        return ("memory", False, f"context.json повреждён: {str(e)[:50]}")


def check_last_trigger():
    """Был ли запуск pipeline/триггер за последние TRIGGER_MAX_HOURS часов."""
    try:
        if not EVENTS.exists():
            return ("trigger", True, "")  # система свежая — не алертим
        last = None
        for ln in EVENTS.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if str(e.get("kind", "")).startswith(("pipeline:", "context:", "published", "measured")):
                last = e.get("ts")
        if not last:
            return ("trigger", True, "")
        dt = datetime.fromisoformat(last)
        hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if hours > TRIGGER_MAX_HOURS:
            return ("trigger", False, f"Нет активности {int(hours)}ч (>{TRIGGER_MAX_HOURS}ч) — триггеры молчат?")
        return ("trigger", True, "")
    except Exception as e:
        return ("trigger", False, f"Проверка активности: {str(e)[:50]}")


CHECKS = [check_n8n, check_bridge, check_supabase, check_ig_token,
          check_memory, check_last_trigger]


def run():
    results = [fn() for fn in CHECKS]
    problems = [msg for _name, ok, msg in results if not ok and msg]
    all_ok = not problems
    if all_ok:
        line = "✅ Все системы работают"
    else:
        line = "⚠️ Проблема: " + " · ".join(problems)
    return all_ok, line, results


def send_telegram(text):
    if not TOKEN or not CHAT:
        return False, "no telegram token/chat"
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json={"chat_id": CHAT, "text": text}, timeout=20)
        return r.json().get("ok", False), r.status_code
    except requests.RequestException as e:
        return False, str(e)


def main():
    p = argparse.ArgumentParser(description="MILA health check")
    p.add_argument("--no-send", action="store_true", help="не слать в Telegram, только печать")
    p.add_argument("--json", action="store_true", help="машинный вывод")
    args = p.parse_args()

    all_ok, line, results = run()

    if args.json:
        print(json.dumps({
            "ok": all_ok, "line": line,
            "checks": {n: {"ok": ok, "msg": m} for n, ok, m in results},
        }, ensure_ascii=False, indent=2))
    else:
        print(line)
        for n, ok, m in results:
            print(f"  {'✓' if ok else '✗'} {n}" + (f" — {m}" if m else ""))

    if not args.no_send:
        sent, info = send_telegram(line)
        if not args.json:
            print(f"\nTelegram: {'отправлено' if sent else 'НЕ отправлено'} ({info})")
    # exit 0 даже при проблемах — это мониторинг, не сбой самого скрипта
    sys.exit(0)


if __name__ == "__main__":
    main()
