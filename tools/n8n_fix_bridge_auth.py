#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
n8n_fix_bridge_auth.py — переключает HTTP Request ноды, которые зовут локальный
мост (127.0.0.1:5051), на httpHeaderAuth-кредентал с Bearer-токеном моста.

Зачем: мост теперь требует Authorization: Bearer <N8N_BRIDGE_TOKEN> (раньше auth
был опционален). Воркфлоу же стучались в мост с nodeCredentialType=supabaseApi —
теперь это 401. Скрипт находит ноды с url *:5051/* и проставляет им
authentication=predefinedCredentialType + nodeCredentialType=httpHeaderAuth +
credentials.httpHeaderAuth={id,name}. Идемпотентно.

Кредентал «MILA bridge bearer» (httpHeaderAuth, Authorization: Bearer <token>)
нужно создать заранее (см. README ниже) и передать его id через --cred-id или
переменную N8N_BRIDGE_CRED_ID.

Запуск:
    cd tools
    python n8n_fix_bridge_auth.py --cred-id <ID>        # применить
    python n8n_fix_bridge_auth.py --cred-id <ID> --dry  # только показать, что изменится
"""
import os
import sys
import json
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

N8N = os.getenv("N8N_BASE_URL", "http://127.0.0.1:5678").rstrip("/")
API_KEY = (os.getenv("N8N_API_KEY") or "").strip()
CRED_NAME = "MILA bridge bearer"
H = {"X-N8N-API-KEY": API_KEY, "accept": "application/json",
     "Content-Type": "application/json"}


def _is_bridge_node(node: dict) -> bool:
    if "httpRequest" not in node.get("type", ""):
        return False
    url = str(node.get("parameters", {}).get("url", ""))
    return ":5051/" in url or url.endswith(":5051")


def _patch_node(node: dict, cred_id: str) -> bool:
    """Проставляет httpHeaderAuth ноде. True если что-то изменилось."""
    p = node.setdefault("parameters", {})
    changed = False
    if p.get("authentication") != "predefinedCredentialType":
        p["authentication"] = "predefinedCredentialType"; changed = True
    if p.get("nodeCredentialType") != "httpHeaderAuth":
        p["nodeCredentialType"] = "httpHeaderAuth"; changed = True
    creds = node.setdefault("credentials", {})
    want = {"id": cred_id, "name": CRED_NAME}
    if creds.get("httpHeaderAuth") != want:
        creds["httpHeaderAuth"] = want; changed = True
    # убираем чужой supabaseApi, если он остался на этой ноде
    if "supabaseApi" in creds:
        del creds["supabaseApi"]; changed = True
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cred-id", default=os.getenv("N8N_BRIDGE_CRED_ID", ""),
                    help="id httpHeaderAuth-кредентала с Bearer-токеном моста")
    ap.add_argument("--dry", action="store_true", help="только показать план")
    args = ap.parse_args()
    if not API_KEY:
        sys.exit("Нет N8N_API_KEY в tools/.env")
    if not args.cred_id:
        sys.exit("Нужен --cred-id (id кредентала 'MILA bridge bearer').")

    r = requests.get(f"{N8N}/api/v1/workflows", headers=H, timeout=20)
    r.raise_for_status()
    workflows = r.json().get("data", [])

    touched = []
    for w in workflows:
        wid = w["id"]
        full = requests.get(f"{N8N}/api/v1/workflows/{wid}", headers=H, timeout=20).json()
        nodes = full.get("nodes", [])
        bridge_nodes = [n for n in nodes if _is_bridge_node(n)]
        if not bridge_nodes:
            continue
        changed_any = False
        for n in bridge_nodes:
            if _patch_node(n, args.cred_id):
                changed_any = True
        if not changed_any:
            print(f"= {w['name']}: уже настроено")
            continue
        if args.dry:
            print(f"~ {w['name']}: обновил бы {len(bridge_nodes)} нод(ы)")
            touched.append(wid)
            continue
        # PUT обратно только разрешённые поля. settings: API принимает строго
        # ограниченный набор — пробрасываем только executionOrder (binaryMode и
        # прочее n8n кладёт сам, но PUT-схема их отвергает как "additional").
        src_settings = full.get("settings", {}) or {}
        body = {"name": full["name"], "nodes": nodes,
                "connections": full.get("connections", {}),
                "settings": {"executionOrder": src_settings.get("executionOrder", "v1")}}
        pr = requests.put(f"{N8N}/api/v1/workflows/{wid}", headers=H,
                          data=json.dumps(body), timeout=25)
        ok = pr.status_code in (200, 201)
        print(f"{'✓' if ok else '✗'} {w['name']}: {len(bridge_nodes)} нод(ы) "
              f"→ httpHeaderAuth (HTTP {pr.status_code})")
        if ok:
            touched.append(wid)
    print(f"\nИтог: {'(dry) ' if args.dry else ''}затронуто воркфлоу: {len(touched)}")


if __name__ == "__main__":
    main()
