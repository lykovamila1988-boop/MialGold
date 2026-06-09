# 📚 MODULES INDEX — Справочник всех функций

## 🗂️ Быстрый поиск

- **agent_manager** — Агенты
- **message_handler** — Цепочка
- **session_manager** — Сессии
- **document_manager** — Документы
- **upload_handler** — Загрузки
- **webapp_utils** — Утилиты
- **job_queue** — Задания
- **security** — Безопасность
- **ui_helpers** — UI
- **routes** — Маршруты
- **file_handler** — Файлы

---

## 📦 agent_manager

**Цель:** Реестр всех агентов и их метаданные

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `list_agents()` | Список всех агентов | `['marina', 'victoria', ...]` |
| `get_agent_module(key)` | Загруженный модуль агента | `<module 'marina'>` |
| `get_agent_metadata(key)` | Метаданные (имя, emoji, роль) | `{'name': '...', 'emoji': '💼', ...}` |
| `get_quick_commands(key)` | Быстрые команды агента | `{'/контент': '...', ...}` |
| `get_tools(key)` | Инструменты агента | `[...]` |

### Пример использования

```python
from agent_manager import list_agents, get_agent_metadata

for agent in list_agents():
    meta = get_agent_metadata(agent)
    print(f"{meta['emoji']} {meta['name']}")
```

---

## 📦 message_handler ⭐ ГЛАВНЫЙ

**Цель:** Логика передачи между агентами, парсинг verdict

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `extract_next_agent(reply)` | Ловит `[→ agent]` в ответе | `'victoria'` или `''` |
| `extract_verdict(reply)` | Ловит `[VERDICT: xxx]` | `'ready_next'` |
| `process_agent_response(reply, agent)` | **ГЛАВНАЯ**: полная обработка ответа | `{should_switch, next_agent, verdict, clean_reply}` |
| `get_pipeline_order()` | Цепочка агентов | `{'marina': 'victoria', ...}` |
| `should_auto_switch(verdict)` | Нужно ли переключиться | `True/False` |

### Пример использования

```python
from message_handler import process_agent_response

# Когда Марина ответила
result = process_agent_response(
    "Пост готов [VERDICT: ready_next] [→ victoria]",
    "marina"
)

if result['should_switch']:
    # Переключиться на next_agent
    switch_to(result['next_agent'])
```

### Цепочка по умолчанию

```
olya (🔍) → marina (💼) → victoria (✍️) → vasya (📅) → rita (🎨) → [END]
```

---

## 📦 session_manager

**Цель:** Управление историей чатов и сессиями

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `save_message(sid, agent, role, content, metadata)` | Сохранить сообщение | `None` |
| `load_history(sid, agent)` | Загрузить историю агента | `[{role, content}, ...]` |
| `get_all_histories(sid)` | Все истории в сессии | `{agent: history, ...}` |
| `trim_history(history)` | Обрезать до 10 последних | `[... последние 10 ...]` |
| `clear_session(sid)` | Очистить сессию | `None` |
| `get_session_stats(sid)` | Статистика | `{agents_active, total_messages, ...}` |

### Пример использования

```python
from session_manager import load_history, save_message

# Загрузить историю Марины
history = load_history("session_123", "marina")

# Сохранить новое сообщение
save_message("session_123", "victoria", "assistant", "Готово!")

# Обрезать историю перед отправкой в агента
trimmed = trim_history(history)
```

---

## 📦 document_manager

**Цель:** Управление документами и их редактурой

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `safe_doc_id(doc_id)` | Валидировать ID документа | `'doc_123'` или `ValueError` |
| `load_record(doc_id, histories)` | Загрузить документ | `{id, stages, final_content, ...}` |
| `save_record(doc_id, agent, user_msg, reply)` | Сохранить этап редактуры | `{id, stages, ...}` |
| `extract_doc_ids(text)` | Найти ID документов в тексте | `{'doc_123', 'doc_456'}` |
| `extract_final_document(reply)` | Ловит `[ДОКУМЕНТ]...[/ДОКУМЕНТ]` | `'готовый текст'` |
| `document_to_text(doc)` | Преобразовать в TXT | `'📄 ...\n✅ ФИНАЛЬНАЯ ВЕРСИЯ...'` |

### Пример использования

```python
from document_manager import save_record, extract_doc_ids

# Сохранить этап редактуры Виктории
doc = save_record(
    "doc_123",
    "victoria",
    "Пост от Марины",
    "Исправлено. [ДОКУМЕНТ]Готовый текст[/ДОКУМЕНТ]"
)

# Найти документы в тексте
ids = extract_doc_ids("Смотри [doc_id:doc_123]")
```

---

## 📦 upload_handler

**Цель:** Обработка загруженных файлов (PDF OCR, DOCX, изображения)

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `extract_pdf_text(raw_bytes)` | Извлечь текст из PDF (с OCR фолбэком) | `(text, note)` |
| `extract_docx_text(raw_bytes)` | Извлечь текст из DOCX | `(text, note)` |
| `describe_image_with_claude(raw_bytes, mime)` | Описать изображение через Claude vision | `(description, error)` |
| `extract_upload(filename, raw, mime)` | Универсальный обработчик | `(text, note)` |
| `looks_garbled(text)` | Проверить битый ли текстовый слой PDF | `True/False` |

### Пример использования

```python
from upload_handler import extract_pdf_text, extract_upload

# PDF с автоматическим OCR
text, note = extract_pdf_text(pdf_bytes)
if note:
    print(f"Внимание: {note}")

# Универсальный обработчик
text, error = extract_upload("document.pdf", file_bytes, "application/pdf")
```

---

## 📦 webapp_utils

**Цель:** Утилиты и вспомогательные функции

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `generate_job_id()` | Генерировать уникальный ID задания | `'a1b2c3d4e5f6'` |
| `generate_session_id()` | Генерировать ID сессии | `'ab12cd34ef56'` |
| `clip_text(text, max_len)` | Обрезать текст если длинный | `'first 500 chars…'` |
| `safe_upload_name(name)` | Убрать опасные символы из имени | `'file_name.pdf'` |
| `looks_garbled(text)` | Проверить кодировку текста | `True/False` |
| `decode_text_file(raw_bytes)` | Декодировать текстовый файл | `'текст'` |

### Пример использования

```python
from webapp_utils import generate_job_id, clip_text, safe_upload_name

job_id = generate_job_id()
safe_name = safe_upload_name("опасное имя.pdf")
preview = clip_text(long_text, max_len=100)
```

---

## 📦 job_queue

**Цель:** Управление асинхронными заданиями

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `create_job(id, sid, agent)` | Создать новое задание | `{id, status: 'pending', ...}` |
| `get_job(id)` | Получить задание | `{id, status, reply, ...}` или `None` |
| `update_job(id, **kwargs)` | Обновить поля | `None` |
| `complete_job(id, reply, doc_id, verdict, next_agent)` | Завершить с результатом | `None` |
| `fail_job(id, error)` | Пометить как ошибка | `None` |
| `remove_job(id)` | Удалить из памяти | `None` |
| `get_all_jobs()` | Все текущие задания | `{id: job, ...}` |

### Пример использования

```python
from job_queue import create_job, complete_job, get_job

# Создать
job = create_job("job_123", "sess_456", "marina")

# Обновить
job_queue.update_job("job_123", reply="Думаю...")

# Завершить
complete_job("job_123", reply="Готово!", verdict="ready_next", next_agent="victoria")

# Получить результат
result_job = get_job("job_123")
```

---

## 📦 security

**Цель:** Безопасность: CSRF, валидация, защита

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `get_persistent_secret()` | Получить Flask secret key | `'abc123...'` |
| `generate_csrf_token()` | Генерировать CSRF token | `'token123...'` |
| `validate_agent_key(key)` | Проверить имя агента | `True/False` |
| `validate_session_id(id)` | Проверить ID сессии | `True/False` |
| `validate_job_id(id)` | Проверить ID задания | `True/False` |
| `validate_doc_id(id)` | Проверить ID документа | `True/False` |
| `safe_message_text(text)` | Очистить текст | `'чистый текст'` |
| `safe_file_name(name)` | Убрать опасные символы | `'safe_name.txt'` |
| `mask_sensitive_data(text)` | Замаскировать tokens в логах | `'masked text'` |
| `is_safe_origin(origin, host)` | Same-origin check | `True/False` |

### Пример использования

```python
from security import validate_agent_key, safe_message_text, mask_sensitive_data

if not validate_agent_key(user_input):
    abort(400)

clean_text = safe_message_text(user_message)

log_entry = mask_sensitive_data(f"Token: {token}")
```

---

## 📦 ui_helpers

**Цель:** Генерация HTML, CSS, JS

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `html_header(title)` | HTML header с CSS | `'<!DOCTYPE html>...'` |
| `html_footer()` | Закрыть HTML | `'</html>'` |
| `render_agent_button(key, name, emoji)` | Кнопка агента | `'<button>...</button>'` |
| `render_message(role, content, emoji)` | Сообщение в чате | `'<div class="message">...</div>'` |
| `render_typing_indicator(name)` | "печатает…" | `'<div>...'` |
| `render_error_message(error)` | Ошибка | `'<div>⚠️ ...'` |
| `render_success_message(msg)` | Успех | `'<div>✅ ...'` |
| `get_agent_color(key)` | Цвет для агента | `'#e8d4f8'` |
| `get_agent_emoji(key)` | Emoji для агента | `'💼'` |
| `escape_html(text)` | Экранировать HTML | `'&lt;div&gt;'` |

### Пример использования

```python
from ui_helpers import html_header, render_agent_button, render_message

html = html_header("MILA Office")
html += render_agent_button("marina", "Марина", "💼")
html += render_message("assistant", "Привет!", emoji="💼")
```

---

## 📦 routes

**Цель:** Flask маршруты

### Функции

| Маршрут | Метод | Что делает | Возвращает |
|---------|--------|-----------|-----------|
| `/api/health` | GET | Проверка статуса | `{status: 'ok'}` |
| `/api/meta` | GET | Метаинформация | `{agents: [...], commands: {...}}` |
| `/api/chat` | POST | Отправить сообщение | `{job: 'id'}` |
| `/api/result?job=X` | GET | Получить результат | `{reply, verdict, next_agent, ...}` |
| `/` | GET | Главная страница | HTML |

### Пример использования

```python
# В главном webapp.py:
from routes import register_routes

register_routes(app)

# Теперь все маршруты доступны:
# GET  http://localhost:5000/api/health
# POST http://localhost:5000/api/chat
# GET  http://localhost:5000/api/result?job=abc123
```

---

## 📦 file_handler

**Цель:** Работа с файлами (загрузки, сохранение, экспорт)

### Функции

| Функция | Что делает | Возвращает |
|---------|-----------|-----------|
| `save_uploaded_file(name, content)` | Сохранить загруженный файл | `(upload_id, safe_name)` |
| `get_upload_path(upload_id)` | Получить путь к загруженному файлу | `Path(...)` |
| `delete_upload(upload_id)` | Удалить загруженный файл | `None` |
| `save_json_file(name, data)` | Сохранить JSON | `Path(...)` |
| `load_json_file(name)` | Загрузить JSON | `{...}` или `{}` |
| `save_text_export(name, content)` | Сохранить текстовый экспорт | `Path(...)` |
| `get_mime_type(filename)` | Определить MIME type | `'application/pdf'` |
| `list_uploads()` | Список всех загруженных файлов | `[{id, size, modified}, ...]` |
| `cleanup_old_uploads(max_age)` | Удалить старые загрузки | `None` |

### Пример использования

```python
from file_handler import save_uploaded_file, save_text_export

# Сохранить загруженный файл
upload_id, safe_name = save_uploaded_file("photo.jpg", file_bytes)

# Экспортировать текст
path = save_text_export("report.txt", "Содержание отчёта")
```

---

## 🔗 ЗАВИСИМОСТИ МЕЖДУ МОДУЛЯМИ

```
routes.py
  ├── agent_manager (list_agents, get_agent_metadata)
  ├── message_handler (process_agent_response)
  ├── job_queue (create_job, get_job, remove_job)
  ├── security (validate_agent_key)
  └── ui_helpers (render_agent_button, render_message)

message_handler.py
  └── agent_manager (list_agents) ← для проверки валидности

document_manager.py
  └── session_manager? (опционально, если используется история)

webapp.py
  ├── routes (register_routes)
  ├── agent_manager
  ├── message_handler
  ├── session_manager
  ├── document_manager
  ├── upload_handler
  ├── job_queue
  ├── security
  ├── ui_helpers
  ├── file_handler
  └── webapp_utils
```

---

## 💡 TIPS

1. **Импортируйте только нужные функции:**
   ```python
   from message_handler import process_agent_response
   ```

2. **Используйте логирование:**
   ```python
   import logging
   logger = logging.getLogger("mila.my_module")
   logger.info("Важная информация")
   ```

3. **Валидируйте входные данные:**
   ```python
   from security import validate_agent_key
   if not validate_agent_key(user_input):
       abort(400)
   ```

4. **Тестируйте модули отдельно:**
   ```bash
   python -c "from agent_manager import list_agents; print(list_agents())"
   ```

---

✅ **ВСЕ МОДУЛИ ДОКУМЕНТИРОВАНЫ И ГОТОВЫ К ИСПОЛЬЗОВАНИЮ!**
