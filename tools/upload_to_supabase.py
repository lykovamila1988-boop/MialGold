#!/usr/bin/env python3
"""
upload_to_supabase.py — заливает данные постов в Supabase (таблица ig_posts),
которую читает живой дашборд в Cowork.

Что делает:
  1. Берёт самый свежий reports/posts_*.json (или указанный файл).
  2. Классифицирует тему каждого поста по ключевым словам.
  3. Upsert (вставка/обновление) в таблицу public.ig_posts через Supabase REST API.

Использование:
    python upload_to_supabase.py                 # последний posts_*.json
    python upload_to_supabase.py <path.json>     # конкретный файл

Нужны переменные в .env:
    SUPABASE_URL          (например https://xxxx.supabase.co)
    SUPABASE_SERVICE_KEY  (ключ service_role — это секрет!)

Тему скрипт угадывает по ключевым словам — это черновая разметка.
При желании можно поправить тему вручную в Supabase или сказать Cowork
«поменяй тему у поста …».
"""
import os
import sys
import glob
import json
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Нет 'requests'. Запустите: pip install requests python-dotenv")
try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("Нет 'python-dotenv'. Запустите: pip install requests python-dotenv")

TOOLS_DIR = Path(__file__).resolve().parent
REPORTS_DIR = TOOLS_DIR.parent / "reports"
load_dotenv(TOOLS_DIR / ".env")

# --- Классификатор темы по ключевым словам --------------------------------
# Возвращает один из: rel (отношения), mom (материнство),
# self (любовь к себе/психология), life (лайфстайл).
THEME_RULES = [
    ("mom",  ["мама", "мам ", "материнств", "ребён", "ребен", "дети", "детьм",
              "первенц", "роди", "день матери"]),
    ("rel",  ["отношени", "мужчин", "муж ", "партнёр", "партнер", "пара ",
              "в паре", "развод", "брак", "любим", "свидан", "premium",
              "премиум", "меркантильн", "他", "женщина и мужчина"]),
    ("life", ["спорт", "калори", "трениров", "подруг", "путешеств", "еда",
              "рецепт", "танц", "босиком", "чем занимаетесь", "хобби"]),
    ("self", ["себя", "себе", "выгоран", "самооцен", "границ", "терпел",
              "страх", "тревог", "устал", "отдых", "вина", "психолог",
              "осознан", "цел", "мечт"]),
]

def classify(caption: str) -> str:
    text = (caption or "").lower()
    for theme, words in THEME_RULES:
        if any(w in text for w in words):
            return theme
    return "self"  # нейтральный дефолт


def latest_posts_file() -> Path:
    files = sorted(glob.glob(str(REPORTS_DIR / "posts_*.json")))
    if not files:
        sys.exit(f"Не найдено posts_*.json в {REPORTS_DIR}. "
                 "Сначала запустите: python get_analytics.py posts")
    return Path(files[-1])


def to_row(p: dict) -> dict:
    return {
        "media_id": str(p.get("id")),
        "post_date": p.get("date") or None,
        "media_type": p.get("type"),
        "theme": classify(p.get("caption", "")),
        "reach": p.get("reach") or 0,
        "likes": p.get("likes") or 0,
        "comments": p.get("comments") or 0,
        "caption": (p.get("caption") or "")[:300],
        "permalink": p.get("link"),
    }


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_posts_file()
    if not src.exists():
        sys.exit(f"Файл не найден: {src}")
    posts = json.loads(src.read_text(encoding="utf-8"))
    rows = [to_row(p) for p in posts if p.get("id") and p.get("date")]
    if not rows:
        sys.exit("В файле нет пригодных постов (нужны поля id и date).")

    # Единый клиент БД (резолвит service-role ключ, обходит RLS для записи).
    try:
        import supa
    except Exception as e:
        sys.exit(f"Не найден клиент supa.py: {e}")
    if not supa.can_write():
        sys.exit("Нет service-role ключа для записи: добавь SUPABASE_SERVICE_ROLE_KEY в "
                 "tools/.env (Supabase → Project Settings → API → service_role). С publishable/"
                 "anon ключом RLS запрещает запись в ig_posts (code 42501).")
    try:
        supa.upsert("ig_posts", rows, on_conflict="media_id")
    except supa.SupabaseError as e:
        sys.exit(f"Ошибка Supabase: {e}")

    # сводка тем
    by_theme = {}
    for row in rows:
        by_theme[row["theme"]] = by_theme.get(row["theme"], 0) + 1
    names = {"rel": "отношения", "self": "любовь к себе",
             "mom": "материнство", "life": "лайфстайл"}
    print(f"\n✅ Залито в Supabase: {len(rows)} постов из {src.name}")
    print("   Темы (черновая разметка):")
    for t, n in sorted(by_theme.items(), key=lambda x: -x[1]):
        print(f"     {names.get(t, t)}: {n}")
    print("\n   Живой дашборд в Cowork обновится при следующем открытии.\n")


if __name__ == "__main__":
    main()
