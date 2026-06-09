# CHAIN_DASHBOARD.py — Интеграция с webapp.py

## Краткая справка

`CHAIN_DASHBOARD.py` — это Flask blueprint для **мониторинга цепочек агентов** в реальном времени. Отслеживает активные цепочки, историю, timeline агентов и метрики производительности.

## Интеграция (3 шага)

### 1. Регистрация blueprint в webapp.py

В файле `e:\MILA GOLD\mila-office\webapp.py` найти строку:

```python
app = Flask(__name__)
```

Сразу после неё добавить:

```python
# ─── CHAIN_DASHBOARD: мониторинг цепочек агентов ──────
from chain_dashboard import chain_bp
app.register_blueprint(chain_bp)
```

### 2. Убедиться, что memory.py логирует события

`chain_dashboard.py` читает события из `memory.EVENTS` (JSONL файл). Убедиться, что он существует:

```python
# Должен быть в memory.py (уже есть)
EVENTS = MEM_DIR / "events.jsonl"

def log_event(kind: str, payload: dict | None = None):
    """Append-only аудит."""
    ...
```

✅ Это уже в `memory.py`, не требует изменений.

### 3. Использовать логирование из pipeline.py (опционально)

Если вы используете `pipeline.py` для запуска цепочек, добавить логирование:

```python
# В начало pipeline.py
from chain_dashboard import log_chain_start, log_chain_step, log_chain_end
import time

# Перед началом цепочки
chain_id = f"content_week_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
from_agent = "n8n"  # или "user"
agents = ["olya", "marina", "victoria", "vasya"]  # список агентов в цепочке

log_chain_start(chain_id, from_agent, agents, description="Еженедельный контент план")

# После каждого агента (обёртка вокруг run_agent)
t0 = time.time()
reply, history = run_agent_with_retry(...)
elapsed_ms = (time.time() - t0) * 1000

log_chain_step(
    chain_id=chain_id,
    agent=agent_key,
    step_num=step_index,
    status="done",  # или "failed"
    elapsed_ms=elapsed_ms,
    input_text=msg,
    output_text=reply
)

# В конце цепочки
total_ms = (time.time() - t_chain_start) * 1000
log_chain_end(chain_id, status="ok", total_ms=total_ms)
```

## Доступные маршруты

После интеграции доступны следующие URL:

### Веб-интерфейс
- **`GET http://127.0.0.1:5000/chains`** — дашборд мониторинга (браузер)

### REST API

#### 1. Активные цепочки
```
GET /chains/api/active
```
**Ответ:**
```json
{
  "ok": true,
  "chains": [
    {
      "chain_id": "content_week_20260608_123456",
      "from_agent": "n8n",
      "agents": ["olya", "marina", "victoria", "vasya"],
      "status": "running",
      "elapsed_ms": 45230,
      "elapsed_human": "45.2s",
      "start_ts": "2026-06-08T10:30:45Z",
      "description": "Еженедельный контент план"
    }
  ],
  "count": 1
}
```

#### 2. История цепочек
```
GET /chains/api/history?limit=50&status=ok
```
Параметры:
- `limit` (int, default=50) — количество записей (макс 200)
- `status` (string) — фильтр по статусу: "ok" или "failed"

#### 3. Timeline агентов
```
GET /chains/api/timeline
```
**Ответ:**
```json
{
  "ok": true,
  "agents": {
    "marina": {
      "status": "running",
      "chain_id": "content_week_...",
      "elapsed_ms": 12345,
      "elapsed_human": "12.3s"
    },
    "victoria": {
      "status": "idle"
    }
  }
}
```

#### 4. Детали цепочки
```
GET /chains/api/details/<chain_id>
```
**Ответ:**
```json
{
  "ok": true,
  "chain": {
    "chain_id": "content_week_...",
    "from_agent": "n8n",
    "agents": ["olya", "marina", "victoria", "vasya"],
    "status": "ok",
    "start_ts": "2026-06-08T10:30:45Z",
    "end_ts": "2026-06-08T10:45:30Z",
    "total_ms": 885000,
    "total_human": "14.8m",
    "steps": [
      {
        "agent": "olya",
        "step_num": 1,
        "status": "done",
        "elapsed_ms": 12345,
        "ts": "2026-06-08T10:32:10Z",
        "input_summary": "Найди 3 вирусные темы...",
        "output_summary": "Тема 1: Тревожная привязанность..."
      }
    ],
    "step_count": 4
  }
}
```

#### 5. Метрики производительности
```
GET /chains/api/metrics
```
**Ответ:**
```json
{
  "ok": true,
  "agents": {
    "marina": {
      "avg_ms": 23456,
      "avg_human": "23.5s",
      "min_ms": 5000,
      "max_ms": 45000,
      "count": 15,
      "success_rate": 93.3,
      "success": 14,
      "failed": 1
    }
  },
  "overall": {
    "avg_ms": 18900,
    "total_tasks": 42,
    "success_rate": 95.2,
    "success": 40,
    "failed": 2
  }
}
```

## Структура логирования

`chain_dashboard.py` читает события из `memory.EVENTS` (JSONL):

```jsonl
{"ts":"2026-06-08T10:30:45Z","kind":"chain:start","payload":{"chain_id":"content_week_...","from_agent":"n8n","agents":["olya","marina","victoria","vasya"],"description":"Еженедельный контент план"}}
{"ts":"2026-06-08T10:32:10Z","kind":"chain:step","payload":{"chain_id":"content_week_...","agent":"olya","step_num":1,"status":"done","elapsed_ms":85200,"input_text":"...","output_text":"..."}}
{"ts":"2026-06-08T10:45:30Z","kind":"chain:end","payload":{"chain_id":"content_week_...","status":"ok","total_ms":885000,"error":""}}
```

Типы событий:
- **`chain:start`** — начало цепочки
- **`chain:step`** — завершение шага (агент)
- **`chain:end`** — конец цепочки

## Примеры использования

### Пример 1: запуск цепочки из n8n с логированием

```python
# В pipeline.py (вызывается из n8n: python pipeline.py new_client --notify)

import time
from chain_dashboard import log_chain_start, log_chain_step, log_chain_end
from datetime import datetime

def run_chain(chain_key):
    chain_id = f"{chain_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    from_agent = "n8n"
    
    chains_config = CHAINS[chain_key]  # из pipeline.py
    agents = [agent_key for agent_key, _ in chains_config]
    
    # Логируем начало
    log_chain_start(chain_id, from_agent, agents, 
                    description=f"Цепочка {chain_key}")
    
    t_start = time.time()
    prev_reply = memory.read_context().get("input")
    
    for step_num, (agent_key, prompt_template) in enumerate(chains_config, 1):
        t0 = time.time()
        
        try:
            # Запускаем агента
            agent = _load_agent(agent_key)
            msg = prompt_template.format(prev=prev_reply, context=json.dumps(memory.read_context()))
            reply, _ = run_agent_with_retry(
                _client, agent["system"], agent["tools"], agent["handle"],
                msg, [], agent_key=agent_key
            )
            
            elapsed_ms = (time.time() - t0) * 1000
            
            # Логируем шаг
            log_chain_step(
                chain_id=chain_id,
                agent=agent_key,
                step_num=step_num,
                status="done",
                elapsed_ms=elapsed_ms,
                input_text=msg,
                output_text=reply
            )
            
            prev_reply = reply
        
        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            log_chain_step(chain_id, agent_key, step_num, "failed", elapsed_ms)
            
            # Логируем ошибку в конце цепочки
            total_ms = (time.time() - t_start) * 1000
            log_chain_end(chain_id, "failed", total_ms, error=str(e)[:100])
            raise
    
    # Логируем успех
    total_ms = (time.time() - t_start) * 1000
    log_chain_end(chain_id, "ok", total_ms)
    
    return prev_reply
```

### Пример 2: проверка метрик из браузера

1. Открыть http://127.0.0.1:5000/chains
2. Видеть в реальном времени:
   - Активные цепочки и затраченное время
   - Какие агенты сейчас работают
   - Среднее время выполнения по агентам
   - Историю завершённых цепочек

### Пример 3: запрос API из Python

```python
import requests

# Получить список активных цепочек
resp = requests.get("http://127.0.0.1:5000/chains/api/active")
chains = resp.json()["chains"]

for chain in chains:
    print(f"{chain['chain_id']}: {chain['elapsed_human']}")

# Получить метрики
resp = requests.get("http://127.0.0.1:5000/chains/api/metrics")
metrics = resp.json()["overall"]
print(f"Overall success rate: {metrics['success_rate']:.1f}%")
```

## Что отслеживается

### 1. Активные цепочки
- ID цепочки
- От какого источника (n8n, user, external)
- Список агентов в цепочке
- Прошедшее время с момента старта
- Статус (всегда "running")

### 2. История цепочек
- Завершённые цепочки с окончательным статусом (ok / failed)
- Общее время выполнения
- Ошибки (если есть)
- Полный список агентов

### 3. Timeline агентов
- Для каждого известного агента
- Статус (running / idle)
- Если работает — какая цепочка и как долго

### 4. Детали цепочки
- Все шаги в цепочке с временем выполнения каждого
- Input/output для каждого шага (первые 200 символов)
- Общее время от start до end

### 5. Метрики производительности
- По каждому агенту:
  - Среднее время выполнения
  - Минимальное и максимальное время
  - Количество выполненных задач
  - Процент успешного выполнения
- Общие метрики:
  - Средний результат по всем агентам
  - Всего задач, успешных, ошибок

## Где логи хранятся

Все события логируются в файл:
```
E:\MILA GOLD\mila-office\memory\events.jsonl
```

Это append-only журнал — каждое событие добавляется одной строкой JSON. Дашборд читает этот файл полностью при каждом обновлении (на production может понадобиться оптимизация: архивирование старых событий, БД и т.п.).

## Ограничения и оптимизация

### Текущие ограничения
- Логирование в памяти (`memory.EVENTS`) — медленно растёт
- При 1000+ событиях дашборд начнёт медленнее работать
- Без механизма ротации логов

### На production (если будет нужна):
1. **Архивирование**: раз в месяц перемещать старые события в `events_archive_2026-06.jsonl`
2. **БД**: переместить события в Supabase `chain_events` таблицу
3. **Кэширование**: кэшировать метрики на часовые интервалы

Но для локального однопользовательского офиса текущий подход нормален.

## Расширения

Можно добавить:

### 1. Экспорт в CSV
```python
@chain_bp.route("/api/export/history.csv")
def export_csv():
    history = _build_chain_history(limit=1000)
    # Экспортировать в CSV
```

### 2. Фильтр по временному периоду
```
GET /chains/api/history?from=2026-06-01&to=2026-06-08
```

### 3. Отправка алертов
Если цепочка падает или медленно выполняется:
```python
if chain["status"] == "failed":
    send_telegram_alert(f"Цепочка {chain_id} упала")
```

### 4. Вебсокеты для live-обновления
Вместо polling каждые 5 сек, использовать WebSocket для push.

## Отладка

Если дашборд не показывает данные:

1. Проверить, что blueprint зарегистрирован:
```python
python -c "from webapp import app; print([r.rule for r in app.url_map.iter_rules() if 'chains' in r.rule])"
```

2. Проверить, что события пишутся в memory.EVENTS:
```bash
tail -20 "E:\MILA GOLD\mila-office\memory\events.jsonl"
```

3. Проверить логи Flask:
```
E:\MILA GOLD\logs\webapp.log
```

## Контакт

При вопросах см. комментарии в коде `chain_dashboard.py` или раздел **"Что это такое"** в начале файла.
