# ERROR_HANDLING.md — Обработка ошибок в цепочках агентов

## Обзор

Цепочка агентов (`mila-office`) подвергается различным типам сбоев на разных уровнях:
1. **Ошибки агентов** — отказ Claude/Gemini, таймаут, invalid JSON от tool-loop
2. **Ошибки передачи** — агент не найден, chain_id потерян, next_agent=None
3. **Ошибки вердикта** — parse неудачи `[VERDICT: xxx]`, неясная судьба
4. **Ошибки файловой системы** — path traversal, файл заблокирован, disk full
5. **Ошибки API** — Instagram token expired, Telegram timeout, Gamma polling неудача
6. **Таймауты** — агент >2 мин, polling >15 мин, subprocess >60 сек

Механизмы обработки:
- **Логирование** в `logs/errors.jsonl` (структурированное) и `logs/*.log` (текстовое)
- **Retry** через `chain_retry.py` (up to 3 tries по умолчанию)
- **Escalation** на другого агента при несовместимой ошибке
- **Split/Merge** для параллельной обработки и консенсуса
- **Fallback** Claude → Gemini при недоступности Claude
- **Telegram alerts** для критических ошибок

---

## 1. Типы ошибок и где они возникают

### 1.1 Ошибки агентов (Agent Errors)

| Ошибка | Причина | Где возникает | Что пишется в логе |
|--------|---------|---------------|--------------------|
| `anthropic.APIError` | Claude недоступен (rate limit, auth, quota) | `base.py:_run_anthropic_agent()` | `error_monitor.log_error()` |
| `anthropic.APIConnectionError` | Сеть (DNS, timeout, refused) | `base.py:_run_anthropic_agent()` | `llm.log` + `errors.jsonl` |
| `anthropic.BadRequestError` | Неверное содержимое messages | `base.py:_run_anthropic_agent()` | `errors.jsonl` + alert |
| `ValueError` при парсинге JSON | Tool-loop вернул invalid JSON | `base.py:_run_anthropic_agent()` | `errors.jsonl` |
| `gemini` API ошибки | Google API (auth, quota) | `base.py:_run_gemini_agent()` | `llm.log` + `errors.jsonl` |
| Timeout (>120 сек) | Агент зависает в tool-loop | `base.py:run_agent()` | `chain_retry.log` |

**Примеры логирования:**
```json
{
  "timestamp": "2026-06-08T14:30:45.123Z",
  "level": "ERROR",
  "error_type": "APIError",
  "error_message": "429 Too Many Requests — retry after 60s",
  "context": {
    "agent": "marina",
    "action": "run_agent",
    "chain_id": "post_2026_06_08_1"
  },
  "traceback": "..."
}
```

### 1.2 Ошибки передачи (Handoff Errors)

| Ошибка | Причина | Симптом |
|--------|---------|---------|
| Agent не найден в `AGENTS_MODULES` | Опечатка в `[→ agent]` или новый агент не зарегистрирован | webapp возвращает 400 |
| `chain_id=None` | Context потерян при переключении | Цепочка разорвана в логе |
| `verdict=None` или неизвестный | Agent не вставил `[VERDICT: xxx]` | Цепочка зависает на `ready_next` |
| Цикл: `A → B → A → B` | Два агента требуют друг у друга исправления | Бесконечное переключение (3+ retry) |
| Split вернул все ошибки | Параллельные агенты все упали | Merge возвращает пустой результат |

**Пример логирования разорванной цепочки:**
```
logs/chain.log:
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_xyz
# ... victoria.py не запущена, нет записи
# Через 60 сек webapp видит, что victoria не ответила → escalate на дима (нейтральный третий)
```

### 1.3 Ошибки файловой системы (FS Errors)

| Ошибка | Пример | Обработка |
|--------|--------|-----------|
| Path traversal | `read_file("../../secret.env")` | `base.py` выбросит `ValueError` |
| File not found | `write_file("xyz.txt")` родитель не существует | `Path.mkdir(parents=True)` создает папку |
| Disk full | `write_file()` блокирует диск | Логируется как CRITICAL + alert |
| Permission denied | Windows NTFS блокировка | Логируется как ERROR, retry через 5 сек |
| Encoding error | Non-UTF8 файл | `read_file()` читает с `errors="replace"` |

**Обработка в base.py:**
```python
def read_file(path: str) -> str:
    try: p = _safe_path(path)      # ← Path traversal защита
    except ValueError as e: return f"Ошибка: {e}"
    try:
        txt = p.read_text(encoding="utf-8")
    except FileNotFoundError: return f"Файл не найден: {p}"
    except Exception as e: return f"Ошибка: {e}"
    # Если слишком большой → обрезаем
    if len(txt) > _READ_MAX_CHARS: ...
```

### 1.4 Ошибки API (Instagram, Telegram, Gamma)

| API | Ошибка | Retry? | Escalate? |
|-----|--------|--------|-----------|
| Instagram Graph | Token expired (401) | ❌ → escalate (CRITICAL) | ✅ Лера (sales) |
| Instagram Graph | Rate limit (429) | ✅ Retry через 10 сек | Только если >3 times |
| Telegram sendMessage | Timeout (5 сек) | ✅ Retry через 2 сек | ❌ (не критично, только алерт) |
| Gamma polling | Status timeout (15 мин) | ✅ Retry poll, но не >5 times | ✅ На Дима (Finance) |
| Any API | DNS error | ✅ Retry через 5 сек (до 3 раз) | ✅ На Марину (fallback prompt) |

**Пример: Token expired**
```python
# в marina.py
try:
    media = graph_api.graph_get(f"{IG_NODE}/media", params=...)
except graph_api.ConfigError as e:
    # Token неверен → CRITICAL
    error_monitor.log_error(e, context={"agent": "marina", "action": "get_posts"}, alert=True, level="CRITICAL")
    # Возвращаем friendly-сообщение пользователю
    return "❌ Instagram token expired. Свяжись с Людмилой для обновления."
```

### 1.5 Таймауты (Timeout Errors)

| Таймаут | Лимит | Обработка |
|---------|-------|-----------|
| run_agent (Claude/Gemini loop) | 120 сек | `anthropic` API timeout → retry на Gemini |
| subprocess (tools scripts) | 60 сек | `subprocess.run(..., timeout=60)` → error |
| Gamma API polling | 15 мин (900 сек) | `while time.time() < deadline` → timeout, retry |
| Telegram sendMessage | 5 сек | `requests.post(..., timeout=5)` → логируем, не alert |
| HTTP requests (graph_api) | 10 сек (в _common.py) | retry с backoff (3 раза) |

**Пример логирования timeout:**
```python
try:
    result = subprocess.run(argv, ..., timeout=60)
except subprocess.TimeoutExpired:
    error_monitor.log_error(
        TimeoutError("Script exceeding 60 seconds"),
        context={"agent": agent_key, "command": cmd},
        alert=True,
        level="CRITICAL"
    )
    # Retry с уменьшенной scope
    return "Команда заняла слишком долго. Попробуй с меньшим диапазоном дат."
```

---

## 2. Retry логика в `chain_retry.py`

### 2.1 Когда retry срабатывает

```python
def retry_chain(chain_id: str, failed_agent: str, reason: str, max_retries: int = 3) -> Optional[Dict]:
    """Перезапустить цепь со сбойного агента."""
    chain["retry_count"] += 1
    if chain["retry_count"] > max_retries:
        # Превышен лимит → FAILED, логируем в error_monitor
        error_monitor.log_error(
            Exception(f"Chain retry limit exceeded: {reason}"),
            context={"chain_id": chain_id, "failed_agent": failed_agent},
            alert=True,
            level="CRITICAL"
        )
        return None
```

**Таблица: когда retry vs escalate vs cancel**

| Сценарий | Retry? | Макс раз | Escalate? | На кого? |
|----------|--------|----------|-----------|----------|
| **Agent timeout (network hiccup)** | ✅ | 3 | ❌ | — |
| **Claude 429 (rate limit)** | ✅ | 2 | ✅ | Gemini fallback |
| **Invalid JSON from agent** | ✅ | 1 | ✅ | Другой агент |
| **File not found** | ❌ | 0 | ✅ | Пользователь (manual) |
| **Token expired** | ❌ | 0 | ✅ | Лера (Sales) или stop |
| **Verdict=None (agent не ответил)** | ✅ | 3 | ✅ | Марина (retry, потом escalate) |
| **Бесконечный цикл (A → B → A)** | ❌ | 0 | ✅ | Дима (скайп, ручно) или отменить |
| **Split: все ветки упали** | ❌ | 0 | ✅ | Марина или пользователь |

### 2.2 Retry логирование

**Логируется в `logs/chain_retries.jsonl`:**
```json
{
  "timestamp": "2026-06-08T14:31:15Z",
  "chain_id": "post_2026_06_08_1",
  "agent_key": "victoria",
  "reason": "api_failure",
  "attempt": 1,
  "max_retries": 3
}
```

**и в `logs/chain_events.jsonl`:**
```json
{
  "timestamp": "2026-06-08T14:31:15Z",
  "event_type": "retry",
  "chain_id": "post_2026_06_08_1",
  "agent_key": "victoria",
  "details": {
    "reason": "api_failure",
    "retry_count": 1,
    "max_retries": 3,
    "action": "retrying from this agent"
  }
}
```

### 2.3 Пример: Retry сценарий (Victoria упала с timeout)

```
[14:30] User отправляет пост Marina
[14:30] Marina обрабатывает → [VERDICT: ready_next] [→ victoria]
[14:31] Victoria.run_agent() запущена
[14:32] Victoria timeout (>120 сек, Claude медленный)

ОБработка в webapp:
  1. job_queue видит что victoria.process() не завершилась за 60 сек → error
  2. Вызывает chain_retry.retry_chain(chain_id, "victoria", "timeout")
  3. chain_retry сбрасывает victoria и последующих в "pending"
  4. Логирует в chain_retries.jsonl
  5. Фронтенд повторно отправляет victoria (или переключается на fallback)

[14:33] Victoria.run_agent() запущена второй раз
[14:34] Victoria успешно завершилась → [VERDICT: done]
[14:35] Цепочка завершена, результат скачан
```

---

## 3. Escalation логика

### 3.1 Когда escalate vs retry

**Retry** — ошибка временная (сеть, rate limit):
```python
if "429" in error_message or "timeout" in error_message:
    return retry_chain(chain_id, agent, "timeout")
```

**Escalate** — агент неподходящий или перегруженный:
```python
if "несоответствие требованиям" in agent_response:  # Victoria требует слишком много
    return escalate_chain(chain_id, "alina", "victoria too strict")  # Алина проверит
```

### 3.2 Escalation карта

```
Ошибка в цепочке:               Escalate на:
───────────────────────────────  ─────────────────────────────
Marina (контент неподходящий) → Rita (дизайнер, свежий взгляд)
Victoria (требует слишком) → Alina (CRM, может упростить)
Vasya (расписание конфликт) → Dima (finance, знает праздники)
Rita (дизайн неподходящий) → Olya (тренды, переобоснование)
Алина (CRM проблема) → Тёма (Telegram, переправить в канал)
Лера (продажи) → Дима (Gumroad, техническая проблема)
```

### 3.3 Escalation логирование

```python
def escalate_chain(chain_id: str, new_agent: str, reason: str = "") -> Optional[Dict]:
    """Переправить цепь на другого агента."""
    # Отмечаем остальных как "skipped"
    for i in range(current_idx + 1, len(chain["agents"])):
        chain["nodes"][skipped_agent].status = "skipped"
    
    # Заменяем оставшихся на нового
    chain["agents"] = chain["agents"][:current_idx + 1] + [new_agent]
    chain["status"] = ChainStatus.ESCALATED.value
    
    # Логируем
    _log_chain_event(chain_id, current_agent, "escalate", {
        "from_agent": current_agent,
        "to_agent": new_agent,
        "reason": reason
    })
```

**в `logs/chain_events.jsonl`:**
```json
{
  "timestamp": "2026-06-08T14:31:15Z",
  "event_type": "escalate",
  "chain_id": "post_2026_06_08_1",
  "agent_key": "victoria",
  "details": {
    "from_agent": "victoria",
    "to_agent": "alina",
    "reason": "victoria too strict"
  }
}
```

---

## 4. Split/Merge логика (параллельная обработка)

### 4.1 Когда использовать split

**Сценарий: Marina написала пост, нужна обработка в разных аспектах**

```python
# Split на несколько агентов параллельно
split_chain(chain_id, ["victoria", "alina", "rita"], context={"task": "review_post"})

# Параллельно:
# - Victoria: редактирует текст
# - Alina: проверяет CRM тег (если lead)
# - Rita: предлагает визуальное оформление

# Когда все готовы:
merge_results(chain_id, [
    {"agent_key": "victoria", "result": "✓ Отредактировано", "error": None},
    {"agent_key": "alina", "result": "Lead добавлен", "error": None},
    {"agent_key": "rita", "result": "Рекомендуемый размер 1080x1350", "error": None}
], merge_strategy="union")

# Result: list of all 3 results
```

### 4.2 Merge стратегии

```python
def merge_results(chain_id, results, merge_strategy="union"):
    """Объединить результаты."""
    if merge_strategy == "union":
        # Все результаты в список (если без ошибок)
        merged = [r.get("result") for r in results if not r.get("error")]
    
    elif merge_strategy == "consensus":
        # Результат с наибольшей "уверенностью" (поле confidence)
        results_with_conf = [r for r in results if r.get("confidence", 0) > 0]
        merged = max(results_with_conf, key=lambda r: r.get("confidence", 0)).get("result")
    
    elif merge_strategy == "first_success":
        # Первый успешный результат (игнорируем остальные)
        for r in results:
            if not r.get("error"):
                merged = r.get("result")
                break
```

**Пример логирования split/merge:**
```json
{
  "event_type": "split",
  "chain_id": "post_2026_06_08_1",
  "details": {
    "to_agents": ["victoria", "alina", "rita"],
    "count": 3,
    "split_id": "2026-06-08T14:30:00Z"
  }
}

{
  "event_type": "merge",
  "chain_id": "post_2026_06_08_1",
  "details": {
    "strategy": "union",
    "results_count": 3,
    "merged": true
  }
}
```

---

## 5. Fallback: Claude → Gemini

### 5.1 Когда fallback срабатывает

```python
def run_agent(...):
    # Сначала пытаемся Claude (для определённых агентов)
    try:
        return _run_anthropic_agent(...)
    except Exception as e:
        # Если Claude недоступен И есть GEMINI_KEY → fallback
        if not GEMINI_KEY:
            raise  # Нет альтернативы → выбрасываем исходную ошибку
        
        console.print(f"[yellow]Claude недоступен ({str(e)[:80]}) → фолбэк на Gemini[/yellow]")
        log("llm", f"fallback claude->gemini agent={agent_key}: {str(e)[:120]}")
        
        # Важно: history остается ЧИСТОЙ (только user-msg добавлен выше)
        # Поэтому можем безопасно перезапустить на Gemini со свежей копией
        return _run_gemini_agent(..., history.copy(), history)
```

**Таблица: какой агент использует какой LLM по умолчанию**

| Agent | LLM | Fallback |
|-------|-----|----------|
| Marina, Victoria, Vasya, Rita | Claude (opus-4-6) | → Gemini |
| Alina, Dima, Tyoma, Olya | Gemini (по умолчанию) | ❌ Нет |
| Manager, Producer | Claude (специально) | → Gemini |
| Lera, Vasia (assistant) | Gemini | ❌ Нет |

**Конфигурация в .env:**
```bash
# Какие агенты используют Claude (остальные → Gemini)
MILA_ANTHROPIC_AGENTS=manager,producer

# Fallback работает если оба ключа есть
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_KEY=AIza...
```

### 5.2 Fallback логирование

```json
{
  "timestamp": "2026-06-08T14:31:20Z",
  "level": "WARNING",
  "error_type": "APIError",
  "error_message": "429 Too Many Requests",
  "context": {
    "agent": "marina",
    "action": "fallback_claude_to_gemini"
  }
}
```

**в `logs/llm.log`:**
```
[2026-06-08 14:31] fallback claude->gemini agent=marina: 429 Too Many Requests
```

---

## 6. Telegram alerts для критических ошибок

### 6.1 Когда отправляется alert

```python
error_monitor.log_error(
    error=exception_obj,
    context={"agent": "marina", "action": "get_posts"},
    alert=True,  # ← Отправляет Telegram
    level="CRITICAL"
)
```

**Условия для alert=True:**
- ❌ Token expired (Instagram)
- ❌ Disk full
- ❌ Chain retry limit exceeded
- ❌ API credentials invalid
- ❌ Timeout >5 мин

**Условия для alert=False:**
- ✅ Network timeout <5 сек (обычно восстанавливается)
- ✅ Rate limit (временный)
- ✅ Single node failure (retry справится)

### 6.2 Telegram сообщение

```
⚠️ **CRITICAL: APIError**

Message: 401 Token expired — please refresh
Context:
• agent: marina
• action: get_posts
• chain_id: post_2026_06_08_1

Time: 2026-06-08T14:31:20Z
```

**Конфигурация в .env:**
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmnoPQRstuvWXYZabcdefg
TELEGRAM_ADMIN_CHAT_ID=-987654321  # Отрицательное число для группы
```

---

## 7. Отладка failed chains (debugging)

### 7.1 Быстрая проверка статуса цепочки

```bash
# Найти цепочку в памяти (webapp работает?)
python -c "from mila_office.chain_retry import get_chain; print(get_chain('post_2026_06_08_1'))"

# Экспортировать в JSON для анализа
python -c "from mila_office.chain_retry import export_chain_to_json; export_chain_to_json('post_2026_06_08_1')"

# Посмотреть в файле
cat "logs/chains/post_2026_06_08_1.json"
```

### 7.2 Просмотр логов цепочки

```bash
# Все события цепочки в хронологическом порядке
grep "chain=post_2026_06_08_1" logs/chain.log

# Все события в структурированном виде
grep "post_2026_06_08_1" logs/chain_events.jsonl | python -m json.tool

# Найти все ошибки для цепочки
grep "post_2026_06_08_1" logs/errors.jsonl | python -m json.tool

# Все попытки retry
grep "post_2026_06_08_1" logs/chain_retries.jsonl | python -c "import sys, json; [print(json.loads(l)) for l in sys.stdin]"
```

### 7.3 Общие сценарии отладки

#### Сценарий 1: Цепочка остановилась на agent=victoria

**Признак:**
```
logs/chain.log:
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_xyz
# ... ничего для victoria после этого
```

**Отладка:**
```bash
# 1. Victoria запущена?
ps aux | grep victoria

# 2. Есть ошибки в victoria.log?
tail -50 logs/victoria.log | grep -i error

# 3. Проверить errors.jsonl на victoria
grep -i victoria logs/errors.jsonl | python -m json.tool

# 4. Проверить webapp (она должна была заметить victoria не ответила)
tail -50 logs/webapp.log | grep -i victoria
```

**Возможные причины и исправления:**
- Victoria зависла → `kill` и перезапустить webapp.py
- Нет chain_id → обновить system prompt victoria
- Victoria упала с exception → проверить victoria.py, может быть новый bug
- Таймаут в Claude → подождать, может быть overload

#### Сценарий 2: Бесконечный цикл (victoria ↔ marina)

**Признак:**
```
logs/chain.log:
[14:30] agent=marina from=user verdict=ready_next next=victoria
[14:31] agent=victoria from=marina verdict=needs_revision next=marina
[14:32] agent=marina from=victoria verdict=ready_next next=victoria
[14:33] agent=victoria from=marina verdict=needs_revision next=marina
[14:34] agent=marina from=victoria verdict=ready_next next=victoria  ← 3+ раза = цикл!
```

**Отладка:**
```bash
# Посмотреть что victoria требует
grep "agent=victoria" logs/victoria.log | tail -5

# Посмотреть что marina ответила
grep "agent=marina" logs/marina.log | tail -5
```

**Решение:**
1. **Вариант 1:** Escalate на Alina (нейтральный третий)
   ```python
   escalate_chain(chain_id, "alina", "victoria too strict, loop detected")
   ```

2. **Вариант 2:** Обновить prompt victoria (слишком строгие требования)
   ```python
   # victoria.py: смягчить требования в SYSTEM prompt
   SYSTEM = "Редактируй пост на предмет ошибок и стиля, но не переделывай полностью если смысл сохранён."
   ```

3. **Вариант 3:** Cancel цепочку и начать заново с другим порядком
   ```python
   cancel_chain(chain_id, "loop detected: victoria ↔ marina")
   ```

#### Сценарий 3: API ошибка (Instagram token, Telegram timeout)

**Признак:**
```
logs/errors.jsonl:
{
  "error_type": "ConfigError",
  "error_message": "401 Token expired",
  "context": {"agent": "marina", "action": "get_posts"}
}
```

**Отладка:**
```bash
# 1. Проверить .env токены
cat tools/.env | grep IG_ACCESS_TOKEN

# 2. Проверить эта ли версия загружена (может быть старая)
grep "INSTAGRAM_ACCESS_TOKEN" tools/.env

# 3. Проверить что marina использует correct ключ
grep -n "graph_get\|INSTAGRAM_TOKEN" mila-office/marina.py | head -10
```

**Решение:**
1. Обновить token через Instagram App Dashboard
2. Копировать в `tools/.env`
3. Перезапустить webapp.py (в base.py есть load_dotenv)
4. Отправить alert Лере (Sales) через Telegram, может быть это важно

#### Сценарий 4: Timeout в агенте (>120 сек)

**Признак:**
```
logs/chain_events.jsonl:
{
  "event_type": "retry",
  "details": {
    "reason": "timeout",
    "retry_count": 1
  }
}
```

**Отладка:**
```bash
# 1. Посмотреть что victoria делала (какие tools вызывала)
grep "agent=victoria" logs/llm.log | grep -i "tool\|call"

# 2. Может быть файл большой? Проверить что она читала
grep "read_file" logs/*.log | tail -5

# 3. Посмотреть сколько по времени заняло
grep "agent=victoria" logs/chain_events.jsonl | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    if e.get('event_type') in ['node_done', 'node_failed']:
        node = e['details']
        print(f'{e[\"agent_key\"]}: {node.get(\"duration_seconds\", \"?\")} сек')
"
```

**Решение:**
1. Если >120 сек обычно → увеличить timeout в base.py
   ```python
   timeout=180  # с 120
   ```

2. Если это tool-loop перебирается (много tool calls) → упростить prompt
3. Если это network → retry обычно помогает (срабатывает fallback на Gemini)
4. Если это Gamma polling → параллелить (split на другие агенты)

---

## 8. Стратегии восстановления (Recovery Strategies)

### 8.1 Быстрое восстановление (сразу)

```python
# 1. Retry (default strategy)
if "timeout" in error or "429" in error:
    chain_retry.retry_chain(chain_id, agent, "timeout", max_retries=3)
    # Авто-перезапуск через job_queue

# 2. Fallback to Gemini (if Claude fails)
if not GEMINI_KEY:
    raise  # Нет альтернативы
return _run_gemini_agent(...)  # Fallback

# 3. Escalate (агент неподходящий)
if "несоответствие требованиям" in response:
    chain_retry.escalate_chain(chain_id, "alina", reason)
```

### 8.2 Отложенное восстановление (через 1-5 мин)

```python
# Split на нескольких агентов (параллельная обработка)
chain_retry.split_chain(chain_id, ["victoria", "alina", "rita"])

# Каждый обрабатывает независимо → merge consensus
results = [...]  # После того как все завершились
chain_retry.merge_results(chain_id, results, merge_strategy="consensus")
```

### 8.3 Ручное восстановление (Людмила или admin)

```python
# Используется webapp dashboard / admin interface

# Вариант 1: Переоткрыть цепочку в другом агенте
POST /api/admin/chain/<chain_id>/redirect?to=alina

# Вариант 2: Отменить цепочку и начать заново
POST /api/admin/chain/<chain_id>/cancel?reason=manual

# Вариант 3: Поделить цепочку пополам (если слишком сложная)
POST /api/admin/chain/<chain_id>/split?agents=victoria,alina,rita

# Вариант 4: Просмотреть логи и истории
GET /api/logs/chain/<chain_id>
GET /api/chain/<chain_id>/history
```

---

## 9. Примеры end-to-end (E2E)

### Пример 1: Успешная цепочка (никаких ошибок)

```
[14:30:00] User: "Напиши пост про самопознание"
           ↓ (session, chain_id="post_2026_06_08_01" создан)

[14:30:05] Marina.run_agent()
           [SYSTEM] You are Marina, marketer. User asks: ...
           [TOOLS] read_file (content plan), write_file (draft post)
           [RESPONSE] Готовый пост (2 параграфа, CTA "напиши ХОЧУ")
           [VERDICT] [VERDICT: ready_next] [→ victoria]

[14:30:15] message_handler.process_agent_response()
           - Парсит [VERDICT: ready_next], [→ victoria]
           - clean_reply = "Готовый пост..."
           - should_switch=True, next_agent="victoria"

[14:30:16] webapp отправляет автоматическое переключение на victoria
           ↓

[14:30:20] Victoria.run_agent()
           [SYSTEM] You are Victoria, editor. Previous agent (Marina) wrote: ...
           [TOOLS] read_file (draft post), write_file (edited post)
           [RESPONSE] Отредактировано (улучшен стиль, исправлены опечатки)
           [VERDICT] [VERDICT: done] [→ vasya]

[14:30:35] message_handler.process_agent_response()
           - Парсит [VERDICT: done], [→ vasya]
           - clean_reply = "Отредактировано..."
           - should_switch=True, next_agent="vasya"

[14:30:36] webapp отправляет автоматическое переключение на vasya
           ↓

[14:30:40] Vasya.run_agent()
           [SYSTEM] You are Vasya, scheduler. Previous agent (Victoria) wrote: ...
           [TOOLS] read_schedule, find_best_time, write_schedule_entry
           [RESPONSE] Запланировано на 2026-06-08 14:00 UTC
           [VERDICT] [VERDICT: done] [→ END]

[14:30:50] message_handler.process_agent_response()
           - Парсит [VERDICT: done], [→ END]
           - should_switch=False (next_agent=None)
           - Цепочка завершена!

[14:30:51] chain_retry.complete_chain()
           - chain["status"] = "success"
           - final_result = "Post ready to publish"

[14:30:52] webapp показывает popup:
           ✅ Цепочка завершена!
           📝 Пост готов
           ⏰ Расписано на 14:00 UTC 2026-06-08
           [Скачать][Опубликовать]

Логи:
  logs/chain.log:
    [14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_2026_06_08_01
    [14:30] agent=victoria from=marina verdict=ready_next next=vasya chain=post_2026_06_08_01
    [14:30] agent=vasya from=victoria verdict=done next=END chain=post_2026_06_08_01
  
  logs/chain_events.jsonl:
    {"event_type": "start", "agent_key": "marina", ...}
    {"event_type": "node_done", "agent_key": "marina", "duration_seconds": 10, ...}
    {"event_type": "node_done", "agent_key": "victoria", "duration_seconds": 15, ...}
    {"event_type": "node_done", "agent_key": "vasya", "duration_seconds": 10, ...}
    {"event_type": "success", "agent_key": "system", ...}
```

### Пример 2: Victoria требует исправления (needs_revision → retry)

```
[14:30:00] User: "Напиши пост"
           → chain_id="post_xyz"

[14:30:10] Marina.run_agent() → [VERDICT: ready_next] [→ victoria]

[14:30:20] Victoria.run_agent()
           [RESPONSE] Пост требует исправления:
                     - Слишком короткий (2 параграфа < 3 требуется)
                     - CTA недостаточно clear
           [VERDICT] [VERDICT: needs_revision] [→ marina]

[14:30:35] message_handler.process_agent_response()
           - Парсит [VERDICT: needs_revision], [→ marina]
           - should_switch=True, next_agent="marina"

[14:30:36] webapp переключает на marina
           ↓

[14:30:40] Marina.run_agent()
           [CONTEXT] Victoria требует: 3+ параграфа, clearer CTA
           [TOOLS] read_file (черновик victoria), write_file (новый черновик)
           [RESPONSE] Расширенный пост (3 параграфа + strong CTA)
           [VERDICT] [VERDICT: ready_next] [→ victoria]

[14:30:50] message_handler.process_agent_response()
           - Парсит [VERDICT: ready_next], [→ victoria]
           - should_switch=True, next_agent="victoria"

[14:30:51] webapp переключает на victoria

[14:31:00] Victoria.run_agent()
           [CONTEXT] Marina переделала пост (attempt 2/3)
           [RESPONSE] ✅ Принято, отредактировано
           [VERDICT] [VERDICT: done] [→ vasya]

[14:31:10] ... цепочка продолжает работу нормально

Логи:
  logs/chain.log:
    [14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_xyz
    [14:30] agent=victoria from=marina verdict=needs_revision next=marina chain=post_xyz  ← Требует
    [14:30] agent=marina from=victoria verdict=ready_next next=victoria chain=post_xyz   ← Переделала
    [14:31] agent=victoria from=marina verdict=done next=vasya chain=post_xyz           ← OK
    [14:31] agent=vasya from=victoria verdict=done next=END chain=post_xyz             ← Завершено
```

### Пример 3: Timeout → Retry → Success

```
[14:30:00] User: "Проанализируй последние посты"
           → chain_id="analytics_001"

[14:30:10] Marina.run_agent()
           [TOOLS] instagram.get_analytics (ищет посты)
           ⏳ 120+ сек... timeout!

[14:31:30] job_queue видит Marina не ответила за 60 сек
           → webapp вызывает chain_retry.retry_chain()

[14:31:31] chain_retry.py:
           - chain["retry_count"] = 1
           - Сбрасывает marina в "pending"
           - Логирует в chain_retries.jsonl

[14:31:35] webapp отправляет Marina снова (но на Gemini fallback вместо Claude)
           ↓

[14:31:40] Marina.run_agent() (на Gemini)
           [TOOLS] instagram.get_analytics (ищет посты)
           ⏳ 15 сек... успешно! (Gemini быстрее)
           [RESPONSE] Анализ последних 5 постов
           [VERDICT] [VERDICT: ready_next] [→ victoria]

[14:31:50] Victoria.run_agent() → Дальше нормально

Логи:
  logs/chain_events.jsonl:
    {"event_type": "node_running", "agent_key": "marina", ...}
    {"event_type": "node_failed", "agent_key": "marina", "error": "timeout", ...}
    {"event_type": "retry", "agent_key": "marina", "details": {"reason": "timeout", "attempt": 1}, ...}
    {"event_type": "node_running", "agent_key": "marina", "details": {"provider": "gemini"}, ...}
    {"event_type": "node_done", "agent_key": "marina", "duration_seconds": 15, ...}

  logs/llm.log:
    [14:31] fallback claude->gemini agent=marina: timeout
```

### Пример 4: Escalate на другого агента

```
[14:30:00] User: "Напиши пост с визуалом"
           → chain_id="post_visual_001"

[14:30:10] Marina.run_agent() → [VERDICT: ready_next] [→ victoria]

[14:30:20] Victoria.run_agent()
           [RESPONSE] Пост очень хороший, но визуал требуется.
           [VERDICT] [VERDICT: needs_visual] [→ rita]

[14:30:35] message_handler видит неизвестный verdict "needs_visual"
           (не в ["ready_next", "done", "needs_revision"])
           → NOT should_auto_switch (default next_agent = None)

[14:30:36] webapp видит что victoria не знает куда передать
           → логирует в errors, может escalate на rita вручную

ИЛИ автоматически (если есть логика):
           chain_retry.escalate_chain(chain_id, "rita", "victoria requests visual design")

[14:31:00] Rita.run_agent()
           [CONTEXT] Victoria → Rita: нужен визуал для поста
           [TOOLS] gamma.create_document (создает визуальную версию)
           [RESPONSE] Визуал готов (gamma PDF)
           [VERDICT] [VERDICT: done] [→ END]

Логи:
  logs/chain_events.jsonl:
    {"event_type": "start", ...}
    {"event_type": "node_done", "agent_key": "marina", ...}
    {"event_type": "node_done", "agent_key": "victoria", ...}
    {"event_type": "escalate", "agent_key": "victoria", "details": {"from_agent": "victoria", "to_agent": "rita", "reason": "..."}, ...}
    {"event_type": "node_done", "agent_key": "rita", ...}
    {"event_type": "success", ...}
```

---

## 10. Контрольный список для интеграции обработки ошибок

### Разработчик добавляет новый инструмент (tool) для агента

- [ ] Tool function имеет try/except блок
- [ ] Все исключения логируются через `error_monitor.log_error()`
- [ ] Для API calls: есть timeout (напр. `requests.get(..., timeout=10)`)
- [ ] Для долгих операций (Gamma, subprocess): есть прогресс-логирование
- [ ] ОК: Если это criticial API (Instagram token) → `alert=True`
- [ ] У пользователя есть friendly message (не traceback)

### Разработчик добавляет нового агента

- [ ] Agent имеет SYSTEM prompt с инструкциями по [VERDICT] и [→ agent]
- [ ] Agent зарегистрирован в `agent_manager.py`
- [ ] Agent добавлен в `message_handler.py:get_pipeline_order()` (если нужен в цепочке)
- [ ] Agent имеет `QUICK` команды для быстрого тестирования
- [ ] Все инструменты (tools) агента обрабатывают ошибки
- [ ] Логирование: agent.py вызывает `base.log("chain", ...)` при переключении

### QA/Testing

- [ ] Тест: успешная цепочка (marina → victoria → vasya → rita)
- [ ] Тест: Victoria требует revision → Marina переделывает
- [ ] Тест: Marina timeout → Retry on Gemini
- [ ] Тест: API failure (Instagram token) → Alert в Telegram
- [ ] Тест: Escalate (victoria strict → alina neutral)
- [ ] Тест: Split/Merge (параллельная обработка)
- [ ] Логи: все события в `logs/chain.log` и `logs/chain_events.jsonl`

### DevOps/Monitoring

- [ ] Логи ротируются (не растут бесконечно)
- [ ] `logs/errors.jsonl` парсится и мониторится (e.g., ELK stack)
- [ ] Telegram alerts приходят для CRITICAL ошибок
- [ ] Dashboard показывает статус цепочек и retry counts
- [ ] Alerting: если >3 retry за час → уведомление

---

## 11. Резюме ошибок и обработка

| Ошибка | Тип | Retry | Escalate | Fallback | Alert |
|--------|-----|-------|----------|----------|-------|
| Timeout (network) | Транзиентная | ✅ 3x | Если >3 | Claude→Gemini | ❌ |
| Claude 429 (rate limit) | Транзиентная | ✅ 2x | Если >2 | Claude→Gemini | ❌ |
| Claude auth failed | Постоянная | ❌ | ✅ (Gemini) | Claude→Gemini | ✅ |
| Token expired (Instagram) | Постоянная | ❌ | ✅ (Лера) | ❌ | ✅ CRITICAL |
| File not found | Постоянная | ❌ | ✅ (Manual) | ❌ | ✅ ERROR |
| Disk full | Постоянная | ❌ | ❌ | ❌ | ✅ CRITICAL |
| Agent produces invalid JSON | Транзиентная | ✅ 1x | ✅ (Другой) | Claude→Gemini | ❌ |
| Victoria too strict (loop) | Дизайн | ❌ | ✅ (Alina) | ❌ | ❌ |
| Split: все ветки упали | Дизайн | ❌ | ❌ | ❌ | ✅ ERROR |
| Gamma polling timeout | Транзиентная | ✅ 3x | ✅ (Dima) | ❌ | ✅ ERROR |

---

## 📝 Быстрая справка

**Где логируются ошибки:**
- `logs/errors.jsonl` — структурированные ошибки (JSON, каждая строка)
- `logs/chain.log` — логирование цепочки (текст, формат: agent=X from=Y verdict=Z)
- `logs/chain_events.jsonl` — события цепочки (JSON: start, retry, escalate, merge, success)
- `logs/chain_retries.jsonl` — все retry попытки (JSON)
- `logs/*.log` (marina.log, victoria.log, etc.) — логи агентов (текст)
- Telegram alerts — критические ТОЛЬКО (на TELEGRAM_ADMIN_CHAT_ID)

**Быстрая отладка:**
```bash
# Посмотреть цепочку
grep "chain=post_xyz" logs/chain*.log logs/chain*.jsonl

# Посмотреть ошибки
grep "post_xyz" logs/errors.jsonl | python -m json.tool

# Посмотреть retry попытки
grep "post_xyz" logs/chain_retries.jsonl

# Статистика
python -c "from mila_office.chain_retry import get_chain_stats; print(get_chain_stats())"

# Экспортировать цепочку
python -c "from mila_office.chain_retry import export_chain_to_json; export_chain_to_json('post_xyz')"
```

**Быстрое восстановление:**
```python
# 1. Retry
from mila_office import chain_retry
chain_retry.retry_chain(chain_id, "victoria", "timeout")

# 2. Escalate
chain_retry.escalate_chain(chain_id, "alina", "victoria too strict")

# 3. Split/Merge (параллельно)
chain_retry.split_chain(chain_id, ["victoria", "alina", "rita"])
chain_retry.merge_results(chain_id, results, "consensus")

# 4. Complete (успех)
chain_retry.complete_chain(chain_id, "Post published")

# 5. Cancel (отмена)
chain_retry.cancel_chain(chain_id, "User cancelled")
```

---

**Документация готова! Используй как справочник при добавлении нового кода с ошибками.**
