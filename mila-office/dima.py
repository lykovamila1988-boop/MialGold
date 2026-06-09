"""Дима — Финансовый агент. python dima.py"""
from base import *
from shared_tools import gumroad_sales as get_gumroad_sales, calc_ltv_and_mrr, get_purchases_data, get_consultations_data, check_supabase_access
import memory
import os

SYSTEM = """Ты — Дима, финансовый агент Людмилы Лыковой. Считаешь деньги, строишь прогнозы, отслеживаешь рост бизнеса.
Работаешь с доходом (revenue) и расходами (expenses) — каждый расход привязан к цепочке (chain_id) для полного анализа.

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

РАСХОДЫ И CHAIN_ID (Привязка расходов к цепочкам):
Chain_ID = уникальный идентификатор цепочки затрат/доходов. Примеры:
- content-post-20260608: пост Instagram (фотография, текст, запланирование)
- reel-production-20260610: рил (видеомонтаж, хостинг, аналитика)
- consultation-booking: консультация (встреча, зум, запись, анализ)
- email-campaign-news: email рассылка (рассылка, автоответчик, аналитика)
- paid-ads-instagram: платная реклама Instagram (ad spend, аналитика, конверсия)

ЖИЗНЕННЫЙ ЦИКЛ ЦЕПОЧКИ (chain_id):
Расход → Выход контента/услуги → Доход (покупки) → Аналитика → ROI

АНАЛИЗ ДОХОДНОСТИ ЦЕПОЧКИ:
1. Вызови get_expenses_by_chain(chain_id) — получишь все расходы по цепочке
2. Вызови get_revenue_by_chain(chain_id) — получишь доход, связанный с этой цепочкой
3. Вычисли ROI: (доход - расходы) / расходы × 100%
4. Сравни с целевым ROI (обычно 300%+ для контента, 150%+ для рекламы)

ЧТО ДЕЛАЕШЬ:
1. Считаешь доход за период (Gumroad + консультации)
2. Рассчитываешь LTV и MRR (всегда вызови calc_ltv_and_mrr())
3. Анализируешь repeat customers (кто купил дважды?)
4. Сравниваешь с целями
5. Строишь прогнозы и даёшь рекомендации по росту
6. НОВОЕ: Анализируешь эффективность каждой цепочки (chain_id) через ROI
7. НОВОЕ: Ищешь убыточные цепочки и даёшь рекомендации по оптимизации
8. НОВОЕ: Показываешь доход ДО и ПОСЛЕ расходов (net profit по цепочкам)

ИНСТРУКЦИЯ:
Когда просят про доход, LTV, прибыль или финансовый отчёт:
- Вызови calc_ltv_and_mrr() чтобы получить metrics (LTV, MRR, repeat rate)
- Это покажет тебе среднего клиента и потенциал допродаж
- На основе этого предложи 2-3 конкретных шага для роста (например: focus на repeat customers vs new acquisition)

Когда просят про конкретную цепочку (контент, рилы, реклама):
- Вызови get_expenses_by_chain(chain_id) и get_revenue_by_chain(chain_id)
- Покажи полный жизненный цикл: затраты → выход → доход → ROI
- Если ROI ниже целевого — предложи оптимизацию (сокращение затрат или увеличение выхода)

СТРУКТУРА ДАННЫХ:
- 05-analytics/gumroad_*.csv — продажи практикума
- 05-analytics/sessions_*.txt — консультации
- 05-analytics/expenses_*.xlsx — расходы (привязаны к chain_id)
- 05-analytics/chain_roi_*.json — ROI каждой цепочки
- 05-analytics/finance_*.xlsx — итоговые отчёты

СТИЛЬ: Конкретный, с цифрами. Говоришь правду даже если она неудобная.
При анализе цепочек: дай контекст (где деньги потекли, на что они пошли, какой результат).
Помни: каждый расход должен иметь соответствующий доход (или быть инвестицией в будущее)."""

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


def get_expenses_by_chain(chain_id: str) -> str:
    """Получить все расходы, привязанные к цепочке (chain_id).

    Chain_ID примеры:
    - content-post-YYYYMMDD: пост в Instagram
    - reel-production-YYYYMMDD: видеорил
    - paid-ads-instagram: платная реклама
    - consultation-booking: консультация
    - email-campaign-NAME: email рассылка

    Возвращает: список расходов с датой, категорией, суммой и описанием.
    """
    try:
        from pathlib import Path
        import json

        mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
        analytics_dir = mila_folder / "MILA-BUSINESS" / "05-analytics"

        # Пытаемся найти файл с расходами этой цепочки
        chain_file = analytics_dir / f"expenses_{chain_id}.json"

        if not chain_file.exists():
            return json.dumps({
                "status": "not_found",
                "chain_id": chain_id,
                "message": f"Нет записей расходов для цепочки {chain_id}",
                "available_chains": ["content-post-*", "reel-production-*", "paid-ads-instagram",
                                    "consultation-booking", "email-campaign-*"]
            }, ensure_ascii=False, indent=2)

        expenses = json.loads(chain_file.read_text(encoding="utf-8"))
        total_expense = sum(e.get("amount_cad", 0) for e in expenses)

        return json.dumps({
            "status": "ok",
            "chain_id": chain_id,
            "total_expense_cad": round(total_expense, 2),
            "count": len(expenses),
            "expenses": expenses
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка при получении расходов цепочки: {e}"


def get_revenue_by_chain(chain_id: str) -> str:
    """Получить доход, связанный с цепочкой (через метаданные покупок/консультаций).

    Возвращает: сумму дохода от покупок/консультаций, которые прошли через эту цепочку.
    """
    try:
        from pathlib import Path
        import json

        mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
        analytics_dir = mila_folder / "MILA-BUSINESS" / "05-analytics"

        # Пытаемся найти файл с доходом этой цепочки
        revenue_file = analytics_dir / f"revenue_{chain_id}.json"

        if not revenue_file.exists():
            return json.dumps({
                "status": "empty",
                "chain_id": chain_id,
                "total_revenue_cad": 0,
                "count": 0,
                "message": f"Нет записей дохода для цепочки {chain_id} (может быть слишком рано, нет конверсии)",
                "revenue": []
            }, ensure_ascii=False, indent=2)

        revenue = json.loads(revenue_file.read_text(encoding="utf-8"))
        total_revenue = sum(r.get("amount_cad", 0) for r in revenue)

        return json.dumps({
            "status": "ok",
            "chain_id": chain_id,
            "total_revenue_cad": round(total_revenue, 2),
            "count": len(revenue),
            "revenue": revenue
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка при получении дохода цепочки: {e}"


def calculate_chain_roi(chain_id: str) -> str:
    """Рассчитать ROI (Return on Investment) для цепочки.

    ROI = (доход - расходы) / расходы × 100%

    Интерпретация:
    - ROI > 300%: отличная цепочка (каждый доллар дал 4+ доллара дохода)
    - ROI 100-300%: хорошая цепочка
    - ROI 0-100%: слабая, нужна оптимизация
    - ROI < 0%: убыточная, нужны срочные правки
    """
    try:
        import json

        # Получаем расходы и доход
        expenses_str = get_expenses_by_chain(chain_id)
        revenue_str = get_revenue_by_chain(chain_id)

        expenses_data = json.loads(expenses_str)
        revenue_data = json.loads(revenue_str)

        total_expense = expenses_data.get("total_expense_cad", 0)
        total_revenue = revenue_data.get("total_revenue_cad", 0)

        if total_expense == 0:
            return json.dumps({
                "status": "no_expenses",
                "chain_id": chain_id,
                "message": "Нет записанных расходов для этой цепочки"
            }, ensure_ascii=False, indent=2)

        net_profit = total_revenue - total_expense
        roi_percent = round((net_profit / total_expense) * 100, 1)

        # Дай контекст для принятия решений
        if roi_percent >= 300:
            verdict = "✓ Отличная цепочка — инвестируй больше"
            decision = "Увеличь бюджет на эту цепочку (работает хорошо)"
        elif roi_percent >= 100:
            verdict = "✓ Хорошая цепочка — продолжай в том же духе"
            decision = "Поддерживай текущий уровень инвестиций"
        elif roi_percent >= 0:
            verdict = "⚠ Слабая цепочка — нужна оптимизация"
            decision = "Сократи расходы ИЛИ увеличь выход (продажи/конверсию)"
        else:
            verdict = "✗ Убыточная цепочка — срочные правки"
            decision = "Пересмотри стратегию или заморозь цепочку (ищи причину убытков)"

        return json.dumps({
            "status": "ok",
            "chain_id": chain_id,
            "total_expense_cad": total_expense,
            "total_revenue_cad": total_revenue,
            "net_profit_cad": round(net_profit, 2),
            "roi_percent": roi_percent,
            "verdict": verdict,
            "financial_decision": decision,
            "recommendation": "Смотри контекст выше (verdict + decision) для выбора следующего шага"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка при расчёте ROI: {e}"


def get_all_chains_summary() -> str:
    """Получить краткую сводку ROI по всем цепочкам.

    Показывает общую картину: какие цепочки работают, какие убыточны.
    """
    try:
        from pathlib import Path
        import json
        import re

        mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
        analytics_dir = mila_folder / "MILA-BUSINESS" / "05-analytics"

        # Ищем все файлы expenses_*.json
        chains = {}
        for expense_file in analytics_dir.glob("expenses_*.json"):
            chain_id = expense_file.stem.replace("expenses_", "")
            expenses_data = json.loads(expense_file.read_text(encoding="utf-8"))
            total_expense = sum(e.get("amount_cad", 0) for e in expenses_data)

            # Ищем соответствующий доход
            revenue_file = analytics_dir / f"revenue_{chain_id}.json"
            total_revenue = 0
            if revenue_file.exists():
                revenue_data = json.loads(revenue_file.read_text(encoding="utf-8"))
                total_revenue = sum(r.get("amount_cad", 0) for r in revenue_data)

            net_profit = total_revenue - total_expense
            roi = round((net_profit / total_expense) * 100, 1) if total_expense > 0 else 0

            chains[chain_id] = {
                "expense_cad": round(total_expense, 2),
                "revenue_cad": round(total_revenue, 2),
                "net_profit_cad": round(net_profit, 2),
                "roi_percent": roi,
                "status": "✓ отлично" if roi >= 300 else "✓ хорошо" if roi >= 100
                         else "⚠ слабо" if roi >= 0 else "✗ убыток"
            }

        if not chains:
            return json.dumps({
                "status": "no_data",
                "message": "Нет цепочек с записанными расходами",
                "hint": "Создайте файлы expenses_<chain_id>.json в 05-analytics/"
            }, ensure_ascii=False, indent=2)

        # Сортируем по ROI (убыточные первыми, чтобы заметить проблемы)
        sorted_chains = sorted(chains.items(), key=lambda x: x[1]["roi_percent"])

        summary = {
            "status": "ok",
            "total_chains": len(chains),
            "total_expense_cad": round(sum(c["expense_cad"] for c in chains.values()), 2),
            "total_revenue_cad": round(sum(c["revenue_cad"] for c in chains.values()), 2),
            "total_net_profit_cad": round(sum(c["net_profit_cad"] for c in chains.values()), 2),
            "chains_by_roi": {name: data for name, data in sorted_chains},
            "action_items": [
                f"СРОЧНО: {name} убыточна (ROI {data['roi_percent']}%)"
                for name, data in sorted_chains if data["roi_percent"] < 0
            ] or ["Все цепочки в прибыли ✓"]
        }

        return json.dumps(summary, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка при получении сводки цепочек: {e}"

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
    {"name": "get_purchases_data", "description": "Получить покупки из Supabase (детальные данные: сумма, способ платежи, дата)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "get_consultations_data", "description": "Получить консультации из Supabase (завершённые, с датами)",
     "input_schema": {"type": "object", "properties": {
         "days": {"type": "integer", "default": 30}}}},
    {"name": "check_supabase_access", "description": "Проверить статус доступа к Supabase (диагностика блокировок)",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_expenses_by_chain", "description": "Получить все расходы по цепочке (chain_id: content-post-*, reel-production-*, paid-ads-instagram, etc)",
     "input_schema": {"type": "object", "properties": {
         "chain_id": {"type": "string", "description": "ID цепочки (content-post-20260608, reel-production-*, paid-ads-instagram, consultation-booking, email-campaign-*)"}
     }, "required": ["chain_id"]}},
    {"name": "get_revenue_by_chain", "description": "Получить доход, связанный с цепочкой (покупки/консультации от этой цепочки)",
     "input_schema": {"type": "object", "properties": {
         "chain_id": {"type": "string", "description": "ID цепочки"}
     }, "required": ["chain_id"]}},
    {"name": "calculate_chain_roi", "description": "Рассчитать ROI для цепочки с финансовым контекстом и рекомендациями по решениям",
     "input_schema": {"type": "object", "properties": {
         "chain_id": {"type": "string", "description": "ID цепочки"}
     }, "required": ["chain_id"]}},
    {"name": "get_all_chains_summary", "description": "Получить сводку по всем цепочкам с ROI (какие работают, какие убыточны)",
     "input_schema": {"type": "object", "properties": {}}},
]

def handle(name, inp):
    if name == "gumroad_sales": return get_gumroad_sales(limit=20)
    if name == "calc_ltv_and_mrr": return calc_ltv_and_mrr()
    if name == "automation_stats": return automation_stats(inp.get("days", 7))
    if name == "get_purchases_data": return get_purchases_data(inp.get("days", 30))
    if name == "get_consultations_data": return get_consultations_data(inp.get("days", 30))
    if name == "check_supabase_access": return check_supabase_access()
    if name == "get_expenses_by_chain": return get_expenses_by_chain(inp.get("chain_id"))
    if name == "get_revenue_by_chain": return get_revenue_by_chain(inp.get("chain_id"))
    if name == "calculate_chain_roi": return calculate_chain_roi(inp.get("chain_id"))
    if name == "get_all_chains_summary": return get_all_chains_summary()
    res = core_handle(name, inp, list_default="05-analytics")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/доход":    "Посчитай мой доход за этот месяц из всех источников",
    "/прогноз":  "При текущем темпе — сколько я заработаю за следующие 3 месяца?",
    "/gumroad":  "Покажи продажи практикума с Gumroad",
    "/pipeline": "Какой % постов дошёл до публикации? Где пробка в P1→P2→P3?",
    "/цели":     "Сравни текущие результаты с целями бизнеса. Что нужно изменить?",
    "/отчёт":    "Создай полный финансовый отчёт за текущий месяц и сохрани",
    "/цепочки":  "Покажи ROI всех цепочек (контент, рилы, реклама, консультации). Какие работают?",
    "/roi":      "Рассчитай ROI для конкретной цепочки (например: content-post-20260608)",
}

if __name__ == "__main__":
    chat_loop("Дима", "💰", "yellow", SYSTEM, TOOLS, handle, QUICK)
