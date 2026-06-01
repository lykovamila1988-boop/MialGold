#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_calcom_workflow.py — создаёт (или обновляет) в локальном n8n workflow
«Cal.com booking → Supabase + Telegram» через n8n REST API.

Поток:
  Webhook (Cal.com BOOKING_CREATED шлёт сюда POST)
    → Code: вытащить из payload имя/email/время/тип
    → Supabase upsert в users (по email)
    → Supabase insert в consultations (статус scheduled)
    → Telegram: пинг Людмиле о новой записи

Идемпотентно: если workflow с тем же именем уже есть — обновляет его (PUT),
а не плодит дубликаты. Креды берёт по ID из tools/.env (уже настроены в n8n).

Запуск:  cd tools && python n8n_calcom_workflow.py
После: в n8n UI открой workflow → Activate → скопируй Production URL вебхука
       → вставь в Cal.com webhook (событие BOOKING_CREATED).
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
SUPABASE_CRED = (os.getenv("N8N_SUPABASE_API_ID") or "").strip()
TELEGRAM_CRED = (os.getenv("N8N_TG_API_ID") or "").strip()
CHAT_ID = (os.getenv("TELEGRAM_ADMIN_CHAT_ID") or "").strip()

WF_NAME = "Cal.com booking → Supabase + Telegram"
WEBHOOK_PATH = "calcom-booking"

H = {"X-N8N-API-KEY": API_KEY, "accept": "application/json",
     "Content-Type": "application/json"}


def _require():
    missing = [n for n, v in [
        ("N8N_API_KEY", API_KEY), ("N8N_SUPABASE_API_ID", SUPABASE_CRED),
        ("N8N_TG_API_ID", TELEGRAM_CRED), ("TELEGRAM_ADMIN_CHAT_ID", CHAT_ID),
    ] if not v]
    if missing:
        sys.exit(f"В tools/.env не заполнено: {', '.join(missing)}")


# Code-нода: Cal.com BOOKING_CREATED payload → плоские поля.
# Cal.com шлёт {triggerEvent, payload:{...}}; гость в payload.attendees[0]
# или payload.responses. Берём максимально терпимо к форме.
PARSE_CODE = r"""
const body = $input.first().json.body || $input.first().json;
const p = body.payload || body;
const att = (p.attendees && p.attendees[0]) || {};
const resp = p.responses || {};
const name = att.name || (resp.name && resp.name.value) || p.name || 'Гость';
const email = att.email || (resp.email && resp.email.value) || p.email || '';
const start = p.startTime || p.start || '';
const title = p.title || p.eventType?.title || p.type || 'Консультация';
const tz = att.timeZone || p.organizer?.timeZone || '';
return [{ json: { name, email, start, title, tz,
  raw_type: body.triggerEvent || 'BOOKING_CREATED' } }];
"""

TG_TEXT = ("=📅 *Новая запись через Cal.com*\\n"
           "👤 {{ $json.name }}\\n"
           "✉️ {{ $json.email }}\\n"
           "🗓 {{ $json.start }}\\n"
           "💬 {{ $json.title }}")


def build_nodes():
    return [
        {
            "parameters": {
                "httpMethod": "POST", "path": WEBHOOK_PATH,
                "responseMode": "onReceived", "options": {},
            },
            "id": "webhook1", "name": "Cal.com Webhook",
            "type": "n8n-nodes-base.webhook", "typeVersion": 2,
            "position": [240, 300], "webhookId": WEBHOOK_PATH,
        },
        {
            "parameters": {"jsCode": PARSE_CODE},
            "id": "code1", "name": "Parse guest",
            "type": "n8n-nodes-base.code", "typeVersion": 2,
            "position": [460, 300],
        },
        {
            "parameters": {
                "resource": "row", "operation": "create", "tableId": "users",
                "dataToSend": "defineBelow",
                "fieldsUi": {"fieldValues": [
                    {"fieldId": "email", "fieldValue": "={{ $json.email }}"},
                    {"fieldId": "name", "fieldValue": "={{ $json.name }}"},
                ]},
            },
            "id": "supa_users", "name": "Supabase: user",
            "type": "n8n-nodes-base.supabase", "typeVersion": 1,
            "position": [680, 200],
            "credentials": {"supabaseApi": {"id": SUPABASE_CRED, "name": "Supabase account"}},
            "onError": "continueRegularOutput",
        },
        {
            "parameters": {
                "resource": "row", "operation": "create", "tableId": "consultations",
                "dataToSend": "defineBelow",
                "fieldsUi": {"fieldValues": [
                    {"fieldId": "type", "fieldValue": "diagnostic"},
                    {"fieldId": "status", "fieldValue": "scheduled"},
                    {"fieldId": "scheduled_at", "fieldValue": "={{ $('Parse guest').item.json.start }}"},
                ]},
            },
            "id": "supa_cons", "name": "Supabase: consultation",
            "type": "n8n-nodes-base.supabase", "typeVersion": 1,
            "position": [900, 300],
            "credentials": {"supabaseApi": {"id": SUPABASE_CRED, "name": "Supabase account"}},
            "onError": "continueRegularOutput",
        },
        {
            "parameters": {
                "chatId": CHAT_ID,
                "text": "={{ '📅 Новая запись через Cal.com\\n👤 ' + $('Parse guest').item.json.name"
                        " + '\\n✉️ ' + $('Parse guest').item.json.email"
                        " + '\\n🗓 ' + $('Parse guest').item.json.start"
                        " + '\\n💬 ' + $('Parse guest').item.json.title }}",
                # parse_mode=HTML: иначе n8n шлёт Markdown и падает на '_' в email/тексте
                # ("can't parse entities"). В HTML подчёркивания безопасны.
                "additionalFields": {"parse_mode": "HTML"},
            },
            "id": "tg1", "name": "Telegram: ping",
            "type": "n8n-nodes-base.telegram", "typeVersion": 1,
            "position": [1120, 300],
            "credentials": {"telegramApi": {"id": TELEGRAM_CRED, "name": "Telegram account"}},
        },
    ]


def build_connections():
    return {
        "Cal.com Webhook": {"main": [[{"node": "Parse guest", "type": "main", "index": 0}]]},
        "Parse guest": {"main": [[
            {"node": "Supabase: user", "type": "main", "index": 0},
            {"node": "Supabase: consultation", "type": "main", "index": 0},
        ]]},
        "Supabase: consultation": {"main": [[{"node": "Telegram: ping", "type": "main", "index": 0}]]},
    }


def payload():
    return {
        "name": WF_NAME,
        "nodes": build_nodes(),
        "connections": build_connections(),
        "settings": {"executionOrder": "v1"},
    }


def find_existing():
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
        sys.exit(f"Ошибка n8n API {r.status_code}: {r.text[:500]}")
    data = r.json()
    wid = data.get("id", wid)
    print(f"✓ Workflow {action}: {WF_NAME}")
    print(f"  id: {wid}")
    print(f"  Test webhook URL:       {N8N}/webhook-test/{WEBHOOK_PATH}")
    print(f"  Production webhook URL:  {N8N}/webhook/{WEBHOOK_PATH}")
    print("  Дальше: открой workflow в n8n UI → Activate → вставь Production URL")
    print("          в Cal.com → Settings → Webhooks (событие BOOKING_CREATED).")


if __name__ == "__main__":
    main()
