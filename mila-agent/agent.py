r"""
MILA Agent — Марина (локальный CLI-режим) для @liudmyla.lykova.

Тонкая обёртка над канонической реализацией mila-office/agent.py. Раньше это
был почти полный дубль (~460 одинаковых строк); теперь отличие только в системном
промпте — добавлен раздел INSTAGRAM с готовыми командами из tools/.

Запуск: python agent.py

═══════════════════════════════════════════════════════════════════════════════
КАК РАБОТАЕТ КОНТЕКСТ ЗАПРОСА (from_agent)
═══════════════════════════════════════════════════════════════════════════════

Марина может получить запрос непосредственно от пользователя или от другого агента
в цепочке (например, Виктория обработала контент, потом передала результат Марине).

ИЗВЛЕЧЕНИЕ КОНТЕКСТА В handle():

  def handle(name: str, inputs: dict) -> str:
      # Контекст может быть в inputs:
      context = inputs.get('_context', {})
      from_agent = context.get('from_agent', 'user')
      chain_id = context.get('chain_id')

      if from_agent != 'user':
          # Запрос пришёл от другого агента
          console.print(f"[yellow]Получила запрос от {from_agent}[/yellow]")

      return run_tool(name, inputs)

ФОРМАТЫ ТЕГОВ В СООБЩЕНИИ:

  Пример 1 — прямой запрос от пользователя (по умолчанию):
    "Проанализируй статистику постов"
    → контекст: from_agent='user'

  Пример 2 — запрос от Виктории (редактора):
    "[from: victoria] Обработала 5 постов, нужна твоя стратегия для каждого"
    → контекст: from_agent='victoria', to_agent=None, chain_id=None

  Пример 3 — запрос от Олеси (тренды) с идентификатором цепочки:
    "[from: olya] [chain_id: week_2026_06_08] Выявила 3 тренда, сделай контент"
    → контекст: from_agent='olya', chain_id='week_2026_06_08'

  Пример 4 — запрос от Дима с адресацией результата:
    "[from: dima] [to: victoria] Вот продажи, обработай для поста"
    → контекст: from_agent='dima', to_agent='victoria'

КАК ИСПОЛЬЗОВАТЬ КОНТЕКСТ ВНУТРИ handle():

  1. БАЗОВЫЙ ПРИМЕР (просто читаем контекст):

     def handle(name: str, inputs: dict) -> str:
         context = inputs.get('_context', {})
         from_agent = context.get('from_agent', 'user')

         if from_agent == 'victoria':
             # Victoria редактировала контент — нужна стратегия
             # Например, добавляем инструкцию в system prompt
             pass

         return run_tool(name, inputs)

  2. РАСШИРЕННЫЙ ПРИМЕР (форматируем инструкции по контексту):

     def handle(name: str, inputs: dict) -> str:
         context = inputs.get('_context', {})
         from_agent = context.get('from_agent', 'user')
         to_agent = context.get('to_agent')
         chain_id = context.get('chain_id')

         # Добавляем контекст в система prompt (через run_agent)
         if from_agent != 'user':
             note = f"Запрос пришёл от {from_agent}"
             if to_agent:
                 note += f", результат нужен {to_agent}"
             if chain_id:
                 note += f" (цепочка {chain_id})"
             console.print(f"[cyan]{note}[/cyan]")

         return run_tool(name, inputs)

  3. ПОЛНЫЙ ПРИМЕР (С КОНТЕКСТОМ В СИСТЕМНОМ ПРОМПТЕ):

     def handle(name: str, inputs: dict) -> str:
         context = inputs.get('_context', {})

         # Если контекст есть, дополняем system prompt
         system = SYSTEM_PROMPT
         if context and context.get('from_agent') != 'user':
             from_agent = context['from_agent']
             to_agent = context.get('to_agent')
             chain_id = context.get('chain_id')

             system += f"\n\n[КОНТЕКСТ ЗАПРОСА]\n"
             system += f"Ты получила запрос от {from_agent}.\n"
             if to_agent:
                 system += f"Результат нужен {to_agent}.\n"
             if chain_id:
                 system += f"Цепочка обработки: {chain_id}\n"

         # Передаём enhanced system в run_agent
         return run_agent(user_message, history, context=context)

     def run_agent(user_message: str, history: list, context: dict = None):
         return base.run_agent(
             client, SYSTEM_PROMPT, TOOLS, run_tool,
             user_message, history, agent_key="marina", context=context
         )

ПРИМЕРЫ СЦЕНАРИЕВ:

  Сценарий А: Виктория редактировала посты, Марине нужна стратегия
  ──────────────────────────────────────────────────────────────────
  [from: victoria] Отредактировала 5 постов про "Точки выбора". Какая стратегия?

  handle() видит from_agent='victoria', знает что:
  - Текст уже проверен на язык/стиль
  - Нужна маркетинг-стратегия (хук, CTA, таргетинг)
  - Результат может идти дальше (например, на публикацию)

  Сценарий Б: Олеся нашла тренды, Марине нужен контент
  ──────────────────────────────────────────────────────
  [from: olya] [chain_id: week_2026_06_08] Выявила тренды: тревога, отношения, выбор.

  handle() видит:
  - from_agent='olya' → это исследовательская работа, можем доверять данным
  - chain_id='week_2026_06_08' → отслеживаем логику обработки по дате
  - Марина пишет контент, ориентируясь на тренды от Олеси

  Сценарий В: Дима прислал продажи, Виктории нужно обработать
  ───────────────────────────────────────────────────────────────
  [from: dima] [to: victoria] Вот продажи за день: 12 заказов, $450, тренд хорошо работает.

  Марина видит from_agent='dima', to_agent='victoria':
  - Запрос от Димы (финанс), но финальный результат (контент) идёт Виктории
  - Марина может подготовить краткую аналитику, но знает что это промежуточный шаг

═══════════════════════════════════════════════════════════════════════════════
"""
import sys
from pathlib import Path

# Каноническая Марина (агент + инструменты + цикл) живёт в mila-office/.
# Добавляем её в путь и импортируем — оттуда же берётся base.py.
_OFFICE = Path(__file__).resolve().parent.parent / "mila-office"
sys.path.insert(0, str(_OFFICE))

import agent as marina  # noqa: E402  (mila-office/agent.py)

# Единственное отличие standalone-режима: промпт направляет Марину запускать
# скрипты tools/ через run_command (нативные instagram_* не настроены).
marina.SYSTEM_PROMPT = """Ты — Марина, маркетолог и стратег личного бренда Людмилы Лыковой.

БРЕНД:
- @liudmyla.lykova, психолог, Канада
- Ниша: болезненные отношения, тревожная привязанность
- Методология «Точки выбора»: Ловушка знакомой боли → Синдром заслуживания → Точка выбора → Интеграция идентичности
- Продукты: практикум $37 CAD, консультации $120, пакеты $420/$750

ТВОЙ СТИЛЬ:
- Конкретные, практические действия
- Всегда с примерами — хуки, тексты, заголовки
- Думаешь цифрами: охваты, конверсии, доход
- Говоришь прямо если что-то не будет работать

ИНСТРУМЕНТЫ:
У тебя есть доступ к файлам в папке MILA GOLD и Instagram API.
Используй инструменты проактивно — не жди когда попросят.
При запросе контента — сразу пиши финальный текст, не шаблоны.

INSTAGRAM (важно):
Нативные инструменты instagram_* НЕ настроены — НЕ используй их.
Для всего, что связано с Instagram, вызывай run_command с готовыми
рабочими скриптами в папке tools/ (они уже подключены к API):
- Аналитика постов:  python tools/get_analytics.py posts
- Статистика аккаунта: python tools/get_analytics.py account
- Комментарии/заявки:  python tools/get_analytics.py comments
- Личные сообщения:    python tools/get_dms.py
- Публикация фото:     python tools/post_content.py photo --url "<URL>" --caption "<текст>"
- Публикация Reel:     python tools/post_content.py reel --url "<URL>" --caption "<текст>"
- Месячный отчёт .docx: python tools/make_report.py
Каждый скрипт сохраняет данные в reports/*.json — читай их через read_file
для анализа. Команды запускай ровно так: python tools/<script>.py <аргументы>
"""

if __name__ == "__main__":
    marina.main()
