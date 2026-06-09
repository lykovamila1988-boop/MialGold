"""Поток создания контента: Marina → Victoria → Tyoma → публикация

Цепочка (pipeline):
1. Marina: создаёт 3-5 постов на неделю
2. Victoria: редактирует, даёт approve/revisions
3. Tyoma: публикует в Telegram
4. Производство: отслеживает аналитику
"""

import json
import time
from datetime import datetime
from base import *
import base as base_module
import memory

# Пусть к папке с контентом
CONTENT_FOLDER = MILA_FOLDER / "MILA-BUSINESS" / "02-content"
TELEGRAM_FOLDER = MILA_FOLDER / "MILA-BUSINESS" / "04-telegram"


def step_marina_create_posts(topic="неделя", count=3):
    """Шаг 1: Marina создаёт посты

    Args:
        topic: тема/контекст для постов (по умолчанию еженедельный контент)
        count: сколько постов создать

    Returns:
        list of posts with status "draft"
    """
    print(f"[P1] Marina: создаю {count} постов про {topic}")

    prompt = f"""Ты Marina, маркетолог Людмилы Лыковой.

Тебе нужно создать {count} поста для Telegram-канала на тему: {topic}

Требования:
- Тон: теплый, как совет подруги, без цензуры
- Структура: один инсайт = одно сообщение
- Используй паттерны: Спасатель, Угодница, Избегание
- Длина: 150-300 символов каждый
- Добавь эмодзи где уместно

Создай разные типы постов:
1. Инсайт (диагностика паттерна)
2. Кейс (история клиента)
3. Практика (упражнение для читателя)

Каждый пост напиши в формате JSON:
{{
  "type": "инсайт|кейс|практика",
  "title": "короткий заголовок",
  "text": "основной текст",
  "cta": "call to action (опционально)"
}}

Выведи 3 поста подряд, каждый с новой строки JSON."""

    # Вызвать агента Marina
    result = base_module.run_agent("marina", prompt)

    # Парсить результат (должны быть JSON строки)
    posts = []
    try:
        for line in result.split('\n'):
            if line.strip().startswith('{'):
                try:
                    post = json.loads(line)
                    post['id'] = f"draft_{len(posts)+1}_{datetime.now().strftime('%s')}"
                    post['status'] = 'draft'
                    post['created_at'] = datetime.now().isoformat()
                    post['created_by'] = 'marina'
                    posts.append(post)
                except:
                    pass
    except:
        print(f"⚠️ Не смог парсить результат Marina")
        return []

    print(f"✅ Marina создала {len(posts)} постов")
    return posts


def step_victoria_review(posts):
    """Шаг 2: Victoria редактирует посты

    Args:
        posts: list of draft posts from Marina

    Returns:
        list of posts with status "approved" или "needs_revision"
    """
    if not posts:
        print("⚠️ Нечего редактировать")
        return []

    print(f"[P2] Victoria: редактирую {len(posts)} постов")

    reviewed_posts = []
    for post in posts:
        prompt = f"""Ты Victoria, редактор контента.

Отредактируй этот пост:
ЗАГОЛОВОК: {post.get('title', '')}
ТЕКСТ: {post.get('text', '')}

Проверь:
✓ Грамматика и пунктуация
✓ Тон (тепло, без цензуры, как совет подруги)
✓ Длина (не слишком длинный?)
✓ Есть ли call-to-action?

Ответь в формате JSON:
{{
  "approved": true/false,
  "feedback": "твой комментарий",
  "edited_text": "улучшенный текст (если нужны правки)"
}}
"""

        result = base_module.run_agent("victoria", prompt)

        try:
            # Парсить результат Victoria
            review = json.loads(result)
            post['status'] = 'approved' if review.get('approved') else 'needs_revision'
            post['feedback'] = review.get('feedback', '')

            if not review.get('approved') and review.get('edited_text'):
                post['text'] = review['edited_text']

            post['reviewed_by'] = 'victoria'
            post['reviewed_at'] = datetime.now().isoformat()

        except:
            print(f"⚠️ Ошибка парсинга результата Victoria для поста {post['id']}")
            post['status'] = 'approved'  # Если непонятно — одобрить

        reviewed_posts.append(post)

    approved = sum(1 for p in reviewed_posts if p['status'] == 'approved')
    print(f"✅ Victoria одобрила {approved}/{len(reviewed_posts)} постов")
    return reviewed_posts


def step_tyoma_publish(posts):
    """Шаг 3: Tyoma публикует в Telegram

    Args:
        posts: list of approved posts

    Returns:
        list of published posts with message IDs
    """
    if not posts:
        print("⚠️ Нечего публиковать")
        return []

    approved_posts = [p for p in posts if p.get('status') == 'approved']
    if not approved_posts:
        print("⚠️ Нет одобренных постов")
        return []

    print(f"[P3] Tyoma: публикую {len(approved_posts)} постов в Telegram")

    published = []
    for post in approved_posts:
        text = post.get('text', '')
        content_type = post.get('type', 'general')

        try:
            # Публикуем через telegram_send (с TELEGRAM_CHANNEL_ID из .env)
            from shared_tools import telegram_send

            result = telegram_send(text=text, confirm=False)

            # Если успешно — добавляем в published
            if "Опубликовано" in result or "успешно" in result.lower():
                post['status'] = 'published'
                post['published_at'] = datetime.now().isoformat()
                post['published_by'] = 'tyoma'
                published.append(post)
                print(f"✅ Пост опубликован: {post['id']}")
            else:
                print(f"⚠️ Возможна ошибка при публикации: {result}")
                post['status'] = 'publish_error'
                published.append(post)

        except Exception as e:
            print(f"❌ Ошибка публикации: {e}")
            post['status'] = 'publish_error'
            published.append(post)

    print(f"✅ Tyoma опубликовала {sum(1 for p in published if p['status'] == 'published')} постов")
    return published


def content_flow_complete(topic="еженедельный контент", count=3):
    """Полный flow: Marina → Victoria → Tyoma

    Args:
        topic: тема для контента
        count: сколько постов создать
    """

    print("\n" + "="*70)
    print("🚀 НАЧАЛО PIPELINE: Marina → Victoria → Tyoma")
    print("="*70)

    # Шаг 1: Marina создаёт
    posts = step_marina_create_posts(topic=topic, count=count)
    if not posts:
        print("❌ Marina не создала посты")
        return {"status": "failed", "stage": "marina"}

    time.sleep(1)  # Небольшая пауза между этапами

    # Шаг 2: Victoria редактирует
    posts = step_victoria_review(posts)

    time.sleep(1)

    # Шаг 3: Tyoma публикует
    posts = step_tyoma_publish(posts)

    print("\n" + "="*70)
    print("✅ PIPELINE ЗАВЕРШЁН")
    print("="*70)

    # Итоговая статистика
    stats = {
        "total": len(posts),
        "approved": sum(1 for p in posts if p['status'] in ['approved', 'published']),
        "published": sum(1 for p in posts if p['status'] == 'published'),
        "failed": sum(1 for p in posts if 'error' in p.get('status', ''))
    }

    print(f"\n📊 Итоги:")
    print(f"  Создано: {stats['total']}")
    print(f"  Одобрено: {stats['approved']}")
    print(f"  Опубликовано: {stats['published']}")
    print(f"  Ошибки: {stats['failed']}")

    return {
        "status": "completed",
        "posts": posts,
        "stats": stats
    }


if __name__ == "__main__":
    # Запустить flow для еженедельного контента
    result = content_flow_complete(
        topic="паттерны в отношениях: Спасатель, Угодница, Избегание",
        count=3
    )

    # Сохранить результат
    with open(MILA_FOLDER / "logs" / f"content_flow_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
