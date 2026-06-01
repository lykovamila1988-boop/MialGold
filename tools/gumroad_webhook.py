#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gumroad_webhook.py — приём и АУТЕНТИФИКАЦИЯ вебхука продажи Gumroad.

Проблема: на endpoint продажи может постучаться кто угодно и создать фиктивную
продажу. Защита здесь — двойная:
  1. Общий секрет (GUMROAD_WEBHOOK_SECRET) — передаётся в URL вебхука как ?secret=…
     или в payload поле 'secret'. Сравнение constant-time (hmac.compare_digest).
     Gumroad по умолчанию НЕ шлёт HMAC-подпись, поэтому секрет в URL — рабочий способ
     (URL знают только ты и Gumroad). Если включишь подпись/свой прокси с HMAC —
     задай GUMROAD_HMAC_SECRET, и проверим X-Gumroad-Signature (sha256).
  2. seller_id: если задан GUMROAD_SELLER_ID, проверяем, что продажа от твоего аккаунта.

При успехе — записывает продажу в Supabase: upsert покупателя в users + строка в
purchases (через service-role, обходя RLS). Идемпотентно по sale_id (не двоит).

Использование (через n8n_bridge /v1/gumroad/sale, payload = тело вебхука Gumroad):
    python gumroad_webhook.py --file payload.json
    python gumroad_webhook.py --file payload.json --signature <hex>   # если есть HMAC
Печатает JSON-результат. Коды: ok=false + reason=unauthorized → 401-эквивалент.
"""
import os
import sys
import json
import hmac
import hashlib
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

TOOLS = Path(__file__).resolve().parent
load_dotenv(TOOLS / ".env")

SHARED_SECRET = (os.getenv("GUMROAD_WEBHOOK_SECRET") or "").strip()
HMAC_SECRET = (os.getenv("GUMROAD_HMAC_SECRET") or "").strip()
SELLER_ID = (os.getenv("GUMROAD_SELLER_ID") or "").strip()


def _fail(reason, code="unauthorized"):
    print(json.dumps({"ok": False, "reason": reason, "code": code}, ensure_ascii=False))
    sys.exit(1)


def verify(payload: dict, raw_body: bytes = b"", signature: str = "") -> None:
    """Аутентифицирует вебхук. Бросает через _fail при провале."""
    # 1. HMAC-подпись (если настроена) — самый строгий путь.
    if HMAC_SECRET:
        if not signature:
            _fail("HMAC настроен, но подпись не передана")
        expected = hmac.new(HMAC_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.strip().lower()):
            _fail("неverная HMAC-подпись")
    # 2. Общий секрет (основной способ для Gumroad без подписи).
    elif SHARED_SECRET:
        got = str(payload.get("secret") or payload.get("_secret") or "").strip()
        if not hmac.compare_digest(SHARED_SECRET, got):
            _fail("неверный или отсутствует secret")
    else:
        _fail("вебхук не защищён: задай GUMROAD_WEBHOOK_SECRET (или GUMROAD_HMAC_SECRET) в .env",
              code="not_configured")
    # 3. seller_id (опционально, доп. слой).
    if SELLER_ID:
        seller = str(payload.get("seller_id") or "").strip()
        if seller and seller != SELLER_ID:
            _fail(f"чужой seller_id ({seller})")


def record_sale(payload: dict) -> dict:
    """Пишет продажу в Supabase: upsert user + insert purchase (идемпотентно по sale_id)."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    import supa
    if not supa.can_write():
        return {"ok": False, "reason": "нет SUPABASE_SERVICE_ROLE_KEY — запись запрещена RLS"}

    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("full_name") or payload.get("purchaser_name") or "").strip()
    sale_id = str(payload.get("sale_id") or payload.get("order_number") or "").strip()
    product = (payload.get("product_name") or payload.get("product_permalink") or "").strip()
    price = payload.get("price")  # центы у Gumroad
    try:
        amount = round(float(price) / 100, 2) if price is not None else None
    except (ValueError, TypeError):
        amount = None

    if not email and not sale_id:
        return {"ok": False, "reason": "нет email/sale_id в payload"}

    # идемпотентность: если такая продажа уже есть — не дублируем
    if sale_id:
        existing = supa.select("purchases", columns="id",
                               filters={"payment_id": f"eq.{sale_id}"}, limit=1)
        if existing:
            return {"ok": True, "duplicate": True, "purchase_id": existing[0]["id"]}

    # upsert покупателя (email уникален; если нет email — синтезируем как у лида)
    if not email:
        email = f"gumroad-{sale_id}@placeholder.mila"
    user = supa.upsert("users", {"email": email, "name": name or None}, on_conflict="email")
    user_id = user[0]["id"] if user else None

    row = supa.insert("purchases", {
        "user_id": user_id, "amount_cad": amount or 0, "currency": "CAD",
        "payment_method": "gumroad", "payment_id": sale_id or None,
        "status": "completed", "source": "gumroad_webhook",
        "notes": product or None,
    })
    return {"ok": True, "purchase_id": (row[0]["id"] if row else None),
            "user_id": user_id, "amount_cad": amount}


def main():
    p = argparse.ArgumentParser(description="Приём вебхука продажи Gumroad (с аутентификацией)")
    p.add_argument("--file", help="JSON-файл с телом вебхука")
    p.add_argument("--signature", default="", help="HMAC-подпись (если включена)")
    args = p.parse_args()

    if args.file:
        raw = Path(args.file).read_bytes()
    else:
        raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except ValueError:
        _fail("payload не JSON", code="bad_request")

    verify(payload, raw_body=raw, signature=args.signature)  # 401 при провале
    result = record_sale(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
