# P3: Оповещения о брошенных корзинах — Инструкция по развёртыванию

**Статус:** Готов к тестированию  
**Срок:** 2026-06-13 (5 дней)  
**Исполнитель:** Developer + Лера  
**Результат:** Автоматические напоминания в Telegram о неоплаченных покупках и просроченных консультациях

---

## 📋 Что это делает

1. **Ежедневно в 09:00 UTC** запускается автоматический процесс
2. **Находит брошенные корзины**:
   - Покупки со статусом `pending` (неоплаченные) старше 24 часов
   - Консультации со статусом `scheduled` (назначенные), но дата уже прошла
3. **Отправляет напоминания** через Telegram каждому клиенту (если у них есть Telegram ID)
4. **Логирует результаты** (отправлено, пропущено, ошибки)

---

## 🛠️ Компоненты

| Файл | Назначение |
|------|-----------|
| `tools/abandoned_cart_alerts.py` | Основной скрипт (поиск + отправка) |
| `tools/n8n_abandoned_workflow.py` | Генератор n8n workflow (расписание) |
| `mila-office/n8n_bridge.py` | HTTP endpoint `/v1/tools/abandoned-alerts` |

---

## 🚀 Шаг 1: Проверка конфига

### В `tools/.env` должно быть:

```bash
# Supabase (для чтения покупок/консультаций)
SUPABASE_URL=https://twrmpbduxemfgxtadkxa.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<ваш service-role ключ>

# Telegram (для отправки напоминаний)
TELEGRAM_BOT_TOKEN=<ваш bot token>
TELEGRAM_ADMIN_CHAT_ID=<chat ID админа для логов>

# n8n (если используете n8n workflow)
N8N_BASE_URL=http://127.0.0.1:5678
N8N_API_KEY=<ваш n8n API key>
N8N_TG_API_ID=<ID Telegram credentials в n8n>
N8N_BRIDGE_PORT=5051
N8N_BRIDGE_TOKEN=<Bearer token для n8n_bridge>
```

**Проверка:**
```bash
cd tools
python -c "from dotenv import load_dotenv; load_dotenv('.env'); import os; print('✓' if os.getenv('SUPABASE_URL') else '✗ SUPABASE_URL')"
```

---

## 🧪 Шаг 2: Тест в dry-run режиме

Сначала запустите БЕЗ отправки сообщений, чтобы увидеть, что найдётся:

```bash
cd tools
python abandoned_cart_alerts.py --dry-run --hours 24
```

**Ожидаемый вывод:**
```json
{
  "ok": true,
  "dry_run": true,
  "abandoned_purchases": [
    {
      "user_id": "...",
      "email": "...",
      "telegram": "123456789",
      "status": "skipped",  // потому что dry-run
      "reason": null
    }
  ],
  "stats": {
    "purchases_checked": 5,
    "sent": 0,
    "skipped": 2,
    "errors": 0
  }
}
```

**Что проверить:**
- ✅ Находится ли покупка со статусом `pending`?
- ✅ Есть ли у клиента Telegram ID в таблице `users`?
- ✅ Статус "skipped" = нет Telegram, "sent" = отправлено

---

## 🔔 Шаг 3: Включить отправку (без расписания)

Если dry-run прошёл успешно:

```bash
python abandoned_cart_alerts.py --hours 24
```

Это отправит **реальные** сообщения в Telegram. Проверьте, что сообщения пришли.

---

## ⏰ Шаг 4: Настроить расписание (n8n)

### Вариант 1: Через n8n UI (рекомендуется)

1. Запустите генератор workflow:
```bash
cd tools
python n8n_abandoned_workflow.py
```

2. Откройте n8n: http://127.0.0.1:5678
3. Найдите workflow **"Daily: Abandoned carts & overdue consultations alerts"**
4. Нажмите **"Activate"** (включить расписание)

### Вариант 2: Через Linux cron (если нет n8n)

```bash
# Добавить в crontab
0 9 * * * cd /home/user/MILA\ GOLD/tools && python abandoned_cart_alerts.py >> alerts.log 2>&1
```

---

## 📊 Мониторинг

После активации можно отслеживать результаты:

```bash
# Глобальная папка логов
ls -la ~/MILA\ GOLD/reports/ | grep abandoned

# Или прямой запрос к Supabase
psql -h twrmpbduxemfgxtadkxa.supabase.co -d postgres -U postgres \
  -c "SELECT COUNT(*) as pending_purchases FROM purchases WHERE status='pending' AND created_at < now() - interval '24h';"
```

---

## ⚙️ Персонализация

### Текст напоминаний

Отредактируйте в `tools/abandoned_cart_alerts.py`:

**Для покупок (практикума):**
```python
text = (
    f"👋 Привет{', ' + p['name'] if p['name'] else ''}!\n\n"
    f"Посмотрела, что ты интересовалась {product}, но пока его не активировала.\n\n"
    f"💰 Стоимость: ${p['amount']:.2f} CAD\n\n"
    f"Может, были вопросы? Я помогу! 🙏"
)
```

**Для консультаций:**
```python
text = (
    f"📞 Привет{', ' + c['name'] if c['name'] else ''}!\n\n"
    f"Напоминаю о твоей консультации ({c['type']}).\n\n"
    f"Если нужно перенести — напиши! 💬"
)
```

### Время отправки

Измените в workflow или n8n_abandoned_workflow.py:
```python
# Было: 09:00 UTC
# Хотите: 18:00 UTC?
"rule": {"interval": [{"field": "hours", "triggerAtHour": [18]}]}
```

### Фильтры

Если хотите отправлять напоминания только после 48h (не 24h):
```bash
python abandoned_cart_alerts.py --hours 48
```

---

## ✅ Критерий приёмки

- [x] Скрипт находит покупки `pending` > 24h
- [x] Скрипт находит консультации `scheduled` в прошлом
- [x] Сообщения отправляются в Telegram (когда не dry-run)
- [ ] **TODO:** Активировано расписание в n8n (должно запускаться ежедневно)
- [ ] **TODO:** За 3 дня собрать метрику: % завершённых покупок возросла?

---

## 🐛 Отладка

| Проблема | Решение |
|---------|---------|
| `Supabase не настроен` | Добавьте `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY` в `tools/.env` |
| `Telegram не находит пользователя` | Убедитесь, что в `users.telegram` есть ID (число), не username |
| `HTTP 401 в n8n` | Проверьте `N8N_BRIDGE_TOKEN` и что мост запущен на порту 5051 |
| `Workflow не запускается в расписание` | Нажмите Activate в n8n UI (синяя кнопка) |
| Сообщения не приходят в Telegram | Проверьте: `python abandoned_cart_alerts.py --dry-run --hours 1` |

---

## 📝 Логирование

Все операции логируются в stderr (для просмотра в n8n или log файлах):

```
[2026-06-08T09:00:00.000000] Поиск брошенных покупок (старше 24h)...
[2026-06-08T09:00:01.234567] Найдено: 3 покупок, 1 консультаций
[2026-06-08T09:00:02.345678] ✓ Telegram отправлено 123456789
[2026-06-08T09:00:02.456789] ✓ Завершено: 2 отправлено, 1 пропущено, 0 ошибок
```

---

## 🔗 Связанные задачи

- **P1** (Reels адаптация) — использует tu же воронку продаж
- **P2** (Дашборд) — отображает метрики по брошенным корзинам

---

**Контакты:** @developer, Лера (агент продаж)  
**Обновлено:** 2026-06-08
