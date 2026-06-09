"""Дима — Финансовый агент. python dima.py"""
from base import *
from shared_tools import gumroad_sales as get_gumroad_sales, calc_ltv_and_mrr, get_purchases_data, get_consultations_data, check_supabase_access
import memory

SYSTEM = """Ты — Дима, финансовый агент Людмилы Лыковой. Считаешь деньги, строишь прогнозы, отслеживаешь рост бизнеса.

ПРОДУКТЫ И ЦЕНЫ (CAD):
- PDF практикум: $37 CAD (Gumroad)
- Разовая консультация: $120 CAD
- Пакет 4 сессии: $420 CAD
- Пакет 8 сессий: $750 CAD
- Групповой разбор: $55 CAD/чел
- Telegram (план): $20 CAD/мес

ЦЕЛИ БИЗНЕСА:
- Месяц 1: $5,000–9,000 CAD
- Квартал 1: стабильные $5,000/мес
- Год 1: $60,000+ CAD

ЧТО ДЕЛАЕШЬ:
1. Считаешь доход за период (Gumroad + консультации)
2. Рассчитываешь LTV и MRR (всегда вызови calc_ltv_and_mrr())
3. Анализируешь repeat customers (кто купил дважды?)
4. Сравниваешь с целями
5. Строишь прогнозы и даёшь рекомендации по росту
6. Ищешь узкие места в монетизации

ИНСТРУКЦИЯ:
Когда просят про доход, LTV, прибыль или финансовый отчёт:
- Вызови calc_ltv_and_mrr() чтобы получить metrics (LTV, MRR, repeat rate)
- Это покажет тебе среднего клиента и потенциал допродаж
- На основе этого предложи 2-3 конкретных шага для роста (например: focus на repeat customers vs new acquisition)

СТРУКТУРА ДАННЫХ:
- 05-analytics/gumroad_*.csv — продажи практикума
- 05-analytics/sessions_*.txt — консультации
- 05-analytics/finance_*.xlsx — итоговые отчёты

СТИЛЬ: Конкретный, с цифрами. Говоришь правду даже если она неудобная."""

def automation_stats(days: int = 7) -> str:
    """Получить статистику успешности P1→P2→P3 (Marina→Victoria→Vasya).
    Показывает сколько постов дошло до каждого этапа и где теряются."""
    try:
        stats = memory.get_automation_stats(days=days)
        if stats.get("status") == "no_data":
            return "Нет данных по автоматизации. Запусти pipeline.py чтобы собрать статистику."

        import json
        return json.dumps(stats, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка при получении статистики: {e}"

TOOLS = core_tools("Читать финансовые данные",
                   "Сохранить финансовый отчёт",
                   "Показать финансовые файлы",
                   list_default="05-analytics") + [
    {"name": "gumroad_sales", "description": "Получить продажи с Gumroad API",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "calc_ltv_and_mrr", "description": "Рассчитать LTV (lifetime value) и MRR (monthly recurring revenue) + repeat rate",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "automation_stats", "description": "Статистика успешности P1→P2→P3 (какой % постов дошёл до публикации)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "description": "Количество дней для анализа", "default": 7}
     }}},
    {"name": "get_purchases_data", "description": "Получить покупки из Supabase (детальные данные: сумма, способ платежа, дата)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "get_consultations_data", "description": "Получить консультации из Supabase (завершённые, с датами)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "check_supabase_access", "description": "Проверить статус доступа к Supabase (диагностика блокировок)",
     "input_schema": {"type": "object", "properties": {}}},
]

def handle(name, inp):
    if name == "gumroad_sales": return get_gumroad_sales(limit=20)
    if name == "calc_ltv_and_mrr": return calc_ltv_and_mrr()
    if name == "automation_stats": return automation_stats(inp.get("days", 7))
    if name == "get_purchases_data": return get_purchases_data(inp.get("days", 30))
    if name == "get_consultations_data": return get_consultations_data(inp.get("days", 30))
    if name == "check_supabase_access": return check_supabase_access()
    res = core_handle(name, inp, list_default="05-analytics")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/доход":    "Посчитай мой доход за этот месяц из всех источников",
    "/прогноз":  "При текущем темпе — сколько я заработаю за следующие 3 месяца?",
    "/gumroad":  "Покажи продажи практикума с Gumroad",
    "/pipeline": "Какой % постов дошёл до публикации? Где пробка в P1→P2→P3?",
    "/цели":     "Сравни текущие результаты с целями бизнеса. Что нужно изменить?",
    "/отчёт":    "Создай полный финансовый отчёт за текущий месяц и сохрани",
}

if __name__ == "__main__":
    chat_loop("Дима", "💰", "yellow", SYSTEM, TOOLS, handle, QUICK)
