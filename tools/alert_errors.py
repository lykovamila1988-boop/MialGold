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
# Время в начале строки лога: "2026-06-03 20:34:03,424 ..."
_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _error_type(line: str) -> str:
    """Сигнатура типа ошибки для группировки. Узнаём частые случаи (Gemini 429,
    нет кредитов Claude, KeyError и т.п.), иначе — общий ярлык."""
    low = line.lower()
    if "gemini api 429" in low or "exceeded your current quota" in low:
        return "Gemini 429 (квота)"
    if "credit balance is too low" in low:
        return "Claude: нет кредитов"
    if "gemini api 5" in low or "service unavailable" in low:
        return "Gemini 5xx (сбой Google)"
    m = re.search(r"\b([\w.]+(?:Error|Exception))\b", line)
    if m:
        return m.group(1).split(".")[-1]   # KeyError, BadRequestError, …
    # «… ERROR mila.webapp: Ошибка агента manager …» → берём суть после ERROR
    m = re.search(r"\bERROR\b\s+([^\n]{0,60})", line)
    return (m.group(1).strip() if m else "ERROR")[:60]


def _ts(line: str) -> str:
    m = _TS_RE.match(line)
    return m.group(1) if m else "—"


def _aggregate(events: list) -> dict:
    """Группирует строки-ошибки по типу: count + первое/последнее время."""
    agg = {}
    for ln in events:
        t = _error_type(ln)
        ts = _ts(ln)
        a = agg.setdefault(t, {"count": 0, "first": ts, "last": ts})
        a["count"] += 1
        if ts != "—":
            if a["first"] == "—":
                a["first"] = ts
            a["last"] = ts
    return agg


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


def _record_file(events, exceptions, agg=None):
    path = REPORTS / f"alerts_{datetime.date.today():%Y-%m-%d}.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        existing = []
    existing.append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "by_type": agg or {},          # сводка по типу: count + first/last
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

    # Группируем по типу: вместо спама одинаковыми строками — сводка
    # «тип × количество, первое/последнее время» (критерий приёмки P1).
    agg = _aggregate(events)
    ordered = sorted(agg.items(), key=lambda kv: kv[1]["count"], reverse=True)
    lines_md = [f"• {t}: ×{a['count']}  ({a['first']} → {a['last']})"
                for t, a in ordered]
    msg = (f"🚨 MILA office: {len(events)} новых ошибок в webapp.log, "
           f"{len(agg)} тип(ов)\n\n" + "\n".join(lines_md))

    if _send_telegram(msg):
        print(f"✅ Отправлено в Telegram: {len(events)} ошибок, {len(agg)} типов.")
    else:
        path = _record_file(events, exceptions, agg)
        print(f"⚠️  {len(events)} новых ошибок ({len(agg)} типов) записаны в {path}")
        print("    (Telegram не настроен — задай TELEGRAM_ALERT_CHAT_ID и токен в tools/.env.)")
    _write_state({"last_count": len(lines)})


if __name__ == "__main__":
    main()
