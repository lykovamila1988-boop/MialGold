#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_weekly_kpi_workflow.py — создаёт/обновляет в локальном n8n workflow
«Weekly KPI digest → Gemini → Telegram».

Поток (понедельник 09:00):
  Schedule Trigger
    → Supabase: purchases / consultations / telegram_leads / content (4 чтения)
    → Code: агрегирует сырые строки в KPI-метрики (продажи, доход, лиды, записи)
    → Gemini (chainLlm + lmChatGoogleGemini): пишет тёплую сводку-дайджест Людмиле
    → Telegram: шлёт дайджест в чат Людмилы

Идемпотентно (PUT при совпадении имени). Креды берёт по ID из tools/.env
(googlePalmApi=Gemini, supabaseApi, telegramApi уже настроены в n8n).

Запуск:  cd tools && python n8n_weekly_kpi_workflow.py
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
GEMINI_CRED = (os.getenv("N8N_GEMINI_ID") or "").strip()
CHAT_ID = (os.getenv("TELEGRAM_ADMIN_CHAT_ID") or "").strip()
GEMINI_MODEL = os.getenv("MILA_GEMINI_MODEL", "gemini-2.5-flash")

WF_NAME = "Weekly KPI digest → Gemini → Telegram"
H = {"X-N8N-API-KEY": API_KEY, "accept": "application/json",
     "Content-Type": "application/json"}


def _require():
    missing = [n for n, v in [
        ("N8N_API_KEY", API_KEY), ("N8N_SUPABASE_API_ID", SUPABASE_CRED),
        ("N8N_TG_API_ID", TELEGRAM_CRED), ("N8N_GEMINI_ID", GEMINI_CRED),
        ("TELEGRAM_ADMIN_CHAT_ID", CHAT_ID),
    ] if not v]
    if missing:
        sys.exit(f"В tools/.env не заполнено: {', '.join(missing)}")


# Code-нода: собирает строки из 4-х Supabase-нод в KPI за последние 7 дней.
# Каждая Supabase-нода отдаёт свой набор; берём их по имени через $items().
AGG_CODE = r"""
const now = new Date();
const weekAgo = new Date(now.getTime() - 7*24*3600*1000);
const inWeek = (ts) => { try { return new Date(ts) >= weekAgo; } catch(e){ return false; } };

const get = (name) => { try { return $items(name).map(i => i.json); } catch(e){ return []; } };

const purchases = get('Supabase: purchases');
const consults  = get('Supabase: consultations');
const leads     = get('Supabase: leads');
const content   = get('Supabase: content');

const wkPurch = purchases.filter(p => inWeek(p.created_at));
const revenue = wkPurch.reduce((s,p) => s + (parseFloat(p.amount_cad)||0), 0);
const wkLeads = leads.filter(l => inWeek(l.created_at));
const hotLeads = leads.filter(l => ['warm','hot'].includes(l.status)).length;
const wkConsults = consults.filter(c => inWeek(c.created_at || c.scheduled_at));
const published = content.filter(c => c.status==='published' && inWeek(c.published_at));

const stats = {
  period: weekAgo.toISOString().slice(0,10) + ' — ' + now.toISOString().slice(0,10),
  sales_week: wkPurch.length,
  revenue_week_cad: Math.round(revenue*100)/100,
  sales_total: purchases.length,
  goal_month_cad: 5000,
  leads_new_week: wkLeads.length,
  leads_hot_warm_total: hotLeads,
  consultations_week: wkConsults.length,
  posts_published_week: published.length,
};
return [{ json: stats }];
"""

DIGEST_PROMPT = (
    "Ты — Стас, операционный директор онлайн-практики психолога Людмилы Лыковой. "
    "Ниша: болезненные отношения, тревожная привязанность; женская аудитория. "
    "Воронка: Reels → Telegram → практикум $37 → диагностика → консультация $120 → пакеты $420/$750. "
    "Цель — $5000/мес.\\n\\n"
    "Вот KPI за неделю (JSON):\\n{{ JSON.stringify($json, null, 2) }}\\n\\n"
    "Напиши КОРОТКИЙ еженедельный дайджест для Людмилы (для Telegram, до 1200 символов):\\n"
    "1) Итог недели в 1-2 предложениях (по цифрам, без воды).\\n"
    "2) Что радует / что проседает — с конкретными числами из JSON.\\n"
    "3) 2-3 приоритета на следующую неделю.\\n"
    "Тон тёплый, деловой, по-русски. НЕ выдумывай цифры, которых нет в JSON; "
    "если данных по метрике нет (0) — так и скажи. Без Markdown-разметки (обычный текст)."
)


def build_nodes():
    def supa_read(name, table, x, y):
        return {
            "parameters": {
                "operation": "getAll", "tableId": table,
                "returnAll": True, "filters": {"conditions": []},
            },
            "id": f"supa_{table}", "name": name,
            "type": "n8n-nodes-base.supabase", "typeVersion": 1,
            "position": [x, y],
            "credentials": {"supabaseApi": {"id": SUPABASE_CRED, "name": "Supabase account"}},
            "onError": "continueRegularOutput",
        }

    return [
        {
            "parameters": {"rule": {"interval": [
                {"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 9}]}},
            "id": "sched1", "name": "Every Monday 09:00",
            "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
            "position": [200, 400],
        },
        supa_read("Supabase: purchases", "purchases", 440, 160),
        supa_read("Supabase: consultations", "consultations", 440, 320),
        supa_read("Supabase: leads", "telegram_leads", 440, 480),
        supa_read("Supabase: content", "content", 440, 640),
        {
            "parameters": {"jsCode": AGG_CODE},
            "id": "agg1", "name": "Aggregate KPI",
            "type": "n8n-nodes-base.code", "typeVersion": 2,
            "position": [720, 400],
        },
        {
            "parameters": {
                "modelName": f"models/{GEMINI_MODEL}",
                # gemini-2.5-flash тратит ~1100 токенов на «мышление» ДО ответа —
                # с дефолтным лимитом текст обрезается. 2500 хватает на дайджест.
                "options": {"maxOutputTokens": 2500},
            },
            "id": "gem1", "name": "Gemini model",
            "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini", "typeVersion": 1,
            "position": [940, 600],
            "credentials": {"googlePalmApi": {"id": GEMINI_CRED, "name": "Google Gemini(PaLM) Api account"}},
        },
        {
            "parameters": {
                "promptType": "define", "text": "=" + DIGEST_PROMPT,
            },
            "id": "chain1", "name": "Write digest",
            "type": "@n8n/n8n-nodes-langchain.chainLlm", "typeVersion": 1.4,
            "position": [980, 400],
        },
        {
            "parameters": {
                "chatId": CHAT_ID,
                "text": "={{ $json.text }}",
                "additionalFields": {"parse_mode": "HTML"},
            },
            "id": "tg1", "name": "Telegram: digest",
            "type": "n8n-nodes-base.telegram", "typeVersion": 1.2,
            "position": [1240, 400],
            "credentials": {"telegramApi": {"id": TELEGRAM_CRED, "name": "Telegram account"}},
        },
    ]


def build_connections():
    # 4 Supabase-ноды стартуют от Schedule; их выходы сходятся в Aggregate.
    sched_targets = [
        {"node": "Supabase: purchases", "type": "main", "index": 0},
        {"node": "Supabase: consultations", "type": "main", "index": 0},
        {"node": "Supabase: leads", "type": "main", "index": 0},
        {"node": "Supabase: content", "type": "main", "index": 0},
    ]
    to_agg = [[{"node": "Aggregate KPI", "type": "main", "index": 0}]]
    return {
        "Every Monday 09:00": {"main": [sched_targets]},
        "Supabase: purchases": {"main": to_agg},
        "Supabase: consultations": {"main": to_agg},
        "Supabase: leads": {"main": to_agg},
        "Supabase: content": {"main": to_agg},
        "Aggregate KPI": {"main": [[{"node": "Write digest", "type": "main", "index": 0}]]},
        # Gemini-модель подключается к chain через ai_languageModel (langchain).
        "Gemini model": {"ai_languageModel": [[{"node": "Write digest", "type": "ai_languageModel", "index": 0}]]},
        "Write digest": {"main": [[{"node": "Telegram: digest", "type": "main", "index": 0}]]},
    }


def payload():
    return {"name": WF_NAME, "nodes": build_nodes(),
            "connections": build_connections(),
            "settings": {"executionOrder": "v1"}}


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
        sys.exit(f"Ошибка n8n API {r.status_code}: {r.text[:600]}")
    data = r.json()
    wid = data.get("id", wid)
    print(f"✓ Workflow {action}: {WF_NAME}")
    print(f"  id: {wid}")
    print(f"  Расписание: понедельник 09:00 (триггер Schedule).")
    print(f"  Модель: models/{GEMINI_MODEL}")
    print(f"  Дальше: открой в n8n UI → Execute Workflow (ручной прогон) для проверки,")
    print(f"          затем Activate для еженедельного автозапуска.")
    return wid


if __name__ == "__main__":
    main()
