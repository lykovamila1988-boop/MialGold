# -*- coding: utf-8 -*-
"""Кирилл — Продюсер эксперта. python producer.py

ПРОИЗВОДСТВЕННЫЙ КОНТЕКСТ И ЦЕПОЧКИ (CHAIN_ID TRACKING):
- Каждый план и стратегия отслеживаются через chain_id для полной истории
- from_agent показывает КТО запросил стратегию (user, manager, marketing, etc)
- Контекст цепочки влияет на МАСШТАБ И ПРИОРИТЕТ анализа:
  * from:user → полный стратегический ревью (квартальный план + все продукты)
  * from:marina → план контента под конкретную кампанию (2-4 недели)
  * from:lera → стратегия продаж и воронка (точки роста дохода)
  * from:vasya → график запуска и сроки (когда, на каком этапе цикла)
"""
from base import *
import json
from datetime import datetime
from pathlib import Path

# Директория для логирования контекста и цепочек продюсерских планов
PRODUCER_LOG_DIR = MILA_FOLDER / "MILA-BUSINESS" / "05-analytics" / "producer-chains"
PRODUCER_LOG_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = """Ты — Кирилл, продюсер эксперта Людмилы Лыковой (@liudmyla.lykova).

ЧЕМ ПРОДЮСЕР ОТЛИЧАЕТСЯ ОТ ОСТАЛЬНЫХ:
- Марина делает контент, Лера — продажи, Стас — операционку офиса.
- Ты отвечаешь за БИЗНЕС САМОГО ЭКСПЕРТА: продуктовую линейку, запуски,
  позиционирование и масштабирование дохода. Ты думаешь не «пост на завтра»,
  а «как за квартал вырасти в деньгах и смыслах».

ЭКСПЕРТ:
- Людмила Лыкова, психолог, Канада. Ниша — болезненные отношения, тревожная
  привязанность. Методология «Точки выбора»: Спасатель / Угодница / Избегание.
- Аудитория: женщины 25–45, русскоязычные, Instagram (~1400) + Telegram.
- Текущая линейка: практикум $37 CAD, консультация $120, пакеты $420 / $750.
- Цель: стабильные $5,000/мес → год 1 $60,000+ CAD.

ЧТО ТЫ ДЕЛАЕШЬ:
1. ПРОДУКТОВАЯ ЛИНЕЙКА — выстраиваешь лестницу: лид-магнит → трипвайр ($37) →
   основной продукт → премиум (пакеты, группа, наставничество). Закрываешь дыры.
2. ЗАПУСКИ — планируешь по фазам: прогрев → открытие продаж → дедлайн → закрытие.
   Считаешь цель запуска в деньгах и в заявках, расписываешь контент под каждую фазу.
3. ПОЗИЦИОНИРОВАНИЕ — большие смыслы и «почему именно она»: личная история
   (эмиграция, выгорание, путь к себе) + авторский метод. Отстройка от конкурентов.
4. МАСШТАБИРОВАНИЕ — где точки роста: цена, новый продукт, групповой формат,
   повторные продажи, удержание. Считаешь юнит-экономику и ставишь приоритеты.
5. УПАКОВКА ОФФЕРОВ — превращаешь экспертизу в понятный оффер: обещание,
   для кого, что внутри, результат, цена, почему сейчас.

ИНСТРУМЕНТЫ:
- read_file / write_file / list_files — материалы офиса (аналитика, контент, продукты).
- run_command — запуск скриптов из tools/ (аналитика Instagram, отчёты).
- log_deliverable — логирование выпусков и контекста для отслеживания цепочки.

КАК МЫСЛИШЬ:
- Сначала факты и числа (из файлов 05-analytics/, отчётов), потом стратегия.
- Каждый план измерим: цель в деньгах/заявках, сроки, как поймём что сработало.
- Бережёшь эксперта от выгорания: план должен быть выполнимым, не «10 запусков в месяц».
- Честно говоришь, если идея не взлетит или линейка дырявая.

ПРОИЗВОДСТВЕННЫЙ КОНТЕКСТ:
Каждый запрос приходит с from_agent и chain_id. Это влияет на масштаб:

from:user, chain_id: (есть) → Полный квартальный стратегический ревью
from:marina, chain_id: → План контента на 2-4 недели под кампанию
from:lera, chain_id: → Стратегия воронки продаж и точки роста доходов
from:vasya, chain_id: → График и сроки запуска (фазы и дедлайны)

ВАЖНО: Каждый план привязываешь к chain_id, логируешь его, связываешь с контентом
и результатами. Выпускаешь конкретные deliverables, не общие советы.

СТИЛЬ: стратегический, тёплый, конкретный. Эмодзи умеренно (🎬 🚀 📈 💡 ⚠️). По-русски.
"""

def _extract_context(inp: dict) -> dict:
    """Извлекает контекст цепочки из входящего сообщения.

    Возвращает:
    {
        'from_agent': str (user, marina, lera, vasya, etc),
        'chain_id': str (например: q2_2026_launch, content_campaign_062026, etc),
        'timestamp': str (ISO format),
        'has_context': bool (True если есть цепочка)
    }
    """
    from_agent = inp.get("from_agent", "user")
    chain_id = inp.get("chain_id", "")

    return {
        "from_agent": from_agent,
        "chain_id": chain_id or f"producer_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "has_context": bool(chain_id)
    }


def _log_deliverable(chain_id: str, from_agent: str, deliverable_type: str,
                    title: str, result: str, tags: list = None) -> None:
    """Логирует выпуск (план, оффер, стратегию) в файл цепочки.

    deliverable_type: 'product_line', 'launch_plan', 'positioning',
                     'scaling_strategy', 'offer', 'quarterly_review'
    """
    try:
        log_file = PRODUCER_LOG_DIR / f"{chain_id}.log"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "from_agent": from_agent,
            "deliverable_type": deliverable_type,
            "title": title,
            "tags": tags or [],
            "result_length": len(result),
            "result_preview": result[:300] if len(result) > 300 else result
        }

        # Append to log
        if log_file.exists():
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        else:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log("producer", f"Ошибка логирования выпуска: {e}")


def get_producer_context(inp: dict) -> str:
    """Показывает как контекст цепочки влияет на стратегию.

    Демонстрирует:
    1. Какой from_agent запросил (это меняет масштаб)
    2. Какая цепочка (это помогает отслеживать deliverables)
    3. Как история этой цепочки влияет на решения
    """
    ctx = _extract_context(inp)
    from_agent = ctx["from_agent"]
    chain_id = ctx["chain_id"]

    # Разные подходы в зависимости от from_agent
    strategy_scope = {
        "user": {
            "scale": "FULL BUSINESS REVIEW",
            "timeframe": "квартал (13 недель)",
            "focus": "все 5 пилларов продюсера: линейка, запуски, позиционирование, масштаб, офферы",
            "deliverables": "квартальный план + продуктовая архитектура + KPI дашборд",
            "decision_level": "стратегический"
        },
        "marina": {
            "scale": "CONTENT-DRIVEN STRATEGY",
            "timeframe": "2-4 недели (одна кампания)",
            "focus": "план запуска под конкретный контент, фазы, сроки, цели",
            "deliverables": "сценарий запуска + контент-план по фазам + целевые метрики",
            "decision_level": "операционный (когда, как много, в какие сроки)"
        },
        "lera": {
            "scale": "SALES FUNNEL & REVENUE",
            "timeframe": "месяц (текущий спринт продаж)",
            "focus": "точки роста дохода, воронка, цены, пакеты, удержание",
            "deliverables": "стратегия воронки + point growth + ценовая архитектура",
            "decision_level": "тактический (какой оффер, цена, условия)"
        },
        "vasya": {
            "scale": "TIMING & SCHEDULING",
            "timeframe": "неделя-две (окно публикации)",
            "focus": "когда стартовать, какие фазы, как размазать по календарю",
            "deliverables": "календарь фаз + дедлайны + точки ключевых действий",
            "decision_level": "логистический (сроки и графики)"
        },
    }

    approach = strategy_scope.get(from_agent, strategy_scope["user"])

    result = f"""🎬 КОНТЕКСТ ЦЕПОЧКИ ПРОДЮСЕРА

Chain ID: {chain_id}
From: {from_agent}
Timestamp: {ctx['timestamp']}
Has saved context: {ctx['has_context']}

📋 МАСШТАБ СТРАТЕГИИ:
- Уровень: {approach['scale']}
- Период: {approach['timeframe']}
- Фокус: {approach['focus']}
- Ожидаемые deliverables: {approach['deliverables']}
- Уровень решения: {approach['decision_level']}

🔗 Все выпуски этой цепочки будут зафиксированы в:
   {PRODUCER_LOG_DIR / f'{chain_id}.log'}

СОВЕТ: Если работаем в цепочке, упоминай chain_id в каждом выпуске,
чтобы отслеживать связь между планом, контентом и результатами.
"""
    return result


TOOLS = [
    {"name": "read_file", "description": "Читать материалы офиса: аналитику, контент, описания продуктов, отчёты",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Сохранить продуктовую линейку, план запуска, позиционирование, оффер",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"},
         "content": {"type": "string"},
         "chain_id": {"type": "string", "description": "Опционально: ID цепочки для логирования"},
         "deliverable_type": {"type": "string", "description": "Опционально: тип выпуска (product_line, launch_plan, positioning, scaling_strategy, offer)"},
         "tags": {"type": "array", "items": {"type": "string"}, "description": "Опционально: теги для классификации"}
     }, "required": ["path", "content"]}},
    {"name": "list_files", "description": "Показать содержимое папки офиса",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "default": ""}}}},
    {"name": "run_command", "description": "Запустить скрипт из tools/ (например аналитика Instagram)",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "get_producer_context", "description": "Показать как контекст цепочки влияет на стратегию и масштаб анализа",
     "input_schema": {"type": "object", "properties": {
         "from_agent": {"type": "string", "description": "Кто запросил (user, marina, lera, vasya, etc)"},
         "chain_id": {"type": "string", "description": "ID цепочки для отслеживания"}
     }}},
]

def handle(name, inp):
    if name == "read_file":
        return read_file(inp["path"])
    if name == "write_file":
        path = inp["path"]
        content = inp["content"]
        chain_id = inp.get("chain_id", "")
        deliverable_type = inp.get("deliverable_type", "")
        tags = inp.get("tags", [])

        # Логируем выпуск если есть контекст цепочки
        if chain_id or deliverable_type:
            ctx = _extract_context(inp)
            title = Path(path).stem
            _log_deliverable(
                chain_id=ctx["chain_id"],
                from_agent=ctx["from_agent"],
                deliverable_type=deliverable_type or "document",
                title=title,
                result=content,
                tags=tags
            )

        return write_file(path, content)

    if name == "list_files":
        return list_files(inp.get("path", ""))
    if name == "run_command":
        return run_command(inp["command"])
    if name == "get_producer_context":
        return get_producer_context(inp)
    return f"Неизвестный инструмент: {name}"

QUICK = {
    "/контекст":        "Покажи контекст цепочки — как масштаб стратегии зависит от того, кто запросил (user, marina, lera, vasya). Используй для понимания deliverables.",
    "/линейка":         "Проанализируй текущие продукты и выстрой продуктовую линейку: лид-магнит → трипвайр → основной → премиум. Где дыры и что добавить? Логируй в chain_id если есть.",
    "/запуск":          "Спланируй запуск по фазам (прогрев → открытие → дедлайн → закрытие) с целью в деньгах, заявках, контентом. Привяжи к chain_id для связи с контентом.",
    "/позиционирование": "Сформулируй позиционирование Людмилы: большие смыслы, отстройка от конкурентов, почему она. Логируй как выпуск к цепочке.",
    "/масштаб":         "Найди точки роста дохода на ближайший квартал с юнит-экономикой и приоритетами. Учитывай контекст (квартальный план vs операционный спринт).",
    "/оффер":           "Упакуй оффер (пакет/группа/наставничество): обещание, для кого, что внутри, результат, цена, почему сейчас. Зафиксируй как deliverable.",
}

if __name__ == "__main__":
    chat_loop("Кирилл", "🎬", "#C8962C", SYSTEM, TOOLS, handle, QUICK)
