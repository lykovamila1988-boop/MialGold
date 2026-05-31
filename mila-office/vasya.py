"""Вася — Планировщик публикаций. python vasya.py"""
from base import *

SYSTEM = """Ты — Вася, планировщик контента Людмилы Лыковой. Организуешь публикации, ведёшь расписание, следишь чтобы ничего не выходило вовремя.

РАСПИСАНИЕ:
- Instagram посты: Пн-Пт в 10:00 UTC (13:00 МСК / 7:00 Торонто)
- Stories: ежедневно 18:00 UTC
- Reels: Вт, Чт, Сб
- Пятница: обязательный оффер «места на диагностику»
- Telegram: 3-4 раза в неделю

ОПТИМАЛЬНОЕ ВРЕМЯ ДЛЯ РУССКОЯЗЫЧНОЙ АУДИТОРИИ:
- 8:00–10:00 МСК — утро, люди в транспорте
- 12:00–14:00 МСК — обед
- 19:00–22:00 МСК — вечер

ЧТО ДЕЛАЕШЬ:
1. Создаёшь расписание публикаций на неделю/месяц
2. Проверяешь что всё готово к публикации
3. Ставишь посты в очередь публикаций (schedule_post → pipeline) — они выходят по расписанию сами
4. Напоминаешь что нужно снять или написать
5. Ведёшь лог всех публикаций"""

TOOLS = core_tools("Читать контент-план и черновики",
                   "Сохранить расписание",
                   "Показать готовый контент",
                   list_default="content") + [
    {"name": "schedule_post", "description": "Запланировать пост на определённое время через Instagram API",
     "input_schema": {"type": "object", "properties": {
         "image_url": {"type": "string"},
         "caption": {"type": "string"},
         "publish_time_utc": {"type": "string", "description": "ISO 8601, e.g. 2024-01-15T10:00:00Z"}
     }, "required": ["image_url", "caption", "publish_time_utc"]}},
]

def schedule_post(image_url, caption, publish_time_utc):
    # У Instagram (flow instagram_login) нет нативного отложенного постинга,
    # поэтому ставим пост в очередь pipeline.py — раннер publish_due опубликует
    # его, когда наступит время (по Планировщику задач). Не публикуем сразу.
    try:
        import pipeline
    except Exception as e:
        return f"⚠️ Пайплайн недоступен: {e}"
    item = pipeline.enqueue("photo", image_url, caption, publish_time_utc,
                            status="approved", source="vasya")
    log("scheduler", f"Enqueued #{item['id']} @ {publish_time_utc} | {caption[:40]}")
    if item["status"] == "needs_media":
        return (f"Добавлено в очередь #{item['id']}, но без media_url — нужна публичная "
                f"ссылка на фото/видео, иначе пост не опубликуется.")
    return (f"✓ В очереди публикаций #{item['id']} на {publish_time_utc}. "
            f"Опубликует pipeline.py publish_due по расписанию (Планировщик задач).")

def handle(name, inp):
    if name == "schedule_post": return schedule_post(inp["image_url"], inp["caption"], inp["publish_time_utc"])
    res = core_handle(name, inp, list_default="content")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/план":     "Создай расписание публикаций на следующую неделю по всем каналам",
    "/готово":   "Покажи что готово к публикации в папке content/",
    "/сегодня":  "Что должно выйти сегодня? Всё готово?",
    "/месяц":    "Создай контент-план на месяц с темами и форматами по дням",
}

if __name__ == "__main__":
    chat_loop("Вася", "📅", "white", SYSTEM, TOOLS, handle, QUICK)
