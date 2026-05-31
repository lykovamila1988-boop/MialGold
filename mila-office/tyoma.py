"""Тёма — Telegram-менеджер. python tyoma.py"""
from base import *

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
5. Смотришь статистику канала

ВАЖНО: Никогда не публикуй без подтверждения если не сказано явно."""

TOOLS = core_tools("Читать контент для публикации",
                   "Сохранить черновик или лог",
                   "Показать файлы Telegram",
                   list_default="04-telegram") + [
    {"name": "telegram_send", "description": "Отправить сообщение в Telegram канал",
     "input_schema": {"type": "object", "properties": {
         "chat_id": {"type": "string", "description": "ID канала, например @mila_channel"},
         "text": {"type": "string", "description": "Текст сообщения"},
         "confirm": {"type": "boolean", "description": "Требует подтверждения", "default": True}
     }, "required": ["chat_id", "text"]}},
    {"name": "telegram_get_updates", "description": "Получить новые сообщения боту (ХОЧУ и вопросы)",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "telegram_channel_stats", "description": "Получить статистику канала",
     "input_schema": {"type": "object", "properties": {"chat_id": {"type": "string"}}}},
]

def tg_send(chat_id, text, confirm=True):
    if not TELEGRAM_TOKEN: return "⚠️ Нет TELEGRAM_BOT_TOKEN в .env"
    if confirm: return f"📋 ЧЕРНОВИК (не опубликовано):\n\n{text}\n\nЧтобы опубликовать — скажи 'подтверди публикацию'"
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        data = r.json()
        if data.get("ok"):
            log("telegram", f"Sent to {chat_id}: {text[:50]}")
            return f"✓ Опубликовано! Message ID: {data['result']['message_id']}"
        return f"Ошибка: {data.get('description')}"
    except Exception as e: return f"Ошибка: {e}"

def tg_updates():
    if not TELEGRAM_TOKEN: return "⚠️ Нет TELEGRAM_BOT_TOKEN в .env"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"limit": 20}, timeout=10)
        updates = r.json().get("result", [])
        messages = []
        for u in updates:
            msg = u.get("message", {})
            if msg.get("text"):
                messages.append({
                    "from": msg.get("from", {}).get("first_name"),
                    "username": msg.get("from", {}).get("username"),
                    "text": msg.get("text"),
                    "time": msg.get("date")
                })
        return json.dumps(messages, ensure_ascii=False, indent=2)
    except Exception as e: return f"Ошибка: {e}"

def tg_stats(chat_id):
    if not TELEGRAM_TOKEN: return "⚠️ Нет TELEGRAM_BOT_TOKEN"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMemberCount",
            params={"chat_id": chat_id}, timeout=10)
        return json.dumps(r.json(), ensure_ascii=False, indent=2)
    except Exception as e: return f"Ошибка: {e}"

def handle(name, inp):
    if name == "telegram_send": return tg_send(inp["chat_id"], inp["text"], inp.get("confirm", True))
    if name == "telegram_get_updates": return tg_updates()
    if name == "telegram_channel_stats": return tg_stats(inp.get("chat_id", ""))
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
