# Supabase Database Access — Полный гайд

## Статус подключения

✅ **Полностью настроено и рабочее**

```
URL:       https://twrmpbduxemfgxtadkxa.supabase.co
Project:   twrmpbduxemfgxtadkxa
Service:   service_role (полный доступ, обходит RLS)
Write:     ✅ Включена
Read:      ✅ Включена
Timeout:   30s (read), 60s (write)
```

## Структура данных

### 1. **ig_posts** — Instagram посты и метрики

```sql
SELECT media_id, post_date, media_type, theme, reach, likes, comments, caption, permalink
WHERE post_date >= '2026-06-01'
ORDER BY post_date DESC
LIMIT 100
```

**Используется:** Rita (аналитика), Olya (тренды)  
**Поля:**
- `media_id` — уникальный ID поста Instagram
- `post_date` — дата публикации
- `media_type` — IMAGE, VIDEO, CAROUSEL, REEL
- `reach` — охват (impressions)
- `likes`, `comments`, `saves` — engagement
- `theme` — тема контента (attachment, vulnerability, др.)

### 2. **telegram_leads** — лиды из Telegram бота

```sql
SELECT tg_user_id, tg_username, tg_name, status, wrote_want, messages_count, created_at
WHERE status IN ('new', 'warm', 'hot', 'converted')
AND created_at >= NOW() - INTERVAL 7 days
```

**Используется:** Olya (тренды), Rita (аналитика)  
**Статусы:**
- `new` — первый контакт
- `warm` — проявил интерес (написал ХОЧУ или вопрос)
- `hot` — готов к консультации
- `converted` — купил продукт
- `inactive` — не писал > 30 дней

**Поля:**
- `wrote_want` — true если писал "ХОЧУ"
- `messages_count` — количество сообщений
- `last_message` — последнее сообщение
- `user_id` — опционально связь с users таблицей

### 3. **purchases** — покупки практикума и сервисов

```sql
SELECT id, user_id, product_id, amount_cad, payment_method, status, created_at
WHERE status = 'completed'
AND created_at >= NOW() - INTERVAL 30 days
```

**Используется:** Dima (финансы), Rita (аналитика)  
**Поля:**
- `amount_cad` — сумма в канадских долларах
- `payment_method` — gumroad, stripe, manual
- `product_id` — ссылка на products таблицу
- `status` — completed, pending, refunded, failed

**Источники доходов:**
- Практикум $37 (Gumroad)
- Консультация $120 (Calendly → purchases)
- Пакеты $420, $750

### 4. **consultations** — забронированные и завершённые консультации

```sql
SELECT id, user_id, type, status, scheduled_at, completed_at, duration_min, platform
WHERE status = 'completed'
AND completed_at >= NOW() - INTERVAL 30 days
```

**Используется:** Dima (финансы), Rita (аналитика)  
**Статусы:**
- `scheduled` — забронирована
- `completed` — прошла
- `cancelled` — отменена
- `no_show` — клиент не пришёл

**Типы:**
- `diagnostic` — диагностика (бесплатно)
- `single` — разовая консультация $120
- `package_4` — пакет 4 сессии $420
- `package_8` — пакет 8 сессий $750

### 5. **products** — каталог продуктов

```sql
SELECT id, slug, name, type, price_cad, duration_min, sessions_count
WHERE is_active = true
ORDER BY sort_order
```

**Продукты:**
- `diagnostic` — диагностика (бесплатная, 20 мин)
- `workbook` — практикум ($37)
- `consultation` — разовая консультация ($120, 60 мин)
- `package` — пакеты консультаций ($420/$750)
- `group` — групповой разбор ($55/человек)

### 6. **telegram_leads** — лиды из Telegram

Уже описана выше.

### 7. **users** — профили клиентов

```sql
SELECT id, email, name, phone, instagram, telegram, role, created_at
```

**Используется:** Alina (клиентская БД)  
**Роли:** client, admin

---

## Доступ из агентов

### Инструменты (TOOLS)

**Все агенты имеют доступ к:**

```python
# Rita (аналитика, product architect)
get_ig_posts_data(days=30)           # Instagram посты
get_telegram_leads_data(status=None)  # Telegram лиды
get_purchases_data(days=30)          # Покупки
check_supabase_access()              # Диагностика

# Dima (финансы)
get_purchases_data(days=30)          # Покупки
get_consultations_data(days=30)      # Консультации
check_supabase_access()              # Диагностика

# Olya (тренды)
get_ig_posts_data(days=30)           # Анализ трендов
get_telegram_leads_data(days=7)      # Качество лидов
check_supabase_access()              # Диагностика
```

### Примеры использования

**Dima: Рассчитать доход за месяц**
```
/доход → вызовет get_purchases_data(days=30) + get_consultations_data(days=30)
→ объединит Gumroad + консультации
→ вернёт LTV, MRR, repeat_rate
```

**Olya: Найти тренды**
```
/тренды → вызовет get_ig_posts_data(days=30) 
→ найдёт топ-посты по reach/likes
→ проанализирует какие темы работают
```

**Rita: Выбрать тему воркбука**
```
/темы → вызовет get_ig_posts_data() + get_telegram_leads_data()
→ соберёт реальные боли аудитории
→ предложит ТОП-3 темы с данными
```

---

## Решённые блокировки

### 1. RLS (Row Level Security) политики

**Проблема:** Таблицы под RLS запрещают чтение publishable ключом  
**Решение:** Используется `SUPABASE_SERVICE_ROLE_KEY` в tools/.env  
**Статус:** ✅ Решено

```
.env: SUPABASE_SERVICE_ROLE_KEY=eyJ...
supa.py: SERVICE_KEY автоматически загружается
Результат: can_write=true, полный доступ
```

### 2. Missing data

**Проблема:** Если таблица пуста, агент должен знать это, а не зависнуть  
**Решение:** Функции возвращают пустой массив `[]`, клиент показывает "no data"  
**Статус:** ✅ Решено

```python
rows = supa.select("ig_posts", limit=100)
# Если пусто: returns []
# Агент видит: {"status": "empty", "count": 0}
```

### 3. Network errors

**Проблема:** Slow network может зависить агента  
**Решение:**
- Read timeout: 30 секунд
- Write timeout: 60 секунд
- Retry logic: 3 попытки с exponential backoff (в pipeline.py)  
**Статус:** ✅ Решено

### 4. Permission errors

**Проблема:** Без service_role ключа запись в БД невозможна (code 42501)  
**Решение:** Проверка `supa.can_write()` перед записью, информативная ошибка  
**Статус:** ✅ Решено

```python
if not supa.can_write():
    raise SupabaseError("Нужен SUPABASE_SERVICE_ROLE_KEY для записи")
```

---

## Диагностика

### Проверить статус подключения

**В любом агенте:**
```
check_supabase_access()
```

**Вернёт:**
```json
{
  "url_set": true,
  "read_key": "service",
  "can_write": true,
  "note": null
}
```

### Если что-то не работает

1. **Таблица возвращает пусто:**
   - ✅ Это нормально, если данных нет
   - Проверь: `SELECT COUNT(*) FROM table_name` в Supabase SQL Editor
   - Убедись что дата фильтра правильная (post_date >= '2026-06-08')

2. **Ошибка: "code 42501" (permission denied):**
   - Проверь tools/.env: есть ли `SUPABASE_SERVICE_ROLE_KEY`
   - Если нет: добавь из Supabase → Project Settings → API → service_role
   - Перезагрузи webapp: `python webapp.py`

3. **Ошибка: "Supabase не настроен":**
   - Проверь tools/.env: есть ли `SUPABASE_URL`
   - Должно быть: `https://twrmpbduxemfgxtadkxa.supabase.co`
   - Перезагрузи: `python mila-office/webapp.py`

4. **Агент зависает при вызове инструмента:**
   - Обычно timeout 30-60s
   - Если часто → проверь интернет или Supabase health (https://status.supabase.com)
   - Retry logic в pipeline.py должен перепробовать автоматически

---

## Архитектура кода

```
tools/_common.py
├── get_ig_posts(days=30)
├── get_telegram_leads(status, days=30)
├── get_purchases(days=30)
├── get_consultations_from_db(days=30)
└── get_supabase_status()

mila-office/shared_tools.py
├── get_ig_posts_data(days=30)
├── get_telegram_leads_data(status, days=30)
├── get_purchases_data(days=30)
├── get_consultations_data(days=30)
└── check_supabase_access()

supa.py (низкоуровневый клиент)
├── available() → bool
├── can_write() → bool
├── select(table, columns, filters, limit)
├── insert/upsert/update/delete (write operations)
└── status() → {url_set, read_key, can_write, note}
```

---

## Требования к данным

Для полного анализа нужны:

**Минимум:**
- ✅ ig_posts: хотя бы 1 пост за последний месяц
- ✅ telegram_leads: хотя бы 1 лид за неделю
- ✅ purchases: хотя бы 1 покупка за месяц

**Рекомендуется:**
- ig_posts: минимум 10 постов (для надёжной статистики)
- telegram_leads: минимум 5 лидов (для анализа качества)
- purchases: минимум 3 покупки (для MRR расчётов)

Если данных меньше → агенты будут отмечать результаты как гипотезы, а не как статистику.

---

## Обновления данных

**Кто пишет в таблицы:**

| Таблица | Источник | Частота |
|---------|----------|---------|
| ig_posts | tools/get_analytics.py | Ежедневно (00:00 UTC) |
| telegram_leads | Telegram bot API (tools/) | В реальном времени |
| purchases | Gumroad webhook + manual | При каждой покупке |
| consultations | Calendly webhook + manual | При каждой консультации |
| users | CRM intake forms | При первом контакте |

**Последняя синхронизация:**
- Проверь: `SELECT MAX(created_at) FROM table_name` в SQL Editor
- Если старше 24h для ig_posts → запусти `tools/get_analytics.py posts`

---

## Лучшие практики

### ✅ Делай
- Вызывай `check_supabase_access()` в начале диагностики
- Используй `days` параметр для фильтрации по датам (не весь датасет)
- Обработай случай пустого результата (`len(rows) == 0`)
- Логируй какие таблицы использовал (`Rita используетinstagram_leads для анализа`)

### ❌ Не делай
- Не запрашивай все данные за всё время (`days=None` или очень большой `limit`)
- Не предполагай структуру данных, проверь `list(rows[0].keys())`
- Не игнорируй ошибки Supabase (они содержат полезный debug info)
- Не коммитьте `SUPABASE_SERVICE_ROLE_KEY` в git!

---

## Полезные ссылки

- **Суpabase проект:** https://app.supabase.com/project/twrmpbduxemfgxtadkxa
- **SQL Editor:** Project → SQL Editor → написать запрос
- **Database Explorer:** Project → Tables → выбрать таблицу
- **API Docs:** Project → API Docs → PostgREST
- **Status:** https://status.supabase.com

