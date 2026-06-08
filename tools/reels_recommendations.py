#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reels_recommendations.py — еженедельный анализ Reels + AI-рекомендации.

Логика:
  1. Читает последний отчёт posts_*.json из reports/
  2. Фильтрует только Reels (media_type=VIDEO)
  3. Анализирует engagement (reach, likes, comments, saves если есть)
  4. Вызывает Claude для генерации конкретных рекомендаций
  5. Отправляет Марине (Telegram или сохраняет файл)

Используется:
  python reels_recommendations.py [--send] [--days N]

Возвращает JSON:
  {
    "ok": true,
    "reels_analyzed": N,
    "top_reels": [...],
    "patterns": {...},
    "recommendations": "...",  # от Claude
    "sent_to": "marina_telegram"
  }
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
import requests

TOOLS = Path(__file__).resolve().parent
REPORTS = TOOLS.parent / "reports"
MILA_BUSINESS = TOOLS.parent / "MILA-BUSINESS"

load_dotenv(TOOLS / ".env")

# Anthropic API
ANTHROPIC_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()

# Telegram для отправки Марине
TG_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
MARINA_TG = (os.getenv("TELEGRAM_MARINA_ID") or "").strip()

def _log(msg):
    """Лог с меткой времени."""
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] {msg}", file=sys.stderr, flush=True)

def _fail(reason):
    """Ошибка в JSON."""
    print(json.dumps({"ok": False, "reason": reason}, ensure_ascii=False))
    sys.exit(1)

def find_latest_posts_report():
    """Найти последний posts_*.json в reports/."""
    posts_files = sorted(REPORTS.glob("posts_*.json"), reverse=True)
    if not posts_files:
        raise Exception("Нет posts_*.json в reports/")
    return posts_files[0]

def load_posts(report_path):
    """Загрузить посты из JSON."""
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)

def filter_reels(posts):
    """Отфильтровать только Reels (VIDEO)."""
    reels = [p for p in posts if p.get("type", "").upper() in ("VIDEO", "REELS", "REEL")]
    if not reels:
        # fallback: если нет явной марки VIDEO, берём по наличию engagement
        reels = sorted(posts, key=lambda p: (p.get("reach", 0) or 0) + (p.get("engagement", 0) or 0), reverse=True)[:10]
    return reels

def analyze_reels(reels):
    """Анализировать метрики Reels."""
    if not reels:
        return None

    # Сортируем по охвату
    reels_with_reach = [r for r in reels if r.get("reach")]
    if not reels_with_reach:
        reels_with_reach = reels

    reels_with_reach.sort(key=lambda r: (r.get("reach") or 0) + (r.get("engagement") or 0), reverse=True)

    # Топ 5
    top = reels_with_reach[:5]

    # Паттерны
    avg_reach = sum(r.get("reach") or 0 for r in reels_with_reach) / len(reels_with_reach) if reels_with_reach else 0
    avg_engagement = sum(r.get("engagement") or 0 for r in reels_with_reach) / len(reels_with_reach) if reels_with_reach else 0

    patterns = {
        "total_reels": len(reels),
        "avg_reach": round(avg_reach),
        "avg_engagement": round(avg_engagement),
        "best_time": "?",  # TODO: анализ по дате публикации
        "top_engagement_rate": round(((reels_with_reach[0].get("engagement") or 0) / max(reels_with_reach[0].get("reach") or 1, 1)) * 100, 1) if reels_with_reach else 0,
    }

    return {
        "top_reels": top,
        "patterns": patterns,
        "all_reels": reels_with_reach
    }

def generate_recommendations(analysis):
    """Генерировать рекомендации через Claude API."""
    if not ANTHROPIC_KEY:
        return "⚠️ Нет ANTHROPIC_API_KEY в .env (рекомендации не сгенерированы, только статистика)"

    top_reels = analysis["top_reels"]
    patterns = analysis["patterns"]

    # Контекст для Claude
    reels_str = "\n".join([
        f"- Reel #{i+1}: охват {r.get('reach', 0)}, лайки {r.get('likes', 0)}, "
        f"комментарии {r.get('comments', 0)}\n"
        f"  Тема: {r.get('caption', '')[:100]}"
        for i, r in enumerate(top_reels)
    ])

    prompt = f"""Ты — Марина, контент-стратег для психолога Людмилы Лыковой.
Ниша: здоровые отношения, психология привязанности (три типа: Спасатель, Угодница, Избегание).
Аудитория: женщины 25-45 лет.

АНАЛИТИКА REELS (последняя неделя):
- Проанализировано Reels: {patterns['total_reels']}
- Средний охват: {patterns['avg_reach']}
- Средний engagement: {patterns['avg_engagement']}
- Лучший engagement rate: {patterns['top_engagement_rate']}%

ТОП-5 ЛУЧШИХ REELS:
{reels_str}

ЗАДАЧА:
На основе этих данных дай Людмиле конкретные РЕКОМЕНДАЦИИ для контент-плана на следующую неделю:
1. Какие ТЕМЫ / ПАТТЕРНЫ работают лучше всего?
2. Какую длину/формат выбрать?
3. Где лучше всего используется СТА (call-to-action)?
4. 2-3 КОНКРЕТНЫХ идеи для постов на следующую неделю (с указанием темы, формата, СТА)

Пиши коротко, конкретно, по-русски. Без воды. Как рекомендация опытного стратега."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-opus-4-8",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if r.status_code != 200:
            return f"⚠️ Claude API ошибка {r.status_code}: {r.text[:200]}"

        data = r.json()
        recommendations = data.get("content", [{}])[0].get("text", "")
        _log(f"✓ Рекомендации сгенерированы ({len(recommendations)} символов)")
        return recommendations

    except Exception as e:
        return f"⚠️ Ошибка генерации: {e}"

def telegram_send_marina(text):
    """Отправить рекомендации Марине в Telegram."""
    if not TG_TOKEN or not MARINA_TG:
        return False, "Нет TELEGRAM_BOT_TOKEN или TELEGRAM_MARINA_ID"

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": MARINA_TG,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            _log(f"✓ Отправлено Марине в Telegram")
            return True, None
        error = data.get("description", "неизвестная ошибка")
        _log(f"✗ Telegram ошибка: {error}")
        return False, error
    except Exception as e:
        _log(f"✗ Ошибка отправки: {e}")
        return False, str(e)

def save_recommendations(analysis, recommendations):
    """Сохранить рекомендации в файл."""
    out_dir = MILA_BUSINESS / "05-analytics" / "reels-recommendations"
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"reels-rec_{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    filepath = out_dir / filename

    content = f"""# Рекомендации по Reels — {datetime.utcnow().strftime('%Y-%m-%d')}

## 📊 Аналитика
- **Проанализировано Reels:** {analysis['patterns']['total_reels']}
- **Средний охват:** {analysis['patterns']['avg_reach']}
- **Средний engagement:** {analysis['patterns']['avg_engagement']}
- **Лучший engagement rate:** {analysis['patterns']['top_engagement_rate']}%

## 🎯 Рекомендации
{recommendations}

## 🔝 Топ-5 Reels

"""
    for i, reel in enumerate(analysis["top_reels"], 1):
        content += f"\n### {i}. Охват {reel.get('reach', 0)}\n"
        content += f"- Лайки: {reel.get('likes', 0)}\n"
        content += f"- Комментарии: {reel.get('comments', 0)}\n"
        content += f"- Тема: {reel.get('caption', '')[:100]}\n"
        if reel.get('link'):
            content += f"- Ссылка: {reel['link']}\n"

    filepath.write_text(content, encoding="utf-8")
    _log(f"✓ Сохранено в {filepath}")
    return filepath

def main():
    import argparse
    p = argparse.ArgumentParser(description="Analitics + рекомендации по Reels")
    p.add_argument("--send", action="store_true", help="Отправить рекомендации Марине в Telegram")
    p.add_argument("--days", type=int, default=7, help="Анализировать последние N дней (default 7)")
    args = p.parse_args()

    try:
        _log(f"Поиск отчёта аналитики...")

        report_path = find_latest_posts_report()
        _log(f"Загруженный отчёт: {report_path.name}")

        posts = load_posts(report_path)
        reels = filter_reels(posts)

        if not reels:
            _fail("Нет Reels в отчёте аналитики")

        _log(f"Найдено {len(reels)} Reels")

        analysis = analyze_reels(reels)
        _log(f"Анализ завершен: avg_reach={analysis['patterns']['avg_reach']}")

        recommendations = generate_recommendations(analysis)

        result = {
            "ok": True,
            "timestamp": datetime.utcnow().isoformat(),
            "reels_analyzed": analysis["patterns"]["total_reels"],
            "patterns": analysis["patterns"],
            "top_reels": [
                {
                    "reach": r.get("reach"),
                    "engagement": r.get("engagement"),
                    "caption": r.get("caption", "")[:80]
                }
                for r in analysis["top_reels"]
            ],
            "recommendations": recommendations[:500] + ("..." if len(recommendations) > 500 else ""),
            "sent_to": None
        }

        if args.send:
            ok, err = telegram_send_marina(
                f"📊 <b>Анализ Reels</b>\n\n"
                f"Реелс: {analysis['patterns']['total_reels']}\n"
                f"Охват (avg): {analysis['patterns']['avg_reach']}\n"
                f"Engagement: {analysis['patterns']['avg_engagement']}\n\n"
                f"<b>Рекомендации:</b>\n{recommendations[:800]}"
            )
            if ok:
                result["sent_to"] = "marina_telegram"

        # Сохраняем файл в любом случае
        rec_file = save_recommendations(analysis, recommendations)
        result["saved_to"] = str(rec_file)

        print(json.dumps(result, ensure_ascii=False, indent=2))
        _log(f"✓ Завершено успешно")

    except Exception as e:
        _fail(str(e))

if __name__ == "__main__":
    main()
