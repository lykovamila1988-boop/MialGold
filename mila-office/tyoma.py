"""Тёма — Telegram-менеджер. python tyoma.py

Телеграм-контекст:
- Отслеживает цепочки постов (chain_id) для кросс-постинга (Instagram → Telegram)
- Синхронизирует контент с Marina (социальная сеть) по единой очереди сообщений
- Ведёт статистику охвата по типам контента (инсайты, кейсы, практики)
"""
from base import *
from shared_tools import telegram_send, telegram_get_updates, telegram_channel_stats
import memory
import json
from datetime import datetime

# TELEGRAM_CHANNEL_ID из .env используется как default для всех функций
# Если агент не передал chat_id — автоматически публикуется в основной канал

SYSTEM = """Ты — Тёма, менеджер Telegram-канала Людмилы Лыковой (@liudmyla.lykova).

КАНАЛ:
Бесплатный Telegram-канал как воронка: подписчики → прогрев → покупка практикума → консультация.

СТРАТЕГИЯ:
- Welcome-цепочка 5 сообщений (уже создана в 04-telegram/)
- Контент 3-4 раза в неделю: инсайты, кейсы, практики
- Пятница: оффер на диагностику
- Пост о практикуме раз в 2 недели

ГОЛОС ЛЮДМИЛЫ ДЛЯ TELEGRAM:
Более личный чем Instagram. Как дневник эксперта.
Короче. Одна мысль = одно сообщение. Без хэштегов. Ссылки на сайт только в Telegram (в Instagram это запрещено).

АРХИТЕКТУРА ПУБЛИКАЦИЙ:
Telegram = ЗЕРКАЛО Instagram + ДОПОЛНЕНИЕ (ссылки на практикум/консультации). Контент идёт через unified message queue:
1. Marina создаёт пост в 02-content/ → кладёт в очередь с type=instagram
2. Васе ставится chain_id (уникальный ID цепочки постов)
3. Тёма видит тот же chain_id → понимает что это кросс-пост и привязывает к исходному посту
4. Telegram-версия: поддерживает ссылки + кнопки (Instagram этого не позволяет)

УМНЫЙ КРОСС-ПОСТИНГ:
- INSTAGRAM ТОЛЬКО: политические/личные посты (не идут в Telegram)
- INSTAGRAM + TELEGRAM: контент про отношения, паттерны, диагностика
- Одна цепочка (chain_id) = один контент в двух местах с адаптацией голоса

ЧТО ДЕЛАЕШЬ:
1. Публикуешь сообщения в канал через Bot API
2. Ведёшь welcome-цепочку для новых подписчиков (через очередь сообщений)
3. Отвечаешь на «ХОЧУ» (через бота) и ссылаешь на консультацию
4. Создаёшь контент для канала (3-4 раза в неделю)
5. Мониторишь статистику канала (members count, инсайты о том что работает)
6. Отслеживаешь цепочки постов (chain_id) из Instagram для синхронизации

ИНСТРУКЦИЯ ПО ОЧЕРЕДИ:
- Когда пишешь сообщение в Telegram: используй send_to_queue() (асинхронно)
- send_to_queue() с chain_id привязывает сообщение к Instagram версии
- metadata содержит: {channel_id, chain_id, source, content_type}
- Это синхронизировано с Marina — одна архитектура для Instagram comments + Telegram

СТАТИСТИКА:
Вызови telegram_channel_stats() для:
- Количества подписчиков
- Активных пользователей
- Лучшего времени для постов (анализируем через очередь)"""

def send_to_queue(text, channel_id="", chat_id="", chain_id="", content_type=""):
    """Поставить Telegram-сообщение в очередь (асинхронно, как Marina комментарии).

    Args:
        text: текст сообщения
        channel_id: ID канала (default: TELEGRAM_CHANNEL_ID из .env)
        chat_id: ID чата / пользователя (если DM, то имеет приоритет над channel_id)
        chain_id: ID цепочки постов (для кросс-постинга с Instagram). Если пусто — создаём новый
        content_type: тип контента (инсайт, кейс, практика, оффер, диагностика)

    Returns: {status, message, id, chain_id}
    """
    # Если есть chain_id — это кросс-пост (синхронизация с Instagram)
    # Если нет chain_id — самостоятельный пост только для Telegram
    if not chain_id:
        # Генерируем новый chain_id для независимого Telegram поста
        import uuid
        chain_id = f"tg_{str(uuid.uuid4())[:8]}"

    # Использовать channel_id или TELEGRAM_CHANNEL_ID из .env как default
    final_channel_id = channel_id or TELEGRAM_CHANNEL_ID
    final_chat_id = chat_id or final_channel_id

    metadata = {
        "channel_id": final_channel_id,
        "chat_id": final_chat_id,
        "chain_id": chain_id,
        "source": "telegram",
        "content_type": content_type or "general",
        "created_at": datetime.now().isoformat()
    }

    result = memory.queue_message(
        "telegram",
        text,
        confirm=False,
        metadata=metadata
    )

    # Добавляем chain_id в ответ для отслеживания
    if isinstance(result, dict):
        result["chain_id"] = chain_id

    return result

TOOLS = core_tools("Читать контент для публикации",
                   "Сохранить черновик или лог",
                   "Показать файлы Telegram",
                   list_default="04-telegram") + [
    {"name": "send_to_queue", "description": "Поставить сообщение в очередь для отправки в Telegram (или синхронизировать с Instagram через chain_id)",
     "input_schema": {"type": "object", "properties": {
         "text": {"type": "string", "description": "Текст сообщения для Telegram"},
         "channel_id": {"type": "string", "description": "ID канала (опционально, если публикация в канал)"},
         "chat_id": {"type": "string", "description": "ID чата/пользователя (опционально, если DM)"},
         "chain_id": {"type": "string", "description": "ID цепочки постов из Instagram (для кросс-постинга). Если пусто — самостоятельный Telegram пост"},
         "content_type": {"type": "string", "description": "Тип контента: инсайт, кейс, практика, оффер, диагностика, welcome"}
     }, "required": ["text"]}},
    {"name": "telegram_get_updates", "description": "Получить новые сообщения боту (ХОЧУ и вопросы)",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "telegram_channel_stats", "description": "Получить статистику канала (количество подписчиков, активность)",
     "input_schema": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID канала для статистики"}}}},
    {"name": "get_cross_post_context", "description": "Получить контекст поста из Instagram для адаптации под Telegram (по chain_id)",
     "input_schema": {"type": "object", "properties": {
         "chain_id": {"type": "string", "description": "ID цепочки постов из Instagram"}
     }, "required": ["chain_id"]}},
    {"name": "list_pending_telegram", "description": "Показать очередь ожидающих Telegram сообщений",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Сколько показать (по умолчанию 10)"}}}},
]

def get_cross_post_context(chain_id):
    """Получить контекст Instagram поста для адаптации под Telegram.

    Если chain_id начинается с 'ig_' — это Instagram пост, ищем его в очереди.
    Возвращает оригинальный контент, чтобы Тёма мог адаптировать под Telegram.
    """
    if not chain_id:
        return {"ok": False, "error": "chain_id is required"}

    try:
        # Ищем в очереди сообщений Instagram пост с этим chain_id
        pending = memory.get_pending_messages(channel="instagram_comments", limit=100)
        for msg in pending:
            if msg.get("metadata", {}).get("chain_id") == chain_id:
                return {
                    "ok": True,
                    "found": True,
                    "chain_id": chain_id,
                    "original_text": msg.get("text", "")[:500],
                    "original_type": msg.get("metadata", {}).get("content_type", "general"),
                    "source": "instagram",
                    "note": "Адаптируй этот контент для Telegram: добавь ссылки на практикум/консультацию, сделай текст короче, используй эмодзи"
                }
        # Если не нашли в очереди — может быть уже опубликовано
        return {
            "ok": True,
            "found": False,
            "chain_id": chain_id,
            "note": "Пост может быть уже опубликован в Instagram. Скажи что публиковать в Telegram."
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_pending_telegram(limit=10):
    """Показать очередь ожидающих Telegram сообщений."""
    try:
        pending = memory.get_pending_messages(channel="telegram", limit=limit)
        if not pending:
            return {"status": "empty", "message": "Очередь пуста — всё отправлено!"}

        formatted = []
        for msg in pending:
            meta = msg.get("metadata", {})
            formatted.append({
                "id": msg.get("id"),
                "text": msg.get("text", "")[:100] + ("..." if len(msg.get("text", "")) > 100 else ""),
                "status": msg.get("status"),
                "type": meta.get("content_type", "general"),
                "chain_id": meta.get("chain_id", "—"),
                "created_at": msg.get("created_at", "")
            })

        return {
            "status": "ok",
            "count": len(pending),
            "limit": limit,
            "items": formatted
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def handle(name, inp):
    if name == "send_to_queue":
        return send_to_queue(
            inp.get("text", ""),
            channel_id=inp.get("channel_id", ""),
            chat_id=inp.get("chat_id", ""),
            chain_id=inp.get("chain_id", ""),
            content_type=inp.get("content_type", "")
        )
    if name == "telegram_get_updates":
        return telegram_get_updates()
    if name == "telegram_channel_stats":
        return telegram_channel_stats(inp.get("chat_id", ""))
    if name == "get_cross_post_context":
        return json.dumps(get_cross_post_context(inp.get("chain_id", "")), ensure_ascii=False, indent=2)
    if name == "list_pending_telegram":
        return json.dumps(list_pending_telegram(inp.get("limit", 10)), ensure_ascii=False, indent=2)
    res = core_handle(name, inp, list_default="04-telegram")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/новые":         "Проверь новые сообщения в боте и напиши ответы на ХОЧУ (как Марина делает для Instagram comments)",
    "/пост":          "Прочитай контент из 04-telegram/ и подготовь пост для канала",
    "/цепочка":       "Прочитай welcome_sequence.txt и поставь в очередь welcome-цепочку для новых подписчиков",
    "/создай":        "Создай 3 поста для Telegram на эту неделю (инсайты, кейсы, оффер на пятницу)",
    "/статус":        "Покажи статус: очередь сообщений + статистика канала (members count)",
    "/синхро":        "Проверь что нового в Instagram (Marina) и адаптируй под Telegram (кросс-постинг)",
    "/кросс CHAIN_ID": "Адаптируй Instagram пост (по chain_id) для Telegram: добавь ссылки, сделай короче",
    "/очередь":       "Покажи список ожидающих Telegram сообщений в очереди",
}

if __name__ == "__main__":
    chat_loop("Тёма", "💬", "blue", SYSTEM, TOOLS, handle, QUICK)
