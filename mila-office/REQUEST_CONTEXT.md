# 📮 REQUEST CONTEXT — Контекст запросов между агентами

## 📝 Проблема

Раньше агент не знал:
- ❌ От КОГО пришел запрос
- ❌ КОМУ вернуть результат
- ❌ КАКОЙ ID цепочки обработки

Теперь агент знает весь контекст! ✅

---

## 🔄 ПОТОК ДАННЫХ: ПОЛНЫЙ КОНТЕКСТ

### Шаг 1: Пользователь отправляет Марине

```javascript
// В браузере
POST /api/chat {
    agent: "marina",
    message: "Напиши пост про выбор",
    from_agent: "user",           // ← От кого
    to_agent: null,               // ← Кому (null = сквозь цепочку)
    chain_id: "workflow_123"      // ← ID цепочки
}
```

### Шаг 2: Сервер создаёт задание

```python
# В routes.py
job = {
    "id": "job_abc123",
    "agent_key": "marina",
    "from_agent": "user",          # Кто отправил
    "to_agent": None,              # Кому адресовано
    "chain_id": "workflow_123",    # ID цепочки
    "status": "pending",
    "reply": None,
}
```

### Шаг 3: Марина обрабатывает и пишет

```
Входящее сообщение:
[from: user] [chain_id: workflow_123]
Напиши пост про выбор

Марина читает контекст и понимает:
- Запрос от пользователя (не от другого агента)
- Это часть цепочки обработки workflow_123
- Результат нужно передать дальше в цепочку

Марина пишет ответ:
Пост готов! [VERDICT: ready_next] [→ victoria]
```

### Шаг 4: Сервер обрабатывает результат

```python
# В routes.py /api/result
job = {
    "agent_key": "marina",
    "from_agent": "user",
    "chain_id": "workflow_123",
    "verdict": "ready_next",
    "next_agent": "victoria",
    
    "chain_context": {
        "current_agent": "marina",
        "from_agent": "user",
        "original_to_agent": None,
        "chain_id": "workflow_123"
    }
}
```

### Шаг 5: Браузер переходит на Викторию и отправляет её вызов

```javascript
// Автоматическое переключение и вызов Виктории
POST /api/chat {
    agent: "victoria",
    message: "Пост от Марины: ...",
    from_agent: "marina",         // ← Теперь от Марины!
    to_agent: "vasya",            // ← Может быть переделегировано
    chain_id: "workflow_123"      // ← Один ID цепочки
}
```

### Шаг 6: Виктория видит контекст

```
Входящее сообщение:
[from: marina] [to: vasya] [chain_id: workflow_123]
Пост от Марины для редактуры...

Виктория понимает:
- Запрос от Марины (знает кто отправил)
- Результат может быть адресован Васе (есть подсказка)
- Это часть цепочки workflow_123 (отслеживаемая работа)

Виктория отредактирует и вернет:
[DOCUMENTO]Готовый текст[/ДОКУМЕНТ] [VERDICT: done]
```

---

## 📦 API СТРУКТУРЫ

### POST /api/chat — Создание задания

```python
# Запрос
{
    "agent": "marina",                # (обязательно) агент
    "message": "Текст сообщения",     # (обязательно) сообщение
    "from_agent": "user",             # (опционально) от кого (default: "user")
    "to_agent": "vasya",              # (опционально) кому адресовано
    "chain_id": "workflow_123"        # (опционально) ID цепочки
}

# Ответ
{
    "job": "job_abc123",
    "ok": true,
    "agent": "marina",
    "from_agent": "user",
    "chain_id": "workflow_123"
}
```

### GET /api/result?job=X — Получение результата

```python
# Ответ
{
    "job": "job_abc123",
    "agent_key": "marina",
    "from_agent": "user",
    "chain_id": "workflow_123",
    
    "reply": "Пост готов!",
    "verdict": "ready_next",
    "next_agent": "victoria",
    
    "chain_context": {
        "current_agent": "marina",
        "from_agent": "user",
        "original_to_agent": null,
        "chain_id": "workflow_123"
    }
}
```

---

## 🎯 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Пример 1: Цепочка в одном воркфлоу

```
User ──→ [from: user, chain_id: workflow_1]
  ↓
Marina (получает от User)
  ├─ Понимает: "Я в цепочке workflow_1 от User"
  ├─ Пишет пост
  └─ [→ victoria]
  
  ↓ [from: marina, to: victoria, chain_id: workflow_1]
  
Victoria (получает от Marina, адресовано ей)
  ├─ Понимает: "Марина отправила, это для меня, часть workflow_1"
  ├─ Редактирует
  └─ [→ vasya]
  
  ↓ [from: victoria, to: vasya, chain_id: workflow_1]
  
Vasya (получает от Victoria, адресовано ему)
  ├─ Понимает: "Виктория отправила, это для меня"
  ├─ Расписывает публикацию
  └─ [VERDICT: done]
```

### Пример 2: Деделегирование задачи

```
User ──→ Marina [to: rita]
         "Напиши и спроектируй визуал"

Marina (получает от User с to: rita)
  ├─ Понимает: "User просит чтобы результат был у Rita"
  ├─ Пишет пост
  └─ [to: rita]  ← Явно переадресовывает
  
  ↓ [from: marina, to: rita]
  
Victoria (получает пост от Marina)
  ├─ Видит to: rita в контексте
  ├─ Редактирует
  └─ Тоже [to: rita]  ← Прокидывает дальше
  
  ↓ [from: victoria, to: rita]
  
Rita (получает от Victoria, адресовано ей)
  ├─ Понимает: "This is для меня специально"
  ├─ Создаёт визуалы
  └─ [VERDICT: done]
```

### Пример 3: Параллельные задачи (один chain_id)

```
Один воркфлоу может разбиться на параллельные:

User (chain_id: wf_123)
  ├─→ Marina (пишет пост, from: user, chain_id: wf_123)
  │     └─→ Victoria (редактирует, from: marina, chain_id: wf_123)
  │
  ├─→ Rita (проектирует визуалы, from: user, chain_id: wf_123)
  │
  └─→ Tyoma (готовит Telegram, from: user, chain_id: wf_123)

Все видят one chain_id, знают что работают на один результат!
```

---

## 🔍 КАК АГЕНТ ИСПОЛЬЗУЕТ КОНТЕКСТ

### В system prompt агента можно добавить:

```
Ты получаешь сообщения с контекстом:
- [from: agent_name] — от какого агента/пользователя
- [to: agent_name] — кому адресовано (если нужно переадресовать)
- [chain_id: id] — ID цепочки обработки

Пример входящего сообщения:
[from: user] [chain_id: workflow_123]
Напиши пост про выбор

Ты понимаешь:
1. Запрос от пользователя (не от другого агента)
2. Это часть цепочки workflow_123
3. Когда завершишь, передашь дальше в цепочку

Когда пишешь ответ, укажи:
- [VERDICT: ready_next] — если передаёшь дальше
- [VERDICT: done] — если это финальный результат
- [→ agent_name] — кому передать (если не стандартная цепочка)
```

### Пример обработки контекста в коде агента:

```python
# Получить контекст запроса
from message_handler import extract_request_context

message = "[from: marina] [chain_id: wf_123] Отредактируй пост..."
context = extract_request_context(message)

print(context)
# {
#     "from_agent": "marina",
#     "to_agent": None,
#     "chain_id": "wf_123"
# }

# Использовать контекст
if context["from_agent"] == "marina":
    print("Получено от Марины, это текст для редактуры")

if context["chain_id"]:
    print(f"Это часть работы {context['chain_id']}")
```

---

## 📊 ХРОНОЛОГИЯ КОНТЕКСТА

```
user (от пользователя)
  ↓
marina (знает что от user)
  ├─ может отправить [to: specific_agent]
  └─ или просто [→ victoria]
  
victoria (знает что от marina)
  ├─ может оставить [to: vasya]
  └─ или переадресовать [to: rita]
  
vasya (знает что от victoria, [to: vasya])
  ├─ может согласиться и [→ rita]
  └─ или обработать и [VERDICT: done]
```

---

## ✅ ПРЕИМУЩЕСТВА КОНТЕКСТА

✅ **Отслеживаемость** — каждый агент знает историю запроса  
✅ **Гибкость** — можно переадресовывать задачи  
✅ **Деделегирование** — явное указание "это для Rita"  
✅ **Параллелизм** — один chain_id для нескольких параллельных задач  
✅ **Отладка** — видно кто отправил и кому  
✅ **Аудит** — полная история цепочки обработки  

---

## 🔧 РЕАЛИЗАЦИЯ В МОДУЛЯХ

### message_handler.py

```python
# Извлечь контекст из сообщения
context = extract_request_context("[from: marina] [to: vasya] текст")
# → {"from_agent": "marina", "to_agent": "vasya", "chain_id": None}

# Построить сообщение с контекстом
msg = build_agent_message(
    content="Отредактируй пост",
    from_agent="marina",
    to_agent="vasya",
    chain_id="wf_123"
)
# → "[from: marina] [to: vasya] [chain_id: wf_123] Отредактируй пост"

# Получить позицию агента в цепочке
info = get_agent_chain_info("victoria")
# → {
#     "agent": "victoria",
#     "position": 2,
#     "previous": "marina",
#     "next": "vasya",
#     "is_final": False
#   }
```

### session_manager.py

```python
# Сохранить сообщение с контекстом
save_message(
    session_id="sess_123",
    agent_key="victoria",
    role="assistant",
    content="Пост отредактирован",
    from_agent="marina",    # Знаем кто отправил
    to_agent="vasya"        # Знаем кому адресовано
)
```

### routes.py

```python
# POST /api/chat с контекстом
POST /api/chat {
    agent: "victoria",
    message: "Отредактируй пост",
    from_agent: "marina",
    to_agent: "vasya",
    chain_id: "wf_123"
}

# GET /api/result возвращает контекст для следующего агента
{
    chain_context: {
        current_agent: "victoria",
        from_agent: "marina",
        original_to_agent: "vasya",
        chain_id: "wf_123"
    }
}
```

---

## 🎉 ИТОГ

Теперь каждый агент знает:
- 📮 От КОГО пришел запрос
- 👤 КОМУ адресовано (если нужна переправка)
- 🔗 КАКОЙ ID цепочки (для отслеживания)

Это позволяет:
- Деделегировать задачи
- Обрабатывать параллельные процессы
- Отслеживать полную историю
- Принимать умные решения в цепочке

**КОНТЕКСТ ЗАПРОСА ГОТОВ!** ✨
