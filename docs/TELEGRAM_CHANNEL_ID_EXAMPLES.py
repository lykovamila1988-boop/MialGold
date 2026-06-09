# -*- coding: utf-8 -*-
"""
ПРИМЕРЫ: Как Tyoma агент использует TELEGRAM_CHANNEL_ID

Эти примеры показывают конкретные способы работы с TELEGRAM_CHANNEL_ID
в коде Tyoma агента и других агентов.

Запустить примеры:
    cd mila-office
    python << 'EOF'
    # вставить код из нужного примера
    EOF
"""

# ==============================================================================
# ПРИМЕР 1: Базовое использование через shared_tools
# ==============================================================================

def example_1_basic_usage():
    """Самый простой способ — использовать функции из shared_tools"""
    from base import TELEGRAM_CHANNEL_ID
    from shared_tools import telegram_send, telegram_channel_stats

    print("ПРИМЕР 1: Базовое использование")
    print(f"Канал: {TELEGRAM_CHANNEL_ID}")
    print()

    # Способ 1: Отправить сообщение БЕЗ указания канала (используется default)
    print("1️⃣  Отправить сообщение в канал (автоматический):")
    result = telegram_send(
        text="Привет! Это автоматический пост из Tyoma",
        confirm=False  # confirm=False → сразу отправляется (для demo)
    )
    print(f"   Результат: {result}")
    print()

    # Способ 2: Отправить в ДРУГОЙ канал (переопределить)
    print("2️⃣  Отправить в личный чат (переопределяем default):")
    result = telegram_send(
        text="Личное уведомление",
        chat_id="818186814",  # Личный чат Людмилы
        confirm=False
    )
    print(f"   Результат: {result}")
    print()

    # Способ 3: Получить статистику основного канала
    print("3️⃣  Получить статистику основного канала:")
    print(f"   → telegram_channel_stats() вернёт статистику для {TELEGRAM_CHANNEL_ID}")
    print()


# ==============================================================================
# ПРИМЕР 2: Использование send_to_queue в tyoma.py
# ==============================================================================

def example_2_send_to_queue():
    """Как Tyoma использует send_to_queue для публикаций"""
    from base import TELEGRAM_CHANNEL_ID
    from tyoma import send_to_queue
    import json

    print("ПРИМЕР 2: send_to_queue в Tyoma")
    print(f"Основной канал: {TELEGRAM_CHANNEL_ID}")
    print()

    # Способ 1: Простая публикация
    print("1️⃣  Простая публикация в основной канал:")
    result = send_to_queue(
        text="Инсайт: Как распознать паттерн Спасателя в себе?",
        content_type="инсайт"
    )
    if isinstance(result, dict):
        print(f"   ✓ Сообщение поставлено в очередь")
        print(f"   ✓ Chain ID: {result.get('chain_id')}")
        print(f"   ✓ Будет отправлено в: {TELEGRAM_CHANNEL_ID}")
    print()

    # Способ 2: Кросс-постинг с Instagram
    print("2️⃣  Кросс-постинг (Instagram → Telegram):")
    result = send_to_queue(
        text="💡 Адаптированная версия для Telegram\n\n"
             "Исходный пост был в Instagram, теперь добавляем ссылку:\n"
             "📚 Купить практикум: https://...",
        content_type="кейс",
        chain_id="ig_abc12345"  # Привязка к Instagram посту
    )
    if isinstance(result, dict):
        print(f"   ✓ Кросс-пост готов")
        print(f"   ✓ Канал: {TELEGRAM_CHANNEL_ID}")
        print(f"   ✓ Привязан к Instagram посту: ig_abc12345")
    print()

    # Способ 3: Явное указание другого канала
    print("3️⃣  Публикация в ДРУГОЙ канал (если нужно):")
    result = send_to_queue(
        text="Приватное сообщение",
        channel_id="999999999",  # Переопределяем default
        content_type="personal"
    )
    if isinstance(result, dict):
        print(f"   ✓ Сообщение в очередь")
        print(f"   ✓ Канал переопределён: 999999999 (не {TELEGRAM_CHANNEL_ID})")
    print()


# ==============================================================================
# ПРИМЕР 3: Как выглядит в обработчике handle()
# ==============================================================================

def example_3_in_handle_function():
    """Как TELEGRAM_CHANNEL_ID используется внутри handle() функции Tyoma"""

    print("ПРИМЕР 3: Использование в handle() диспетчере")
    print()
    print("Когда пользователь вызывает инструмент, вот что происходит:")
    print()

    # Сценарий 1: telegram_send
    print("1️⃣  Пользователь вызывает инструмент 'telegram_send':")
    print("""
    User: "Опубликуй сообщение про медитацию"

    Tyoma (в handle()):
    ┌─────────────────────────────────────────┐
    │ if name == "telegram_send":             │
    │     return telegram_send(                │
    │         text=inp.get("text", ""),      │
    │         chat_id=inp.get("chat_id", ""), │  ← пусто
    │         confirm=inp.get("confirm", ...) │
    │     )                                    │
    │                                          │
    │ В shared_tools.py:                       │
    │ final_chat_id = chat_id or TELEGRAM... │  ← используется
    │ final_chat_id = "" or "1003005733230"  │
    │ final_chat_id = "1003005733230"        │  ← вот это
    └─────────────────────────────────────────┘

    Result: ✓ Сообщение публикуется в 1003005733230
    """)
    print()

    # Сценарий 2: telegram_channel_stats
    print("2️⃣  Пользователь вызывает инструмент 'telegram_channel_stats':")
    print("""
    User: "Сколько подписчиков в канале?"

    Tyoma (в handle()):
    ┌─────────────────────────────────────────┐
    │ if name == "telegram_channel_stats":   │
    │     return telegram_channel_stats(       │
    │         inp.get("chat_id", "")  ← пусто │
    │     )                                    │
    │                                          │
    │ В shared_tools.py:                       │
    │ final_chat_id = chat_id or TELEGRAM... │
    │ final_chat_id = "" or "1003005733230"  │
    │ final_chat_id = "1003005733230"        │
    └─────────────────────────────────────────┘

    Result: ✓ Возвращает статистику канала 1003005733230
    """)
    print()


# ==============================================================================
# ПРИМЕР 4: Интеграция в систему очередей
# ==============================================================================

def example_4_queue_integration():
    """Как TELEGRAM_CHANNEL_ID интегрируется в систему очередей"""
    from base import TELEGRAM_CHANNEL_ID
    from tyoma import send_to_queue

    print("ПРИМЕР 4: Интеграция в систему очередей")
    print()

    print("Когда Tyoma ставит сообщение в очередь:")
    print()
    print("Код:")
    print("""
    result = send_to_queue(
        text="Новый пост",
        content_type="инсайт"
        # ← channel_id НЕ указан
    )
    """)
    print()
    print("Внутри send_to_queue():")
    print(f"""
    final_channel_id = channel_id or TELEGRAM_CHANNEL_ID
    final_channel_id = "" or "{TELEGRAM_CHANNEL_ID}"
    final_channel_id = "{TELEGRAM_CHANNEL_ID}"

    metadata = {{
        "channel_id": "{TELEGRAM_CHANNEL_ID}",
        "chain_id": "tg_abc12345",
        "content_type": "инсайт",
        "source": "telegram"
    }}

    memory.queue_message("telegram", text, metadata=metadata)
    """)
    print()
    print("Результат: Сообщение в очереди помечено для отправки в")
    print(f"           основной канал {TELEGRAM_CHANNEL_ID}")
    print()


# ==============================================================================
# ПРИМЕР 5: Как другие агенты могут использовать
# ==============================================================================

def example_5_other_agents():
    """Как другие агенты (Producer, Dima, Manager) могут использовать TELEGRAM_CHANNEL_ID"""
    from base import TELEGRAM_CHANNEL_ID

    print("ПРИМЕР 5: Использование в других агентах")
    print()

    # Producer - публикует в Telegram после Instagram
    print("1️⃣  Producer (при публикации в Instagram):")
    print(f"""
    # Когда Instagram пост готов, можно уведомить в Telegram
    from shared_tools import telegram_send

    telegram_send(
        text=f"✓ Пост опубликован: {{title}}",
        # ← автоматически идёт в {TELEGRAM_CHANNEL_ID}
    )
    """)
    print()

    # Dima - отчёты о продажах
    print("2️⃣  Dima (финансовые отчёты):")
    print(f"""
    # Отправить отчёт о продажах в канал
    from shared_tools import telegram_send
    from base import TELEGRAM_CHANNEL_ID

    stats = calculate_sales()
    telegram_send(
        text=f"💰 Отчёт: {{stats}}",
        chat_id=TELEGRAM_CHANNEL_ID  # явно или используется default
    )
    """)
    print()

    # Manager - мониторинг
    print("3️⃣  Manager (оповещения об ошибках):")
    print(f"""
    # Когда что-то упало, уведомить админа И канал
    from shared_tools import telegram_send
    from base import TELEGRAM_CHANNEL_ID, TELEGRAM_ADMIN_CHAT_ID

    # Админу приватно
    telegram_send(
        text=f"⚠️ ОШИБКА: {{error}}",
        chat_id=TELEGRAM_ADMIN_CHAT_ID
    )

    # В канал публично
    telegram_send(
        text=f"⏸️ Сейчас техническое обслуживание",
        chat_id=TELEGRAM_CHANNEL_ID
    )
    """)
    print()


# ==============================================================================
# ПРИМЕР 6: Обработка ошибок
# ==============================================================================

def example_6_error_handling():
    """Что если TELEGRAM_CHANNEL_ID не установлен?"""

    print("ПРИМЕР 6: Обработка ошибок")
    print()

    # Сценарий: TELEGRAM_CHANNEL_ID = None (не в .env)
    print("Если в tools/.env НЕ установлен TELEGRAM_CHANNEL_ID:")
    print()
    print("""
    telegram_send(text="Привет")

    В shared_tools.py:
    final_chat_id = chat_id or TELEGRAM_CHANNEL_ID
    final_chat_id = "" or None
    final_chat_id = None

    if not final_chat_id:
        return "⚠️ Нет chat_id и TELEGRAM_CHANNEL_ID не установлен в .env"

    Result: ⚠️ Ошибка вместо молчаливого отказа
    """)
    print()
    print("✅ Это правильно — лучше явная ошибка чем скрытая проблема")
    print()


# ==============================================================================
# ПРИМЕР 7: Тестирование
# ==============================================================================

def example_7_testing():
    """Как проверить что TELEGRAM_CHANNEL_ID работает"""

    print("ПРИМЕР 7: Проверка работы")
    print()

    print("Способ 1️⃣  — Проверить что переменная загружена:")
    print("""
    from base import TELEGRAM_CHANNEL_ID
    print(TELEGRAM_CHANNEL_ID)
    # Должно вывести: 1003005733230
    """)
    print()

    print("Способ 2️⃣  — Проверить что функции используют default:")
    print("""
    from shared_tools import telegram_send

    # Без chat_id → используется TELEGRAM_CHANNEL_ID
    result = telegram_send(text="Тест", confirm=True)
    print(result)  # Должно показать черновик для TELEGRAM_CHANNEL_ID
    """)
    print()

    print("Способ 3️⃣  — Проверить Tyoma интеграцию:")
    print("""
    from tyoma import send_to_queue

    result = send_to_queue(text="Тест")
    if isinstance(result, dict):
        print(f"✓ Очередь работает для канала {result.get('channel_id')}")
    """)
    print()

    print("Способ 4️⃣  — Проверить через Flask:")
    print("""
    curl http://127.0.0.1:5000/api/health
    # Должно показать: "telegram": {"configured": true}
    """)
    print()


# ==============================================================================
# ПРИМЕР 8: Полный workflow
# ==============================================================================

def example_8_full_workflow():
    """Полный процесс от идеи до публикации в Telegram"""

    print("ПРИМЕР 8: Полный workflow Instagram → Telegram")
    print()

    print("""
    Шаг 1️⃣  — Marina создаёт пост в Instagram
    ┌──────────────────────────────────────────────┐
    │ Marina: "Напиши пост про паттерн Спасателя"  │
    │ → Создаёт текст                              │
    │ → chain_id = "ig_abc12345"                    │
    └──────────────────────────────────────────────┘


    Шаг 2️⃣  — Pост публикуется в Instagram
    ┌──────────────────────────────────────────────┐
    │ Vasya: "Опубликуй пост"                      │
    │ → instagram_publish_post(...)                │
    │ → Instagram получает пост ✓                  │
    │ → metadata хранит chain_id="ig_abc12345"     │
    └──────────────────────────────────────────────┘


    Шаг 3️⃣  — Tyoma синхронизирует в Telegram
    ┌──────────────────────────────────────────────┐
    │ Tyoma: "Адаптируй Instagram пост для TG"    │
    │ → Читает оригинальный текст                  │
    │ → Адаптирует (добавляет ссылки)             │
    │ → send_to_queue(                             │
    │     text="Адаптированный текст",             │
    │     chain_id="ig_abc12345",  ← связь!       │
    │     content_type="кейс"                      │
    │     # ← channel_id не указан                 │
    │   )                                          │
    │                                              │
    │ Внутри send_to_queue():                      │
    │ final_channel_id = "" or TELEGRAM_CHANNEL... │
    │ final_channel_id = "1003005733230"           │
    │ → Сообщение в очередь с этим каналом ✓     │
    └──────────────────────────────────────────────┘


    Шаг 4️⃣  — Когда n8n/task запускает публикацию
    ┌──────────────────────────────────────────────┐
    │ Берёт сообщение из очереди:                  │
    │ {                                            │
    │   "text": "Адаптированный текст",            │
    │   "channel_id": "1003005733230", ← вот!     │
    │   "chain_id": "ig_abc12345",                 │
    │ }                                            │
    │                                              │
    │ telegram_send(chat_id="1003005733230", ...)  │
    │ → Отправляет в Telegram ✓                   │
    │                                              │
    │ Результат:                                   │
    │ • Instagram: Пост в основном аккаунте       │
    │ • Telegram: Синхронизированный пост в канале│
    │ • Связь через chain_id="ig_abc12345"        │
    │ • Оба используют TELEGRAM_CHANNEL_ID где надо│
    └──────────────────────────────────────────────┘
    """)
    print()


# ==============================================================================
# ГЛАВНОЕ МЕНЮ
# ==============================================================================

if __name__ == "__main__":
    import sys

    examples = {
        "1": ("Базовое использование", example_1_basic_usage),
        "2": ("send_to_queue в Tyoma", example_2_send_to_queue),
        "3": ("Использование в handle()", example_3_in_handle_function),
        "4": ("Интеграция в очереди", example_4_queue_integration),
        "5": ("Другие агенты", example_5_other_agents),
        "6": ("Обработка ошибок", example_6_error_handling),
        "7": ("Тестирование", example_7_testing),
        "8": ("Полный workflow", example_8_full_workflow),
        "все": ("Все примеры", None),
    }

    print("\n" + "="*60)
    print("ПРИМЕРЫ: TELEGRAM_CHANNEL_ID в Tyoma агенте")
    print("="*60 + "\n")

    for key, (title, _) in examples.items():
        print(f"  {key}: {title}")

    print(f"\nИспользование: python << 'EOF'")
    print(f"               exec(open('TELEGRAM_CHANNEL_ID_EXAMPLES.py').read())")
    print(f"               example_1_basic_usage()")
    print(f"               EOF\n")

    # Если запустить как скрипт — показать первый пример
    print("Первый пример:\n")
    example_1_basic_usage()
