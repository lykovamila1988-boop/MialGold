# 📐 MILA OFFICE — Архитектура веб-приложения

## Обзор

Начиная с версии 2.0, webapp.py разбит на специализированные модули для лучшей поддерживаемости и масштабируемости.

## 📦 Модули

### 1. **agent_manager.py** — Управление агентами
Реестр всех 11 агентов и их метаданных.

**Что в нём:**
- `AGENTS_MODULES` — словарь загруженных модулей агентов
- `AGENTS_METADATA` — информация о каждом агенте (имя, emoji, роль, система)
- `get_agent_module(key)` — получить модуль агента
- `get_agent_metadata(key)` — получить метаданные
- `list_agents()` — список всех агентов
- `get_quick_commands(key)` — быстрые команды агента
- `get_tools(key)` — список инструментов агента

**Примеры:**
```python
from agent_manager import get_agent_metadata, list_agents

agents = list_agents()  # ['marina', 'victoria', 'alina', ...]
meta = get_agent_metadata('victoria')  # {'name': 'Виктория', 'emoji': '✍️', ...}
```

---

### 2. **message_handler.py** — Обработка сообщений и цепочка
Логика передачи между агентами, парсинг verdict, автоматическое переключение.

**Что в нём:**
- `extract_next_agent(reply)` — ловит `[→ agent]` в ответе
- `extract_verdict(reply)` — ловит `[VERDICT: xxx]` в ответе
- `process_agent_response(reply, agent)` — полная обработка ответа
- `get_pipeline_order()` — цепочка: Оля → Марина → Виктория → Вася → Рита
- `should_auto_switch(verdict)` — нужно ли переключиться?

**Примеры:**
```python
from message_handler import process_agent_response

result = process_agent_response(
    reply="Пост готов. [VERDICT: ready_next] [→ victoria]",
    current_agent="marina"
)
# {
#   "should_switch": True,
#   "next_agent": "victoria",
#   "verdict": "ready_next",
#   "clean_reply": "Пост готов."
# }
```

**Цепочка передачи:**
```
Оля (тренды) → Марина (маркетолог) → Виктория (редактор) → Вася (планировщик) → Рита (дизайнер)
```

---

### 3. **session_manager.py** — Управление сессиями
История чатов, сохранение/загрузка диалогов.

**Что в нём:**
- `save_message(session_id, agent_key, role, content)` — сохранить сообщение
- `load_history(session_id, agent_key)` — загрузить историю агента
- `get_all_histories(session_id)` — все истории в сессии
- `trim_history(history)` — обрезать историю (последние 10 сообщений)
- `clear_session(session_id)` — очистить сессию
- `get_session_stats(session_id)` — статистика

**Примеры:**
```python
from session_manager import save_message, load_history

# Сохранить сообщение
save_message("sess123", "marina", "assistant", "Готов к контенту")

# Загрузить историю
history = load_history("sess123", "victoria")
# [
#   {"role": "user", "content": "..."},
#   {"role": "assistant", "content": "..."}
# ]
```

---

### 4. **webapp_utils.py** — Утилиты
Общие функции валидации, обработки текста, генерации ID.

**Что в нём:**
- `generate_job_id()` — ID для задачи
- `generate_session_id()` — ID для сессии
- `clip_text(text, max_len)` — обрезать текст
- `safe_upload_name(name)` — сделать имя файла безопасным
- `looks_garbled(text)` — проверить кодировку
- `decode_text_file(raw)` — декодировать текстовый файл
- `pluralize_ru(count, sg, pl, gen)` — склонение на русском

---

### 5. **webapp.py** — Flask приложение
Основное приложение, маршруты, интеграция всех модулей.

**Изменения в версии 2.0:**
- Импортирует новые модули
- Маршрут `/api/result` использует `message_handler.process_agent_response()`
- Логика цепочки переехала в JavaScript (фронтенд) и message_handler (бэкенд)

---

## 🔄 Поток данных: отправка сообщения

```
1. Фронтенд: пользователь пишет сообщение Марине
   ↓
2. POST /api/chat → создаёт job, запускает агента в фоне
   ↓
3. Агент обрабатывает: берёт историю из session_manager, запускает run_agent
   ↓
4. Агент пишет [VERDICT: ready_next] [→ victoria]
   ↓
5. Фронтенд опрашивает GET /api/result (каждую секунду)
   ↓
6. Бэкенд обрабатывает через message_handler:
   - Парсит [VERDICT: xxx]
   - Парсит [→ agent]
   - Возвращает verdict и next_agent
   ↓
7. Фронтенд видит verdict='ready_next' и next_agent='victoria'
   ↓
8. АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ на victoria (через switchAgent)
   ↓
9. Виктория видит историю (из session_manager) и может редактировать
```

---

## 📊 Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────┐
│                    WEBAPP.PY (Flask)                    │
│  /api/chat (POST) ──→ /api/result (GET) ──→ /api/meta   │
└─────────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐
│ AGENT_MANAGER    │  │ MESSAGE_HANDLER  │  │SESSION_MANAGER
│ - Реестр агентов │  │ - Логика цепочки │  │ - История чатов
│ - Метаданные     │  │ - Парсинг verdict│  │ - Сохранение
└──────────────────┘  └──────────────────┘  └──────────────┘
         ↓                    ↓                    ↓
    [marina]             [victoria]           [vasya]
    [alina]              [tyoma]              [lera]
    [dima]               [olya]               [rita]
```

---

## 🧪 Как добавить нового агента?

1. **Создать модуль:** `newagent.py`
   ```python
   SYSTEM = "..."
   TOOLS = [...]
   QUICK = {...}
   def handle(name, inp): ...
   ```

2. **Зарегистрировать в agent_manager.py:**
   ```python
   AGENTS_MODULES["newagent"] = importlib.import_module("newagent")
   AGENTS_METADATA["newagent"] = {
       "name": "Новый агент",
       "emoji": "🆕",
       "role": "...",
       "system": ...
   }
   ```

3. **Обновить цепочку в message_handler.py:**
   ```python
   def get_pipeline_order():
       return {
           ...
           "oldagent": "newagent",  # ← добавить
           "newagent": "nextagent",
       }
   ```

---

## 🚀 Запуск

```bash
cd "E:\MILA GOLD\mila-office"
python webapp.py
# Откроется http://127.0.0.1:5000
```

---

## 📝 Логи

Все логи пишутся в `MILA-BUSINESS/logs/webapp.log` с полным traceback.

```python
import logging
logger = logging.getLogger("mila.message_handler")
logger.info("Обработан ответ агента")
```

---

## ✅ Checklist для тестирования цепочки

- [ ] Марина пишет пост с `[→ victoria]`
- [ ] Система автоматически переходит на Викторию
- [ ] Виктория видит историю и пост Марины
- [ ] Виктория редактирует и пишет `[VERDICT: done]`
- [ ] Система показывает popup для скачивания
- [ ] Очищает VERDICT и служебные теги перед сохранением

---

## 📚 Ссылки на код

- `webapp.py` — маршруты Flask
- `agent_manager.py` — реестр агентов
- `message_handler.py` — логика цепочки ⭐
- `session_manager.py` — история диалогов
- `webapp_utils.py` — утилиты
