#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_poller.py — поток «ХОЧУ» на polling (вебхук на localhost невозможен).

Слушает бота @LiudmilaLykovabot через getUpdates. На каждое входящее сообщение:
  • если текст содержит триггер-слово (ХОЧУ, цена, практикум…) →
      1) lead_capture: upsert клиента в Supabase (users + telegram_leads, статус hot)
      2) уведомляет Людмилу (TELEGRAM_ADMIN_CHAT_ID) карточкой лида + черновиком ответа
  • иначе просто логирует (можно расширить).

Запуск:  cd tools ; python telegram_poller.py
Остановка: Ctrl+C. Долгоживущий процесс — держать в своём окне.

⚠️ Пока поллер работает, getUpdates занят им (как раньше ManyChat). Вернуть
ManyChat = остановить поллер и setWebhook (см. manychat_webhook_backup.txt).

ВАЖНО: уведомления идут ТОЛЬКО админу (Людмиле). Клиенту бот сам НЕ отвечает —
Людмила одобряет/правит черновик вручную (принцип «человек одобряет»).
"""
import os
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from dotenv import load_dotenv

TOOLS = Path(__file__).resolve().parent
load_dotenv(TOOLS / ".env")

TOKEN = os.getenv("TELEGRAM_API", "").strip()
ADMIN = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
TRIGGERS = ["хочу", "цена", "сколько", "заказ", "практикум", "записаться", "хочу практикум"]

OFFSET_FILE = TOOLS.parent / "reports" / "tg_offset.txt"


def _load_offset() -> int:
    try:
        return int(OFFSET_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _save_offset(v: int):
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(v), encoding="utf-8")


def send(chat_id, text):
    """Шлёт сообщение. UTF-8 через data-binary не нужен — requests кодирует сам."""
    try:
        r = requests.post(f"{API}/sendMessage",
                          json={"chat_id": chat_id, "text": text},
                          timeout=20)
        return r.json().get("ok", False)
    except requests.RequestException as e:
        print(f"[send ERR] {e}", file=sys.stderr)
        return False


def capture_lead(msg):
    """Вызывает lead_capture.py для записи лида в Supabase. Возвращает dict-результат."""
    chat = msg.get("chat", {})
    frm = msg.get("from", {})
    name = " ".join(x for x in [frm.get("first_name"), frm.get("last_name")] if x) or "—"
    args = [
        sys.executable, str(TOOLS / "lead_capture.py"),
        "--name", name,
        "--telegram", ("@" + frm["username"]) if frm.get("username") else name,
        "--tg-user-id", str(frm.get("id", "")),
        "--source", "telegram",
        "--message", msg.get("text", ""),
    ]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60,
                             encoding="utf-8")
        return json.loads(out.stdout.strip().splitlines()[-1]) if out.stdout.strip() else {"ok": False, "error": out.stderr[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def notify_admin(msg, lead):
    """Карточка лида + черновик ответа — только Людмиле, не клиенту."""
    frm = msg.get("from", {})
    who = ("@" + frm["username"]) if frm.get("username") else (frm.get("first_name") or "клиент")
    text = msg.get("text", "")
    draft = ("Здравствуйте! Спасибо, что написали 🤍 Сейчас пришлю детали по практикуму "
             "«Почему я снова выбрала не того». Это PDF, 36 страниц, $37 CAD — заполняете "
             "в своём темпе. Хотите, расскажу подробнее или сразу пришлю ссылку на оплату?")
    card = (
        f"🔥 Новая заявка (ХОЧУ)\n\n"
        f"От: {who}\n"
        f"Сообщение: «{text}»\n"
        f"Статус в CRM: {lead.get('lead_status', '?')}"
        f"{'  ✅ записан' if lead.get('ok') else '  ⚠️ не записан: ' + str(lead.get('error',''))}\n\n"
        f"✍️ Черновик ответа (скопируй/поправь и отправь сама):\n{draft}"
    )
    send(ADMIN, card)


def handle(update, notify=True):
    msg = update.get("message") or update.get("edited_message")
    if not msg or not msg.get("text"):
        return
    text = msg["text"].lower()
    frm = msg.get("from", {})
    print(f"[msg] @{frm.get('username')} ({frm.get('id')}): {msg['text'][:60]}")
    if any(t in text for t in TRIGGERS):
        print("  → триггер ХОЧУ, пишу лид…")
        lead = capture_lead(msg)
        print(f"  → lead: {lead}")
        if not notify:
            print("  [no-notify] лид записан, уведомление Людмиле НЕ отправлено")
        elif ADMIN:
            notify_admin(msg, lead)
            print("  → уведомление отправлено админу")
        else:
            print("  [!] TELEGRAM_ADMIN_CHAT_ID пуст — некому слать уведомление")


def main():
    p = argparse.ArgumentParser(description="Telegram-поллер потока ХОЧУ")
    p.add_argument("--no-notify", action="store_true",
                   help="не слать уведомления Людмиле (только запись лида + лог)")
    p.add_argument("--once", action="store_true",
                   help="один проход getUpdates и выход (для теста)")
    args = p.parse_args()
    if not TOKEN:
        sys.exit("Нет TELEGRAM_API в .env")
    notify = not args.no_notify
    print(f"telegram_poller запущен. Триггеры: {', '.join(TRIGGERS)}")
    print(f"Уведомления Людмиле: {'ВКЛ → ' + (ADMIN or '?') if notify else 'ВЫКЛ (--no-notify)'}")
    print("Ctrl+C для остановки.\n")
    offset = _load_offset()
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                            params={"offset": offset + 1, "timeout": 30}, timeout=40)
            data = r.json()
            if not data.get("ok"):
                print(f"[getUpdates ERR] {data}", file=sys.stderr)
                time.sleep(5)
                continue
            for u in data.get("result", []):
                offset = max(offset, u["update_id"])
                _save_offset(offset)
                try:
                    handle(u, notify=notify)
                except Exception as e:
                    print(f"[handle ERR] {e}", file=sys.stderr)
            if args.once:
                print("[once] один проход выполнен, выход.")
                break
        except requests.RequestException as e:
            print(f"[poll ERR] {e}", file=sys.stderr)
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nОстановлено.")
            break


if __name__ == "__main__":
    main()
