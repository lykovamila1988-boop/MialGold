#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_reels_workflow.py — создаёт n8n workflow для еженедельного анализа Reels.

Поток (каждый понедельник 09:00 UTC):
  Schedule Trigger
    → HTTP: вызывает reels_recommendations.py
    → Code: форматирует результат для Марины
    → Telegram: отправляет рекомендации Марине

Идемпотентно (PUT при совпадении имени).

Запуск:  cd tools && python n8n_reels_workflow.py
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
MARINA_TG = (os.getenv("TELEGRAM_MARINA_ID") or "").strip()

WF_NAME = "Weekly: Reels analytics → AI recommendations → Марина"
H = {"X-N8N-API-KEY": API_KEY, "accept": "application/json", "Content-Type": "application/json"}

def _require():
    missing = [n for n, v in [
        ("N8N_API_KEY", API_KEY),
        ("N8N_TG_API_ID", TELEGRAM_CRED),
        ("TELEGRAM_MARINA_ID", MARINA_TG),
    ] if not v]
    if missing:
        sys.exit(f"В tools/.env не заполнено: {', '.join(missing)}")

def build_nodes():
    """Ноды для workflow."""
    return [
        # 1. Расписание: каждый понедельник в 09:00 UTC
        {
            "parameters": {
                "rule": {
                    "interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 9}]
                }
            },
            "id": "sched_weekly",
            "name": "Every Monday 09:00 UTC",
            "type": "n8n-nodes-base.scheduleTrigger",
            "typeVersion": 1.2,
            "position": [200, 400],
        },

        # 2. HTTP: вызываем n8n_bridge для запуска Python скрипта
        {
            "parameters": {
                "method": "POST",
                "url": "http://127.0.0.1:5051/v1/tools/reels-recommendations",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Authorization", "value": "Bearer {{$env.N8N_BRIDGE_TOKEN}}"}
                    ]
                },
                "queryParameters": {
                    "parameters": [
                        {"name": "send", "value": "1"}
                    ]
                },
            },
            "id": "http_reels",
            "name": "Call n8n_bridge: reels-recommendations",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.1,
            "position": [500, 400],
        },

        # 3. Code: форматируем результат для красивого отправления
        {
            "parameters": {
                "jsCode": """
const result = $json;
const patterns = result.patterns || {};
const reels = result.top_reels || [];

const emoji = '📊';
const title = '<b>Анализ Reels: рекомендации на неделю</b>';
const stats =
  `\\n<b>Статистика:</b>\\n` +
  `• Реелс: ${patterns.total_reels || 0}\\n` +
  `• Охват (avg): ${patterns.avg_reach || 0}\\n` +
  `• Engagement (avg): ${patterns.avg_engagement || 0}\\n` +
  `• Лучший rate: ${patterns.top_engagement_rate || 0}%`;

const recs = result.recommendations || '';
const recsText = recs.substring(0, 1500) + (recs.length > 1500 ? '...' : '');

const text = emoji + ' ' + title + stats + '\\n\\n' + recsText +
  '\\n\\n📎 Полный отчёт сохранён в папке reels-recommendations';

return [{json: {text}}];
"""
            },
            "id": "format_msg",
            "name": "Format for Telegram",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [750, 400],
        },

        # 4. Telegram: отправляем рекомендации Марине
        {
            "parameters": {
                "chatId": MARINA_TG,
                "text": "={{ $json.text }}",
                "additionalFields": {"parse_mode": "HTML"},
            },
            "id": "tg_marina",
            "name": "Telegram: to Marina",
            "type": "n8n-nodes-base.telegram",
            "typeVersion": 1.2,
            "position": [1000, 400],
            "credentials": {"telegramApi": {"id": TELEGRAM_CRED, "name": "Telegram account"}},
        },
    ]

def build_connections():
    """Соединения между нодами."""
    return {
        "Every Monday 09:00 UTC": {
            "main": [[{"node": "Call n8n_bridge: reels-recommendations", "type": "main", "index": 0}]]
        },
        "Call n8n_bridge: reels-recommendations": {
            "main": [[{"node": "Format for Telegram", "type": "main", "index": 0}]]
        },
        "Format for Telegram": {
            "main": [[{"node": "Telegram: to Marina", "type": "main", "index": 0}]]
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
    print(f"  Расписание: каждый понедельник в 09:00 UTC")
    print(f"\n📋 Следующие шаги:")
    print(f"  1. Открой n8n UI → {N8N}")
    print(f"  2. Найди workflow '{WF_NAME}'")
    print(f"  3. Нажми 'Execute Workflow' для проверки")
    print(f"  4. Нажми 'Activate' для еженедельного запуска")
    print(f"\n⚠️  ТРЕБУЕТ: ANTHROPIC_API_KEY в tools/.env для Claude анализа")

    return wid

if __name__ == "__main__":
    main()
