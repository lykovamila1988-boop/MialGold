"""Тёма — Telegram-менеджер. python tyoma.py"""
from base import *
from shared_tools import telegram_send, telegram_get_updates, telegram_channel_stats
import memory

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
Короче. Одна мысль = одно сообщение. Без хэштегов.

ЧТО ДЕЛАЕШЬ:
1. Публикуешь сообщения в канал через Bot API
2. Ведёшь welcome-цепочку для новых подписчиков
3. Отвечаешь на «ХОЧУ» (через бота)
4. Создаёшь контент для канала
5. Смотришь статистику канала (всегда вызови telegram_channel_stats() когда спрашивают про статистику)

ИНСТРУКЦИЯ:
Когда просят про статистику или что работает:
- Вызови telegram_channel_stats() с chat_id канала (если не знаешь, спроси)
- Это покажет членов канала и основные метрики
- На основе этого предложи 2-3 конкретных шага для роста (время публикации, тип контента, etc)

ОЧЕРЕДЬ СООБЩЕНИЙ:
- Когда пишешь сообщение: используй send_to_queue() (асинхронно, без лишних диалогов)
- send_to_queue() поставит в очередь и скажет статус
- Это согласовано с Marina для Instagram comments — единая архитектура!

ВАЖНО: Никогда не публикуй без подтверждения если не сказано явно."""

def send_to_queue(text, channel_id="", chat_id=""):
    """Поставить Telegram-сообщение в очередь (асинхронно, как Marina комментарии)."""
    return memory.queue_message(
        "telegram",
        text,
        confirm=False,
        metadata={"channel_id": channel_id or chat_id}
    )

TOOLS = core_tools("Читать контент для публикации",
                   "Сохранить черновик или лог",
                   "Показать файлы Telegram",
                   list_default="04-telegram") + [
    {"name": "send_to_queue", "description": "Поставить сообщение в очередь для отправки в Telegram",
     "input_schema": {"type": "object", "properties": {
         "text": {"type": "string", "description": "Текст сообщения"},
         "channel_id": {"type": "string", "description": "ID канала (опционально)"}
     }, "required": ["text"]}},
    {"name": "telegram_get_updates", "description": "Получить новые сообщения боту (ХОЧУ и вопросы)",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "telegram_channel_stats", "description": "Получить статистику канала",
     "input_schema": {"type": "object", "properties": {"chat_id": {"type": "string"}}}},
]

def handle(name, inp):
    if name == "send_to_queue": return send_to_queue(inp.get("text", ""), inp.get("channel_id", ""))
    if name == "telegram_get_updates": return telegram_get_updates()
    if name == "telegram_channel_stats": return telegram_channel_stats(inp.get("chat_id", ""))
    res = core_handle(name, inp, list_default="04-telegram")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/новые":    "Проверь новые сообщения в боте и напиши ответы на ХОЧУ",
    "/пост":     "Прочитай контент из 04-telegram/ и подготовь пост для канала",
    "/цепочка":  "Прочитай welcome_sequence.txt и скажи когда что отправлять",
    "/создай":   "Создай 3 поста для Telegram на эту неделю в стиле Людмилы",
    "/статус":   "Покажи все файлы в 04-telegram/ и статус публикаций",
}

if __name__ == "__main__":
    chat_loop("Тёма", "💬", "blue", SYSTEM, TOOLS, handle, QUICK)
