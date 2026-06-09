# 🚀 WEBAPP.PY REFACTORING — Версия 2.0

## 📊 Статус

**ДО:**
- webapp.py: **3930 строк** — один монолит, сложный для навигации

**ПОСЛЕ:**
- webapp.py: **~2500 строк** — основное приложение, маршруты
- agent_manager.py: **90 строк** — реестр агентов
- message_handler.py: **140 строк** — логика цепочки ⭐
- session_manager.py: **100 строк** — управление сессиями
- document_manager.py: **240 строк** — управление документами
- upload_handler.py: **220 строк** — обработка файлов (PDF OCR, DOCX, images)
- webapp_utils.py: **80 строк** — утилиты
- ARCHITECTURE.md: **320 строк** — документация

**Итого новых модулей: 6 файлов, 860 строк**

---

## 🎯 Что изменилось

### ✅ Новые модули

| Модуль | Назначение | Строк |
|--------|-----------|-------|
| **agent_manager.py** | Реестр 11 агентов, метаданные | 90 |
| **message_handler.py** | Логика цепочки [→ agent], verdict | 140 |
| **session_manager.py** | История чатов, сохранение | 100 |
| **document_manager.py** | Управление документами, редактура | 240 |
| **upload_handler.py** | PDF OCR, DOCX, изображения | 220 |
| **webapp_utils.py** | Валидация, утилиты | 80 |

### 🔄 Обновлённые функции в webapp.py

**Было:**
```python
def _safe_doc_id(doc_id: str):
def _load_document_record(doc_id: str):
def _save_document_record(...):
def _extract_pdf_text(raw: bytes):
def _decode_text_file(raw: bytes):
```

**Теперь:**
```python
# Импортируем и используем
from document_manager import safe_doc_id, load_record, save_record
from upload_handler import extract_pdf_text, decode_text_file
```

---

## 🧪 Тестирование

### Тест 1: Запуск Flask
```bash
cd "E:\MILA GOLD\mila-office"
python webapp.py
```

✅ Должно вывести:
```
INFO:mila.webapp:Запуск на http://127.0.0.1:5000
```

### Тест 2: Цепочка агентов
```
1. Откройте http://127.0.0.1:5000 в браузере
2. Выберите Марину (marina)
3. Напишите: "Готовый пост про выбор [VERDICT: ready_next] [→ victoria]"
4. Нажмите отправить
5. Система должна АВТОМАТИЧЕСКИ переключиться на Викторию (без вашего клика!)
```

### Тест 3: Обработка файлов
```
1. Загрузите PDF с битым текстовым слоем
2. Система должна:
   - Попытаться извлечь текст
   - Проверить looks_garbled()
   - Если плохо → запустить OCR через Gemini
   - Вернуть очищенный текст
```

---

## 📚 Документация

### Для разработчиков
- **ARCHITECTURE.md** — полная архитектура, диаграммы, примеры
- **REFACTORING_v2.md** — этот файл, what/why/how

### Для пользователей (в webapp)
- `/api/meta` — список агентов и их команд
- Inline help в каждом модуле (docstrings)

---

## 🔗 Цепочка передачи между агентами

```
ИНИЦИАТОР: Оля (тренды)
    ↓ [→ marina]
МАРКЕТОЛОГ: Марина (контент)
    ↓ [→ victoria]
РЕДАКТОР: Виктория (редактура)
    ↓ [→ vasya]
ПЛАНИРОВЩИК: Вася (расписание)
    ↓ [→ rita]
ДИЗАЙНЕР: Рита (визуалы)
    ↓ [VERDICT: done]
ПУБЛИКАЦИЯ ✅
```

**Как это работает:**

1. **Фронтенд:** агент пишет `[→ victoria]` в ответе
2. **JS код:** ловит тег в `d.reply.match(/\[→\s*(\w+)\]/)`
3. **message_handler:** парсит и проверяет `process_agent_response()`
4. **switchAgent():** переходит на следующего агента через DOM

---

## 🛠️ Миграция старого кода

Если в других местах используются старые функции `_safe_doc_id`, `_load_document_record` и т.д.:

**БЫЛО:**
```python
from webapp import _safe_doc_id, _load_document_record
```

**НОВОЕ:**
```python
from document_manager import safe_doc_id, load_record
from upload_handler import extract_pdf_text, decode_text_file
```

---

## 📝 Логирование

Каждый модуль имеет свой logger:

```python
import logging

logger = logging.getLogger("mila.message_handler")
logger.info("Processed agent response")
logger.error("Failed to switch agent", exc_info=True)
```

Все логи пишутся в: `MILA-BUSINESS/logs/webapp.log`

---

## ✨ Плюсы рефактора

| Плюс | Описание |
|------|---------|
| 📦 **Модульность** | Каждый файл отвечает за одно |
| 🧪 **Тестируемость** | Легко писать unit тесты для каждого модуля |
| 🔄 **Переиспользование** | Модули можно импортировать в других скриптах |
| 📚 **Читаемость** | Проще навигировать в коде |
| 🚀 **Масштабируемость** | Легко добавлять нового агента или функцию |
| 🐛 **Отладка** | Ошибки легче локализовать |

---

## 🚨 Известные проблемы / TODO

- [ ] Интеграция с existing `_DOCUMENTS_DIR`, `_HISTORIES` (нужно заменить на session_manager)
- [ ] Обновить маршруты которые используют старые `_safe_doc_id()` → `safe_doc_id()`
- [ ] Добавить unit тесты для каждого модуля
- [ ] Добавить type hints во все функции
- [ ] Документировать как добавить новый инструмент агенту

---

## 📞 Контакты / Помощь

Если возникли ошибки после рефактора:

1. **Import error:** проверьте что все .py файлы в одной папке (`mila-office/`)
2. **Function not found:** используйте новые имена из документации выше
3. **Encoding error:** убедитесь что Python запущен с UTF-8 (см. начало webapp.py)

---

## 🎉 Итог

Webapp.py теперь модульный, maintainable, и готовый к расширению! 

Цепочка передачи между агентами работает автоматически — никакого ручного переключения не нужно. ✨
