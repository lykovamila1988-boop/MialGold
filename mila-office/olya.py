"""Оля — Исследователь трендов. python olya.py"""
from base import *

SYSTEM = """Ты — Оля, исследователь трендов и контент-стратег. Мониторишь что вирусится в нише психологии отношений.

НИША ЛЮДМИЛЫ:
- Болезненные отношения, тревожная привязанность
- Русскоязычная аудитория, женщины 25-45
- Instagram + Telegram

КОНКУРЕНТНАЯ СРЕДА:
Психология в русскоязычном Instagram очень конкурентная.
Уникальность Людмилы: личная история (эмиграция, депрессия), авторская методология, формат «подруга-эксперт».

ЧТО ДЕЛАЕШЬ:
1. Находишь вирусные темы прямо сейчас
2. Анализируешь почему контент залетает
3. Предлагаешь углы которые никто не занял
4. Смотришь что делают конкуренты
5. Даёшь конкретные хуки и заголовки

КАК ДУМАЕШЬ:
- Что болит у аудитории ПРЯМО СЕЙЧАС?
- Какой формат они смотрят до конца?
- Что они пересылают подругам?
- Какой хук цепляет в первые 3 секунды?

ВАЖНО: Даёшь конкретные примеры, не абстрактные советы."""

TOOLS = [
    {"name": "web_search", "description": "Поиск трендов и вирусного контента",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
] + core_tools("Читать аналитику и предыдущие отчёты",
               "Сохранить исследование и идеи",
               "Показать файлы аналитики",
               list_default="05-analytics")

def web_search(query: str) -> str:
    try:
        r = requests.get("https://duckduckgo.com/html/",
            params={"q": query, "kl": "ru-ru"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        from html.parser import HTMLParser
        class P(HTMLParser):
            def __init__(self):
                super().__init__(); self.results = []; self._cur = ""
            def handle_starttag(self, t, a):
                if t == "a": self._cur = ""
            def handle_data(self, d): self._cur += d
            def handle_endtag(self, t):
                if t == "a" and len(self._cur.strip()) > 20:
                    self.results.append(self._cur.strip())
        p = P(); p.feed(r.text)
        return "\n".join(p.results[:10]) or "Результаты не найдены"
    except Exception as e:
        return f"Поиск недоступен: {e}. Даю ответ на основе знаний."

def handle(name, inp):
    if name == "web_search": return web_search(inp["query"])
    res = core_handle(name, inp, list_default="05-analytics")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/тренды":       "Что сейчас вирусится в нише психологии отношений в Instagram? Дай 5 тем с хуками",
    "/хуки":         "Придумай 10 хуков для Reels которые заставят досмотреть до конца",
    "/конкуренты":   "Проанализируй что делают топ-психологи в Instagram. Что мне взять от них?",
    "/угол":         "Какие темы в нише НЕ заняты конкурентами? Где есть свободное место?",
    "/идеи":         "Дай 20 идей контента основанных на болях аудитории прямо сейчас",
}

if __name__ == "__main__":
    chat_loop("Оля", "🔍", "magenta", SYSTEM, TOOLS, handle, QUICK)
