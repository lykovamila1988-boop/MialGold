"""Виктория — Редактор и корректор. python victoria.py

КОНТЕКСТ АГЕНТ-К-АГЕНТУ:
═════════════════════════════════════════════════════════════════════════

Виктория может получать сообщения от пользователя (человека) или от других агентов.
Контекст передаётся в [from:agent_name] тегах и вкладывается в system prompt.

ПРИМЕРЫ ИЗ РЕАЛЬНОЙ РАБОТЫ:
─────────────────────────────────────────────────────────────────────────

1. Запрос от ПОЛЬЗОВАТЕЛЯ (человека):
   Ты видишь обычное сообщение: "Проверь пост про выбор"
   → Нет [from:] тага → контекст из базы
   → Работаешь как обычно: читаешь файл, редактируешь, одобряешь

2. Запрос от МАРИНЫ (маркетер):
   Сообщение: "Проверь пост про выбор [from: marina]"
   → Марина написала пост и хочет твоего одобрения
   → ДЕЙСТВИЕ: оцени критичнее (она может быть предвзята), дай конкретный фидбек
   → ОТВЕТ: либо одобрь (approve_post), либо попроси доработку (request_revisions)
   → Марина ждёт твоего ответа перед публикацией

3. Запрос от ЛЁРЫ (продажи):
   Сообщение: "Прочитай этот текст для презентации [from: lera]"
   → Лёра готовит текст для звонка с клиентом, не для Instagram
   → ДЕЙСТВИЕ: проверяй иначе — может быть более формальный тон, чем для постов
   → КОНТЕКСТ: это для реального общения, не публикация

4. Запрос от ОЛИ (тренды):
   Сообщение: "Проверь текст про тренд недели [from: olya]"
   → Оля исследовала тренд и хочет знать, подходит ли для голоса Людмилы
   → ДЕЙСТВИЕ: оцени релевантность голосу + актуальность тренда
   → Если хорошо → одобри, если нужны правки → отправь на доработку

═════════════════════════════════════════════════════════════════════════

КАК РАЗЛИЧАТЬ КОНТЕКСТ В handle():
─────────────────────────────────────────────────────────────────────────

При запуске агента из webapp.py или office.py контекст передаётся:
  • Через системный prompt (добавляется автоматически)
  • Как параметр context в run_agent() вызове
  • Парсится из сообщения если стоит [from:agent_name] таг

В handle() функции ТЫ МОЖЕШЬ ИЗВЛЕЧЬ контекст и адаптировать логику:
  • Если from_agent == "marina" → строже к качеству (она маркетер, может быть bias)
  • Если from_agent == "lera" → проверяй стиль под презентацию/звонок
  • Если from_agent == "user" → обычная критика, как диалог с человеком

═════════════════════════════════════════════════════════════════════════
"""

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


def answer_message(msg_id, answer=""):
    """Victoria отвечает на сообщение от другого агента (помечает как answered)."""
    try:
        import memory
        result = memory.answer_agent_message(msg_id, answer or "Обработано")
        log("victoria", f"Answered message {msg_id}")
        return f"✓ Сообщение отмечено как ответленное"
    except Exception as e:
        log("victoria", f"Error answering message: {e}")
        return f"⚠️ Ошибка: {e}"

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

# ═════════════════════════════════════════════════════════════════════════
# КОНТЕКСТ АГЕНТ-К-АГЕНТУ: КАК ЭТО РАБОТАЕТ
# ═════════════════════════════════════════════════════════════════════════
#
# ИНФРАСТРУКТУРА:
# ───────────────────────────────────────────────────────────────────────────
# 1. system_prompt_builder.py — парсит [from:agent_name] теги из сообщения
# 2. compose_system() в base.py — вкладывает контекст в system prompt Виктории
# 3. run_agent() в base.py — передаёт контекст в handle() через параметр context
#
# ПОТОК ИНФОРМАЦИИ:
# ───────────────────────────────────────────────────────────────────────────
#
#   webapp.py / office.py (ввод от пользователя)
#         ↓
#   "Проверь пост [from: marina]"  ← таг в сообщении
#         ↓
#   system_prompt_builder.extract_context_from_message()
#         ↓
#   {"from_agent": "marina", "to_agent": None, "chain_id": None}
#         ↓
#   compose_system() вкладывает в system prompt:
#   "✓ Ты получила запрос от: marina"
#   "✓ Запрос пришел от Marina. Это может быть результат их работы..."
#         ↓
#   run_agent(..., context=...)
#         ↓
#   handle(name, inp, context) ← ЭТОТ КОНТЕКСТ
#
# ПРИМЕРЫ СЦЕНАРИЕВ:
# ───────────────────────────────────────────────────────────────────────────
#
# СЦЕНАРИЙ 1: Марина написала пост, просит одобрение
# ────────────────────────────────────────────────────────────────────────────
#   Марина (agent.py) → watson.send_message("marina", "Проверь пост [from: marina]")
#   ↓
#   Виктория получает (from_agent="marina")
#   ↓
#   В handle(): от Марины → требуй проверки голоса (она может быть близка к тексту)
#   ↓
#   Victoria → approve_post() или request_revisions()
#   ↓
#   Марина ждёт ответа перед публикацией
#
# СЦЕНАРИЙ 2: Пользователь напрямую просит проверить текст
# ────────────────────────────────────────────────────────────────────────────
#   webapp.py: пользователь вводит "Проверь пост про выбор" (БЕЗ [from:] тага)
#   ↓
#   system_prompt_builder → from_agent="user"
#   ↓
#   В handle(): обычная критика, как диалог с человеком
#   ↓
#   Victoria выводит оценку + фидбек
#
# СЦЕНАРИЙ 3: Оля исследовала тренд, хочет проверить текст
# ────────────────────────────────────────────────────────────────────────────
#   Оля (olya.py) → watson.send_message("victoria", "Проверь текст про тренд [from: olya]")
#   ↓
#   Виктория (from_agent="olya")
#   ↓
#   В handle(): адаптируй фидбек — не забыть про актуальность тренда
#   ↓
#   Victoria → approve_post() с контекстом о тренде
#   или → request_revisions() с примечанием про голос Людмилы
#
# СЦЕНАРИЙ 4: Цепочка работы (Марина → Виктория → Вася)
# ────────────────────────────────────────────────────────────────────────────
#   Марина пишет пост → victoria одобряет → vasya (планировщик) публикует
#   Контекст: chain_id="post_12345" отслеживает всю цепочку
#   В handle(): if chain_id → логируй переход на следующего агента
#
# ═════════════════════════════════════════════════════════════════════════

def handle(name, inp, context=None):
    """Обработать инструмент, адаптируясь к контексту запроса.

    Args:
        name: имя инструмента (generate_image, approve_post и т.д.)
        inp: параметры инструмента
        context: опциональный контекст {from_agent, to_agent, chain_id}
                 (вкладывается автоматически из system prompt)

    АДАПТАЦИЯ К КОНТЕКСТУ:
    ─────────────────────────────────────────────────────────────────
    • from_agent == "marina" — Марина (маркетер) может быть предвзята.
      Требуй более строгой проверки на соответствие голосу.

    • from_agent == "lera" (продажи) — текст может быть для презентации/звонка.
      Проверяй не только Instagram-стиль, но и профессиональность.

    • from_agent == "olya" (тренды) — Оля исследует тренды.
      Оцени релевантность волне + соответствие голосу.

    • from_agent == "user" — обычный запрос от человека.
      Стандартная критика как в диалоге.
    """

    # Парсим контекст из системного prompt если не передан явно
    if context is None:
        context = {}
    from_agent = context.get("from_agent", "user").lower()
    chain_id = context.get("chain_id", "")

    # Логируем для отладки
    if from_agent != "user" or chain_id:
        log("victoria", f"handle({name}) from={from_agent} chain={chain_id}")

    # ─── ИНСТРУМЕНТЫ ─────────────────────────────────────────────
    if name == "generate_image":
        return generate_image(
            inp.get("text", ""),
            inp.get("style", "minimalist"),
            inp.get("size", "1080x1350")
        )

    if name == "approve_post":
        post_id = inp.get("post_id", "")
        feedback = inp.get("feedback", "")

        # Если запрос от другого агента (например, Марина написала пост),
        # уведомляем об этом в логе для трейсинга цепочки
        if from_agent != "user":
            log("victoria", f"approve_post({post_id}) — Victoria одобрила пост от {from_agent}")

        return approve_post(post_id, feedback)

    if name == "request_revisions":
        post_id = inp.get("post_id", "")
        feedback = inp.get("feedback", "")

        # Адаптируем обратную связь к источнику
        if from_agent == "marina":
            # Марина хорошо знает Instagram, но может мисс что-то про голос Людмилы
            feedback_adapted = (
                f"[МАРИНА] {feedback}\n\n"
                f"↳ Помни о голосе Людмилы — читатель узнаёт себя в каждой фразе. "
                f"Не просто информация, а разговор."
            )
        elif from_agent == "olya":
            # Оля исследует тренды, важно сохранить актуальность
            feedback_adapted = (
                f"[ОЛЯ] {feedback}\n\n"
                f"↳ Тренд хороший, но давай проверим как он звучит голосом Людмилы. "
                f"Сейчас звучит может быть слишком трендово?"
            )
        elif from_agent == "lera":
            # Лёра может писать для презентаций, может нужен другой стиль
            feedback_adapted = (
                f"[ЛЁРА] {feedback}\n\n"
                f"↳ Если это для Instagram — нужен голос Людмилы. "
                f"Если для презентации/звонка — может быть более официально."
            )
        else:
            feedback_adapted = feedback

        if from_agent != "user":
            log("victoria", f"request_revisions({post_id}) от {from_agent}")

        return request_revisions(post_id, feedback_adapted)

    # ─── ОБЩИЕ ИНСТРУМЕНТЫ (из base.py) ───────────────────────────
    res = core_handle(name, inp)
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/проверь":   "Покажи все файлы в content/posts/ и проверь последний пост",
    "/посты":     "Прочитай все файлы из content/posts/ и оцени каждый по шкале 1-10",
    "/стиль":     "Объясни как звучит голос Людмилы — дай 3 примера правильного и неправильного",
    "/файлы":     "Покажи что есть в папке для проверки",
    "/сообщения": "Покажи сообщения от других агентов (Лера, Марина и т.д.)",
}

# Сообщения показываются динамически в handle, не добавляем в статический SYSTEM
# (иначе старые сообщения остаются в prompt forever и создают циклы)

if __name__ == "__main__":
    chat_loop("Виктория", "✍️", "green", SYSTEM, TOOLS, handle, QUICK)
