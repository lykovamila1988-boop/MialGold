# CHAIN_DASHBOARD.py — Архитектура и диаграммы

## Общая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        PIPELINE (n8n или user)                  │
│  python pipeline.py content_week                                │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   АГЕНТЫ (Марина → Виктория → Вася)             │
│  • Запуск каждого агента                                        │
│  • Передача результата следующему                              │
│  • Time tracking                                                │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼ (опционально)
┌─────────────────────────────────────────────────────────────────┐
│           CHAIN_DASHBOARD ЛОГИРОВАНИЕ                           │
│  log_chain_start()  ──→  [chain:start]  ──→                     │
│  log_chain_step()   ──→  [chain:step]   ──→                     │
│  log_chain_end()    ──→  [chain:end]    ──→                     │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MEMORY.EVENTS (JSONL)                         │
│  mila-office/memory/events.jsonl                                │
│                                                                 │
│  {"ts":"...", "kind":"chain:start", "payload":{...}}           │
│  {"ts":"...", "kind":"chain:step",  "payload":{...}}           │
│  {"ts":"...", "kind":"chain:end",   "payload":{...}}           │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CHAIN_DASHBOARD.PY                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Модели данных:                                          │  │
│  │ • _build_active_chains()      ← какие цепи выполняются  │  │
│  │ • _build_chain_history()      ← история завершённых     │  │
│  │ • _build_agent_timeline()     ← что делает каждый агент │  │
│  │ • _build_chain_details()      ← полные логи цепи        │  │
│  │ • _build_performance_metrics()← метрики (avg time, %)   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                     │
│                    (REST API маршруты)                         │
└─────────────────┬───────────────────────────────────────────────┘
                  │
       ┌──────────┴──────────────────────────┬────────────────────┐
       │                                      │                    │
       ▼                                      ▼                    ▼
   API: JSON                          WEB: HTML+CSS+JS        CLI: curl
   /chains/api/                       /chains                 (скрипты)
   • active                           (дашборд)
   • history
   • timeline
   • details/<id>
   • metrics
       │                                      │                    │
       └──────────────────────┬───────────────┴────────────────────┘
                              │
                    (ФРОНТЕНД Обновляет каждые 5 сек)
```

## Жизненный цикл цепочки

```
1. ИНИЦИАЛИЗАЦИЯ
   ┌────────────────────────────────────────┐
   │ pipeline.py запускает цепочку           │
   │ chain_id = "content_week_20260608..."   │
   │ agents = ["olya", "marina", "victoria"] │
   └────────────────┬───────────────────────┘
                    │
                    ▼
   ┌────────────────────────────────────────┐
   │ log_chain_start(                        │
   │   chain_id=...,                        │
   │   from_agent="n8n",                    │
   │   agents=[...],                        │
   │   description="..."                    │
   │ )                                      │
   └────────────────┬───────────────────────┘
                    │
                    ▼ ✓ EVENT: chain:start

2. ВЫПОЛНЕНИЕ (для каждого агента)
   ┌────────────────────────────────────────┐
   │ t0 = time.time()                       │
   │ reply = run_agent(olya, msg)           │
   │ elapsed_ms = (time.time() - t0) * 1000 │
   └────────────────┬───────────────────────┘
                    │
                    ▼
   ┌────────────────────────────────────────┐
   │ log_chain_step(                        │
   │   chain_id=...,                        │
   │   agent="olya",                        │
   │   step_num=1,                          │
   │   status="done",                       │
   │   elapsed_ms=elapsed_ms                │
   │ )                                      │
   └────────────────┬───────────────────────┘
                    │
                    ▼ ✓ EVENTS: chain:step (для каждого агента)

3. ЗАВЕРШЕНИЕ
   ┌────────────────────────────────────────┐
   │ total_ms = (time.time() - t_start) ... │
   │                                        │
   │ if error:                              │
   │   status = "failed"                    │
   │ else:                                  │
   │   status = "ok"                        │
   └────────────────┬───────────────────────┘
                    │
                    ▼
   ┌────────────────────────────────────────┐
   │ log_chain_end(                         │
   │   chain_id=...,                        │
   │   status="ok" or "failed",             │
   │   total_ms=total_ms,                   │
   │   error=""                             │
   │ )                                      │
   └────────────────┬───────────────────────┘
                    │
                    ▼ ✓ EVENT: chain:end
   
   Цепочка завершена и видна в истории на дашборде.
```

## Структура дашборда (UI)

```
┌──────────────────────────────────────────────────────────────────┐
│                    MILA OFFICE — Мониторинг цепочек             │
│                   Отслеживание и производительность            │
│                               [Обновить]                        │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌────────────┐
│ Активные цепочки     │  │ Timeline агентов     │  │ Произв-ть  │
│                      │  │                      │  │            │
│ 2 цепочки            │  │ marina:   ▶ Работает │  │ Успеш: 95% │
│                      │  │ victoria: ⚪ Ждёт     │  │ Задач: 42  │
│ • content_week...    │  │ alina:    ▶ Работает │  │ Время: 18s │
│   От: n8n            │  │ vasya:    ⚪ Ждёт     │  │            │
│   Прошло: 45.2s      │  │ olya:     ⚪ Ждёт     │  │            │
│                      │  │ dima:     ⚪ Ждёт     │  │            │
│ • new_client...      │  │                      │  │            │
│   От: user           │  │                      │  │            │
│   Прошло: 12.3s      │  │                      │  │            │
└──────────────────────┘  └──────────────────────┘  └────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    История цепочек (последние 20)               │
│                                                                  │
│ ┌─────────────────────────────┐                                 │
│ │ content_week_20260608_123456 │ ✅ Завершено  14.8m            │
│ │ Агенты: olya, marina, vic... │                               │
│ └─────────────────────────────┘                                 │
│                                                                  │
│ ┌─────────────────────────────┐                                 │
│ │ new_client_20260608_115000   │ ✅ Завершено  8.3m             │
│ │ Агенты: alina, lera          │                               │
│ └─────────────────────────────┘                                 │
│                                                                  │
│ ┌─────────────────────────────┐                                 │
│ │ weekly_report_20260607_102200│ ❌ Ошибка 22.1m               │
│ │ Агенты: dima, marina, manager│ ⚠️ Timeout на шаге 2         │
│ └─────────────────────────────┘                                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

(Обновляется каждые 5 сек, данные из API /chains/api/*)
```

## Поток данных через цепочку

```
pipeline.py запускает цепочку
       │
       ├─→ log_chain_start()
       │   ├─→ memory.log_event("chain:start", {...})
       │   └─→ mila-office/memory/events.jsonl (append)
       │
       ├─→ ДЛЯ КАЖДОГО АГЕНТА:
       │
       │   [Agent 1: Olya]
       │   ├─→ msg = "Найди тренды..."
       │   ├─→ reply = run_agent(...)
       │   └─→ log_chain_step("olya", status="done", elapsed_ms=85000)
       │       └─→ memory.log_event("chain:step", {...})
       │           └─→ mila-office/memory/events.jsonl (append)
       │
       │   [Agent 2: Marina]
       │   ├─→ msg = prev_reply + " Напиши пост..."
       │   ├─→ reply = run_agent(...)
       │   └─→ log_chain_step("marina", status="done", elapsed_ms=130000)
       │
       │   [Agent 3: Victoria]
       │   ├─→ msg = prev_reply + " Отредактируй..."
       │   ├─→ reply = run_agent(...)
       │   └─→ log_chain_step("victoria", status="done", elapsed_ms=45000)
       │
       ├─→ log_chain_end(status="ok", total_ms=260000)
       │   └─→ memory.log_event("chain:end", {...})
       │       └─→ mila-office/memory/events.jsonl (append)
       │
       └─→ (опционально) Notify n8n webhook

ДАШБОРД:
  1. Читает mila-office/memory/events.jsonl
  2. Парсит события, группирует по chain_id
  3. Строит модели: active_chains, history, timeline, details
  4. Отдаёт по API /chains/api/*
  5. Фронтенд рендерит HTML каждые 5 сек
```

## Интеграция с webapp.py

```
┌────────────────────────────────────────┐
│         webapp.py запускается          │
│         python webapp.py               │
└────────┬───────────────────────────────┘
         │
         ├─→ from flask import Flask
         │   app = Flask(__name__)
         │
         ├─→ ✅ NEW: from chain_dashboard import chain_bp
         │              app.register_blueprint(chain_bp)
         │
         ├─→ Загружаются маршруты:
         │   • GET /                          (главная)
         │   • GET /api/meta                  (agents list)
         │   • POST /api/chat                 (chat)
         │   • ... (другие маршруты webapp)
         │
         └─→ ✅ + Маршруты из chain_dashboard:
             • GET /chains                    (дашборд HTML)
             • GET /chains/api/active        (JSON)
             • GET /chains/api/history       (JSON)
             • GET /chains/api/timeline      (JSON)
             • GET /chains/api/details/<id>  (JSON)
             • GET /chains/api/metrics       (JSON)

Браузер открывает http://127.0.0.1:5000/chains
         │
         ▼
┌────────────────────────────────────────┐
│         HTML ДАШБОРД (инлайн)          │
│  _DASHBOARD_HTML переменная             │
│                                        │
│  JavaScript каждые 5 сек:              │
│  fetch("/chains/api/active")           │
│  fetch("/chains/api/timeline")         │
│  fetch("/chains/api/metrics")          │
│  fetch("/chains/api/history")          │
│                                        │
│  Рендерит эти данные в карточки       │
└────────────────────────────────────────┘
```

## Классы и функции (сыммари)

```
ОСНОВНЫЕ ФУНКЦИИ ЛОГИРОВАНИЯ (для pipeline.py):
  log_chain_start(chain_id, from_agent, agents, description)
  log_chain_step(chain_id, agent, step_num, status, elapsed_ms, ...)
  log_chain_end(chain_id, status, total_ms, error)

МОДЕЛИ ДАННЫХ (читают из memory.EVENTS):
  _read_chain_events() → list[dict]
    └─ все события вида {"kind": "chain:*"}

  _build_active_chains() → list[dict]
    └─ цепочки без chain:end события
    └─ {"chain_id", "from_agent", "agents", "status", "elapsed_ms", ...}

  _build_chain_history(limit=50) → list[dict]
    └─ все события chain:end
    └─ {"chain_id", "status", "total_ms", "error", ...}

  _build_agent_timeline() → dict
    └─ {"agent_name": {"status": "running"|"idle", "chain_id", ...}}

  _build_chain_details(chain_id) → dict
    └─ {"chain_id", "from_agent", "agents", "steps": [...], ...}

  _build_performance_metrics() → dict
    └─ {"agent_name": {"avg_ms", "min_ms", "max_ms", "success_rate"}, ...}

REST API МАРШРУТЫ (Flask Blueprint):
  @chain_bp.route("/api/active") → api_active_chains()
  @chain_bp.route("/api/history") → api_chain_history()
  @chain_bp.route("/api/timeline") → api_agent_timeline()
  @chain_bp.route("/api/details/<id>") → api_chain_details()
  @chain_bp.route("/api/metrics") → api_performance_metrics()
  @chain_bp.route("") → dashboard_html()

HTML ДАШБОРД (JavaScript):
  loadDashboard() — загружает все 4 API вызова параллельно
  renderActive() — карточка активных цепочек
  renderTimeline() — карточка timeline агентов
  renderMetrics() — карточка метрик
  renderHistory() — история цепочек
```

## Формат событий (JSONL)

```json
Событие 1: Начало цепочки
{
  "ts": "2026-06-08T10:30:45Z",
  "kind": "chain:start",
  "payload": {
    "chain_id": "content_week_20260608_103045",
    "from_agent": "n8n",
    "agents": ["olya", "marina", "victoria", "vasya"],
    "description": "Еженедельный контент-план"
  }
}

Событие 2: Завершение шага 1 (Olya)
{
  "ts": "2026-06-08T10:31:10Z",
  "kind": "chain:step",
  "payload": {
    "chain_id": "content_week_20260608_103045",
    "agent": "olya",
    "step_num": 1,
    "status": "done",
    "elapsed_ms": 85000,
    "input_text": "Найди 3 вирусные темы...",
    "output_text": "Тема 1: Тревожная привязанность..."
  }
}

Событие 3: Завершение шага 2 (Marina)
{
  "ts": "2026-06-08T10:33:20Z",
  "kind": "chain:step",
  "payload": {
    "chain_id": "content_week_20260608_103045",
    "agent": "marina",
    "step_num": 2,
    "status": "done",
    "elapsed_ms": 130000,
    "input_text": "Напиши Reels...",
    "output_text": "Готовый текст Reels..."
  }
}

...еще события...

Событие N: Конец цепочки
{
  "ts": "2026-06-08T10:45:30Z",
  "kind": "chain:end",
  "payload": {
    "chain_id": "content_week_20260608_103045",
    "status": "ok",
    "total_ms": 900000,
    "error": ""
  }
}
```

## Временные интервалы в дашборде

```
REAL-TIME обновления:

webapp.py:
  └─ слушает HTTP запросы на /chains/api/*

Дашборд (браузер):
  └─ JavaScript fetch() каждые 5 сек
     ├─ /chains/api/active     (активные цепочки)
     ├─ /chains/api/timeline   (timeline агентов)
     ├─ /chains/api/metrics    (метрики)
     └─ /chains/api/history    (история)

chain_dashboard.py:
  └─ читает memory.EVENTS (JSONL файл) целиком
     ├─ полный скан каждый раз (для < 10000 событий OK)
     └─ парсит JSON, группирует по chain_id

Результат:
  └─ Дашборд обновляется в браузере каждые 5 сек
     ├─ новые цепочки появляются мгновенно (< 1 сек)
     ├─ завершённые цепочки исчезают из активных
     └─ история обновляется
```

## Оптимизация (future)

```
ТЕКУЩЕЕ СОСТОЯНИЕ (v1):
  • Ежедневные цепочки: OK (десятки событий/день)
  • История за месяц: OK (< 1000 событий)
  • Полный скан JSONL: O(n) — нормально

ПРОБЛЕМЫ ПОСЛЕ 1 ГОДА ИСПОЛЬЗОВАНИЯ:
  • events.jsonl: > 100 MB
  • Полный скан: > 5 сек
  • Браузер: лаги при обновлении

РЕШЕНИЕ (на production):
  ┌────────────────────────────────────────┐
  │ 1. РОТАЦИЯ ЛОГОВ                       │
  │    • Раз в месяц архивировать:         │
  │    • events.jsonl → events_2026-06.jsonl│
  │    • Новый events.jsonl для текущего   │
  │    • История читается из архивов       │
  │                                        │
  │ 2. МИГРАЦИЯ В БД                       │
  │    • Supabase: таблица chain_events    │
  │    • INSERT при log_chain_start/step   │
  │    • SELECT с индексом по chain_id    │
  │    • Быстрые агрегирующие запросы     │
  │                                        │
  │ 3. КЭШИРОВАНИЕ МЕТРИК                 │
  │    • Считать метрики раз в час        │
  │    • Хранить в memory.py / Supabase   │
  │    • Дашборд использует кэш вместо    │
  │      полного скана                    │
  └────────────────────────────────────────┘
```

## Зависимости и требования

```
ТРЕБУЕТСЯ:
  ✓ Flask                          (уже есть в webapp.py)
  ✓ memory.py с EVENTS (JSONL)     (уже есть)
  ✓ base.py для compose_system()   (уже есть)
  ✓ Python 3.8+
  ✓ Стандартная lib (json, logging, datetime, pathlib)

НЕ ТРЕБУЕТСЯ:
  ✗ SQLAlchemy, PostgreSQL, Redis
  ✗ Новые pip-пакеты
  ✗ Конфигурация

СОВМЕСТИМОСТЬ:
  ✓ Совместимо со всеми версиями Python 3.8+
  ✓ Работает на Windows/Linux/Mac
  ✓ Работает с webapp.py в том же процессе (Flask)
  ✓ Работает с pipeline.py в отдельном процессе (читает shared JSONL)
```

## Пример: время выполнения цепочки

```
Цепочка: content_week
Агенты:  olya (3) → marina (2) → victoria (1) → vasya (4)
                              └─ резерв

┌──────────────────────────────────┐
│ 10:30:45  START                  │
│           chain:start             │
├──────────────────────────────────┤
│ 10:30:45 - 10:31:10  OLYA (25s)  │  ═══════════════════════
│           chain:step #1           │
├──────────────────────────────────┤
│ 10:31:10 - 10:33:20  MARINA (2m) │  ═══════════════════════════════════
│           chain:step #2           │
├──────────────────────────────────┤
│ 10:33:20 - 10:34:05  VICTORIA(45s)│ ═════════════════════════
│           chain:step #3           │
├──────────────────────────────────┤
│ 10:34:05 - 10:34:20  VASYA (15s) │ ══════════
│           chain:step #4           │
├──────────────────────────────────┤
│ 10:34:20  END                    │
│           chain:end (ok)          │
│           total_ms: 215000        │
│           total_human: 3m 35s     │
└──────────────────────────────────┘

МЕТРИКИ:
  olya:    avg=25s,  count=12,  success_rate=100%
  marina:  avg=120s, count=8,   success_rate=87.5% ⚠️ SLOW!
  victoria:avg=45s,  count=15,  success_rate=100%
  vasya:   avg=18s,  count=20,  success_rate=95%

ДАШБОРД ПОКАЗЫВАЕТ:
  [TIMELINE]
    olya:     ⚪ Ждёт (24s от последней)
    marina:   ▶ Работает в цепи #2 (2m 15s прошло)
    victoria: ⚪ Ждёт (2h назад)
    vasya:    ⚪ Ждёт
```

---

## Диаграмма: полный цикл

```
┌──────────────────────────────────────────────────────────────┐
│                     CHAIN LIFECYCLE                          │
└──────────────────────────────────────────────────────────────┘

     pipeline.py
         │
         ├─→ ИНИЦИАЛИЗАЦИЯ
         │   • chain_id = "my_chain_xxx"
         │   • agents = [список]
         │   • t_start = time.time()
         │   │
         │   └─→ LOG START
         │       log_chain_start(...)
         │       → memory.log_event("chain:start", {...})
         │       → events.jsonl
         │
         ├─→ ДЛЯ КАЖДОГО АГЕНТА (LOOP)
         │   │
         │   ├─→ АГЕНТ 1
         │   │   • t0 = time.time()
         │   │   • reply = run_agent(...)
         │   │   • elapsed = (time.time() - t0) * 1000
         │   │   │
         │   │   └─→ LOG STEP
         │   │       log_chain_step(..., step_num=1, ...)
         │   │       → memory.log_event("chain:step", {...})
         │   │       → events.jsonl
         │   │
         │   ├─→ АГЕНТ 2
         │   │   • t0 = time.time()
         │   │   • reply = run_agent(prev_reply + ...)
         │   │   • elapsed = (time.time() - t0) * 1000
         │   │   │
         │   │   └─→ LOG STEP
         │   │       log_chain_step(..., step_num=2, ...)
         │   │       → events.jsonl
         │   │
         │   └─→ ... АГЕНТ N ...
         │
         ├─→ ЗАВЕРШЕНИЕ
         │   • total_ms = (time.time() - t_start) * 1000
         │   • status = "ok" или "failed"
         │   │
         │   └─→ LOG END
         │       log_chain_end(..., total_ms, status)
         │       → memory.log_event("chain:end", {...})
         │       → events.jsonl
         │
         └─→ ГОТОВО


↓ ↓ ↓  (Параллельно дашборд читает события)  ↓ ↓ ↓

ДАШБОРД ЧИТАЕТ СОБЫТИЯ:

    mila-office/memory/events.jsonl
         │
         ├─→ chain_dashboard.py
         │   • _read_chain_events() → все события
         │   • _build_active_chains() → какие цепи выполняются
         │   • _build_chain_history() → история завершённых
         │   • _build_agent_timeline() → что делает каждый агент
         │   • _build_chain_details(id) → полные логи
         │   • _build_performance_metrics() → метрики
         │   │
         │   ├─→ API МАРШРУТЫ (Flask)
         │   │   • /chains/api/active
         │   │   • /chains/api/history
         │   │   • /chains/api/timeline
         │   │   • /chains/api/details/<id>
         │   │   • /chains/api/metrics
         │   │
         │   └─→ HTML ДАШБОРД
         │       • /chains (браузер)
         │       • JavaScript fetch() каждые 5 сек
         │       • Рендерит карточки (active, timeline, metrics, history)
         │
         └─→ БРАУЗЕР (http://127.0.0.1:5000/chains)
             ┌──────────────────────────┐
             │ Активные цепочки    │ 2  │
             ├──────────────────────────┤
             │ Timeline агентов:        │
             │  marina: ▶ работает     │
             │  victoria: ⚪ ждёт       │
             ├──────────────────────────┤
             │ Успешность: 95.2%        │
             │ Задач: 42                │
             ├──────────────────────────┤
             │ История цепочек: 20      │
             └──────────────────────────┘
```
