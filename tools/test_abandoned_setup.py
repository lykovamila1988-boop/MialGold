#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_abandoned_setup.py — быстрая проверка конфига P3.

Запуск: cd tools && python test_abandoned_setup.py
"""
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

TOOLS = Path(__file__).resolve().parent
load_dotenv(TOOLS / ".env")

def check(name, value, required=True):
    """Проверить переменную окружения."""
    status = "✓" if value else "✗"
    print(f"  {status} {name}: {('*' * 8) if value else '(не задана)'}")
    if required and not value:
        return False
    return True

print("=" * 60)
print("ПРОВЕРКА КОНФИГА P3: Алерты о брошенных корзинах")
print("=" * 60)

# Суть конфига
all_ok = True

print("\n📌 SUPABASE (обязательно):")
all_ok &= check("SUPABASE_URL", os.getenv("SUPABASE_URL"))
all_ok &= check("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

print("\n📌 TELEGRAM (обязательно):")
all_ok &= check("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
all_ok &= check("TELEGRAM_ADMIN_CHAT_ID", os.getenv("TELEGRAM_ADMIN_CHAT_ID"))

print("\n📌 n8n (опционально, для расписания):")
check("N8N_BASE_URL", os.getenv("N8N_BASE_URL"), required=False)
check("N8N_API_KEY", os.getenv("N8N_API_KEY"), required=False)
check("N8N_BRIDGE_TOKEN", os.getenv("N8N_BRIDGE_TOKEN"), required=False)

print("\n" + "=" * 60)
if all_ok:
    print("✅ ГОТОВО К ТЕСТИРОВАНИЮ!")
    print("\nСледующие шаги:")
    print("  1. python abandoned_cart_alerts.py --dry-run --hours 24")
    print("  2. Проверьте, что находятся покупки/консультации")
    print("  3. python abandoned_cart_alerts.py --hours 24  # РЕАЛЬНАЯ отправка")
    sys.exit(0)
else:
    print("❌ ОШИБКА КОНФИГА")
    print("\nДобавьте недостающие переменные в tools/.env:")
    print("  SUPABASE_URL=https://twrmpbduxemfgxtadkxa.supabase.co")
    print("  SUPABASE_SERVICE_ROLE_KEY=<из Supabase → Settings → API → service_role>")
    print("  TELEGRAM_BOT_TOKEN=<из @BotFather>")
    print("  TELEGRAM_ADMIN_CHAT_ID=<ваш chat ID в Telegram>")
    sys.exit(1)
