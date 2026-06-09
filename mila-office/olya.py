"""Оля — Исследователь трендов. python olya.py

КОНТЕКСТ И ЦЕПОЧКИ (CHAIN_ID TRACKING):
- Каждый анализ отслеживается через chain_id для полной истории
- from_agent показывает КТО запросил тренд-анализ (user, marina, victoria, etc)
- Контекст цепочки влияет на ГЛУБИНУ И НАПРАВЛЕНИЕ анализа:
  * from:user → глубокий общий тренд-анализ
  * from:marina → анализ под пост (узкий угол)
  * from:victoria → тренды для редактуры (что резонирует с голосом)
  * from:vasya → временные тренды (что быстро вирусится)
"""
from base import *
from shared_tools import get_weekly_analytics, get_ig_posts_data, get_telegram_leads_data, check_supabase_access
import memory
import json
from datetime import datetime
from pathlib import Path

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
- get_trend_context() — показать как контекст цепочки влияет на анализ

КАК ДУМАЕШЬ:
- Что болит у аудитории ПРЯМО СЕЙЧАС?
- Какой формат они смотрят до конца?
- Что они пересылают подругам?
- Какой хук цепляет в первые 3 секунды?

КОНТЕКСТ ЦЕПОЧКИ:
Каждый запрос приходит с from_agent и chain_id. Это влияет на анализ:

from:user, chain_id: (есть) → Глубокий стратегический анализ, 5-10 тем
from:marina, chain_id: → Узкий анализ под конкретный пост (1-3 угла)
from:victoria, chain_id: → Фокус на голосе и резонансе с аудиторией
from:vasya, chain_id: → Тренды которые БЫСТРО вирусятся (час, день, неделя)

ВАЖНО: Даёшь конкретные примеры, не абстрактные советы. Логируй контекст анализа."""

TOOLS = [
    {"name": "web_search", "description": "Поиск трендов и вирусного контента",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "get_trend_context",
     "description": "Показать как контекст цепочки (from_agent, chain_id) влияет на глубину и направление анализа. "
                    "Используй перед основным анализом чтобы понять какой подход нужен.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "monitor_competitors",
     "description": "Мониторинг топ-аккаунтов конкурентов из memory/competitors.json: по каждому "
                    "ищет свежие упоминания/контент в вебе. Используй, чтобы понять, что РАБОТАЕТ "
                    "на рынке прямо сейчас, и извлечь паттерн (а не копировать). "
                    "Контекст (from_agent) меняет глубину анализа.",
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
    {"name": "get_weekly_analytics", "description": "Получить еженедельную аналитику Instagram (охват, лайки, комментарии). "
                                                     "Контекст: используется как базис для трендов (какой контент РАБОТАЕТ прямо сейчас).",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "description": "Количество дней (по умолч. 7)", "default": 7}}}},
    {"name": "get_ig_posts_data", "description": "Получить посты из Supabase (детальные метрики: reach, likes, comments)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "get_telegram_leads_data", "description": "Получить Telegram лидов из Supabase (статус, писали ли ХОЧУ)",
     "input_schema": {"type": "object", "properties": {
         "status": {"type": "string", "default": "new"},
         "days": {"type": "integer", "default": 7}}}},
    {"name": "check_supabase_access", "description": "Проверить статус доступа к Supabase",
     "input_schema": {"type": "object", "properties": {}}},
] + core_tools("Читать аналитику и предыдущие отчёты",
               "Сохранить исследование и идеи",
               "Показать файлы аналитики",
               list_default="05-analytics")

# Ключ SerpApi (serpapi.com) из tools/.env — base уже загрузил его. Имя — SERP_API.
SERP_API_KEY = os.getenv("SERP_API", "").strip()

# ─── CHAIN CONTEXT TRACKING ──────────────────────────────────────
# Логируем контекст анализа трендов для каждой цепочки

TRENDS_LOG_DIR = MILA_FOLDER / "MILA-BUSINESS" / "05-analytics" / "trends-chains"
TRENDS_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _extract_context(inp: dict) -> dict:
    """Извлекает контекст цепочки из входящего сообщения.

    Возвращает:
    {
        'from_agent': str (user, marina, victoria, vasya, etc),
        'chain_id': str (например: post_2026_06_08_1),
        'timestamp': str (ISO format),
        'has_context': bool (True если есть цепочка)
    }
    """
    from_agent = inp.get("from_agent", "user")
    chain_id = inp.get("chain_id", "")

    return {
        "from_agent": from_agent,
        "chain_id": chain_id or f"direct_trend_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "has_context": bool(chain_id)
    }


def _log_trend_analysis(chain_id: str, from_agent: str, analysis_type: str, result: str) -> None:
    """Логирует анализ в файл цепочки (для аналитики как контекст влияет на результат)."""
    try:
        log_file = TRENDS_LOG_DIR / f"{chain_id}.log"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "from_agent": from_agent,
            "analysis_type": analysis_type,  # trends, hooks, competitors, etc
            "result_length": len(result),
            "result_preview": result[:200] if len(result) > 200 else result
        }

        # Append to log
        if log_file.exists():
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        else:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log(f"olya", f"Error logging trend analysis: {e}")


def get_trend_context(inp: dict) -> str:
    """Показывает как контекст цепочки влияет на глубину анализа.

    Демонстрирует:
    1. Какой from_agent запросил (это меняет подход)
    2. Какая цепочка (это помогает отслеживать)
    3. Какие метрики влияют на анализ
    """
    ctx = _extract_context(inp)
    from_agent = ctx["from_agent"]
    chain_id = ctx["chain_id"]

    # Получаем текущую аналитику для контекста
    try:
        analytics = json.loads(get_weekly_analytics(days=7))
    except:
        analytics = {"status": "unavailable"}

    # Разные подходы в зависимости от from_agent
    analysis_approach = {
        "user": {
            "depth": "FULL",
            "scope": "5-10 глубоких тем + стратегический анализ",
            "timeline": "тренды на неделю-месяц",
            "detail": "все углы, конкуренты, паттерны"
        },
        "marina": {
            "depth": "NARROW",
            "scope": "2-3 угла конкретно под пост",
            "timeline": "что вирусится ТУТ И СЕЙЧАС",
            "detail": "только релевантное для написания"
        },
        "victoria": {
            "depth": "VOICE",
            "scope": "тренды которые резонируют с голосом Людмилы",
            "timeline": "долгоиграющие тренды",
            "detail": "фокус на аутентичности и соответствии бренду"
        },
        "vasya": {
            "depth": "TIMING",
            "scope": "что быстро вирусится (час, день)",
            "timeline": "микротренды и временные окна",
            "detail": "КОГДА публиковать, какой формат"
        },
        "rita": {
            "depth": "VISUAL",
            "scope": "визуальные тренды и эстетика",
            "timeline": "что сейчас смотрится в Reels",
            "detail": "палитра, стиль, эффекты"
        }
    }

    approach = analysis_approach.get(from_agent, analysis_approach["user"])

    result = f"""📊 КОНТЕКСТ АНАЛИЗА ТРЕНДОВ

┌─ Запрос пришёл ──────────────────────────────────────
│ От: {from_agent.upper()}
│ Цепочка: {chain_id}
│ Время: {ctx['timestamp']}
│ Контекст передан: {'✓ Да' if ctx['has_context'] else '✗ Нет'}
└──────────────────────────────────────────────────────

📈 ТЕКУЩАЯ АНАЛИТИКА (за 7 дней):
{json.dumps(analytics.get('summary', {}), ensure_ascii=False, indent=2) if analytics.get('status') == 'ok' else 'Недоступна'}

🎯 ПОДХОД АНАЛИЗА:
Глубина: {approach['depth']}
Охват: {approach['scope']}
Временной горизонт: {approach['timeline']}
Детальность: {approach['detail']}

💡 КАК ЭТО ВЛИЯЕТ НА РЕЗУЛЬТАТ:
- from:{from_agent} → фокусируюсь на {approach['scope']}
- Аналитика показывает текущую производительность контента
- Совмещаю веб-тренды с реальной статистикой Людмилы
- Результат: {approach['scope'].lower()} на основе фактических данных"""

    # Логируем этот анализ контекста
    _log_trend_analysis(chain_id, from_agent, "context_analysis", result)

    return result


def web_search(query: str, inp: dict = None) -> str:
    """Веб-поиск. Первичный бэкенд — SerpApi (serpapi.com, ключ SERP_API из .env):
    структурированная Google-выдача с реальными ссылками (включая Instagram-посты).
    Фолбэк — DuckDuckGo lite (POST, без ключа), если SerpApi недоступен/исчерпан.
    Возвращает «заголовок — url» построчно.

    Если передан inp с контекстом (from_agent, chain_id), логирует результат для аналитики.
    """

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
    result = None
    if SERP_API_KEY:
        try:
            res = _serpapi(query)
            if res:
                result = "\n".join(res[:10])
                # Логируем успешный поиск через SerpApi
                if inp:
                    ctx = _extract_context(inp)
                    _log_trend_analysis(ctx["chain_id"], ctx["from_agent"], "web_search_serpapi",
                                      f"query={query}, results={len(res)}")
                return result
        except Exception:
            pass
    try:
        res = _ddg_lite(query)
        result = "\n".join(res[:10]) or "Результаты не найдены"
        # Логируем поиск через DuckDuckGo
        if inp:
            ctx = _extract_context(inp)
            _log_trend_analysis(ctx["chain_id"], ctx["from_agent"], "web_search_ddg",
                              f"query={query}, results={len(res) if res else 0}")
        return result
    except Exception as e:
        msg = (f"Поиск недоступен: {e}. Отвечаю на основе знаний — "
               f"помечай такие выводы как непроверенные.")
        if inp:
            ctx = _extract_context(inp)
            _log_trend_analysis(ctx["chain_id"], ctx["from_agent"], "web_search_error", str(e))
        return msg

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


def monitor_competitors(limit: int = 8, inp: dict = None) -> str:
    """Читает memory/competitors.json и по каждому аккаунту ищет свежие
    упоминания/контент в вебе. Instagram API чужую аналитику не даёт — поэтому
    смотрим публичный веб. Возвращает сырьё для анализа паттернов (хуки/темы).

    Если передан inp с контекстом, логирует результат для аналитики цепочки.
    """
    ctx = _extract_context(inp) if inp else {"chain_id": "unknown", "from_agent": "unknown"}

    try:
        data = memory.read_competitors()
    except Exception as e:
        msg = ("Память (memory.py) недоступна — список конкурентов не прочитать. "
               "Пока могу искать тренды через web_search по темам ниши.")
        _log_trend_analysis(ctx["chain_id"], ctx["from_agent"], "monitor_competitors_error", str(e))
        return msg

    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    if not accounts:
        msg = ("Список конкурентов пуст (memory/competitors.json). Попроси Людмилу "
               "заполнить 10–20 аккаунтов (ник + почему смотрим), тогда смогу мониторить. "
               "Пока могу искать тренды через web_search по темам ниши.")
        _log_trend_analysis(ctx["chain_id"], ctx["from_agent"], "monitor_competitors_empty", "")
        return msg

    try:
        limit = max(1, min(int(limit or 8), len(accounts)))
    except (ValueError, TypeError):
        limit = min(8, len(accounts))

    out = [f"Мониторинг {limit} из {len(accounts)} аккаунтов (обновлён список: {data.get('updated','—')}):\n"]
    for acc in accounts[:limit]:
        handle_ = acc.get("handle", "?")
        why = acc.get("why_watch", "")
        q = f"{handle_} instagram reels"
        found = web_search(q, inp)
        out.append(f"### {handle_}" + (f" — {why}" if why else ""))
        out.append(found[:600] if found else "(ничего не найдено)")
        out.append("")

    out.append("Задача: по этим данным извлеки ПОВТОРЯЮЩИЙСЯ паттерн (хук, структура, "
               "эмоц. триггер, тема), а не копируй. Передай Марине идею в голосе Людмилы.")

    result = "\n".join(out)
    _log_trend_analysis(ctx["chain_id"], ctx["from_agent"], "monitor_competitors",
                       f"checked={limit} accounts, total_len={len(result)}")

    return result


def handle(name, inp):
    """Dispatcher для инструментов. Передаёт контекст (inp) где нужно для логирования цепочки."""
    if name == "web_search":
        return web_search(inp["query"], inp)  # Передаём контекст для логирования
    if name == "get_trend_context":
        return get_trend_context(inp)  # Демонстрация влияния контекста
    if name == "monitor_competitors":
        return monitor_competitors(inp.get("limit", 8), inp)  # Передаём контекст для логирования
    if name == "add_competitor":
        return add_competitor(inp.get("handle", ""), inp.get("why_watch", ""))
    if name == "remove_competitor":
        return remove_competitor(inp.get("handle", ""))
    if name == "list_competitors":
        return list_competitors()
    if name == "get_weekly_analytics":
        return get_weekly_analytics(inp.get("days", 7))
    if name == "get_ig_posts_data":
        return get_ig_posts_data(inp.get("days", 30))
    if name == "get_telegram_leads_data":
        return get_telegram_leads_data(inp.get("status"), inp.get("days", 7))
    if name == "check_supabase_access":
        return check_supabase_access()
    res = core_handle(name, inp, list_default="05-analytics")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/контекст":     "Покажи как контекст цепочки (от кого запрос, какая цепочка) влияет на глубину анализа. "
                     "Вызови get_trend_context и объясни какой подход Оля использует при от разных агентов.",
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
