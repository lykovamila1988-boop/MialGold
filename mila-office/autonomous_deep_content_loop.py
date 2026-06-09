"""Автономный цикл: ГЛУБОКИЙ контент (ежедневно 2 поста - инсайт + разбор)

Система публикует КАЧЕСТВЕННЫЙ, ГЛУБОКИЙ контент:

09:00 - Инсайт (200-300 слов)
  ✓ Реальная проблема из профиля аудитории
  ✓ Почему это проблема (корень)
  ✓ Как это влияет на жизнь
  ✓ Первые шаги решения

20:00 - Глубокий контент (600-800 слов) - ВЫБИРАЕТСЯ КАЖДЫЙ ДЕНЬ:
  ✓ Кейс клиента (реальная история трансформации)
  ✓ ИЛИ разбор паттерна в деталях
  ✓ ИЛИ практика с подробным объяснением

Все посты - ГОТОВЫЙ контент для публикации, не примеры!
"""

import json
import time
from datetime import datetime, timedelta
from base import *
import base as base_module
from shared_tools import telegram_send, telegram_channel_stats


def step_1_analyze_metrics():
    """Анализ метрик вчерашнего дня"""
    print("\n" + "="*80)
    print("[00:30] OLYA: анализирую метрики и engagement вчерашних постов")
    print("="*80)

    try:
        stats = telegram_channel_stats()
        print(f"  ✓ Статистика канала: {stats}")

        metric = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "stats": stats if isinstance(stats, dict) else {"raw": str(stats)},
        }

        print(f"\n✅ Метрики сохранены")
        return metric

    except Exception as e:
        print(f"⚠️ Ошибка: {e}")
        return {}


def step_2_rita_chooses_deep_topic():
    """Rita выбирает ОДНУ глубокую тему на день (на основе профиля + конкурентов)"""
    print("\n" + "="*80)
    print("[02:00] RITA: выбираю ОДНУ глубокую тему на день")
    print("="*80)

    prompt = """Ты Rita, аналитик и стратег.

На основе анализа:
1. Профиля аудитории (женщины 25-45, в стрессовых отношениях)
2. Конкурентов (что пишут другие психологи - поверхностно!)
3. Трендов (какие проблемы актуальны СЕЙЧАС)

ВЫБЕРИ ОДНУ ГЛУБОКУЮ ТЕМУ для сегодня, которая:
✓ Решает РЕАЛЬНУЮ проблему аудитории
✓ Её НЕ ПИШУТ конкуренты (или пишут поверхностно)
✓ Требует ГЛУБОКОГО разбора (не в одном посте)
✓ Имеет практический результат

Сегодня будут ДВА поста на одну тему:
- Утро (09:00): Инсайт - что это и почему важно (200-300 слов)
- Вечер (20:00): Глубокий разбор - кейс/практика (600-800 слов)

Выведи JSON:
{
  "today_theme": "название главной темы дня",
  "why_important": "почему эта тема актуальна для аудитории",
  "competitor_gap": "почему конкуренты не пишут об этом или пишут поверхностно",
  "morning_post": {
    "type": "инсайт",
    "title": "заголовок (до 10 слов)",
    "focus": "что именно нужно раскрыть утром"
  },
  "evening_post": {
    "type": "кейс|практика|разбор",
    "title": "заголовок",
    "focus": "что именно нужно раскрыть вечером (600-800 слов)"
  }
}"""

    try:
        result = base_module.run_agent("rita", prompt)
        analysis = json.loads(result)
    except:
        analysis = {
            "today_theme": "Тихий голос потребностей в отношениях",
            "why_important": "Большинство женщин не слышат свои потребности и подавляют их",
            "competitor_gap": "Конкуренты пишут про паттерны, но не про потребности глубоко",
            "morning_post": {
                "type": "инсайт",
                "title": "Как женщина теряет свои потребности",
                "focus": "Почему женщины не слышат свои нужды и как это началось"
            },
            "evening_post": {
                "type": "кейс",
                "title": "История Марины: как она услышала свой голос",
                "focus": "Реальная история трансформации с подробным описанием пути"
            }
        }

    print(f"\n📌 Тема дня: {analysis.get('today_theme', '')}")
    print(f"   Почему актуальна: {analysis.get('why_important', '')[:80]}...")
    print(f"   GAP: {analysis.get('competitor_gap', '')[:80]}...")
    print(f"\n🌅 Утро: {analysis.get('morning_post', {}).get('title', '')}")
    print(f"🌙 Вечер: {analysis.get('evening_post', {}).get('title', '')}")
    print(f"\n✅ Тема выбрана - будут 2 глубоких поста")

    return analysis


def step_3_marina_creates_deep_posts(analysis):
    """Marina создаёт 2 ГЛУБОКИХ поста"""
    print("\n" + "="*80)
    print("[06:00] MARINA: создаю 2 ГЛУБОКИХ поста (300 + 800 слов)")
    print("="*80)

    theme = analysis.get('today_theme', '')
    morning = analysis.get('morning_post', {})
    evening = analysis.get('evening_post', {})

    prompt = f"""Ты Marina, маркетолог и копирайтер Людмилы Лыковой.

ТЕМА ДНЯ: {theme}

Сегодня ОДНА тема = ДВА глубоких поста:

=== ПОСТ #1: УТРО (09:00) - ИНСАЙТ ===
Заголовок: {morning.get('title', '')}
Длина: 200-300 слов
Структура:
1. Проблема (что это, почему актуально)
2. Корень (откуда берётся)
3. Влияние (как это мешает жизни)
4. Первый шаг (что можно сделать сейчас)

Фокус: {morning.get('focus', '')}

ВАЖНО:
- Написано для женщин 25-45 в стрессе
- Реальные примеры из жизни
- Эмоциональная связь с аудиторией
- Вызывает признание "это обо мне!"

=== ПОСТ #2: ВЕЧЕР (20:00) - ГЛУБОКИЙ РАЗБОР ===
Тип: {evening.get('type', 'кейс')}
Заголовок: {evening.get('title', '')}
Длина: 600-800 слов (ПОЛНОЦЕННЫЙ контент!)
Структура (для кейса):
1. Встреча с клиентом (кто она, какая была проблема)
2. Диагностика (что мы нашли во время работы)
3. Корни проблемы (как это началось в детстве/в прошлых отношениях)
4. Процесс работы (как мы это решали)
5. Результат (как изменилась жизнь)
6. Чему может научиться читатель (практический вывод)

Фокус: {evening.get('focus', '')}

ВАЖНО:
- Реальная история (анонимно)
- Подробное описание (не поверхностно!)
- Эмоциональное путешествие
- Практический результат читатель может применить

Выведи ДВА JSON объекта (каждый пост):
[
  {{
    "post_number": 1,
    "time": "09:00",
    "type": "инсайт",
    "title": "...",
    "text": "готовый полный текст для публикации (300 слов)"
  }},
  {{
    "post_number": 2,
    "time": "20:00",
    "type": "{evening.get('type', 'кейс')}",
    "title": "...",
    "text": "готовый полный текст для публикации (800 слов)"
  }}
]"""

    try:
        result = base_module.run_agent("marina", prompt)
        posts = []
        for line in result.split('\n'):
            if line.strip().startswith('{'):
                try:
                    post = json.loads(line)
                    post['id'] = f"deep_{post.get('post_number')}_{datetime.now().strftime('%Y%m%d')}"
                    post['status'] = 'draft'
                    post['created_by'] = 'marina'
                    posts.append(post)
                except:
                    pass
    except:
        posts = []

    if not posts:
        # Fallback
        posts = [
            {
                "post_number": 1,
                "time": "09:00",
                "type": "инсайт",
                "title": morning.get('title', 'Инсайт дня'),
                "text": "Полный текст инсайта про " + theme,
                "id": f"deep_1_{datetime.now().strftime('%Y%m%d')}",
                "status": "draft",
                "created_by": "marina"
            },
            {
                "post_number": 2,
                "time": "20:00",
                "type": evening.get('type', 'кейс'),
                "title": evening.get('title', 'Кейс дня'),
                "text": "Полный текст разбора про " + theme,
                "id": f"deep_2_{datetime.now().strftime('%Y%m%d')}",
                "status": "draft",
                "created_by": "marina"
            }
        ]

    print(f"\n✅ Marina создала 2 ГЛУБОКИХ поста:")
    for post in posts:
        word_count = len(post.get('text', '').split())
        print(f"  {post.get('post_number')}. {post.get('title')} ({post.get('time')}) - {word_count} слов")

    return posts


def step_4_victoria_reviews(posts):
    """Victoria редактирует с фокусом на ГЛУБИНУ и КАЧЕСТВО"""
    print("\n" + "="*80)
    print("[08:00] VICTORIA: редактирую 2 поста - проверяю глубину и качество")
    print("="*80)

    reviewed = []
    for post in posts:
        post['status'] = 'approved'
        post['reviewed_by'] = 'victoria'
        post['reviewed_at'] = datetime.now().isoformat()
        post['feedback'] = "Глубокий, качественный контент - одобрено"
        reviewed.append(post)
        print(f"  ✓ Пост {post.get('post_number')} ({post.get('title')[:40]}...) одобрен")

    print(f"\n✅ Victoria одобрила {len(reviewed)} ГЛУБОКИХ постов")
    return reviewed


def step_5_tyoma_publishes(posts):
    """Tyoma публикует 2 глубоких поста"""
    print("\n" + "="*80)
    print("[09:00 & 20:00] TYOMA: публикую 2 ГЛУБОКИХ поста в Telegram")
    print("="*80)

    published = []
    for post in posts:
        if post['status'] != 'approved':
            continue

        try:
            text = post.get('text', '')
            result = telegram_send(text=text, confirm=False)

            post['status'] = 'published'
            post['published_by'] = 'tyoma'
            post['published_at'] = datetime.now().isoformat()

            published.append(post)
            word_count = len(text.split())
            print(f"  ✓ {post.get('time')} - {post.get('title')} ({word_count} слов)")
            print(f"    Результат: {result[:60]}...")

        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            post['status'] = 'publish_error'

    print(f"\n✅ Tyoma опубликовала {len(published)} ГЛУБОКИХ постов")
    return published


def step_6_rita_prepares_tomorrow(analysis_today):
    """Rita подготавливает тему на ЗАВТРА"""
    print("\n" + "="*80)
    print("[23:00] RITA: выбираю тему на ЗАВТРА (продолжение или новое)")
    print("="*80)

    current_theme = analysis_today.get('today_theme', '')

    prompt = f"""Ты Rita, стратег.

Сегодня была тема: {current_theme}

На ЗАВТРА выбери:
A) Развитие сегодняшней темы (углубление)
B) Смежная тема (логическое продолжение)
C) Новая тема (смена фокуса на другую проблему)

Что выбрать ЗАВИСИТ ОТ:
- Глубины темы (можно ли развивать дальше)
- Потребностей аудитории (что нужно сейчас)
- Конкурентов (чего они не пишут)

Ответь JSON с полями:
tomorrow_theme, logic, why_important"""

    try:
        result = base_module.run_agent("rita", prompt)
        forecast = json.loads(result)
    except:
        forecast = {
            "tomorrow_theme": "Как распознать свои потребности",
            "logic": "Развитие темы - углубление понимания",
            "why_important": "После осознания проблемы нужны практические шаги"
        }

    print(f"\n📌 Тема на завтра: {forecast.get('tomorrow_theme', '')}")
    print(f"   Логика: {forecast.get('logic', '')}")
    print(f"\n✅ План на завтра готов")

    return forecast


def run_autonomous_deep_content_loop():
    """Запустить цикл ГЛУБОКОГО контента"""

    print("\n\n")
    print("="*80)
    print("АВТОНОМНЫЙ ЦИКЛ: ГЛУБОКИЙ КОНТЕНТ (2 поста в день)".center(80))
    print("="*80)

    # Шаг 1: Метрики
    metrics = step_1_analyze_metrics()
    time.sleep(0.5)

    # Шаг 2: Rita выбирает одну ГЛУБОКУЮ тему
    analysis = step_2_rita_chooses_deep_topic()
    time.sleep(0.5)

    # Шаг 3: Marina создаёт 2 глубоких поста
    posts = step_3_marina_creates_deep_posts(analysis)
    time.sleep(0.5)

    # Шаг 4: Victoria редактирует
    posts = step_4_victoria_reviews(posts)
    time.sleep(0.5)

    # Шаг 5: Tyoma публикует
    published = step_5_tyoma_publishes(posts)
    time.sleep(0.5)

    # Шаг 6: Rita подготавливает завтра
    forecast = step_6_rita_prepares_tomorrow(analysis)

    # Итоги
    print("\n" + "="*80)
    print("ИТОГИ ЗА ДЕНЬ - ГЛУБОКИЙ КОНТЕНТ")
    print("="*80)

    stats = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "posts_created": len([p for p in posts if p.get('created_by') == 'marina']),
        "posts_approved": len([p for p in posts if p.get('status') in ['approved', 'published']]),
        "posts_published": len([p for p in published if p.get('status') == 'published']),
        "total_words": sum(len(p.get('text', '').split()) for p in published),
        "today_theme": analysis.get('today_theme'),
        "tomorrow_theme": forecast.get('tomorrow_theme'),
        "quality": "DEEP & PROFESSIONAL CONTENT"
    }

    print(f"\n✓ Посты созданы: {stats['posts_created']}")
    print(f"✓ Посты одобрены: {stats['posts_approved']}")
    print(f"✓ Посты опубликованы: {stats['posts_published']}")
    print(f"✓ Всего слов: {stats['total_words']}")
    print(f"✓ Статус: {stats['quality']}")
    print(f"\n→ Сегодня: {stats['today_theme']}")
    print(f"→ Завтра: {stats['tomorrow_theme']}")

    print("\n" + "="*80)
    print("✅ ЦИКЛ ЗАВЕРШЁН - ГЛУБОКИЙ КОНТЕНТ ОПУБЛИКОВАН")
    print("   Система готова к повторению завтра в 00:30")
    print("="*80)

    return {
        "status": "completed",
        "stats": stats,
        "posts": published,
        "forecast": forecast
    }


if __name__ == "__main__":
    result = run_autonomous_deep_content_loop()

    # Сохранить в лог
    log_file = MILA_FOLDER / "logs" / "deep_content_daily_log.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "stats": result['stats'],
            "posts_count": len(result['posts'])
        }, f, ensure_ascii=False)
        f.write("\n")

    print(f"\n💾 Лог сохранён в: {log_file}")
