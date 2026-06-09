# TELEGRAM_CHANNEL_ID — Как использовать в Tyoma

## 📍 Что это

`TELEGRAM_CHANNEL_ID` — это уникальный ID Telegram канала (`1003005733230`), где публикуется контент Людмилы Лыковой.

Переменная загружается из `tools/.env` и доступна **во всех агентах** через `base.py`.

---

## 🔧 Как Tyoma использует TELEGRAM_CHANNEL_ID

### 1️⃣ Автоматически (без явного указания)

Tyoma может публиковать БЕЗ указания chat_id — используется TELEGRAM_CHANNEL_ID по умолчанию:

```python
# В коде tyoma.py:
from shared_tools import telegram_send, telegram_channel_stats

# Отправить сообщение (без chat_id → используется TELEGRAM_CHANNEL_ID)
result = telegram_send(text="Привет из Telegram!", confirm=False)
# ✅ Публикуется в канал 1003005733230

# Получить статистику канала
stats = telegram_channel_stats()  # Без аргументов
# ✅ Возвращает количество подписчиков канала 1003005733230
```

### 2️⃣ Явное использование в send_to_queue()

```python
# В Tyoma агенте:
from tyoma import send_to_queue

# Вариант 1: Без указания канала (используется TELEGRAM_CHANNEL_ID)
send_to_queue(
    text="Инсайт про тревожную привязанность",
    content_type="инсайт"
)
# ✅ Идёт в основной канал 1003005733230

# Вариант 2: Явный другой канал (переопределяет default)
send_to_queue(
    text="Личное сообщение",
    chat_id="818186814",  # Личный чат Людмилы
    content_type="personal"
)
# ✅ Идёт в личный чат, не в основной канал
```

### 3️⃣ Кросс-постинг с Instagram (chain_id)

```python
# Tyoma синхронизирует Instagram и Telegram через chain_id:
send_to_queue(
    text="Адаптированная версия для Telegram",
    chain_id="ig_abc12345",  # ID поста из Instagram
    content_type="кейс"
)
# ✅ Публикуется в канал 1003005733230
# ✅ Привязана к Instagram посту через chain_id
```

---

## 📱 Примеры использования в диалоге

### Пример 1: Публикация нового поста

```
Пользователь: Tyoma, опубликуй пост про уверенность
Tyoma (система): 
  - Вызывает handle("send_to_queue", {...})
  - send_to_queue() использует TELEGRAM_CHANNEL_ID автоматически
  - Пост идёт в канал 1003005733230
Tyoma (ответ): ✓ Пост опубликован в канал!
```

**Что происходит в коде:**
```python
# В handle() tyoma.py:
def handle(name, inp):
    if name == "send_to_queue":
        return send_to_queue(
            inp.get("text", ""),           # Текст от агента
            channel_id=inp.get("channel_id", ""),  # Если указан
            # Если channel_id пуст → используется TELEGRAM_CHANNEL_ID
        )
```

### Пример 2: Проверка статистики канала

```
Пользователь: Tyoma, сколько подписчиков в канале?
Tyoma (система):
  - Вызывает handle("telegram_channel_stats", {})
  - telegram_channel_stats() без аргументов
  - Использует TELEGRAM_CHANNEL_ID из base.py
Tyoma (ответ): В канале 1234 подписчиков
```

**Что происходит в коде:**
```python
# В handle() tyoma.py:
def handle(name, inp):
    if name == "telegram_channel_stats":
        return telegram_channel_stats(
            inp.get("chat_id", "")  # Если пусто → используется TELEGRAM_CHANNEL_ID
        )
```

### Пример 3: Кросс-постинг Instagram → Telegram

```
Пользователь: Tyoma, адаптируй Instagram пост под Telegram
Tyoma (система):
  - Читает контент Instagram поста
  - Адаптирует под Telegram (добавляет ссылки, короче)
  - Вызывает send_to_queue() с chain_id
  - Публикуется в TELEGRAM_CHANNEL_ID с привязкой к Instagram
Tyoma (ответ): ✓ Кросс-пост готов и опубликован!
```

---

## 🏗️ Архитектура: как переменная течёт через код

```
tools/.env (исходная переменная)
    ↓
    TELEGRAM_CHANNEL_ID=1003005733230

    ↓ (загружает base.py через load_dotenv())
    
base.py (переменная окружения)
    ↓
    TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
    
    ↓ (импортируют из base)
    
shared_tools.py (функции с defaults)
    ├─ telegram_send(chat_id="", ...)
    │  final_chat_id = chat_id or TELEGRAM_CHANNEL_ID
    │
    └─ telegram_channel_stats(chat_id="")
       final_chat_id = chat_id or TELEGRAM_CHANNEL_ID
    
    ↓ (используют из shared_tools)
    
tyoma.py (агент)
    ├─ send_to_queue()
    │  final_channel_id = channel_id or TELEGRAM_CHANNEL_ID
    │
    └─ handle() dispatcher
       → вызывает telegram_send()
       → вызывает telegram_channel_stats()
       → все используют TELEGRAM_CHANNEL_ID как default
```

---

## 💡 Когда используется TELEGRAM_CHANNEL_ID

| Ситуация | Используется? | Пример |
|----------|--------------|--------|
| `send_to_queue("текст")` | ✅ Да | Базовая публикация в канал |
| `send_to_queue("текст", chat_id="999")` | ❌ Нет | Переопределяется на 999 |
| `telegram_send(text="текст")` | ✅ Да | Отправка в основной канал |
| `telegram_send(text="текст", chat_id="999")` | ❌ Нет | Переопределяется на 999 |
| `telegram_channel_stats()` | ✅ Да | Статистика основного канала |
| `telegram_channel_stats(chat_id="999")` | ❌ Нет | Статистика канала 999 |
| Кросс-постинг с chain_id | ✅ Да | Идёт в основной канал + привязка |

---

## ⚙️ Технические детали

### Где определяется в base.py

```python
# Строка ~47 в base.py
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")          # ← ВОТ
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")   # ← И ВОТ
```

### Как импортируется в tyoma.py

```python
# Строка 8 в tyoma.py
from base import *  # ← Импортирует всё из base, включая TELEGRAM_CHANNEL_ID
```

### Как используется в shared_tools.py

```python
# Строка 10 в shared_tools.py
from base import GUMROAD_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHANNEL_ID, TELEGRAM_ADMIN_CHAT_ID, log

# Строка 26-30 в shared_tools.py
def telegram_send(chat_id="", text="", confirm=True):
    # ...
    final_chat_id = chat_id or TELEGRAM_CHANNEL_ID  # ← Используется здесь
```

---

## 🧪 Проверка работы

### Через Python REPL

```python
# В mila-office/:
python
>>> from base import TELEGRAM_CHANNEL_ID
>>> print(TELEGRAM_CHANNEL_ID)
1003005733230

>>> from shared_tools import telegram_send
>>> result = telegram_send(text="Тест", confirm=False)
# Сообщение будет отправлено в канал 1003005733230
```

### Через Tyoma CLI

```bash
cd mila-office
python tyoma.py

# В интерактивном режиме:
/пост
# → Tyoma прочитает контент и опубликует в TELEGRAM_CHANNEL_ID

/статус
# → Покажет статистику TELEGRAM_CHANNEL_ID
```

### Через Flask веб-интерфейс

```
http://127.0.0.1:5000
→ Выберите Tyoma
→ Напишите сообщение: "Создай пост"
→ Tyoma создаст и опубликует в TELEGRAM_CHANNEL_ID
```

---

## ⚠️ Важно знать

### ✅ Правильное использование

```python
# Хорошо: Позволяет agentam гибко выбирать канал
send_to_queue(text, channel_id="")      # → используется default
send_to_queue(text, channel_id="999")   # → используется явный канал
```

### ❌ Неправильное использование

```python
# Плохо: Жёсткий канал без возможности переопределить
final_chat_id = TELEGRAM_CHANNEL_ID  # Всегда используется

# Плохо: Забыли, что переменная есть, пишут параметр как обязательный
def telegram_send(chat_id):  # ← должно быть chat_id=""
    ...
```

---

## 📚 Связанные файлы

- **tools/.env** — где хранится значение `TELEGRAM_CHANNEL_ID=1003005733230`
- **mila-office/base.py** — где загружается переменная
- **mila-office/shared_tools.py** — где используется как default
- **mila-office/tyoma.py** — где агент использует через send_to_queue()
- **mila-office/shared_tools.py:26** — функция `telegram_send()`
- **mila-office/shared_tools.py:67** — функция `telegram_channel_stats()`

---

## 🔗 Интеграция с другими агентами

Хотя TELEGRAM_CHANNEL_ID создан в основном для Tyoma, другие агенты тоже могут его использовать:

```python
# Любой агент может импортировать:
from base import TELEGRAM_CHANNEL_ID
from shared_tools import telegram_send

# И использовать:
telegram_send(text="Уведомление от Dima")  # → в TELEGRAM_CHANNEL_ID
```

Это полезно для:
- **Producer** — публиковать в Telegram после Instagram
- **Dima** — отправлять отчёты о продажах
- **Manager** — уведомления об ошибках или событиях

---

## 📝 Примеры из жизни

### Сценарий 1: Еженедельный контент

```
1. Marina создаёт пост в Instagram
2. Vasya расписывает на неделю
3. Tyoma видит что пост готов → адаптирует для Telegram
4. send_to_queue(text, chain_id=ig_abc) → публикуется в TELEGRAM_CHANNEL_ID
5. Оба поста связаны через chain_id для аналитики
```

### Сценарий 2: Новый лид

```
1. Telegram бот получает ХОЧУ от пользователя
2. Tyoma видит сообщение (telegram_get_updates)
3. Tyoma отправляет ответ: telegram_send(text="спасибо")
4. Используется TELEGRAM_CHANNEL_ID для публичных уведомлений
5. Для личного ответа пользователю используется его chat_id
```

### Сценарий 3: Статистика

```
1. Дима спрашивает: "Как статистика канала?"
2. Tyoma вызывает: telegram_channel_stats()
3. Без явного chat_id → используется TELEGRAM_CHANNEL_ID
4. Возвращает: "В канале 1234 подписчиков"
```

---

**Дата создания:** 2026-06-08  
**Версия:** 1.0  
**Статус:** ✅ TELEGRAM_CHANNEL_ID полностью интегрирован во все агенты
