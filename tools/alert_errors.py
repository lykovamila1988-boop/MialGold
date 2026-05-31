#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alert_errors.py — алерт по новым ошибкам агентов из logs/webapp.log.

Находит НОВЫЕ ERROR-строки с прошлого запуска (состояние в reports/.alert_state.json)
и либо шлёт их в Telegram (если задан TELEGRAM_ALERT_CHAT_ID + токен), либо
записывает в reports/alerts_YYYY-MM-DD.json. Рассчитан на запуск по расписанию
(cron / Планировщик задач Windows) — частота определяет SLA «время до реакции».

Использование:
    python alert_errors.py

Настройка Telegram-доставки в tools/.env:
    TELEGRAM_BOT_TOKEN=...        (или legacy TELEGRAM_API)
    TELEGRAM_ALERT_CHAT_ID=...    (id чата/канала офиса)
Без них алерты пишутся в файл — потерь нет.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import re
import json
import datetime
from pathlib import Path
from dotenv import load_dotenv
import requests

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
REPORTS = ROOT / "reports"
STATE = REPORTS / ".alert_state.json"
LOG_FILE = LOGS / "webapp.log"

load_dotenv(ROOT / "tools" / ".env")
_EXC_RE = re.compile(r"^[\w.]+(Error|Exception)\b")


def _read_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _write_state(d):
    REPORTS.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API")
    chat = os.getenv("TELEGRAM_ALERT_CHAT_ID")
    if not token or not chat:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text[:4000]}, timeout=10)
        return bool(r.json().get("ok"))
    except Exception as e:
        print(f"[!] Telegram отправка не удалась: {e}")
        return False


def _record_file(events, exceptions):
    path = REPORTS / f"alerts_{datetime.date.today():%Y-%m-%d}.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        existing = []
    existing.append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "errors": events, "exceptions": exceptions,
    })
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    if not LOG_FILE.exists():
        print("Нет logs/webapp.log — нечего проверять.")
        return
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    last = _read_state().get("last_count", 0)
    if last > len(lines):   # лог ротировали/обрезали — читаем заново
        last = 0
    new = lines[last:]

    events = [ln.strip() for ln in new if " ERROR " in ln]
    exceptions = [ln.strip() for ln in new if _EXC_RE.match(ln.strip())]

    if not events:
        _write_state({"last_count": len(lines)})
        print("Новых ошибок нет. ✅")
        return

    msg = f"🚨 MILA office: {len(events)} новых ошибок в webapp.log\n\n" + "\n".join(events[-5:])
    if exceptions:
        msg += "\n\nИсключения:\n" + "\n".join(exceptions[-5:])

    if _send_telegram(msg):
        print(f"✅ Отправлено в Telegram: {len(events)} ошибок.")
    else:
        path = _record_file(events, exceptions)
        print(f"⚠️  {len(events)} новых ошибок записаны в {path}")
        print("    (Telegram не настроен — задай TELEGRAM_ALERT_CHAT_ID и токен в tools/.env.)")
    _write_state({"last_count": len(lines)})


if __name__ == "__main__":
    main()
