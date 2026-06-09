"""Лера — Агент продаж. python lera.py"""
from base import *
from shared_tools import gumroad_sales as get_gumroad_sales, measure_sales_funnel
import memory
import uuid
from datetime import datetime

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
- «Не для всех» работает лучше чем «для всем»
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

КОНТЕКСТ ЗАПРОСОВ — РАЗНЫЕ ПОДХОДЫ:
[from: telegram] — Запрос из Telegram-последовательности: адаптируй текст под messenger (короче, прямолинейнее, ссылки разрешены)
[from: email] — Запрос из email-воронки: пишешь для длинного письма с историей, рекомендацией, мягкий оффер в конце
[from: content] — Запрос из контент-плана (Марина): пиши продающий пост с хуком, энергией, CTA «напиши ХОЧУ»
[from: user] — Прямой запрос от человека: полная гибкость, спрашивай уточнения если нужны

ПОСЛЕ НАПИСАНИЯ:
Всегда заканчивай с: "Отправляю Victoria на редактуру" и вызови send_to_victoria()"""

def send_to_victoria(post_text, post_type="post", context=None):
    """Отправить текст Victoria на редактуру с контекстом цепочки."""
    try:
        # Генерируем chain_id если его нет — для отслеживания цепочки обработки
        chain_id = context.get("chain_id") if context else None
        if not chain_id:
            chain_id = f"lera_{post_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        from_agent = context.get("from_agent", "user") if context else "user"

        # Добавляем контекст в вопрос для Victoria
        question_prefix = ""
        if from_agent == "telegram":
            question_prefix = "[from: telegram] Этот текст для Telegram. "
        elif from_agent == "email":
            question_prefix = "[from: email] Это часть email-воронки. "
        elif from_agent == "content":
            question_prefix = "[from: content] Это контент-пост из плана. "
        elif from_agent != "user":
            question_prefix = f"[from: {from_agent}] "

        msg = memory.send_agent_message("lera", "victoria",
                                       f"Редактура {post_type}",
                                       f"{question_prefix}[chain_id: {chain_id}]\n\n{post_text}")

        # Логируем отправку с контекстом
        log("lera.sales_context", f"send_to_victoria type={post_type} from={from_agent} chain={chain_id} msg_id={msg['id']}")

        return f"✓ Отправлено Victoria на редактуру (ID: {msg['id']}, цепочка: {chain_id})\n\nВиктория проверит:\n- Грамматику и пунктуацию\n- Голос Людмилы\n- Хук в первых 2 строках\n- CTA в конце\n- Общую длину и эмоцию\n\nОжидаю одобрения..."
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
    {"name": "send_to_victoria", "description": "Отправить пост Victoria на редактуру с сохранением контекста цепочки",
     "input_schema": {"type": "object", "properties": {
         "post_text": {"type": "string", "description": "Текст поста для редактуры"},
         "post_type": {"type": "string", "description": "Тип: post, story, reel, email, telegram, gumroad", "default": "post"},
         "chain_id": {"type": "string", "description": "ID цепочки обработки для отслеживания (опционально)"}
     }, "required": ["post_text"]}},
]

def handle(name, inp, context=None):
    if name == "gumroad_sales":
        return get_gumroad_sales(limit=10)
    if name == "measure_sales_funnel":
        return measure_sales_funnel(inp.get("days", 30))
    if name == "send_to_victoria":
        # Передаём контекст в send_to_victoria для отслеживания цепочки
        context_dict = context or {}
        return send_to_victoria(
            inp.get("post_text", ""),
            inp.get("post_type", "post"),
            context=context_dict
        )
    res = core_handle(name, inp)
    return res if res is not None else f"Неизвестный инструмент: {name}"

def get_sales_approach(from_agent):
    """Вернуть рекомендацию по подходу в зависимости от контекста запроса."""
    approaches = {
        "telegram": {
            "name": "Telegram-ориентированный",
            "style": "Прямой, конкретный, со ссылками (в мессенджере разрешены). Нет лирики — только факт и CTA.",
            "example": "✓ Длина: 150-300 символов\n✓ CTA: кнопка, ссылка или @username\n✓ Тон: как текст подруги в чате"
        },
        "email": {
            "name": "Email-ориентированный",
            "style": "Длинная форма, история → ценность → мягкий оффер. Рассказываем про жизнь, вводим товар как естественное решение.",
            "example": "✓ Длина: 800-1500 символов\n✓ Структура: личная история → триггер → решение → оффер\n✓ Тон: как письмо от подруги, которая волнуется"
        },
        "content": {
            "name": "Content-план ориентированный",
            "style": "Продающий пост с сильным хуком. Эмоция, идентификация, CTA «напиши ХОЧУ» или свайп для консультации.",
            "example": "✓ Длина: 250-600 символов\n✓ Хук: первые 2 строки цепляют\n✓ CTA: call-to-action, специфичный (напиши, проверь, узнай тест)"
        },
        "user": {
            "name": "Универсальный",
            "style": "Гибко в зависимости от задачи. Спрашиваем уточнения если они нужны.",
            "example": "✓ Уточняем формат, целевую аудиторию, цель\n✓ Адаптируемся под требования"
        }
    }
    return approaches.get(from_agent, approaches["user"])

def log_sales_chain(chain_id, action, details=""):
    """Логировать действие в цепочке продаж."""
    log("lera.sales_context", f"chain={chain_id} action={action} {details}")

QUICK = {
    "/продажи":  "Покажи продажи с Gumroad и скажи как улучшить конверсию",
    "/оффер":    "Напиши 3 варианта продающего поста для практикума $37",
    "/воронка":  "Проанализируй мою воронку и скажи где теряются покупатели",
    "/акция":    "Придумай акцию которая увеличит продажи на этой неделе",
    "/gumroad":  "Напиши улучшенное описание для страницы Gumroad и сохрани",
    "/подходы":  "Покажи разные продажные подходы (Telegram vs Email vs Content vs Universal)",
}

if __name__ == "__main__":
    # Поддержка контекста цепочки: если запуск из другого процесса с контекстом,
    # его можно передать через environment или аргументы
    context = {
        "from_agent": os.getenv("LERA_FROM_AGENT", "user"),
        "chain_id": os.getenv("LERA_CHAIN_ID"),
        "to_agent": "lera"
    }
    # Фильтруем пустые значения
    context = {k: v for k, v in context.items() if v}

    # Расширенный чат с контекстом
    client = get_client()
    console = Console()
    console.print(f"\n[bold]🎯 Лера готова к работе[/bold]")
    console.print(f"[dim]Команды: {' · '.join(QUICK.keys())} · /выход[/dim]\n")
    history = []

    while True:
        try:
            user = Prompt.ask(f"[bold]Ты[/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not user:
            continue
        if user == "/выход":
            break
        if user == "/помощь":
            for k, v in QUICK.items():
                console.print(f"  [bold]{k}[/bold] — {v}")
            continue
        if user == "/подходы":
            console.print("\n[bold cyan]Разные продажные подходы:[/bold cyan]\n")
            for agent_key, approach in [("telegram", get_sales_approach("telegram")),
                                       ("email", get_sales_approach("email")),
                                       ("content", get_sales_approach("content")),
                                       ("user", get_sales_approach("user"))]:
                console.print(f"[bold]{approach['name']}:[/bold]")
                console.print(f"  {approach['style']}\n  {approach['example']}\n")
            continue

        msg = QUICK.get(user, user)
        console.print(f"\n[bold red]Лера:[/bold red]", end=" ")
        try:
            # Проверяем контекст в сообщении и извлекаем если есть
            extracted_context = None
            if system_prompt_builder:
                extracted_context = system_prompt_builder.extract_context_from_message(msg)

            # Объединяем контекст из переменных окружения и извлеченный из сообщения
            full_context = {**context}
            if extracted_context:
                full_context.update(extracted_context)

            # Передаём контекст в run_agent
            reply, history = run_agent(client, SYSTEM, TOOLS, handle, msg, history,
                                      agent_key="lera", context=full_context if full_context else None)
            console.print(Markdown(reply))
        except Exception as e:
            console.print(f"[red]Ошибка: {e}[/red]")
