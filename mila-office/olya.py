"""Оля — Исследователь трендов. python olya.py"""
from base import *
from shared_tools import get_weekly_analytics
import memory
# memory нужна для monitor_competitors (читает competitors.json) и управления конкурентами.
# Импортируем её ЯВНО так как используем add_competitor, remove_competitor.

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
2. Анализируешь почему контент залетает (используй get_weekly_analytics для проверки)
3. Предлагаешь углы которые никто не занял
4. Смотришь что делают конкуренты (monitor_competitors)
5. Даёшь конкретные хуки и заголовки

ИНСТРУМЕНТЫ:
- get_weekly_analytics() — сколько охвата, лайков, комментариев в прошлую неделю?
  Вызови перед анализом чтобы понимать что уже работает
- web_search() — найти вирусные темы и тренды
- monitor_competitors() — посмотреть что делают конкуренты

КАК ДУМАЕШЬ:
- Что болит у аудитории ПРЯМО СЕЙЧАС?
- Какой формат они смотрят до конца?
- Что они пересылают подругам?
- Какой хук цепляет в первые 3 секунды?

ВАЖНО: Даёшь конкретные примеры, не абстрактные советы."""

TOOLS = [
    {"name": "web_search", "description": "Поиск трендов и вирусного контента",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "monitor_competitors",
     "description": "Мониторинг топ-аккаунтов конкурентов из memory/competitors.json: по каждому "
                    "ищет свежие упоминания/контент в вебе. Используй, чтобы понять, что РАБОТАЕТ "
                    "на рынке прямо сейчас, и извлечь паттерн (а не копировать).",
     "input_schema": {"type": "object", "properties": {
         "limit": {"type": "integer", "description": "сколько аккаунтов проверить (по умолч. 8)"}}}},
    {"name": "add_competitor", "description": "Добавить аккаунт в список мониторинга",
     "input_schema": {"type": "object", "properties": {
         "handle": {"type": "string", "description": "Instagram ник (без @)"},
         "why_watch": {"type": "string", "description": "Почему смотрим (пишет про же темы, популярна в нише и т.д.)"}
     }, "required": ["handle", "why_watch"]}},
    {"name": "remove_competitor", "description": "Удалить аккаунт из списка мониторинга",
     "input_schema": {"type": "object", "properties": {
         "handle": {"type": "string", "description": "Instagram ник (без @)"}
     }, "required": ["handle"]}},
    {"name": "list_competitors", "description": "Показать список всех мониторируемых конкурентов",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_weekly_analytics", "description": "Получить еженедельную аналитику Instagram (охват, лайки, комментарии)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "description": "Количество дней (по умолч. 7)", "default": 7}}}},
] + core_tools("Читать аналитику и предыдущие отчёты",
               "Сохранить исследование и идеи",
               "Показать файлы аналитики",
               list_default="05-analytics")

# Ключ SerpApi (serpapi.com) из tools/.env — base уже загрузил его. Имя — SERP_API.
SERP_API_KEY = os.getenv("SERP_API", "").strip()


def web_search(query: str) -> str:
    """Веб-поиск. Первичный бэкенд — SerpApi (serpapi.com, ключ SERP_API из .env):
    структурированная Google-выдача с реальными ссылками (включая Instagram-посты).
    Фолбэк — DuckDuckGo lite (POST, без ключа), если SerpApi недоступен/исчерпан.
    Возвращает «заголовок — url» построчно."""

    def _serpapi(q):
        r = requests.get("https://serpapi.com/search.json",
                         params={"q": q, "engine": "google", "num": 10,
                                 "api_key": SERP_API_KEY}, timeout=25)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(data["error"])
        out = []
        for x in data.get("organic_results", []):
            title = (x.get("title") or "").strip()
            link = (x.get("link") or "").strip()
            if title:
                out.append(f"{title} — {link}" if link else title)
        return out

    def _ddg_lite(q):
        # lite.duckduckgo.com/lite/ (POST) — старый duckduckgo.com/html/ (GET) с 2026
        # отдаёт HTTP 202 anomaly (бан скрейпера). lite работает без ключа.
        from html.parser import HTMLParser
        r = requests.post("https://lite.duckduckgo.com/lite/", data={"q": q},
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                          timeout=12)
        r.raise_for_status()
        # <a class="result-link" href="URL">TITLE</a>
        class P(HTMLParser):
            def __init__(s): super().__init__(); s.cap=False; s.href=""; s.cur=""; s.out=[]
            def handle_starttag(s, t, a):
                if t == "a" and dict(a).get("class") == "result-link":
                    s.cap = True; s.cur = ""; s.href = dict(a).get("href", "")
            def handle_data(s, d):
                if s.cap: s.cur += d
            def handle_endtag(s, t):
                if t == "a" and s.cap:
                    if s.cur.strip():
                        s.out.append(f"{s.cur.strip()} — {s.href}" if s.href else s.cur.strip())
                    s.cap = False
        p = P(); p.feed(r.text)
        return p.out

    # 1) SerpApi если есть ключ; при любой ошибке (квота/сеть) — тихий фолбэк на DDG.
    if SERP_API_KEY:
        try:
            res = _serpapi(query)
            if res:
                return "\n".join(res[:10])
        except Exception:
            pass
    try:
        res = _ddg_lite(query)
        return "\n".join(res[:10]) or "Результаты не найдены"
    except Exception as e:
        return (f"Поиск недоступен: {e}. Отвечаю на основе знаний — "
                f"помечай такие выводы как непроверенные.")

def add_competitor(handle: str, why_watch: str) -> str:
    """Добавить аккаунт в список конкурентов для мониторинга."""
    try:
        result = memory.add_competitor(handle, why_watch)
        if result.get("status") == "exists":
            return f"⚠️ {handle} уже в списке мониторинга"
        return f"✓ {handle} добавлен в список конкурентов"
    except Exception as e:
        return f"Ошибка при добавлении: {e}"


def remove_competitor(handle: str) -> str:
    """Удалить аккаунт из списка мониторинга."""
    try:
        result = memory.remove_competitor(handle)
        if result.get("status") == "not_found":
            return f"⚠️ {handle} не найден в списке"
        return f"✓ {handle} удалён из списка конкурентов"
    except Exception as e:
        return f"Ошибка при удалении: {e}"


def list_competitors() -> str:
    """Показать список всех конкурентов."""
    try:
        competitors = memory.list_competitors()
        if not competitors:
            return "Список конкурентов пуст. Добавь аккаунты через add_competitor"

        result = ["📊 Мониторируемые конкуренты:\n"]
        for i, acc in enumerate(competitors, 1):
            handle = acc.get("handle", "?")
            why = acc.get("why_watch", "")
            result.append(f"{i}. @{handle}")
            if why:
                result.append(f"   Почему: {why}")

        return "\n".join(result)
    except Exception as e:
        return f"Ошибка при получении списка: {e}"


def monitor_competitors(limit: int = 8) -> str:
    """Читает memory/competitors.json и по каждому аккаунту ищет свежие
    упоминания/контент в вебе. Instagram API чужую аналитику не даёт — поэтому
    смотрим публичный веб. Возвращает сырьё для анализа паттернов (хуки/темы)."""
    try:
        data = memory.read_competitors()
    except Exception:
        return ("Память (memory.py) недоступна — список конкурентов не прочитать. "
                "Пока могу искать тренды через web_search по темам ниши.")
    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    if not accounts:
        return ("Список конкурентов пуст (memory/competitors.json). Попроси Людмилу "
                "заполнить 10–20 аккаунтов (ник + почему смотрим), тогда смогу мониторить. "
                "Пока могу искать тренды через web_search по темам ниши.")
    try:
        limit = max(1, min(int(limit or 8), len(accounts)))
    except (ValueError, TypeError):
        limit = min(8, len(accounts))
    out = [f"Мониторинг {limit} из {len(accounts)} аккаунтов (обновлён список: {data.get('updated','—')}):\n"]
    for acc in accounts[:limit]:
        handle_ = acc.get("handle", "?")
        why = acc.get("why_watch", "")
        q = f"{handle_} instagram reels"
        found = web_search(q)
        out.append(f"### {handle_}" + (f" — {why}" if why else ""))
        out.append(found[:600] if found else "(ничего не найдено)")
        out.append("")
    out.append("Задача: по этим данным извлеки ПОВТОРЯЮЩИЙСЯ паттерн (хук, структура, "
               "эмоц. триггер, тема), а не копируй. Передай Марине идею в голосе Людмилы.")
    return "\n".join(out)


def handle(name, inp):
    if name == "web_search": return web_search(inp["query"])
    if name == "monitor_competitors": return monitor_competitors(inp.get("limit", 8))
    if name == "add_competitor": return add_competitor(inp.get("handle", ""), inp.get("why_watch", ""))
    if name == "remove_competitor": return remove_competitor(inp.get("handle", ""))
    if name == "list_competitors": return list_competitors()
    if name == "get_weekly_analytics": return get_weekly_analytics(inp.get("days", 7))
    res = core_handle(name, inp, list_default="05-analytics")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/тренды":       "Что сейчас вирусится в нише психологии отношений в Instagram? Дай 5 тем с хуками",
    "/хуки":         "Придумай 10 хуков для Reels которые заставят досмотреть до конца",
    "/конкуренты":   "Запусти monitor_competitors по списку из competitors.json. Для каждого аккаунта "
                     "извлеки паттерн (хук/структура/тема), что повторяется — и что из этого взять Людмиле "
                     "под её голос. Не копируй, адаптируй.",
    "/угол":         "Какие темы в нише НЕ заняты конкурентами? Где есть свободное место?",
    "/идеи":         "Дай 20 идей контента основанных на болях аудитории прямо сейчас",
    "/бриф":         "Прочитай шаблон reels/_brief_template.md (read_file). Найди через web_search "
                     "1 свежую рабочую тему недели и заполни шаблон ПОЛНОСТЬЮ: тема, боль, хук в "
                     "первые 3 сек, раскадровка, ОДИН CTA (напиши ХОЧУ / ссылка в bio), голос Людмилы. "
                     "Верни готовый бриф в формате шаблона.",
}

if __name__ == "__main__":
    chat_loop("Оля", "🔍", "magenta", SYSTEM, TOOLS, handle, QUICK)
