# -*- coding: utf-8 -*-
"""Рита — архитектор цифровых продуктов."""
import glob
import json as _json
from base import *
from shared_tools import get_ig_posts_data, get_telegram_leads_data, get_purchases_data, check_supabase_access

SYSTEM = """Ты — Рита, product architect Людмилы Лыковой.

Твоя задача — превращать идею цифрового продукта в ясную структуру, которую Марина сможет написать, а Виктория отредактировать.

Работай для ниши: женщины 25-45, болезненные отношения, тревожная привязанность, метод Людмилы «Точки выбора».

ДВА РЕЖИМА РАБОТЫ:

А) АНАЛИЗ АУДИТОРИИ → ТЕМЫ (инструмент analyze_audience).
   Вызови analyze_audience, чтобы получить РЕАЛЬНЫЕ сигналы: топ-посты по
   вовлечённости (что заходит), боли из комментариев/лидов, экспертные темы профиля.
   На их основе предложи ТОП-3 ТЕМЫ для воркбука. По каждой теме:
   • боль аудитории (на каких данных видно — цитата/метрика, без выдумок);
   • обещание результата;
   • почему продастся (связь с воронкой $37→$120→пакеты);
   • черновое название.
   Если данных мало (комменты пустые / мало постов) — ЧЕСТНО скажи это и опирайся
   на экспертные темы профиля, помечая выводы как гипотезы, не как статистику.

Б) СТРУКТУРА ПРОДУКТА (когда тема выбрана).
   Формат ответа:
   1. Название продукта.
   2. Для кого и какое обещание результата.
   3. Структура: главы/модули в логическом порядке.
   4. Упражнения и рабочие страницы.
   5. Тон и ограничения: что обязательно сохранить в голосе Людмилы.
   6. Краткое ТЗ для Марины.

Не пиши полный текст продукта. Не придумывай неподтверждённые факты из биографии
Людмилы. Не используй данные клиентских сессий. Делай структуру продаваемой, но
терапевтически аккуратной."""

TOOLS = [
    {"name": "analyze_audience",
     "description": "Собрать реальные сигналы об аудитории и болях: топ-посты по "
                    "вовлечённости из reports/, боли из комментариев/лидов, экспертные "
                    "темы профиля. Используй ПЕРЕД тем как предлагать темы воркбука.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_ig_posts_data",
     "description": "Получить Instagram посты из Supabase за последние N дней (reach, likes, comments)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "get_telegram_leads_data",
     "description": "Получить Telegram лидов из Supabase (status: new/warm/hot/converted/inactive)",
     "input_schema": {"type": "object", "properties": {
         "status": {"type": "string", "default": "new"},
         "days": {"type": "integer", "default": 7}}}},
    {"name": "get_purchases_data",
     "description": "Получить покупки из Supabase (сумма, способ платежа, дата)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "check_supabase_access",
     "description": "Проверить статус доступа к Supabase (можно ли читать/писать)",
     "input_schema": {"type": "object", "properties": {}}},
] + core_tools(
    "Прочитать продуктовые материалы, аналитику или черновики",
    "Сохранить структуру продукта или заметку",
    "Показать файлы продуктов и бизнес-папок",
    list_default="products",
)


def _latest(prefix):
    """Свежий файл reports/<prefix>_*.json или None."""
    reports = MILA_FOLDER / "reports"
    files = sorted(reports.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def analyze_audience() -> str:
    """Собирает РЕАЛЬНЫЕ сигналы для выбора темы воркбука. Ничего не выдумывает:
    отдаёт модели сырьё (топ-посты, боли из комментов, темы профиля) + честные
    пометки о нехватке данных. Синтез в топ-3 темы делает сам агент по SYSTEM."""
    out = {"signals": {}, "gaps": []}

    # 1) Топ-посты по вовлечённости — что реально заходит аудитории.
    pf = _latest("posts")
    if pf:
        try:
            data = _json.loads(pf.read_text(encoding="utf-8"))
            posts = data.get("posts", data) if isinstance(data, dict) else data
            posts = [p for p in posts if isinstance(p, dict)]
            def _eng(p):
                return p.get("engagement") or (p.get("likes", 0) + p.get("comments", 0))
            top = sorted(posts, key=_eng, reverse=True)[:5]
            out["signals"]["top_posts"] = [{
                "caption": (p.get("caption") or "")[:160],
                "reach": p.get("reach"), "likes": p.get("likes"),
                "comments": p.get("comments"), "engagement": _eng(p),
            } for p in top]
            out["signals"]["posts_analyzed"] = len(posts)
        except Exception as e:
            out["gaps"].append(f"posts: ошибка чтения ({e})")
    else:
        out["gaps"].append("Нет файлов reports/posts_*.json — топ-темы по охвату недоступны.")

    # 2) Боли из комментариев/лидов (триггер-слова ХОЧУ/цена/…).
    cf = _latest("comments")
    if cf:
        try:
            data = _json.loads(cf.read_text(encoding="utf-8"))
            comments = data.get("comments", []) if isinstance(data, dict) else []
            leads = data.get("leads", []) if isinstance(data, dict) else []
            out["signals"]["comments_total"] = len(comments)
            out["signals"]["leads_total"] = len(leads)
            out["signals"]["lead_quotes"] = [(c.get("text") or "")[:140] for c in leads[:10]]
            if not comments:
                out["gaps"].append("Комментарии пусты (нет данных/прав) — боли из комментов недоступны, "
                                   "опирайся на темы профиля и топ-посты.")
        except Exception as e:
            out["gaps"].append(f"comments: ошибка чтения ({e})")
    else:
        out["gaps"].append("Нет файлов reports/comments_*.json.")

    # 3) Экспертные темы и ниша из профиля (всегда есть — defaults).
    try:
        import memory
        prof = memory.read_profile().get("business", {})
        out["signals"]["profile_topics"] = prof.get("top_topics", [])
        out["signals"]["audience"] = prof.get("audience", "")
        out["signals"]["funnel"] = prof.get("products", "")
    except Exception:
        pass

    out["instruction"] = ("По этим сигналам предложи ТОП-3 темы воркбука (см. режим А в "
                          "системном промпте). Где данных мало — помечай выводы как гипотезы.")
    return _json.dumps(out, ensure_ascii=False, indent=2)


def handle(name, inp):
    if name == "analyze_audience":
        return analyze_audience()
    if name == "get_ig_posts_data":
        return get_ig_posts_data(inp.get("days", 30))
    if name == "get_telegram_leads_data":
        return get_telegram_leads_data(inp.get("status"), inp.get("days", 7))
    if name == "get_purchases_data":
        return get_purchases_data(inp.get("days", 30))
    if name == "check_supabase_access":
        return check_supabase_access()
    res = core_handle(name, inp, list_default="products")
    return res if res is not None else f"Неизвестный инструмент: {name}"


QUICK = {
    "/темы":    "Запусти analyze_audience и предложи ТОП-3 темы для воркбука: по каждой — "
                "боль (на данных), обещание результата, почему продастся, черновое название.",
    "/воркбук": "Собери структуру воркбука: главы, упражнения, поток, promise, ограничения голоса.",
}


if __name__ == "__main__":
    chat_loop("Рита", "📚", "magenta", SYSTEM, TOOLS, handle, QUICK)
