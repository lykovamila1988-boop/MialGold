#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_n8n_workflows.py — импортирует n8n/workflows/*.json в локальный n8n через public API.

n8n public API (POST /api/v1/workflows) принимает только name, nodes, connections,
settings — поля active / id / meta / tags / pinData отвергаются с 400. Скрипт их
вырезает. Идемпотентно: workflow с уже существующим именем пропускается (не дублируем).
Все импортируются НЕАКТИВНЫМИ (n8n создаёт workflow выключенным; активируем вручную).

Ключ берётся из tools/.env → N8N_API_KEY. База — http://localhost:5678.

Запуск:  python import_n8n_workflows.py [--force]
  --force  пересоздать (удалить одноимённый и создать заново)
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

ROOT = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
load_dotenv(ROOT / "tools" / ".env")
load_dotenv(ROOT / ".env")

BASE = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")
KEY = os.getenv("N8N_API_KEY", "").strip()
WF_DIR = ROOT / "n8n" / "workflows"
ALLOWED = ("name", "nodes", "connections", "settings")  # что принимает API на создание


def _headers():
    return {"X-N8N-API-KEY": KEY, "Content-Type": "application/json"}


def list_existing():
    """{name: id} существующих workflow."""
    r = requests.get(f"{BASE}/api/v1/workflows", headers=_headers(), timeout=20)
    r.raise_for_status()
    return {w["name"]: w["id"] for w in r.json().get("data", [])}


def clean(wf: dict) -> dict:
    out = {k: wf[k] for k in ALLOWED if k in wf}
    out.setdefault("settings", {"executionOrder": "v1"})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="пересоздать одноимённые")
    args = p.parse_args()
    if not KEY:
        sys.exit("Нет N8N_API_KEY в .env")
    if not WF_DIR.exists():
        sys.exit(f"Нет папки {WF_DIR}")

    try:
        existing = list_existing()
    except Exception as e:
        sys.exit(f"n8n API недоступен ({BASE}): {e}")
    print(f"n8n: уже есть {len(existing)} workflow")

    created = skipped = failed = 0
    for f in sorted(WF_DIR.glob("*.json")):
        wf = json.loads(f.read_text(encoding="utf-8"))
        name = wf.get("name", f.stem)
        if name in existing:
            if args.force:
                requests.delete(f"{BASE}/api/v1/workflows/{existing[name]}",
                                headers=_headers(), timeout=20)
                print(f"  ↻ удалил старый «{name}»")
            else:
                print(f"  = пропуск «{name}» (уже есть)")
                skipped += 1
                continue
        payload = clean(wf)
        r = requests.post(f"{BASE}/api/v1/workflows", headers=_headers(),
                          json=payload, timeout=20)
        if r.status_code in (200, 201):
            print(f"  ✓ создан «{name}» (id {r.json().get('id')}) — НЕАКТИВЕН")
            created += 1
        else:
            print(f"  ✗ «{name}» → {r.status_code}: {r.text[:200]}")
            failed += 1
    print(f"\nИтог: создано {created}, пропущено {skipped}, ошибок {failed}")


if __name__ == "__main__":
    main()
