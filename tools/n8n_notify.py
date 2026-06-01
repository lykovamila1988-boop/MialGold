#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отправка уведомления в Telegram админу (для n8n webhook office-done)."""
import sys
import json
import os
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")  # tools/.env

TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API") or "").strip()
CHAT = (os.getenv("TELEGRAM_ADMIN_CHAT_ID") or os.getenv("TELEGRAM_ALERT_CHAT_ID") or "").strip()


def main():
    if "--file" in sys.argv:
        i = sys.argv.index("--file")
        path = Path(sys.argv[i + 1])
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        payload = json.loads(sys.argv[1])
    else:
        payload = json.load(sys.stdin)

    chain = payload.get("chain", "?")
    summary = payload.get("summary", "")
    text = f"✅ MILA Office: {chain}\n\n{summary}"[:4000]

    if not TOKEN or not CHAT:
        print(json.dumps({"ok": False, "error": "No TELEGRAM token/chat in tools/.env"},
                         ensure_ascii=False))
        sys.exit(1)

    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT, "text": text},
        timeout=20,
    )
    ok = r.json().get("ok", False)
    print(json.dumps({"ok": ok, "telegram_status": r.status_code}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
