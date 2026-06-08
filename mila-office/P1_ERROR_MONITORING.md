# P1: Улучшенный мониторинг ошибок в webapp.py

**Статус:** ✅ ЗАВЕРШЕНО
**Дата:** 2026-06-08
**Срок:** 3 дня (выполнено за 1 день)

## Задача

Разработать и внедрить централизованный механизм логирования ошибок с полной трассировкой стека для webapp.py.

**Критерий приёмки:** Все ошибки веб-приложения логируются с детализацией, позволяющей точно определить причину.

## Решение

### 1. Новый модуль: error_monitor.py

Централизованный логгер для всех ошибок приложения.

**Основные функции:**

```python
log_error(error, context={}, alert=False, level="ERROR")
    # Логирует исключение с полным traceback
    # Отправляет Telegram alert если alert=True
    # Возвращает ID записи в логе

get_error_stats(hours=24)
    # Возвращает статистику ошибок за период:
    # - total_errors: количество
    # - by_type: группировка по типу (ValueError, TimeoutError, etc)
    # - by_level: группировка по серьёзности (ERROR, CRITICAL)
    # - by_context: группировка по источнику (webapp, pipeline, etc)

get_recent_errors(limit=10)
    # Возвращает последние N ошибок с полной информацией

clear_old_errors(days=30)
    # Удаляет ошибки старше N дней (для очистки лога)
```

**Хранилище:** `logs/errors.jsonl` (структурированный лог в JSON Lines формате)

Пример записи:
```json
{
  "timestamp": "2026-06-08T14:05:32Z",
  "level": "ERROR",
  "error_type": "ValueError",
  "error_message": "invalid literal for int()",
  "traceback": "Traceback (most recent call last):\n  ...",
  "context": {
    "source": "webapp",
    "endpoint": "/api/agent-message",
    "agent": "lera"
  }
}
```

### 2. Интеграция в webapp.py

**Глобальные error handlers:**

```python
@app.errorhandler(500)      # Логирует, отправляет Telegram alert, возвращает 500
@app.errorhandler(404)      # Логирует 404, но без alert
@app.errorhandler(Exception) # Перехватывает все необработанные исключения
```

**API endpoints для просмотра ошибок:**

```
GET /api/errors/stats?hours=24
    # Статистика ошибок за последние N часов
    # Response: {"ok": true, "total_errors": 5, "by_type": {...}, ...}

GET /api/errors/recent?limit=10
    # Последние N ошибок с деталями
    # Response: {"ok": true, "count": 3, "errors": [...]}
```

### 3. Telegram алерты

Когда происходит критическая ошибка (500, CRITICAL level):
- Отправляется сообщение в Telegram Людмиле
- Включает тип ошибки, сообщение, контекст, время

Требование: `TELEGRAM_BOT_TOKEN` и `TELEGRAM_ADMIN_CHAT_ID` в `.env`

## Использование

### Для разработчиков (логирование собственных ошибок)

В любом месте код:
```python
import error_monitor

try:
    # Ваш код
    risky_operation()
except ValueError as e:
    error_monitor.log_error(e, context={
        "source": "my_module",
        "action": "risky_operation",
        "user_id": current_user.id
    }, alert=True)  # True для критических ошибок
```

### Для операторов (просмотр ошибок)

1. **В браузере:** http://localhost:5000/api/errors/stats
2. **Последние ошибки:** http://localhost:5000/api/errors/recent?limit=5
3. **На диске:** `logs/errors.jsonl` (структурированный лог)
4. **В Telegram:** Критические ошибки приходят автоматически

## Данные для анализа

### Дневная статистика

```bash
curl http://localhost:5000/api/errors/stats?hours=24
```

Ответ:
```json
{
  "ok": true,
  "period": "last 24 hours",
  "total_errors": 12,
  "by_type": {
    "ValueError": 5,
    "TimeoutError": 3,
    "FileNotFoundError": 2,
    "RuntimeError": 2
  },
  "by_level": {
    "ERROR": 10,
    "CRITICAL": 2
  },
  "by_context": {
    "webapp": 8,
    "pipeline": 3,
    "test": 1
  }
}
```

### Трендинг

Можно запустить простой скрипт для сбора метрик:

```python
import requests
from datetime import datetime

stats = requests.get("http://localhost:5000/api/errors/stats").json()
print(f"{datetime.now().isoformat()} - Errors: {stats['total_errors']}")
```

Сохранять в `logs/metrics.csv` для анализа трендов.

## Тестирование

**Вручную:**
```bash
# Запустить тест error_monitor
python mila-office/error_monitor.py

# Проверить что лог создан
cat logs/errors.jsonl

# Проверить API
curl http://localhost:5000/api/errors/stats
curl http://localhost:5000/api/errors/recent?limit=5
```

**Автоматически (когда Flask запущен):**
1. Вызвать несуществующий endpoint: `http://localhost:5000/api/invalid/endpoint` → 404
2. Вызвать endpoint с ошибкой (например, добавить `1/"string"` в middleware)
3. Проверить `/api/errors/recent` — должна появиться запись

## Достигнутые KPI

✅ **Все ошибки логируются:** Каждое исключение пишется в `logs/errors.jsonl` с полным traceback

✅ **Детализация:** Логируется тип ошибки, сообщение, стек вызовов, контекст (endpoint, agent, action)

✅ **Структурированность:** JSON Lines формат позволяет легко парсить и анализировать

✅ **Telegram алерты:** Критические ошибки отправляются оператору в реальном времени

✅ **Статистика:** API endpoints для анализа ошибок по типам, уровню, источнику

## Следующие шаги

1. **Дашборд (опционально):** Добавить в браузер UI для визуализации ошибок
   - Таблица последних ошибок
   - Граф по типам/времени
   - Фильтрация по агенту/endpoint

2. **Автоматическая очистка:** Запустить `error_monitor.clear_old_errors(days=30)` через cron/n8n

3. **Интеграция с Supabase (опционально):** Архивировать ошибки в таблицу для долгосрочного анализа

## Файлы

- `mila-office/error_monitor.py` — основной модуль (290 строк)
- `mila-office/webapp.py` — интеграция (добавлено 50+ строк)
- `logs/errors.jsonl` — структурированный лог (создаётся автоматически)
- `P1_ERROR_MONITORING.md` — эта документация

---

**Статус:** ✅ Production Ready
