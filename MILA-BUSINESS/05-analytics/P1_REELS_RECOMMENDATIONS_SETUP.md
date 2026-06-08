# P1: Автоматическая адаптация контента Reels на основе аналитики

**Статус:** Готов к тестированию  
**Срок:** 2026-06-15 (7 дней)  
**Исполнитель:** Developer + Марина  
**Результат:** Еженедельные AI-рекомендации по адаптации контент-плана на основе аналитики

---

## 📋 Что это делает

1. **Каждый понедельник в 09:00 UTC** запускается анализ Reels
2. **Анализирует метрики**:
   - Охват (reach) всех Reels за неделю
   - Вовлечённость (likes + comments)
   - Engagement rate
3. **Использует Claude AI** для генерации конкретных рекомендаций:
   - Какие ТЕМЫ / ПАТТЕРНЫ работают лучше
   - Какой формат выбрать (длина, структура)
   - Где лучше использовать CTA
   - 2-3 конкретные идеи для постов на следующую неделю
4. **Отправляет Марине** в Telegram с полным анализом
5. **Сохраняет отчёт** в `MILA-BUSINESS/05-analytics/reels-recommendations/`

---

## 🛠️ Компоненты

| Файл | Назначение |
|------|-----------|
| `tools/reels_recommendations.py` | Основной скрипт (чтение analytics + Claude анализ) |
| `tools/n8n_reels_workflow.py` | Генератор n8n workflow (еженедельное расписание) |
| `mila-office/n8n_bridge.py` | HTTP endpoint `/v1/tools/reels-recommendations` |

---

## 🚀 Шаг 1: Проверка конфига

### В `tools/.env` должно быть:

```bash
# Anthropic API (для Claude анализа)
ANTHROPIC_API_KEY=sk-ant-...

# Telegram (для отправки рекомендаций Марине)
TELEGRAM_BOT_TOKEN=<ваш bot token>
TELEGRAM_MARINA_ID=<telegram ID Марины (число)>

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
python -c "from dotenv import load_dotenv; load_dotenv('.env'); import os; print('✓ ANTHROPIC_API_KEY' if os.getenv('ANTHROPIC_API_KEY') else '✗ ANTHROPIC_API_KEY missing')"
```

---

## 🧪 Шаг 2: Тест анализа (без отправки)

```bash
cd tools
python reels_recommendations.py
```

**Ожидаемый вывод:**
```json
{
  "ok": true,
  "timestamp": "2026-06-08T...",
  "reels_analyzed": 15,
  "patterns": {
    "total_reels": 15,
    "avg_reach": 2450,
    "avg_engagement": 145,
    "top_engagement_rate": 8.5
  },
  "top_reels": [
    {"reach": 5200, "engagement": 320, "caption": "Три типа - кто ты..."},
    ...
  ],
  "recommendations": "На основе анализа вижу, что Reels о паттернах...",
  "saved_to": "/path/to/reels-rec_2026-06-08.md"
}
```

**Что проверить:**
- ✅ Находятся ли Reels из отчёта analytics?
- ✅ Правильно ли считается reach и engagement?
- ✅ Генерируются ли рекомендации от Claude?
- ✅ Сохраняется ли отчёт в файл?

---

## 📤 Шаг 3: Включить отправку Марине

```bash
python reels_recommendations.py --send
```

Это отправит рекомендации Марине в Telegram (в чат с ID `TELEGRAM_MARINA_ID`). Проверьте, что сообщение пришло.

---

## ⏰ Шаг 4: Настроить еженедельное расписание (n8n)

### Вариант 1: Через n8n UI (рекомендуется)

1. Запустите генератор workflow:
```bash
cd tools
python n8n_reels_workflow.py
```

2. Откройте n8n: http://127.0.0.1:5678
3. Найдите workflow **"Weekly: Reels analytics → AI recommendations → Марина"**
4. Нажмите **"Activate"** (включить расписание)

### Вариант 2: Через Linux cron (если нет n8n)

```bash
# Добавить в crontab (понедельник 09:00 UTC)
0 9 * * 1 cd /home/user/MILA\ GOLD/tools && python reels_recommendations.py --send >> reels-rec.log 2>&1
```

---

## 📊 Мониторинг

Отчёты сохраняются в:
```
MILA-BUSINESS/05-analytics/reels-recommendations/
  reels-rec_2026-06-08.md
  reels-rec_2026-06-15.md
  ...
```

Каждый отчёт содержит:
- Статистику (охват, engagement)
- ТОП-5 Reels с метриками
- **AI-рекомендации** от Claude
- Ссылки на лучшие посты

---

## ⚙️ Персонализация

### Изменить время запуска

Отредактируйте в `tools/n8n_reels_workflow.py`:

```python
# Было: понедельник 09:00 UTC
# Хотите: пятница 18:00?
"rule": {"interval": [{"field": "weeks", "triggerAtDay": [5], "triggerAtHour": 18}]}
```

### Изменить модель Claude

По умолчанию используется `claude-opus-4-8`. Если хотите более быструю (но менее мощную):

```python
# В reels_recommendations.py, строка ~180
"model": "claude-sonnet-4-6",  # или claude-haiku-4-5-20251001
```

### Собственный промпт для анализа

Отредактируйте `prompt` в функции `generate_recommendations()` (строки ~140-165).

---

## ✅ Критерий приёмки

- [x] Скрипт читает последний отчёт posts_*.json
- [x] Фильтрует только Reels (VIDEO)
- [x] Анализирует reach, engagement, engagement rate
- [x] Вызывает Claude API для генерации рекомендаций
- [x] Отправляет результат Марине в Telegram (когда --send)
- [x] Сохраняет отчёт в файл
- [ ] **TODO:** Активировано расписание в n8n (должно запускаться каждый понедельник)
- [ ] **TODO:** За неделю собрать метрику: улучшилась ли конверсия Reels?

---

## 🐛 Отладка

| Проблема | Решение |
|---------|---------|
| `Нет posts_*.json в reports/` | Запустите `python get_analytics.py posts` для создания отчёта |
| `Нет ANTHROPIC_API_KEY` | Добавьте ключ в `tools/.env` (из console.anthropic.com) |
| `Telegram не находит Марину` | Убедитесь, что `TELEGRAM_MARINA_ID` = число (не username) |
| `HTTP 401 в n8n` | Проверьте `N8N_BRIDGE_TOKEN` в env и запущен ли мост на порту 5051 |
| `Claude генерирует на английском` | Проверьте, что в prompt используется русский язык (строка ~145) |
| Рекомендации не приходят в Telegram | Запустите `python reels_recommendations.py --send` для проверки |

---

## 📊 Примеры рекомендаций

Claude может дать что-то вроде:

> **Что работает хорошо:**
> 1. **Реелс о трёх типах** (Спасатель/Угодница/Избегание) — engagement rate 8.5% (выше среднего)
> 2. **Реелс-истории** (личный пример) — охват выше на 40%
> 3. **Рилс с вопросом в конце** — больше комментариев
>
> **Что улучшить:**
> - Делай рилсы 45-60 сек, не 30 сек
> - Начинай с сильного крючка (первые 3 сек — решающие)
>
> **Идеи на следующую неделю:**
> 1. Рилс: "Какой паттерн ты узнаёшь в себе — Спасатель, Угодница или Избегание?" (вопрос → комментарии)
> 2. Рилс: История из консультации — как клиентка узнала свой паттерн
> 3. Карусель: Как перейти от паттерна к выбору (5 шагов)

---

## 🔗 Связанные задачи

- **P3** (Брошенные корзины) — отслеживает конверсию из Reels
- **P2** (Дашборд) — визуализирует воронку от Reels до продажи

---

**Контакты:** @developer, Марина (контент-стратег)  
**Обновлено:** 2026-06-08
