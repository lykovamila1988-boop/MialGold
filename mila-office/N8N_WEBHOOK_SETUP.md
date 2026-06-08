# n8n Webhook Setup для расписания постов (Vasya)

## Цель

Заменить Windows Task Scheduler на n8n webhook для более надёжного расписания публикаций.

Текущий механизм:
- Vasya ставит посты в очередь (status="approved", when="2026-06-08T10:00:00Z")
- Windows Task Scheduler каждый час запускает `tools/pipeline.py publish_due`
- Посты публикуются когда время наступает

**Новый механизм (n8n):**
- Vasya ставит посты в очередь (как раньше)
- n8n workflow вызывает `POST /api/pipeline/publish_due` каждый час
- Flask webapp публикует посты (как раньше)

## Требования

1. **n8n запущен** на `http://localhost:5678` (должно быть, т.к. уже используется)
2. **Flask webapp запущен** на `http://localhost:5000`
3. **N8N_BRIDGE_TOKEN** установлен в `tools/.env` (уже есть)

## Шаг 1: Создать простой n8n workflow

1. Открыть http://localhost:5678 → **New → New workflow**

2. Добавить **Trigger: Schedule**
   - Type: `Interval` или `Cron`
   - Interval: каждый час (`1 hour`)
   - Timezone: UTC или Toronto (что используется)

3. Добавить **HTTP Request node**
   - Method: `POST`
   - URL: `http://localhost:5000/api/pipeline/publish_due`
   - Headers (если нужны): нет специальных требований
   - Body: пусто (POST без параметров)

4. Добавить **Switch node** (опционально, для логирования)
   - Условие: если HTTP код 200
   - Ветка успеха: Send to Telegram/Log
   - Ветка ошибки: Alert

5. **Save & Activate** workflow

## Шаг 2: Тестирование

1. В браузере открыть: `http://localhost:5000/api/pipeline/publish_due`
   (или через curl: `curl -X POST http://localhost:5000/api/pipeline/publish_due`)

2. Должен вернуться ответ:
   ```json
   {
     "ok": true,
     "status": "published",
     "published": 0,
     "changed": 0
   }
   ```

3. Поставить несколько постов в очередь через Vasya

4. Запустить n8n workflow вручную (зелёная кнопка Execute)

5. Проверить что посты опубликовались (в webapp → Dashboard → Published section)

## Шаг 3: Отключить Windows Task Scheduler (опционально)

Если n8n работает надёжно (7+ дней без сбоев):

1. Открыть **Task Scheduler** → `MILA OFFICE publish_due`
2. Отключить задачу (или удалить)
3. Оставить n8n как единственный источник расписания

## API Endpoint

### POST /api/pipeline/publish_due

**Назначение:** Опубликовать все посты из очереди с status="approved" и time <= now

**Request:**
```
POST /api/pipeline/publish_due
Content-Type: application/json
```

**Response (200 OK):**
```json
{
  "ok": true,
  "status": "published",
  "published": 2,
  "changed": 2,
  "timestamp": "2026-06-08T14:05:32Z"
}
```

**Error (500):**
```json
{
  "ok": false,
  "error": "Описание ошибки"
}
```

## Мониторинг

Для логирования вызовов n8n → Flask:

1. В n8n workflow добавить после HTTP Request:
   ```
   Telegram node → Send message
   Text: "Published: {{ $json.published }} posts at {{ now() }}"
   To: TELEGRAM_ADMIN_CHAT_ID
   ```

2. Или в webapp.py уже логируется в `/logs/webapp.log`:
   ```
   tail -f logs/webapp.log | grep "publish_due"
   ```

## Трублшутинг

### n8n workflow не запускается

- Проверить что n8n у вас в `N8N_USER_FOLDER=repo n8n-data`
- Проверить: `docker ps` или `ps aux | grep n8n`
- Перезагрузить n8n

### HTTP Request возвращает 500

1. Проверить что Flask запущен: `http://localhost:5000`
2. Посмотреть логи Flask:
   ```
   tail -f logs/webapp.log | grep "publish_due"
   ```
3. Проверить что tools/pipeline.py доступен в PYTHONPATH

### Посты не публикуются

1. Проверить что посты в очереди (webapp → Dashboard → Posts)
2. Проверить что status="approved" и when <= now
3. Вызвать вручную:
   ```bash
   curl -X POST http://localhost:5000/api/pipeline/publish_due
   ```

## Преимущества n8n над Task Scheduler

✅ **Надёжнее:**
- Не зависит от Windows перезагрузки
- Встроенный retry и error handling
- Логирование всех вызовов

✅ **Гибче:**
- Можно добавить дополнительные действия (Telegram alert, Slack message, etc)
- Можно менять расписание без перезагрузки
- Вести историю всех публикаций

✅ **Проще дебагить:**
- UI для визуализации workflow
- История выполнения с временами
- Встроенный тестер

## Дополнительные шаги (опционально)

### 1. Добавить error handling

После HTTP Request node добавить:
```
If error:
  → Send Telegram alert to TELEGRAM_ADMIN_CHAT_ID
  → Retry after 5 minutes
```

### 2. Добавить логирование в Supabase

После успешной публикации:
```
→ Save to Supabase:
  table: "publish_log"
  published: {{ $json.published }}
  timestamp: {{ now() }}
```

### 3. Уведомления об успехе

Отправить в Telegram Людмиле:
```
Сегодня опубликовано {{ $json.published }} постов 🚀
```

---

**Статус:** Готово к внедрению. Flask endpoint протестирован ✓
