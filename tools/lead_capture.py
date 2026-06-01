#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lead_capture.py — захват лида «ХОЧУ» в Supabase (Разрыв 3: единый профиль клиента).

Идея: одно входящее событие (написал «ХОЧУ» в Telegram / оставил email) →
  1) upsert в public.users  (единый человек, по email или telegram)
  2) insert/update в public.telegram_leads со связью user_id
Так разрозненные события (лид → покупка → сессия) сшиваются в одну историю.

Вызывается из n8n (Execute Command) или из Python:
    python lead_capture.py --telegram @anna --name "Анна" --message "ХОЧУ практикум"
    python lead_capture.py --email anna@x.com --name "Анна" --source instagram

Пишет через Supabase REST с ключом из tools/.env. Печатает JSON-результат
(n8n его распарсит). Ничего не публикует наружу — только запись в БД.
"""
import os
import sys
import json
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from dotenv import load_dotenv

ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
# Сервисный ключ обходит RLS (предпочтительно для записи с сервера). Если его нет —
# берём anon/publishable (тогда для записи нужны RLS-политики, см. миграцию).
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_ANON_KEY")
                or os.getenv("SUPABASE_PUBLISHABLE_KEY", ""))
TRIGGER_WORDS = ["хочу", "want", "цена", "сколько", "заказ", "практикум"]


def _headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _check_config():
    if not SUPABASE_URL or not SUPABASE_KEY:
        sys.exit(json.dumps({"ok": False, "error": "Нет SUPABASE_URL/ключа в tools/.env"},
                            ensure_ascii=False))


def upsert_user(email=None, name=None, telegram=None, instagram=None, phone=None):
    """Создаёт или обновляет человека в public.users. Ключ слияния — email
    (если есть), иначе telegram. Возвращает строку users (с id)."""
    url = f"{SUPABASE_URL}/rest/v1/users"
    if not email and not telegram:
        sys.exit(json.dumps({"ok": False, "error": "Нужен email или telegram"},
                            ensure_ascii=False))
    # В схеме users.email = NOT NULL UNIQUE. У Telegram-лида email'а обычно нет,
    # поэтому синтезируем ДЕТЕРМИНИРОВАННЫЙ placeholder из telegram-хэндла —
    # так повторное «ХОЧУ» сольётся в ту же строку (merge), а не создаст дубль.
    if not email and telegram:
        handle = telegram.lstrip("@").strip().lower() or "unknown"
        email = f"tg-{handle}@placeholder.mila"
    payload = {k: v for k, v in {
        "email": email, "name": name, "telegram": telegram,
        "instagram": instagram, "phone": phone,
    }.items() if v}
    # email теперь всегда есть и уникален → upsert по нему (идемпотентно).
    r = requests.post(url, headers=_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
                      params={"on_conflict": "email"}, json=payload, timeout=20)
    if not r.ok:
        sys.exit(json.dumps({"ok": False, "stage": "upsert_user",
                             "status": r.status_code, "body": r.text[:300]}, ensure_ascii=False))
    rows = r.json()
    return rows[0] if rows else {}


def record_lead(user_id, tg_user_id=None, tg_username=None, tg_name=None,
                source=None, message=None, wrote_want=False):
    """Пишет/обновляет лид в public.telegram_leads со связью на users."""
    url = f"{SUPABASE_URL}/rest/v1/telegram_leads"
    payload = {k: v for k, v in {
        "user_id": user_id, "tg_user_id": tg_user_id, "tg_username": tg_username,
        "tg_name": tg_name, "source": source, "last_message": message,
        "wrote_want": wrote_want, "status": "hot" if wrote_want else "new",
    }.items() if v is not None}
    # tg_user_id уникален в схеме → on_conflict; если его нет, просто insert.
    params = {}
    pref = "return=representation"
    if tg_user_id:
        params["on_conflict"] = "tg_user_id"
        pref = "resolution=merge-duplicates,return=representation"
    r = requests.post(url, headers=_headers({"Prefer": pref}),
                      params=params, json=payload, timeout=20)
    if not r.ok:
        sys.exit(json.dumps({"ok": False, "stage": "record_lead",
                             "status": r.status_code, "body": r.text[:300]}, ensure_ascii=False))
    rows = r.json()
    return rows[0] if rows else {}


def main():
    p = argparse.ArgumentParser(description="Захват лида ХОЧУ в Supabase")
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--telegram", help="@username или имя")
    p.add_argument("--tg-user-id", help="числовой Telegram user id (уникальный)")
    p.add_argument("--instagram")
    p.add_argument("--phone")
    p.add_argument("--source", default="telegram")
    p.add_argument("--message", default="")
    args = p.parse_args()
    _check_config()

    wrote_want = any(w in (args.message or "").lower() for w in TRIGGER_WORDS)
    user = upsert_user(email=args.email, name=args.name, telegram=args.telegram,
                       instagram=args.instagram, phone=args.phone)
    lead = record_lead(user.get("id"), tg_user_id=args.tg_user_id,
                       tg_username=args.telegram, tg_name=args.name,
                       source=args.source, message=args.message, wrote_want=wrote_want)
    print(json.dumps({
        "ok": True, "wrote_want": wrote_want,
        "user_id": user.get("id"), "user_email": user.get("email"),
        "lead_id": lead.get("id"), "lead_status": lead.get("status"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
