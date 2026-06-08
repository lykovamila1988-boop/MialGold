# n8n Workflow: Автоматическая генерация Instagram отчётов

## Назначение

Этот workflow генерирует ежедневные отчёты о производительности постов Instagram:
- `reports/posts_*.json` — статистика всех опубликованных постов (reach, likes, comments)
- `reports/comments_*.json` — комментарии с автоматическим обнаружением лидов

Данные используются:
- **Rita** — анализ аудитории и психологических паттернов
- **Olya** — исследование трендов и рекомендации
- **Dima** — корреляция с продажами и прогнозы

---

## Конфигурация Workflow

### 1. Trigger (Триггер): Schedule

```
Type: Cron/Schedule
Pattern: "0 0 * * *"  (каждый день в 00:00 UTC)
или: "0 */6 * * *"    (каждые 6 часов)
```

### 2. Шаг 1: Вызов Flask API

```http
POST http://localhost:5000/api/fetch-analytics
Content-Type: application/json

{
  "type": "posts"
}
```

**Ожидаемый ответ:**
```json
{
  "status": "ok",
  "report_file": "reports/posts_2026-06-08_120000.json",
  "posts_count": 15,
  "period": "last 30 days"
}
```

### 3. Шаг 2: Проверка результата

```
Condition: response.status === "ok"
```

- **Yes** → Продолжить на шаг 3 (логирование)
- **No** → Отправить алерт (шаг 4)

### 4. Шаг 3: Логирование успеха (опционально)

```
Action: Save to log file or Slack notification
Message: "✓ Instagram отчёт сгенерирован: {report_file}"
```

### 5. Шаг 4: Алерт при ошибке (опционально)

```
Action: Send Telegram/Slack message
Message: "❌ Ошибка при генерации Instagram отчёта"
```

---

## API Endpoint

### POST /api/fetch-analytics

Вызывает скрипт `tools/get_analytics.py` и сохраняет результат.

**Parameters:**
- `type` (string): `"posts"`, `"comments"`, или `"account"`
- `days` (integer, optional): Сколько дней анализировать (по умолчанию 30)

**Response:**
```json
{
  "status": "ok",
  "report_file": "reports/posts_2026-06-08_120000.json",
  "posts_count": 15,
  "period": "last 30 days",
  "summary": {
    "total_reach": 12345,
    "total_engagement": 456,
    "avg_reach_per_post": 823,
    "top_post_reach": 2100
  }
}
```

---

## Структура Отчёта: posts_*.json

```json
{
  "posts": [
    {
      "id": "17999...",
      "date": "2026-06-05T14:30:00+00:00",
      "type": "CAROUSEL_ALBUM",
      "caption": "Почему я выбираю не того...",
      "reach": 1234,
      "likes": 45,
      "comments": 12,
      "saves": 8,
      "link_clicks": 3,
      "engagement_rate": 4.8,
      "media_url": "https://..."
    },
    ...
  ],
  "summary": {
    "total_posts": 15,
    "period": "2026-05-09 to 2026-06-08",
    "total_reach": 12345,
    "total_engagement": 456,
    "avg_reach_per_post": 823,
    "avg_engagement_rate": 3.7,
    "top_post": {
      "id": "17999...",
      "reach": 2100,
      "engagement": 78
    }
  },
  "generated_at": "2026-06-08T00:30:00Z"
}
```

---

## Структура Отчёта: comments_*.json

```json
{
  "comments": [
    {
      "id": "17999..._comment123",
      "post_id": "17999...",
      "username": "user_name",
      "text": "Хочу эту консультацию!",
      "is_lead": true,
      "lead_keywords": ["хочу"],
      "date": "2026-06-07T12:00:00+00:00"
    },
    ...
  ],
  "leads": [
    {
      "username": "user_name",
      "comment": "Хочу эту консультацию!",
      "post_date": "2026-06-05",
      "detected_keywords": ["хочу"]
    }
  ],
  "summary": {
    "total_comments": 89,
    "total_leads": 3,
    "lead_rate": 3.4,
    "keywords_found": ["хочу", "цена", "заказ"]
  },
  "generated_at": "2026-06-08T00:35:00Z"
}
```

---

## Env Variables (tools/.env)

Убедитесь что эти переменные установлены в `tools/.env`:

```env
IG_ACCESS_TOKEN=your_token_here
IG_USER_ID=your_user_id
GRAPH_API_VERSION=v21.0
IG_API_FLOW=facebook  # или instagram_login
```

---

## Примеры использования данных в агентах

### Rita: Анализ аудитории

```python
# Читает latest posts_*.json
posts = read_file("reports/posts_*.json")  # latest
engagement_data = analyze_audience(posts)
```

### Olya: Тренды и рекомендации

```python
# Использует get_weekly_analytics() который читает reports/
weekly = get_weekly_analytics(days=7)
print(f"Средний охват: {weekly['summary']['avg_reach_per_post']}")
```

### Dima: Корреляция с продажами

```python
# Читает posts и комментарии для анализа воронки
funnel = measure_sales_funnel()  # Внутри читает reports/
print(f"CTR: {funnel['summary']['avg_ctr']}")
```

---

## Troubleshooting

### Workflow не запускается

1. Проверьте что Flask приложение запущено: `python mila-office/webapp.py`
2. Проверьте URL: http://localhost:5000/api/fetch-analytics
3. Проверьте логи Flask: `mila-office/logs/`

### Ошибка "API Rate Limit"

- Уменьшите частоту workflow (не чаще 1 раза в 6 часов)
- Проверьте значение `IG_RATE_LIMIT_PER_HOUR` в `.env`

### Файлы не создаются

1. Проверьте что папка `reports/` существует
2. Проверьте разрешения на запись в `reports/`
3. Проверьте логи: `grep "save_report" mila-office/logs/errors.jsonl`

### Данные не совпадают с Instagram

- Reports генерируются с задержкой (Instagram нужно время на обновление)
- Проверьте что прошло минимум 6 часов с публикации поста
- Используйте `--days 30` для полных данных

---

## Schedule Examples

### Ежедневно в полночь (UTC)

```
"0 0 * * *"
```

### Каждые 6 часов

```
"0 */6 * * *"
```

### 3 раза в день (09:00, 15:00, 21:00 UTC)

```
"0 9,15,21 * * *"
```

---

## Формула расчёта Engagement Rate

```
Engagement Rate (%) = (likes + comments + saves) / reach * 100
```

Пример: 45 likes + 12 comments + 8 saves = 65 interactions
Reach = 1234
Engagement = 65 / 1234 * 100 = 5.3%

---

**Статус:** ✓ Документировано и готово к использованию
