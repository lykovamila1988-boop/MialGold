#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supa.py — общий клиент Supabase (PostgREST) для MILA GOLD.

Единое место доступа к БД проекта mila-platform. Резолвит ключи из tools/.env:
  • запись/полный доступ — SUPABASE_SERVICE_ROLE_KEY (или legacy SUPABASE_SERVICE_KEY).
    Обходит RLS — нужен для вставок/обновлений из агентов и аплоадеров.
  • чтение — SUPABASE_PUBLISHABLE_KEY / SUPABASE_ANON_KEY (под RLS: видны только строки,
    разрешённые политикой; продакшн-таблицы без anon-политики вернут пусто).

⚠️  Сейчас в .env только publishable/anon ключ → запись запрещена RLS (401, code 42501),
    а многие таблицы под RLS читаются пусто. Чтобы агенты реально работали с БД (читать
    продажи/лиды/kpi и писать), добавь в tools/.env:
        SUPABASE_SERVICE_ROLE_KEY=...   (Supabase → Project Settings → API → service_role)

API:
    supa.available()           -> можно ли читать (есть URL + ключ)
    supa.can_write()           -> есть ли service-role ключ (запись в обход RLS)
    supa.select(table, columns="*", filters=None, order=None, limit=None) -> list[dict]
    supa.upsert(table, rows, on_conflict=None)   # требует service-role
    supa.insert(table, rows)                      # требует service-role
    supa.update(table, values, filters)           # требует service-role
    supa.delete(table, filters)                   # требует service-role
"""
import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
# service-role: полный доступ (обходит RLS). Канон + legacy-имена.
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
               or os.getenv("SUPABASE_SERVICE_ROLE") or "").strip()
# чтение под RLS: publishable/anon.
PUBLIC_KEY = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
              or os.getenv("SUPABASE_KEY") or "").strip()
READ_KEY = SERVICE_KEY or PUBLIC_KEY
WRITE_KEY = SERVICE_KEY

_session = requests.Session()


class SupabaseError(Exception):
    """Ошибка вызова Supabase REST (сеть, RLS, валидация)."""


def available() -> bool:
    return bool(URL and READ_KEY)


def can_write() -> bool:
    """True только при наличии service-role ключа (запись в обход RLS)."""
    return bool(URL and WRITE_KEY)


def _headers(key, extra=None):
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    if extra:
        h.update(extra)
    return h


def _check(r, action):
    if r.status_code not in (200, 201, 204, 206):
        try:
            msg = r.json().get("message", r.text)
        except ValueError:
            msg = r.text
        raise SupabaseError(f"{action} → HTTP {r.status_code}: {msg}")


def select(table, columns="*", filters=None, order=None, limit=None):
    """GET строк таблицы. filters: {col: 'eq.value'} (синтаксис PostgREST)."""
    if not available():
        raise SupabaseError("Supabase не настроен (нет SUPABASE_URL или ключа).")
    params = {"select": columns}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    try:
        r = _session.get(f"{URL}/rest/v1/{table}", headers=_headers(READ_KEY),
                         params=params, timeout=30)
    except requests.RequestException as e:
        raise SupabaseError(f"Сетевая ошибка: {e}")
    _check(r, f"select {table}")
    return r.json() if r.content else []


def _write(method, table, body=None, params=None, prefer="return=representation"):
    if not can_write():
        raise SupabaseError(
            "Запись в Supabase требует service-role ключа. Добавь SUPABASE_SERVICE_ROLE_KEY "
            "в tools/.env (Supabase → Project Settings → API → service_role). С publishable/"
            "anon ключом RLS запрещает вставку/обновление (code 42501).")
    headers = _headers(WRITE_KEY, {"Content-Type": "application/json", "Prefer": prefer})
    try:
        r = _session.request(method, f"{URL}/rest/v1/{table}", headers=headers,
                             params=params, data=(json.dumps(body) if body is not None else None),
                             timeout=60)
    except requests.RequestException as e:
        raise SupabaseError(f"Сетевая ошибка: {e}")
    _check(r, f"{method} {table}")
    return r.json() if r.content else []


def insert(table, rows):
    return _write("POST", table, body=rows if isinstance(rows, list) else [rows])


def upsert(table, rows, on_conflict=None):
    params = {"on_conflict": on_conflict} if on_conflict else None
    return _write("POST", table, body=rows if isinstance(rows, list) else [rows],
                  params=params, prefer="resolution=merge-duplicates,return=representation")


def update(table, values, filters):
    return _write("PATCH", table, body=values, params=filters)


def delete(table, filters):
    return _write("DELETE", table, params=filters, prefer="return=minimal")


def status():
    """Краткий статус подключения (для диагностики/агентов)."""
    return {
        "url_set": bool(URL),
        "read_key": "service" if SERVICE_KEY else ("publishable/anon" if PUBLIC_KEY else None),
        "can_write": can_write(),
        "note": None if can_write() else
                "Только чтение под RLS. Для записи добавь SUPABASE_SERVICE_ROLE_KEY в tools/.env.",
    }


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    if available():
        try:
            print("products:", len(select("products", limit=10)), "rows readable")
        except SupabaseError as e:
            print("read check:", e)
