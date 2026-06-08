"""Виктория — Редактор и корректор. python victoria.py"""
from base import *
import requests
import json
from datetime import datetime

SYSTEM = """Ты — Виктория, опытный редактор и корректор. Работаешь с текстами Людмилы Лыковой (@liudmyla.lykova), психолога и коуча из Канады.

ТВОЯ ЗАДАЧА:
Проверять тексты перед публикацией и создавать визуалы для них. Ты страж качества — ничего не выходит пока ты не одобришь.

ГОЛОС ЛЮДМИЛЫ (сохраняй всегда):
- Тёплый, как близкая подруга-эксперт
- Русский язык, «ты», без жаргона
- Личные истории и кейсы
- Заканчивает вопросом или «ХОЧУ»
- Ниша: женщины в болезненных отношениях

ЧТО ПРОВЕРЯЕШЬ:
1. Пунктуация — особенно запятые в деепричастных оборотах
2. Голос — звучит как Людмила, не как шаблон
3. Хук — цепляет в первых двух строках?
4. CTA — есть вопрос или призыв в конце?
5. Длина — не слишком длинно для Instagram?
6. Эмоция — читатель узнаёт себя?

ВИЗУАЛЫ:
- После редактуры используй generate_image() чтобы создать изображение для поста
- Размер для Instagram: 1080x1350 (фото) или 1080x1920 (stories)
- Стиль: минималистичный, женственный, спокойные цвета (не яркие)

ФОРМАТ ОТВЕТА:
- Оценка 1-10
- Что хорошо (конкретно)
- Что исправить (с примером как)
- Финальная версия (если вносишь правки): выдай ПОЛНЫЙ исправленный текст, обёрнутый
  в маркеры [ДОКУМЕНТ] … [/ДОКУМЕНТ] — тогда приложение предложит скачать чистый
  готовый файл. Оценку и комментарии пиши ВНЕ маркеров.
- Если нужен визуал: используй generate_image() и дай ссылку на изображение"""

def generate_image(text, style="minimalist", size="1080x1350"):
    """Generate image for post (Canva/DALL-E API)"""
    canva_key = os.getenv("CANVA_API_KEY", "").strip()
    dalle_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not canva_key and not dalle_key:
        return (f"⚠️ Нет API ключей для генерации изображений.\n"
                f"Добавьте CANVA_API_KEY или OPENAI_API_KEY в .env\n"
                f"Текст для визуала: '{text}'\n"
                f"Можете использовать это описание в Canva вручную.")

    try:
        # Пытаемся DALL-E если есть ключ
        if dalle_key:
            headers = {"Authorization": f"Bearer {dalle_key}"}
            payload = {
                "model": "dall-e-3",
                "prompt": (f"Создай минималистичное женское изображение для Instagram поста. "
                          f"Текст поста: {text[:200]}. "
                          f"Стиль: {style}, спокойные тёплые цвета, размер {size}"),
                "n": 1,
                "size": f"{size.split('x')[0]}x{size.split('x')[1]}"
            }
            r = requests.post("https://api.openai.com/v1/images/generations",
                            headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                url = r.json()["data"][0]["url"]
                log("victoria", f"Generated image via DALL-E: {url[:80]}")
                return f"✓ Изображение создано:\n{url}\n\nРазмер: {size}, Стиль: {style}"
    except Exception as e:
        log("victoria", f"DALL-E error: {e}")

    # Fallback: инструкция для ручной генерации через Canva
    return (f"📐 Используйте Canva для создания изображения:\n"
            f"1. Откройте https://www.canva.com/designs/new\n"
            f"2. Выберите шаблон {size}\n"
            f"3. Текст: {text[:100]}...\n"
            f"4. Стиль: {style}, спокойные цвета\n"
            f"5. Сохраните и получите URL")

def approve_post(post_id, feedback=""):
    """Victoria утверждает пост — готов к публикации"""
    try:
        from mila_office import memory

        status = memory.update_post(post_id, {
            "status": "approved",
            "approved_by": "victoria",
            "approved_at": datetime.datetime.utcnow().isoformat(),
            "feedback": feedback
        })
        log("victoria", f"Post {post_id} approved")
        return f"✓ Пост {post_id} одобрен и готов к публикации!"
    except Exception as e:
        log("victoria", f"Error approving post: {e}")
        return f"⚠️ Ошибка при одобрении поста: {e}"

def request_revisions(post_id, feedback):
    """Victoria просит переделать пост"""
    try:
        from mila_office import memory

        status = memory.update_post(post_id, {
            "status": "needs_fixes",
            "reviewed_by": "victoria",
            "reviewed_at": datetime.datetime.utcnow().isoformat(),
            "feedback": feedback
        })
        log("victoria", f"Post {post_id} sent for revisions")
        return f"⚠️ Пост отправлен на доработку.\n\nОсобенности:\n{feedback}"
    except Exception as e:
        log("victoria", f"Error requesting revisions: {e}")
        return f"⚠️ Ошибка при отправке на доработку: {e}"

TOOLS = [
    {"name": "generate_image",
     "description": "Сгенерировать изображение для поста (Canva/DALL-E API или инструкция)",
     "input_schema": {
         "type": "object",
         "properties": {
             "text": {"type": "string", "description": "Текст поста для визуала"},
             "style": {"type": "string", "description": "Стиль (minimalist, elegant, bold и т.д.)", "default": "minimalist"},
             "size": {"type": "string", "description": "Размер (1080x1350 для фото, 1080x1920 для stories)", "default": "1080x1350"}
         },
         "required": ["text"]
     }},
    {"name": "approve_post",
     "description": "Одобрить пост — разрешить публикацию (Victoria только)",
     "input_schema": {
         "type": "object",
         "properties": {
             "post_id": {"type": "string", "description": "ID поста или название файла"},
             "feedback": {"type": "string", "description": "Комментарий (опционально)", "default": ""}
         },
         "required": ["post_id"]
     }},
    {"name": "request_revisions",
     "description": "Отправить пост на доработку — нужны правки (Victoria только)",
     "input_schema": {
         "type": "object",
         "properties": {
             "post_id": {"type": "string", "description": "ID поста или название файла"},
             "feedback": {"type": "string", "description": "Что нужно исправить (обязательно)"}
         },
         "required": ["post_id", "feedback"]
     }}
] + core_tools("Прочитать файл с текстом для редактуры",
                   "Сохранить отредактированную версию",
                   "Показать файлы в папке")

def handle(name, inp):
    if name == "generate_image":
        return generate_image(inp.get("text", ""), inp.get("style", "minimalist"), inp.get("size", "1080x1350"))
    if name == "approve_post":
        return approve_post(inp.get("post_id", ""), inp.get("feedback", ""))
    if name == "request_revisions":
        return request_revisions(inp.get("post_id", ""), inp.get("feedback", ""))
    res = core_handle(name, inp)
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/проверь":   "Покажи все файлы в content/posts/ и проверь последний пост",
    "/посты":     "Прочитай все файлы из content/posts/ и оцени каждый по шкале 1-10",
    "/стиль":     "Объясни как звучит голос Людмилы — дай 3 примера правильного и неправильного",
    "/файлы":     "Покажи что есть в папке для проверки",
}

if __name__ == "__main__":
    chat_loop("Виктория", "✍️", "green", SYSTEM, TOOLS, handle, QUICK)
