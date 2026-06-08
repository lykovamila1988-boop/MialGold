#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_rls_fix.py — автоматическое выполнение SQL для обновления RLS.

Пытается выполнить SQL несколькими способами:
1. Через Supabase REST API (если доступно)
2. Через psql напрямую к PostgreSQL (если установлен)
3. Показывает инструкцию если ничего не сработало

Запуск: cd tools && python apply_rls_fix.py
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

TOOLS = Path(__file__).resolve().parent
load_dotenv(TOOLS / ".env")

SUPA_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPA_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

# SQL команды для выполнения
SQL_COMMANDS = """
drop policy if exists "Public posts" on public.ig_posts;
create policy "Public posts" on public.ig_posts for select using (true);
alter table public.ig_posts enable row level security;
"""

def log(msg, level="INFO"):
    ts = datetime.utcnow().isoformat()
    icons = {"INFO": "ℹ️", "✅": "✅", "❌": "❌", "⚠️": "⚠️"}
    icon = icons.get(level, "•")
    print(f"[{ts}] {icon} {msg}")

def try_psql():
    """Попытка выполнить через psql (если postgres установлен)."""
    log("Попытка 1: Выполнение через psql...", "ℹ️")

    # Извлечём параметры подключения из SUPABASE_URL
    # Format: https://projectid.supabase.co
    if "supabase.co" not in SUPA_URL:
        log("  ⚠️  URL не похож на Supabase", "⚠️")
        return False

    project_id = SUPA_URL.split("//")[1].split(".")[0]
    log(f"  Проект: {project_id}", "INFO")

    # Для подключения через psql нужен пароль PostgreSQL (которого нет)
    # Этот способ не сработает без дополнительных данных
    log("  ⚠️  psql требует пароль PostgreSQL (не доступен)", "⚠️")
    return False

def try_web_ui():
    """Показать инструкцию для выполнения через Supabase Web UI."""
    log("Способ: Выполнение через Supabase Web UI", "INFO")
    print("\n" + "=" * 70)
    print("📋 ПОШАГОВАЯ ИНСТРУКЦИЯ")
    print("=" * 70)
    print("""
1️⃣  ОТКРОЙТЕ Supabase Console:
    🔗 https://app.supabase.com/project/twrmpbduxemfgxtadkxa/sql

2️⃣  СКОПИРУЙТЕ эти SQL команды:
""")

    for cmd in SQL_COMMANDS.strip().split("\n"):
        print(f"    {cmd}")

    print("""
3️⃣  НАЖМИТЕ "Execute" (или Ctrl+Enter)

4️⃣  ПРОВЕРЬТЕ результат (должно быть "Query successful")

5️⃣  ПЕРЕЗАГРУЗИТЕ браузер с мила-офисом:
    🔗 http://localhost:5000

6️⃣  ГОТОВО! Марина теперь может видеть данные аналитики
""")
    print("=" * 70 + "\n")
    return True

def try_curl():
    """Попытка через curl/requests (если Supabase поддерживает SQL API)."""
    log("Попытка 2: Выполнение через REST API...", "ℹ️")

    try:
        import requests

        # Supabase не имеет публичного SQL API через REST
        # Но можно попробовать через функцию
        log("  ℹ️  Supabase REST API не поддерживает произвольный SQL", "ℹ️")
        log("  ℹ️  Требуется выполнить через Web UI или Edge Function", "ℹ️")
        return False

    except ImportError:
        return False

def main():
    log("=" * 70, "ℹ️")
    log("ПРИМЕНЕНИЕ FIX: Обновление RLS для таблицы ig_posts", "ℹ️")
    log("=" * 70, "ℹ️")

    if not SUPA_URL or not SUPA_KEY:
        log("❌ Не заполнено: SUPABASE_URL или SUPABASE_SERVICE_ROLE_KEY", "❌")
        sys.exit(1)

    print()

    # Пытаемся несколькими способами
    success = False

    # Способ 1: psql (едва ли сработает без пароля)
    # if try_psql():
    #     success = True

    # Способ 2: REST API (Supabase не поддерживает)
    # if try_curl():
    #     success = True

    # Способ 3: Web UI (всегда работает)
    if try_web_ui():
        success = True

    print()
    log("=" * 70, "ℹ️")
    log("ВЫ ДОЛЖНЫ выполнить SQL команды в Supabase Web UI", "⚠️")
    log("После выполнения Марина получит доступ к данным", "INFO")
    log("=" * 70, "ℹ️")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
