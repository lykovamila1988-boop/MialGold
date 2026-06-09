# CHAIN_DASHBOARD.py — Мониторинг цепочек агентов в реальном времени

## Что это?

Полнофункциональный Flask blueprint для отслеживания выполнения цепочек агентов (когда Марина → Виктория → Вася в одной "цепочке"). Показывает:

- ✅ **Активные цепочки** — какие цепи выполняются прямо сейчас, как долго работают
- ✅ **История цепочек** — все завершённые цепи с временем выполнения и статусом
- ✅ **Timeline агентов** — для каждого агента видно, работает ли он (и в какой цепи)
- ✅ **Детали цепочки** — по любой цепи: все шаги, время каждого этапа, input/output
- ✅ **Метрики производительности** — среднее время по агентам, success rate, min/max

## Файлы

| Файл | Назначение |
|------|-----------|
| `chain_dashboard.py` | **Основной модуль** — Flask blueprint + логирование + API + веб-интерфейс |
| `CHAIN_DASHBOARD_INTEGRATION.md` | **Инструкция по интеграции** — как подключить к webapp.py |
| `CHAIN_DASHBOARD_EXAMPLE.py` | **Практические примеры** — как использовать в pipeline.py |
| `CHAIN_DASHBOARD_README.md` | Этот файл |

## Быстрый старт (60 секунд)

### 1. Регистрация в webapp.py

В файле `webapp.py` найти:
```python
app = Flask(__name__)
```

Добавить после неё:
```python
from chain_dashboard import chain_bp
app.register_blueprint(chain_bp)
```

### 2. Запустить веб-интерфейс

```bash
cd "E:\MILA GOLD\mila-office"
python webapp.py
```

### 3. Открыть дашборд

Перейти на **http://127.0.0.1:5000/chains**

### 4. (Опционально) Добавить логирование в pipeline.py

```python
from chain_dashboard import log_chain_start, log_chain_step, log_chain_end

# Перед цепочкой
log_chain_start(chain_id, from_agent="n8n", agents=["olya", "marina", "victoria"])

# После каждого агента
log_chain_step(chain_id, agent="marina", step_num=2, status="done", elapsed_ms=12345)

# После цепочки
log_chain_end(chain_id, status="ok", total_ms=45000)
```

## Концепция: как это работает

```
pipeline.py (цепочка) ──→ memory.log_event() ──→ memory.EVENTS (JSONL) ──→ chain_dashboard.py ──→ API + веб-интерфейс
                                                                                 │
                                                                                 └──→ дашборд: http://127.0.0.1:5000/chains
```

1. **Логирование** (`pipeline.py`): вызываем `log_chain_start()`, `log_chain_step()`, `log_chain_end()`
2. **Хранилище** (`memory.py`): события пишутся в `mila-office/memory/events.jsonl` (append-only)
3. **Чтение** (`chain_dashboard.py`): читает JSONL, парсит события, строит модели данных
4. **API**: GET-маршруты отдают JSON для программного доступа
5. **Веб-интерфейс**: HTML+JS дашборд, автообновляется каждые 5 сек

## API маршруты

### Веб-интерфейс
```
GET /chains
```
Красивый дашборд в браузере с графиком timeline, метриками и историей.

### REST API (JSON)

#### Активные цепочки
```
GET /chains/api/active
```
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
      "elapsed_human": "45.2s"
    }
  ],
  "count": 1
}
```

#### История цепочек
```
GET /chains/api/history?limit=50&status=ok
```
Параметры:
- `limit` — количество записей (по умолчанию 50, макс 200)
- `status` — фильтр: "ok" или "failed" (опционально)

#### Timeline агентов
```
GET /chains/api/timeline
```
```json
{
  "ok": true,
  "agents": {
    "marina": {"status": "running", "chain_id": "content_week_...", "elapsed_human": "12.3s"},
    "victoria": {"status": "idle"},
    "alina": {"status": "running", "chain_id": "new_client_...", "elapsed_human": "5.1s"}
  }
}
```

#### Детали цепочки
```
GET /chains/api/details/content_week_20260608_123456
```
```json
{
  "ok": true,
  "chain": {
    "chain_id": "content_week_...",
    "from_agent": "n8n",
    "agents": ["olya", "marina", "victoria", "vasya"],
    "status": "ok",
    "total_human": "14.8m",
    "steps": [
      {
        "agent": "olya",
        "step_num": 1,
        "status": "done",
        "elapsed_human": "2.3s",
        "input_summary": "Найди 3 вирусные...",
        "output_summary": "Тема 1: Тревожная..."
      },
      ...
    ]
  }
}
```

#### Метрики производительности
```
GET /chains/api/metrics
```
```json
{
  "ok": true,
  "agents": {
    "marina": {
      "avg_human": "23.5s",
      "min_human": "5.0s",
      "max_human": "45.0s",
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

## Функции логирования

### 1. Начало цепочки
```python
from chain_dashboard import log_chain_start

log_chain_start(
    chain_id="content_week_20260608_123456",
    from_agent="n8n",  # откуда пришла цепочка
    agents=["olya", "marina", "victoria", "vasya"],  # какие агенты в цепи
    description="Еженедельный контент-план"  # опционально
)
```

### 2. Завершение шага (после агента)
```python
from chain_dashboard import log_chain_step
import time

t0 = time.time()
reply, _ = run_agent(...)
elapsed_ms = (time.time() - t0) * 1000

log_chain_step(
    chain_id="content_week_...",
    agent="marina",  # какой агент выполнил
    step_num=2,  # порядковый номер в цепи
    status="done",  # "done" или "failed"
    elapsed_ms=elapsed_ms,
    input_text=msg[:500],  # опционально: что дали на вход
    output_text=reply[:500]  # опционально: что вернул агент
)
```

### 3. Конец цепочки
```python
from chain_dashboard import log_chain_end

total_ms = (time.time() - t_start) * 1000

log_chain_end(
    chain_id="content_week_...",
    status="ok",  # "ok" или "failed"
    total_ms=total_ms,
    error=""  # опционально: если "failed", то текст ошибки
)
```

## Пример интеграции в pipeline.py

```python
import time
from datetime import datetime
from chain_dashboard import log_chain_start, log_chain_step, log_chain_end

def run_chain(chain_key):
    # Генерируем уникальный ID для цепочки
    chain_id = f"{chain_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Получаем конфиг
    chains_config = CHAINS[chain_key]
    agents = [agent_key for agent_key, _ in chains_config]
    
    # ─── ЛОГИРОВАНИЕ: начало ───
    log_chain_start(chain_id, from_agent="n8n", agents=agents,
                    description=f"Цепочка {chain_key}")
    
    t_chain_start = time.time()
    prev_reply = ""
    
    # Запускаем агентов
    for step_num, (agent_key, prompt_template) in enumerate(chains_config, 1):
        t0 = time.time()
        
        try:
            agent = _load_agent(agent_key)
            msg = prompt_template.format(prev=prev_reply)
            reply, _ = run_agent_with_retry(
                client, agent["system"], agent["tools"],
                agent["handle"], msg, [], agent_key=agent_key
            )
            
            elapsed_ms = (time.time() - t0) * 1000
            
            # ─── ЛОГИРОВАНИЕ: шаг выполнен ───
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
            
            # ─── ЛОГИРОВАНИЕ: шаг упал ───
            log_chain_step(chain_id, agent_key, step_num, "failed", elapsed_ms)
            
            # ─── ЛОГИРОВАНИЕ: цепочка упала ───
            total_ms = (time.time() - t_chain_start) * 1000
            log_chain_end(chain_id, "failed", total_ms, error=str(e)[:100])
            
            raise
    
    # ─── ЛОГИРОВАНИЕ: конец цепочки ───
    total_ms = (time.time() - t_chain_start) * 1000
    log_chain_end(chain_id, "ok", total_ms)
    
    return prev_reply
```

## Примеры использования

### Из Python: запросить метрики
```python
import requests

resp = requests.get("http://127.0.0.1:5000/chains/api/metrics")
metrics = resp.json()

print(f"Success rate: {metrics['overall']['success_rate']:.1f}%")
print(f"Avg time: {metrics['overall']['avg_ms']:.0f}ms")
```

### Из браузера: открыть детали цепочки
```
http://127.0.0.1:5000/chains/api/details/content_week_20260608_123456
```

### Из cron/n8n: проверить, не упала ли цепочка
```bash
curl -s http://127.0.0.1:5000/chains/api/active | grep -q '"status":"running"'
if [ $? -eq 0 ]; then
  echo "Цепочки выполняются"
else
  echo "Цепочек нет"
fi
```

## Структура данных в памяти

События пишутся в `mila-office/memory/events.jsonl` в формате JSONL (JSON Lines):

```json
{"ts":"2026-06-08T10:30:45Z","kind":"chain:start","payload":{"chain_id":"content_week_...","from_agent":"n8n","agents":["olya","marina","victoria","vasya"],"description":"..."}}
{"ts":"2026-06-08T10:32:10Z","kind":"chain:step","payload":{"chain_id":"content_week_...","agent":"olya","step_num":1,"status":"done","elapsed_ms":85200}}
{"ts":"2026-06-08T10:34:20Z","kind":"chain:step","payload":{"chain_id":"content_week_...","agent":"marina","step_num":2,"status":"done","elapsed_ms":130000}}
{"ts":"2026-06-08T10:45:30Z","kind":"chain:end","payload":{"chain_id":"content_week_...","status":"ok","total_ms":885000}}
```

Типы событий:
- **`chain:start`** — начало цепочки
  - `chain_id`, `from_agent`, `agents[]`, `description`
- **`chain:step`** — завершение шага (агента)
  - `chain_id`, `agent`, `step_num`, `status`, `elapsed_ms`, `input_text`, `output_text`
- **`chain:end`** — конец цепочки
  - `chain_id`, `status` ("ok"/"failed"), `total_ms`, `error`

## Что дальше?

### Для быстрого старта:
1. ✅ Добавить import и регистрацию blueprint в `webapp.py`
2. ✅ Запустить `webapp.py` и открыть http://127.0.0.1:5000/chains
3. ✅ Вот и всё! Дашборд будет показывать события, которые пишет `memory.py`

### Для полного мониторинга:
1. Добавить логирование в `pipeline.py` (см. примеры выше)
2. Запустить цепочку: `python pipeline.py content_week`
3. Смотреть в реальном времени на дашборде: http://127.0.0.1:5000/chains

### Расширения (на future):
- Экспорт в CSV
- Алерты (Telegram) при падении цепочки
- WebSocket для live-обновления вместо polling
- Ротация логов (архив > месяца в отдельный файл)

## Кодовая база

- **chain_dashboard.py** (500+ строк)
  - Модели данных: `_build_active_chains()`, `_build_chain_history()`, `_build_agent_timeline()`, `_build_chain_details()`, `_build_performance_metrics()`
  - API маршруты: `/chains/api/active`, `/chains/api/history`, `/chains/api/timeline`, `/chains/api/details/<id>`, `/chains/api/metrics`
  - Веб-интерфейс: HTML+CSS+JS дашборд на одном файле (инлайн `_DASHBOARD_HTML`)
  - Функции логирования: `log_chain_start()`, `log_chain_step()`, `log_chain_end()`

- **Зависимости**
  - Flask (уже есть в webapp.py)
  - memory.py (уже есть)
  - Никакие новые пакеты не требуются!

## Вопросы?

### Дашборд не показывает данные
1. Проверить, что Flask запущен: `python webapp.py`
2. Проверить логи: `tail -20 logs/webapp.log`
3. Проверить файл событий: `tail -20 mila-office/memory/events.jsonl`

### Как добавить свою цепочку?
1. Определить цепочку в `CHAINS` в `pipeline.py`
2. Обернуть её в `run_chain_with_logging()` (см. CHAIN_DASHBOARD_EXAMPLE.py)
3. При запуске: `python pipeline.py your_chain`

### Может ли дашборд замедлиться?
При > 10000 событий файл станет большим. Решение:
- Архивировать старые события в отдельный файл (месячная ротация)
- Переместить в Supabase (если будет нужно)
- Для локального офиса (текущий режим) это не проблема

## Автор

Создано как часть **MILA OFFICE** агентной архитектуры (июнь 2026).

Используется для мониторинга цепочек агентов, которые работают синхронно (Марина → Виктория → Вася) и асинхронно (n8n вызывает цепочки по расписанию).
