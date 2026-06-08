#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_abandoned_workflow.py — создаёт n8n workflow для алертов о брошенных корзинах.

Поток (ежедневно в 09:00 UTC):
  Schedule Trigger (09:00)
    → HTTP: вызывает abandoned_cart_alerts.py
    → Telegram: отправляет итоги администратору

Идемпотентно (PUT при совпадении имени).

Запуск:  cd tools && python n8n_abandoned_workflow.py
"""
import os
import sys
import json
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

N8N = os.getenv("N8N_BASE_URL", "http://127.0.0.1:5678").rstrip("/")
API_KEY = (os.getenv("N8N_API_KEY") or "").strip()
TELEGRAM_CRED = (os.getenv("N8N_TG_API_ID") or "").strip()
CHAT_ID = (os.getenv("TELEGRAM_ADMIN_CHAT_ID") or "").strip()

WF_NAME = "Daily: Abandoned carts & overdue consultations alerts"
H = {"X-N8N-API-KEY": API_KEY, "accept": "application/json", "Content-Type": "application/json"}

def _require():
    missing = [n for n, v in [
        ("N8N_API_KEY", API_KEY),
        ("N8N_TG_API_ID", TELEGRAM_CRED),
        ("TELEGRAM_ADMIN_CHAT_ID", CHAT_ID),
    ] if not v]
    if missing:
        sys.exit(f"В tools/.env не заполнено: {', '.join(missing)}")

def build_nodes():
    """Ноды для workflow."""
    return [
        # 1. Расписание: каждый день в 09:00 UTC
        {
            "parameters": {
                "rule": {
                    "interval": [{"field": "hours", "triggerAtHour": [9], "triggerAtMinute": 0}]
                }
            },
            "id": "sched_daily",
            "name": "Every day 09:00 UTC",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [200, 400],
        },

        # 2. HTTP POST: вызываем n8n_bridge (который запускает Python скрипт)
        {
            "parameters": {
                "method": "POST",
                "url": "http://127.0.0.1:5051/v1/tools/abandoned-alerts",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "httpHeaderAuth",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Authorization", "value": "Bearer {{$env.N8N_BRIDGE_TOKEN}}"}
                    ]
                },
                "queryParameters": {
                    "parameters": [
                        {"name": "hours", "value": "24"}
                    ]
                },
            },
            "id": "http_alerts",
            "name": "Call n8n_bridge: abandoned-alerts",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [500, 400],
        },

        # 3. Code: форматируем результат для Telegram
        {
            "parameters": {
                "jsCode": """
const data = $json;
const stats = data.stats || {};
const purchases = data.abandoned_purchases || [];
const consultations = data.overdue_consultations || [];

const sent = stats.sent || 0;
const skipped = stats.skipped || 0;
const errors = stats.errors || 0;

const text =
  `📊 <b>Алерты о брошенных корзинах</b>\\n\\n` +
  `Проверено покупок: ${stats.purchases_checked || 0}\\n` +
  `Проверено консультаций: ${stats.consultations_checked || 0}\\n\\n` +
  `<b>Результаты:</b>\\n` +
  `✅ Отправлено: ${sent}\\n` +
  `⏭️  Пропущено (нет Telegram): ${skipped}\\n` +
  `❌ Ошибок: ${errors}\\n\\n` +
  (purchases.length > 0 ? `<b>Брошенные покупки:</b> ${purchases.length}\\n` : '') +
  (consultations.length > 0 ? `<b>Просроченные консультации:</b> ${consultations.length}\\n` : '') +
  `\\n🕐 Время: ${new Date().toISOString()}`;

return [{json: {text}}];
"""
            },
            "id": "format_msg",
            "name": "Format message",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [750, 400],
        },

        # 4. Telegram: отправляем итоги администратору
        {
            "parameters": {
                "chatId": CHAT_ID,
                "text": "={{ $json.text }}",
                "additionalFields": {"parse_mode": "HTML"},
            },
            "id": "tg_report",
            "name": "Telegram: report to admin",
            "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2,
            "position": [1000, 400],
            "credentials": {"telegramApi": {"id": TELEGRAM_CRED, "name": "Telegram account"}},
        },
    ]

def build_connections():
    """Соединения между нодами."""
    return {
        "Every day 09:00 UTC": {
            "main": [[{"node": "Call abandoned_cart_alerts.py", "type": "main", "index": 0}]]
        },
        "Call abandoned_cart_alerts.py": {
            "main": [[{"node": "Format message", "type": "main", "index": 0}]]
        },
        "Format message": {
            "main": [[{"node": "Telegram: report to admin", "type": "main", "index": 0}]]
        },
    }

def payload():
    return {
        "name": WF_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {"executionOrder": "v1"}
    }

def find_existing():
    """Найти существующий workflow по имени."""
    r = requests.get(f"{N8N}/api/v1/workflows", headers=H, timeout=15)
    r.raise_for_status()
    for w in r.json().get("data", []):
        if w.get("name") == WF_NAME:
            return w["id"]
    return None

def main():
    _require()
    body = payload()
    wid = find_existing()

    if wid:
        r = requests.put(f"{N8N}/api/v1/workflows/{wid}", headers=H,
                         data=json.dumps(body), timeout=20)
        action = "обновлён"
    else:
        r = requests.post(f"{N8N}/api/v1/workflows", headers=H,
                          data=json.dumps(body), timeout=20)
        action = "создан"

    if r.status_code not in (200, 201):
        sys.exit(f"Ошибка n8n API {r.status_code}: {r.text[:600]}")

    data = r.json()
    wid = data.get("id", wid)

    print(f"✓ Workflow {action}: {WF_NAME}")
    print(f"  ID: {wid}")
    print(f"  Расписание: ежедневно в 09:00 UTC")
    print(f"\n📋 Следующие шаги:")
    print(f"  1. Открой n8n UI → {N8N}")
    print(f"  2. Найди workflow '{WF_NAME}'")
    print(f"  3. Нажми 'Execute Workflow' для проверки (должен вызвать Python скрипт)")
    print(f"  4. Нажми 'Activate' для запуска по расписанию")
    print(f"\n⚠️  ВАЖНО: Python скрипт должен быть доступен как webhook.")
    print(f"  Вариант 1 (простой): Запусти в отдельном терминале:")
    print(f"     python -m flask --app abandoned_cart_alerts:app run --port 5000")
    print(f"  Вариант 2 (интегрированный): Добавь wrapper в mila-office/n8n_bridge.py")

    return wid

if __name__ == "__main__":
    main()
