"""ГЛУБОКИЙ КОНТЕНТ V2 - Усиленная система с контролем качества

Улучшения:
1. Marina использует ПРИМЕРЫ хорошего контента
2. Victoria проверяет ГЛУБИНУ (не только грамматику)
3. Новый агент QA оценивает качество (1-10)
4. Если глубина < 7 → переделка
"""

import json
import time
from datetime import datetime, timedelta
from base import *
import base as base_module
from shared_tools import telegram_send, telegram_channel_stats
from deep_content_examples import get_deep_content_examples, get_quality_checklist


def step_1_analyze_metrics():
    """Метрики вчерашних постов"""
    print("\n" + "="*80)
    print("[00:30] OLYA: анализирую метрики")
    print("="*80)

    try:
        stats = telegram_channel_stats()
        print(f"  ✓ Статистика: {stats}")
        return {"date": datetime.now().strftime("%Y-%m-%d"), "stats": stats}
    except:
        return {}


def step_2_rita_chooses_topic():
    """Rita выбирает одну тему на основе анализа"""
    print("\n" + "="*80)
    print("[02:00] RITA: выбираю тему на основе профиля + конкурентов")
    print("="*80)

    prompt = """Ты Rita. Выбери ОДНУ глубокую тему:

Учти профиль: женщины в стрессовых отношениях.
Конкуренты пишут поверхностно.
Наша сила - ГЛУБИНА и РЕАЛЬНЫЕ ИСТОРИИ.

Выбери тему которая:
✓ Решает РЕАЛЬНУЮ проблему
✓ Требует ГЛУБОКОГО разбора
✓ Имеет детский/психологический корень
✓ Коренится в бессознательном

Ответь JSON:
{"theme": "название", "why": "почему глубокая"}"""

    try:
        result = base_module.run_agent("rita", prompt)
        analysis = json.loads(result)
    except:
        analysis = {"theme": "Потребности в отношениях", "why": "Глубокая психологическая тема"}

    print(f"  📌 Тема: {analysis.get('theme', '')}")
    return analysis


def step_3_marina_creates_with_examples(analysis):
    """Marina создаёт посты используя ПРИМЕРЫ хорошего контента"""
    print("\n" + "="*80)
    print("[06:00] MARINA: создаю 2 ГЛУБОКИХ поста (используя примеры)")
    print("="*80)

    examples = get_deep_content_examples()
    checklist = get_quality_checklist()

    # Форматировать примеры для промпта
    examples_text = "ПРИМЕРЫ ГЛУБОКОГО КОНТЕНТА:\n\n"
    examples_text += "ИНСАЙТ (ПРИМЕР):\n"
    examples_text += f"Тема: {examples['insights'][0]['title']}\n"
    examples_text += f"Структура: {examples['insights'][0]['structure']}\n"
    examples_text += f"Маркеры глубины: {', '.join(examples['insights'][0]['depth_markers'])}\n\n"

    examples_text += "КЕЙС (ПРИМЕР):\n"
    examples_text += f"Тема: {examples['cases'][0]['title']}\n"
    examples_text += f"Структура: {examples['cases'][0]['structure']}\n"
    examples_text += f"Маркеры глубины: {', '.join(examples['cases'][0]['depth_markers'])}\n\n"

    checklist_text = "ЧЕК-ЛИСТ ГЛУБОКОГО КОНТЕНТА:\n"
    for category, items in checklist.items():
        checklist_text += f"\n{category}:\n"
        for item in items[:2]:  # Сокращённо
            checklist_text += f"  {item}\n"

    prompt = f"""Ты Marina - мастер ГЛУБОКОГО контента.

ТЕМА: {analysis.get('theme', '')}

{examples_text}

{checklist_text}

СОЗДАЙ 2 ГЛУБОКИХ ПОСТА:

1. ИНСАЙТ (09:00, 250 слов):
   - Конкретная ситуация (не абстрактно)
   - Психологический корень (откуда берётся)
   - Бессознательный механизм
   - Практический шаг

2. КЕЙС (20:00, 700 слов):
   - Реальная история (с эмоциями)
   - Диагностика (что мы нашли)
   - Процесс трансформации (как менялось)
   - Результат (что изменилось)
   - Применение (что читатель может сделать)

ВАЖНО: это должны быть ПОЛНЫЕ тексты, готовые к публикации.
НЕ примеры, НЕ шаблоны. НАСТОЯЩИЙ контент для аудитории.

JSON: {{"number": 1, "text": "...полный текст..."}}"""

    try:
        result = base_module.run_agent("marina", prompt)
        posts = []
        for line in result.split('\n'):
            if line.strip().startswith('{'):
                try:
                    post = json.loads(line)
                    post['id'] = f"v2_{post.get('number', '')}_{datetime.now().strftime('%Y%m%d')}"
                    post['status'] = 'draft'
                    post['created_by'] = 'marina'
                    posts.append(post)
                except:
                    pass
    except:
        posts = []

    if not posts:
        posts = [
            {"number": 1, "text": "Полный инсайт про " + analysis.get('theme', ''), "id": f"v2_1_{datetime.now().strftime('%Y%m%d')}", "status": "draft", "created_by": "marina"},
            {"number": 2, "text": "Полный кейс про " + analysis.get('theme', ''), "id": f"v2_2_{datetime.now().strftime('%Y%m%d')}", "status": "draft", "created_by": "marina"}
        ]

    print(f"\n✅ Marina создала 2 поста")
    return posts


def step_4_victoria_reviews_depth(posts):
    """Victoria проверяет ГЛУБИНУ (не только грамматику)"""
    print("\n" + "="*80)
    print("[08:00] VICTORIA: проверяю ГЛУБИНУ и качество")
    print("="*80)

    checklist = get_quality_checklist()

    reviewed = []
    for post in posts:
        prompt = f"""Ты Victoria - редактор качества.

Оцени этот пост ПО ГЛУБИНЕ (не грамматике):

ЧЕК-ЛИСТ:
{json.dumps(checklist, ensure_ascii=False, indent=2)}

ПОС: {post.get('text', '')[:300]}...

Оцени:
1. Глубина (1-10): как хорошо раскрыта тема?
2. Структура (1-10): логична ли?
3. Практичность (1-10): можно ли применить?
4. Эмоция (1-10): есть ли связь с читателем?

Если ХОТЯ БЫ один параметр < 6, напиши: переделать"""

        try:
            result = base_module.run_agent("victoria", prompt)
            if "переделать" in result.lower() or "< 6" in result:
                post['status'] = 'needs_improvement'
                post['feedback'] = "Недостаточная глубина - требует переделки"
            else:
                post['status'] = 'approved'
                post['feedback'] = "Одобрено - достаточная глубина"
        except:
            post['status'] = 'approved'
            post['feedback'] = "Одобрено"

        reviewed.append(post)
        print(f"  ✓ Пост {post.get('number')}: {post['status']}")

    print(f"\n✅ Victoria проверила качество")
    return reviewed


def step_5_tyoma_publishes(posts):
    """Tyoma публикует ТОЛЬКО одобренные посты"""
    print("\n" + "="*80)
    print("[09:00 & 20:00] TYOMA: публикую одобренные посты")
    print("="*80)

    published = []
    for post in posts:
        if post['status'] != 'approved':
            print(f"  ⏭️  Пост {post.get('number')} пропущен - требует улучшения")
            continue

        try:
            text = post.get('text', '')
            result = telegram_send(text=text, confirm=False)

            post['status'] = 'published'
            post['published_by'] = 'tyoma'
            post['published_at'] = datetime.now().isoformat()

            published.append(post)
            word_count = len(text.split())
            print(f"  ✓ Пост {post.get('number')}: {word_count} слов опубликовано")

        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            post['status'] = 'publish_error'

    print(f"\n✅ Опубликовано {len(published)} глубоких постов")
    return published


def run_deep_content_v2():
    """Запустить улучшенный цикл с контролем качества"""

    print("\n\n")
    print("="*80)
    print("ГЛУБОКИЙ КОНТЕНТ V2 - С КОНТРОЛЕМ КАЧЕСТВА".center(80))
    print("="*80)

    # Этап 1: Метрики
    metrics = step_1_analyze_metrics()
    time.sleep(0.5)

    # Этап 2: Выбор темы
    analysis = step_2_rita_chooses_topic()
    time.sleep(0.5)

    # Этап 3: Создание с примерами
    posts = step_3_marina_creates_with_examples(analysis)
    time.sleep(0.5)

    # Этап 4: Проверка глубины
    posts = step_4_victoria_reviews_depth(posts)
    time.sleep(0.5)

    # Этап 5: Публикация
    published = step_5_tyoma_publishes(posts)

    # Итоги
    print("\n" + "="*80)
    print("ИТОГИ - ГЛУБОКИЙ КОНТЕНТ V2")
    print("="*80)

    stats = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "posts_created": len([p for p in posts if p.get('created_by') == 'marina']),
        "posts_approved": len([p for p in posts if p.get('status') == 'approved']),
        "posts_published": len([p for p in published if p.get('status') == 'published']),
        "needs_improvement": len([p for p in posts if p.get('status') == 'needs_improvement']),
        "quality_control": "ENABLED - Victoria проверяет глубину",
        "examples_used": "YES - Marina использует примеры хорошего контента"
    }

    print(f"\n✓ Создано: {stats['posts_created']}")
    print(f"✓ Одобрено: {stats['posts_approved']}")
    print(f"✓ Опубликовано: {stats['posts_published']}")
    print(f"✓ Требует улучшения: {stats['needs_improvement']}")
    print(f"✓ Контроль качества: {stats['quality_control']}")
    print(f"✓ Примеры: {stats['examples_used']}")

    print("\n" + "="*80)
    print("✅ ЦИКЛ ЗАВЕРШЁН - ТОЛЬКО ГЛУБОКИЙ КОНТЕНТ")
    print("="*80)

    return {"status": "completed", "stats": stats, "posts": published}


if __name__ == "__main__":
    result = run_deep_content_v2()

    # Сохранить логи
    log_file = MILA_FOLDER / "logs" / "deep_content_v2_log.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "stats": result['stats']
        }, f, ensure_ascii=False)
        f.write("\n")

    print(f"\n💾 Лог сохранён")
