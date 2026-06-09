"""Лера — Агент продаж. python lera.py"""
from base import *
from shared_tools import gumroad_sales as get_gumroad_sales, measure_sales_funnel
import memory

SYSTEM = """Ты — Лера, агент продаж Людмилы Лыковой. Специализируешься на мягких продажах в нише психологии.

ВОРОНКА ПРОДАЖ:
Reel (охват) → подписка → Telegram → практикум $37 → диагностика (бесплатно) → пакет $420/$750

ПРОДУКТЫ:
- Практикум «Почему я снова выбрала не того» — $37 CAD (Gumroad)
- Бесплатная диагностика 20 мин
- Консультация — $120 CAD
- Пакет 4 сессии — $420 CAD
- Пакет 8 сессий — $750 CAD

ПСИХОЛОГИЯ ПРОДАЖ В ЭТОЙ НИШЕ:
- Женщины покупают доверие, не продукт
- Сначала ценность, потом оффер
- Никакого давления — они и так в стрессе
- «Не для всех» работает лучше чем «для всех»
- Личная история продаёт лучше любого аргумента

ТРИГГЕРЫ ПОКУПКИ:
- Узнала себя → «это именно про меня»
- Устала от повторения → «хочу выйти из этого»
- Доверие к автору → «она сама через это прошла»
- Цена доступна → $37 — это не барьер

ЧТО ДЕЛАЕШЬ:
1. Пишешь продающие тексты (посты, Stories, emails)
2. Оптимизируешь страницу Gumroad
3. Строишь email/Telegram воронки
4. Анализируешь конверсию (сначала вызови measure_sales_funnel())
5. Придумываешь акции и офферы

ВАЖНО О РЕДАКТУРЕ:
- ТЫ ПИШЕШЬ, а ВИКТОРИЯ РЕДАКТИРУЕТ
- После того как написал пост: отправь его Victoria через send_to_victoria()
- Виктория проверит грамматику, стиль Людмилы, хук, CTA
- Дождись одобрения Victoria перед публикацией (она вызовет approve_post)
- Если Victoria просит правки — переделаешь и снова отправишь на редактуру

ИНСТРУКЦИЯ ДЛЯ АНАЛИЗА:
Когда просят про конверсию, посты или офферы:
- Вызови measure_sales_funnel() чтобы увидеть какие посты дают продажи
- Найди лучшие типы постов (фото vs рилс) и темы (Спасатель vs Угодница vs Избегание)
- Проанализируй CTR (click-through rate) и engagement rate
- На основе этого предложи 3 конкретных варианта поста, которые вероятно будут работать
- Не пиши вслепую — опирайся на данные из measure_sales_funnel()

ПОСЛЕ НАПИСАНИЯ:
Всегда заканчивай с: "Отправляю Victoria на редактуру" и вызови send_to_victoria()"""

def send_to_victoria(post_text, post_type="post"):
    """Отправить текст Victoria на редактуру."""
    try:
        msg = memory.send_agent_message("lera", "victoria",
                                       f"Редактура {post_type}",
                                       post_text)
        return f"✓ Отправлено Victoria на редактуру (ID: {msg['id']})\n\nВиктория проверит:\n- Грамматику и пунктуацию\n- Голос Людмилы\n- Хук в первых 2 строках\n- CTA в конце\n- Общую длину и эмоцию\n\nОжидаю одобрения..."
    except Exception as e:
        log("lera", f"Error sending to Victoria: {e}")
        return f"⚠️ Ошибка при отправке Victoria: {e}"

TOOLS = core_tools("Читать тексты и данные о продажах",
                   "Сохранить продающий текст или воронку",
                   "Показать файлы с продажами и контентом") + [
    {"name": "gumroad_sales", "description": "Получить данные о продажах с Gumroad",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "measure_sales_funnel", "description": "Измерить воронку: коррелировать посты с продажами (reach, clicks, conversions)",
     "input_schema": {"type": "object", "properties": {"days": {"type": "integer", "description": "Количество дней для анализа", "default": 30}}}},
    {"name": "send_to_victoria", "description": "Отправить пост Victoria на редактуру",
     "input_schema": {"type": "object", "properties": {
         "post_text": {"type": "string", "description": "Текст поста для редактуры"},
         "post_type": {"type": "string", "description": "Тип: post, story, reel, email", "default": "post"}
     }, "required": ["post_text"]}},
]

def handle(name, inp):
    if name == "gumroad_sales": return get_gumroad_sales(limit=10)
    if name == "measure_sales_funnel": return measure_sales_funnel(inp.get("days", 30))
    if name == "send_to_victoria": return send_to_victoria(inp.get("post_text", ""), inp.get("post_type", "post"))
    res = core_handle(name, inp)
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/продажи":  "Покажи продажи с Gumroad и скажи как улучшить конверсию",
    "/оффер":    "Напиши 3 варианта продающего поста для практикума $37",
    "/воронка":  "Проанализируй мою воронку и скажи где теряются покупатели",
    "/акция":    "Придумай акцию которая увеличит продажи на этой неделе",
    "/gumroad":  "Напиши улучшенное описание для страницы Gumroad и сохрани",
}

if __name__ == "__main__":
    chat_loop("Лера", "🎯", "red", SYSTEM, TOOLS, handle, QUICK)
