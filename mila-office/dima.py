"""Дима — Финансовый агент. python dima.py"""
from base import *

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
2. Сравниваешь с целями
3. Строишь прогнозы
4. Говоришь что нужно сделать чтобы вырасти
5. Ищешь узкие места в монетизации

СТРУКТУРА ДАННЫХ:
- 05-analytics/gumroad_*.csv — продажи практикума
- 05-analytics/sessions_*.txt — консультации
- 05-analytics/finance_*.xlsx — итоговые отчёты

СТИЛЬ: Конкретный, с цифрами. Говоришь правду даже если она неудобная."""

TOOLS = core_tools("Читать финансовые данные",
                   "Сохранить финансовый отчёт",
                   "Показать финансовые файлы",
                   list_default="05-analytics") + [
    {"name": "gumroad_sales", "description": "Получить продажи с Gumroad API",
     "input_schema": {"type": "object", "properties": {"period": {"type": "string", "default": "month"}}}},
]

def gumroad_sales(period="month"):
    token = GUMROAD_TOKEN
    if not token: return "⚠️ Нет GUMROAD_ACCESS_TOKEN в .env"
    try:
        r = requests.get("https://api.gumroad.com/v2/sales",
                        params={"access_token": token}, timeout=10)
        sales = r.json().get("sales", [])
        total = sum(float(s.get("price", 0))/100 for s in sales)
        return json.dumps({"count": len(sales), "total_usd": round(total, 2), "sales": sales[:5]}, indent=2)
    except Exception as e:
        return f"Gumroad ошибка: {e}"

def handle(name, inp):
    if name == "gumroad_sales": return gumroad_sales(inp.get("period", "month"))
    res = core_handle(name, inp, list_default="05-analytics")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/доход":    "Посчитай мой доход за этот месяц из всех источников",
    "/прогноз":  "При текущем темпе — сколько я заработаю за следующие 3 месяца?",
    "/gumroad":  "Покажи продажи практикума с Gumroad",
    "/цели":     "Сравни текущие результаты с целями бизнеса. Что нужно изменить?",
    "/отчёт":    "Создай полный финансовый отчёт за текущий месяц и сохрани",
}

if __name__ == "__main__":
    chat_loop("Дима", "💰", "yellow", SYSTEM, TOOLS, handle, QUICK)
