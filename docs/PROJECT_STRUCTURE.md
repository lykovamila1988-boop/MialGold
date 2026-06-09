# Структура проекта MILA GOLD

## 📂 Основные папки

### `MILA-BUSINESS/` — Рабочие данные (основная папка)
- **01-praktikum/** — Практикум (PDF, HTML редактура, финальные версии)
- **02-content/** — Контент: `content-plan.md` (календарь), posts/, reels/, stories/
- **03-clients/** — CRM: intake-forms/, session-notes/ (⚠️ конфиденциально)
- **04-telegram/** — Контент для Telegram канала
- **05-analytics/** — Отчёты, статистика, KPI (gumroad_*.csv, sessions_*.txt)

### `mila-office/` — Агенты (11 штук)
```
agent.py       — Marina (маркетинг)
victoria.py    — Victoria (редактура)
lera.py        — Lera (копирайтинг)
rita.py        — Rita (аналитика)
dima.py        — Dima (финансы)
olya.py        — Olya (тренды)
tyoma.py       — Tyoma (Telegram)
alina.py       — Alina (клиенты)
vasya.py       — Vasya (расписание)
producer.py    — Producer (публикация)
manager.py     — Manager (Стас, оптимизация)

base.py        — Базовая инфраструктура (run_agent, tools, memory)
shared_tools.py — Общие инструменты (Supabase, Gumroad, API)
memory.py      — Единый источник памяти (notes, posts, clients)
pipeline.py    — P1→P2→P3 цепочки (Marina→Victoria→Vasya)
webapp.py      — Flask веб-интерфейс (http://127.0.0.1:5000)
office.py      — CLI меню запуска агентов (python office.py)
```

### `tools/` — Instagram/Threads API скрипты
```
_common.py           — Общая инфраструктура (API, токены, Supabase)
get_analytics.py     — Получить статистику постов
get_comments.py      — Получить комментарии с обнаружением лидов
get_dms.py           — Direct messages
post_content.py      — Публикация в Instagram + Threads
get_threads.py       — Threads API
make_report.py       — Сборка .docx отчётов из JSON
.env                 — Токены и секреты (⚠️ не коммитить)
```

### `mila-agent/` — Старая копия Marina (устаревшее)
Оставлено для обратной совместимости. **Рабочая версия Marina в `mila-office/agent.py`**

### `docs/` — Документация
```
SUPABASE_ACCESS.md              — Гайд доступа к БД
PROJECT_STRUCTURE.md (этот файл) — Структура проекта
SUMMARY_P1P2P3.md               — Цепочки контента
CHAIN_EXAMPLES.md               — Примеры agent interactions
```

### `scripts/` — Батники запуска
```
start-mila.bat  — Запустить Flask webapp + agents
stop-mila.bat   — Остановить все процессы
```

### `logs/` — Логи приложений
```
webapp.log              — Flask логи
archive/                — Архивированные старые логи
user_activity.jsonl     — История действий пользователя (не коммитить)
```

### `reports/` — Аналитика (генерируется)
```
posts_YYYY-MM-DD.json       — Статистика постов (Instagram API)
comments_YYYY-MM-DD.json    — Комментарии с обнаруженными лидами
account_YYYY-MM-DD.json     — Статистика аккаунта
```

### `n8n-data/` — рабочая папка n8n (не коммитить)
```
.n8n/                   — БД workflows, credentials, history
.cache/                 — Кеш (80+ МБ, автоматически очищается)
```

### `node_modules/` — Зависимости (в .gitignore)
Генерируется при `npm install`. Не коммитить.

### `sales_texts/` — Тексты для продаж
Мини-папка с вариантами копий, гайдов по продажам.

### Root файлы
```
CLAUDE.md           — Инструкции для Claude Code
README.md           — Описание проекта
package.json        — NPM зависимости
.env.txt            — Шаблон переменных окружения
.gitignore          — Исключения для git
```

---

## 🔧 Конфигурация окружения

### `tools/.env` (основной)
```env
# Instagram / Facebook
IG_ACCESS_TOKEN=...
IG_USER_ID=...
FB_PAGE_ID=...
IG_API_FLOW=facebook          # или 'instagram_login'

# Threads
THREADS_ACCESS_TOKEN=...
THREADS_USER_ID=...

# Supabase (для агентов)
SUPABASE_URL=https://twrmpbduxemfgxtadkxa.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...  # ⚠️ Секрет! Не коммитить

# AI APIs
ANTHROPIC_API_KEY=...
GEMINI_KEY=...

# Other
TELEGRAM_BOT_TOKEN=...
GUMROAD_ACCESS_TOKEN=...
GRAPH_API_VERSION=v21.0
```

### Старые переменные (не используются в текущей версии)
```env
# Устаревшие имена (замены для совместимости):
INSTAGRAM_ACCESS_TOKEN → IG_ACCESS_TOKEN
INSTAGRAM_BUSINESS_ACCOUNT_ID → IG_USER_ID
```

---

## 📊 Размеры (после реорганизации)

| Папка | Размер | Назначение |
|-------|--------|-----------|
| n8n-data | 19 МБ | Рабочие данные n8n (БД, логи) |
| node_modules | 8.6 МБ | NPM зависимости (не коммитить) |
| MILA-BUSINESS | 7.7 МБ | Рабочие данные (контент, клиенты) |
| logs | 6.3 МБ | Логи приложений |
| mila-office | 2.8 МБ | Код агентов |
| reports | 2.4 МБ | Аналитика (генерируется) |
| tools | 780 КБ | API скрипты |
| docs | 68 КБ | Документация |
| **TOTAL** | **52 МБ** | (было 150+ МБ) |

---

## 🗑️ Что было удалено (реорганизация)

- `MILA/` — дублировала MILA-BUSINESS/
- `backups/` — старые резервные копии
- `.pytest_cache/`, `.qodo/` — служебные папки
- `n8n-data/.cache/` — 80 МБ кеша (пересоздаётся автоматически)
- 25+ служебных файлов (*_SUMMARY.txt, *_GUIDE.md) из root
- Дубли praktikum (оставлена одна копия)

**Результат:** Проект сокращен с 150+ МБ до 52 МБ, структура чистая.

---

## 🚀 Типичные операции

### Запустить веб-приложение
```bash
cd mila-office
python webapp.py
# Открыть http://127.0.0.1:5000
```

### Запустить агента из CLI
```bash
cd mila-office
python office.py           # Меню выбора агента
python agent.py            # Запустить Marina напрямую
python dima.py             # Запустить Dima
```

### Опубликовать в Instagram
```bash
cd tools
python post_content.py photo --url "https://..." --caption "..."
python post_content.py reel --url "https://..." --caption "..." --threads
```

### Получить аналитику
```bash
cd tools
python get_analytics.py posts   # Топ-посты
python get_analytics.py comments  # Комментарии + лиды
python make_report.py           # .docx отчёт
```

---

## ⚠️ Конфиденциальность

**НИКОГДА не коммитить:**
- `tools/.env` — токены, секреты
- `MILA-BUSINESS/03-clients/session-notes/` — конфиденциальные заметки клиентов
- `MILA-BUSINESS/03-clients/intake-forms/` (кроме README)
- `logs/user_activity.jsonl` — история действий

---

## 📝 Документация

- **CLAUDE.md** — инструкции для Claude Code при работе с проектом
- **docs/SUPABASE_ACCESS.md** — гайд подключения и использования БД
- **docs/SUMMARY_P1P2P3.md** — описание цепочек контента
- Каждая папка `MILA-BUSINESS/*/` имеет свой `README.txt`

---

**Дата последней актуализации:** 2026-06-08
**Коммит:** 8521e05 (Реорганизация файловой системы)
