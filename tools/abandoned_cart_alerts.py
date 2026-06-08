#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
abandoned_cart_alerts.py — алерты о брошенных корзинах и незавершённых консультациях.

Логика:
  1. Читает из Supabase purchases со статусом 'pending' (неоплаченные) старше 24h
  2. Читает из Supabase consultations со статусом 'scheduled' но дата уже прошла
  3. Отправляет персонализированные напоминания через Telegram (если есть telegram юзера)
  4. Логирует результаты (отправлено/ошибка)

Используется из n8n webhook или прямого вызова:
  python abandoned_cart_alerts.py [--dry-run] [--hours N]

Возвращает JSON:
  {
    "ok": true,
    "abandoned_purchases": [{"user_id": "...", "email": "...", "status": "sent|skipped|error"}],
    "overdue_consultations": [...],
    "stats": {"purchases_checked": N, "sent": N, "errors": N}
  }
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
import requests

TOOLS = Path(__file__).resolve().parent
load_dotenv(TOOLS / ".env")

# Supabase
SUPA_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPA_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

# Telegram
TG_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()

def _log(msg):
    """Лог с меткой времени."""
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] {msg}", file=sys.stderr, flush=True)

def _fail(reason):
    """Вывести ошибку в JSON и выход."""
    print(json.dumps({"ok": False, "reason": reason}, ensure_ascii=False))
    sys.exit(1)

def _check(r, action):
    """Проверить HTTP ответ от Supabase."""
    if r.status_code not in (200, 201):
        try:
            msg = r.json().get("message", r.text)
        except ValueError:
            msg = r.text
        raise Exception(f"{action} → HTTP {r.status_code}: {msg}")

def supa_get(table, filters=None):
    """Получить строки из Supabase (читает через service-role)."""
    if not SUPA_URL or not SUPA_KEY:
        raise Exception("Supabase не настроен (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")

    url = f"{SUPA_URL}/rest/v1/{table}?select=*"
    headers = {"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}"}

    if filters:
        for col, op_val in filters.items():
            url += f"&{col}={op_val}"

    r = requests.get(url, headers=headers, timeout=15)
    _check(r, f"supa_get {table}")
    return r.json() if isinstance(r.json(), list) else []

def telegram_send_user(user_id_or_tg, text):
    """Отправить сообщение конкретному юзеру в Telegram."""
    if not TG_TOKEN:
        return False, "Нет TELEGRAM_BOT_TOKEN"

    # user_id_or_tg может быть telegram ID (число) или username
    chat_id = str(user_id_or_tg)

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            _log(f"✓ Telegram отправлено {chat_id}")
            return True, None
        error = data.get("description", "неизвестная ошибка")
        _log(f"✗ Telegram {chat_id}: {error}")
        return False, error
    except Exception as e:
        _log(f"✗ Telegram {chat_id}: {e}")
        return False, str(e)

def find_abandoned_purchases(hours=24):
    """Найти покупки со статусом pending старше N часов."""
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat() + "Z"

        # Фильтр: status=pending И created_at < cutoff
        purchases = supa_get("purchases", {
            "status": "eq.pending",
            "created_at": f"lt.{cutoff_iso}"
        })

        # Обогащаем данными юзера (email, telegram)
        result = []
        for p in purchases:
            user_id = p.get("user_id")
            if user_id:
                try:
                    users = supa_get("users", {"id": f"eq.{user_id}"})
                    user = users[0] if users else {}
                except Exception:
                    user = {}
            else:
                user = {}

            result.append({
                "purchase_id": p.get("id"),
                "user_id": user_id,
                "email": user.get("email", ""),
                "telegram": user.get("telegram", ""),
                "name": user.get("name", ""),
                "amount": p.get("amount_cad"),
                "created_at": p.get("created_at"),
                "notes": p.get("notes", "")  # product name
            })

        return result
    except Exception as e:
        raise Exception(f"Ошибка поиска брошенных покупок: {e}")

def find_overdue_consultations():
    """Найти консультации со статусом scheduled, но дата уже прошла."""
    try:
        now_iso = datetime.utcnow().isoformat() + "Z"

        # Фильтр: status=scheduled И scheduled_at < now
        consultations = supa_get("consultations", {
            "status": "eq.scheduled",
            "scheduled_at": f"lt.{now_iso}"
        })

        # Обогащаем данными юзера
        result = []
        for c in consultations:
            user_id = c.get("user_id")
            if user_id:
                try:
                    users = supa_get("users", {"id": f"eq.{user_id}"})
                    user = users[0] if users else {}
                except Exception:
                    user = {}
            else:
                user = {}

            result.append({
                "consultation_id": c.get("id"),
                "user_id": user_id,
                "email": user.get("email", ""),
                "telegram": user.get("telegram", ""),
                "name": user.get("name", ""),
                "type": c.get("type", "single"),
                "scheduled_at": c.get("scheduled_at"),
                "status": c.get("status")
            })

        return result
    except Exception as e:
        raise Exception(f"Ошибка поиска просроченных консультаций: {e}")

def send_alerts(purchases, consultations, dry_run=False):
    """Отправить напоминания для брошенных покупок и консультаций."""
    stats = {"purchases_checked": len(purchases), "consultations_checked": len(consultations),
             "sent": 0, "skipped": 0, "errors": 0}

    results = {
        "abandoned_purchases": [],
        "overdue_consultations": []
    }

    # Напоминания о брошенных покупках
    for p in purchases:
        status = "sent"
        reason = None

        if not p["telegram"]:
            status = "skipped"
            reason = "Нет Telegram"
        elif not dry_run:
            # Генерируем текст напоминания
            product = p["notes"] or "практикум"
            text = (
                f"👋 Привет{', ' + p['name'] if p['name'] else ''}!\n\n"
                f"Посмотрела, что ты интересовалась {product}, но пока его не активировала.\n\n"
                f"💰 Стоимость: ${p['amount']:.2f} CAD\n\n"
                f"Может, были вопросы? Я помогу! 🙏\n\n"
                f"Активировать: через ссылку из письма Gumroad"
            )

            ok, err = telegram_send_user(p["telegram"], text)
            if not ok:
                status = "error"
                reason = err

        if status == "sent":
            stats["sent"] += 1
        elif status == "skipped":
            stats["skipped"] += 1
        elif status == "error":
            stats["errors"] += 1

        results["abandoned_purchases"].append({
            "user_id": p["user_id"],
            "email": p["email"],
            "telegram": p["telegram"],
            "status": status,
            "reason": reason
        })

    # Напоминания о просроченных консультациях
    for c in consultations:
        status = "sent"
        reason = None

        if not c["telegram"]:
            status = "skipped"
            reason = "Нет Telegram"
        elif not dry_run:
            text = (
                f"📞 Привет{', ' + c['name'] if c['name'] else ''}!\n\n"
                f"Напоминаю о твоей консультации ({c['type']}).\n\n"
                f"Дата была: {c['scheduled_at'][:10] if c['scheduled_at'] else '?'}\n\n"
                f"Если нужно перенести или остались вопросы — напиши! 💬"
            )

            ok, err = telegram_send_user(c["telegram"], text)
            if not ok:
                status = "error"
                reason = err

        if status == "sent":
            stats["sent"] += 1
        elif status == "skipped":
            stats["skipped"] += 1
        elif status == "error":
            stats["errors"] += 1

        results["overdue_consultations"].append({
            "user_id": c["user_id"],
            "email": c["email"],
            "telegram": c["telegram"],
            "status": status,
            "reason": reason
        })

    return results, stats

def main():
    p = argparse.ArgumentParser(description="Алерты о брошенных корзинах")
    p.add_argument("--dry-run", action="store_true", help="Не отправлять, только показать")
    p.add_argument("--hours", type=int, default=24, help="Покупки старше N часов (default 24)")
    args = p.parse_args()

    try:
        _log(f"Поиск брошенных покупок (старше {args.hours}h) и просроченных консультаций...")

        purchases = find_abandoned_purchases(hours=args.hours)
        consultations = find_overdue_consultations()

        _log(f"Найдено: {len(purchases)} покупок, {len(consultations)} консультаций")

        results, stats = send_alerts(purchases, consultations, dry_run=args.dry_run)

        output = {
            "ok": True,
            "dry_run": args.dry_run,
            "timestamp": datetime.utcnow().isoformat(),
            **results,
            "stats": stats
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))
        _log(f"✓ Завершено: {stats['sent']} отправлено, {stats['skipped']} пропущено, {stats['errors']} ошибок")

    except Exception as e:
        _fail(str(e))

if __name__ == "__main__":
    main()
