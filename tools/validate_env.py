#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_env.py — стартовый предохранитель: проверяет tools/.env ДО запуска системы.

Без этой проверки агент стартует с битым/пустым токеном и сыплет ошибки, которые
выглядят как баги кода, а не как проблема конфигурации. Скрипт ловит это заранее
и говорит человеческим языком, что именно не так.

Проверяет (наличие + базовая форма, без обращений к сети):
  • ANTHROPIC_KEY / GEMINI_KEY — есть хотя бы один LLM-провайдер
  • TELEGRAM_API — формат «<digits>:<token>»
  • IG_ACCESS_TOKEN — формат IGAA… (instagram_login) или EAA… (facebook)
  • SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY — для записи (лиды/продажи/kpi)
  • N8N_BRIDGE_TOKEN — мост без него не стартует
  • типичные порчи: пробелы/кавычки/склейка URL в значениях, дубли ключей

Запуск:
    python validate_env.py            # отчёт; код выхода 0 (ок) / 1 (есть ошибки)
    python validate_env.py --strict   # код 1 также при предупреждениях
Вызывается в mila-boot.ps1 перед стартом сервисов.
"""
import os
import sys
import re
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ENV = Path(__file__).resolve().parent / ".env"

OK, WARN, ERR = "✓", "⚠", "✗"


def _parse_env(path):
    """Читает .env вручную (не через dotenv), чтобы поймать дубли и сырые значения."""
    pairs, dupes, raw = {}, [], []
    if not path.exists():
        return pairs, dupes, raw, False
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k in pairs:
            dupes.append(k)
        pairs[k] = v.strip()
        raw.append((k, v))
    return pairs, dupes, raw, True


def validate():
    env, dupes, raw, exists = _parse_env(ENV)
    problems, warnings = [], []

    if not exists:
        return [f"{ERR} Файл не найден: {ENV}"], []

    def get(*names):
        for n in names:
            if env.get(n):
                return env[n], n
        return "", names[0]

    # 1. LLM-провайдер (хотя бы один)
    claude, _ = get("ANTHROPIC_API_KEY", "ANTHROPIC_KEY")
    gemini, _ = get("GEMINI_KEY", "GOOGLE_API_KEY")
    if not claude and not gemini:
        problems.append(f"{ERR} Нет LLM-ключа: задай ANTHROPIC_KEY или GEMINI_KEY")
    else:
        if claude and not claude.startswith("sk-ant-"):
            warnings.append(f"{WARN} ANTHROPIC ключ не похож на формат sk-ant-…")

    # 2. Telegram
    tg, tgname = get("TELEGRAM_API", "TELEGRAM_BOT_TOKEN")
    if not tg:
        warnings.append(f"{WARN} TELEGRAM_API не задан — поток ХОЧУ и алерты не работают")
    elif not re.match(r"^\d+:[\w-]{30,}$", tg):
        problems.append(f"{ERR} {tgname} битый: ожидается «<id>:<token>»")

    # 3. Instagram токен
    ig, _ = get("IG_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN")
    flow = (env.get("IG_API_FLOW") or "facebook").lower()
    if not ig:
        warnings.append(f"{WARN} IG_ACCESS_TOKEN не задан — Instagram-аналитика/постинг не работают")
    elif flow == "instagram_login" and not ig.startswith("IGAA"):
        warnings.append(f"{WARN} IG_API_FLOW=instagram_login, но токен не IGAA… — проверь")
    elif flow == "facebook" and not ig.startswith("EAA"):
        warnings.append(f"{WARN} IG_API_FLOW=facebook, но токен не EAA… — проверь")

    # 4. Supabase (запись)
    surl, _ = get("SUPABASE_URL")
    skey, _ = get("SUPABASE_SERVICE_ROLE_KEY")
    if not surl:
        warnings.append(f"{WARN} SUPABASE_URL не задан — БД недоступна")
    elif not surl.startswith("https://"):
        problems.append(f"{ERR} SUPABASE_URL должен начинаться с https://")
    if surl and not skey:
        warnings.append(f"{WARN} Нет SUPABASE_SERVICE_ROLE_KEY — запись лидов/продаж/KPI заблокирована RLS")

    # 5. n8n bridge token
    if not env.get("N8N_BRIDGE_TOKEN"):
        warnings.append(f"{WARN} N8N_BRIDGE_TOKEN не задан — мост n8n не стартует")

    # 6. типичные порчи значений
    for k, v in raw:
        val = v.strip()
        if val != v:
            warnings.append(f"{WARN} {k}: пробелы по краям значения")
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            warnings.append(f"{WARN} {k}: значение в кавычках (dotenv возьмёт их буквально)")
        if "http" in val and not k.endswith("URL") and "URL" not in k and k not in ("ANTHROPIC_BASE_URL",):
            # склейка URL в секрет (как было с META_APP_SECRET) — частая порча
            if re.search(r"\w(https?://)", val):
                problems.append(f"{ERR} {k}: к значению приклеен URL ({val[:20]}…) — почини")
    for d in sorted(set(dupes)):
        warnings.append(f"{WARN} Дубль ключа в .env: {d} (победит последний)")

    return problems, warnings


def main():
    p = argparse.ArgumentParser(description="Валидация tools/.env при старте")
    p.add_argument("--strict", action="store_true", help="ненулевой код выхода и при предупреждениях")
    args = p.parse_args()

    problems, warnings = validate()
    if not problems and not warnings:
        print(f"{OK} .env в порядке — критичных проблем нет.")
        sys.exit(0)
    for w in warnings:
        print(w)
    for e in problems:
        print(e)
    print()
    if problems:
        print(f"{ERR} Итог: {len(problems)} ошибк(и), {len(warnings)} предупреждений. Почини ошибки перед запуском.")
        sys.exit(1)
    print(f"{OK} Критичных ошибок нет ({len(warnings)} предупреждений).")
    sys.exit(1 if args.strict else 0)


if __name__ == "__main__":
    main()
