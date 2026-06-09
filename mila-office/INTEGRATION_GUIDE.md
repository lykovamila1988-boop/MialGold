# Алина CRM — Руководство интеграции

## Что было добавлено

### 1. alina.py (обновлен)
**Файл**: `mila-office/alina.py`

**Что добавлено**:
- ✅ **CRM контекст** — полная воронка customer journey (4 стадии)
- ✅ **from_agent awareness** — Алина знает, от кого пришел запрос (Лера, Людмила, Дима и т.д.)
- ✅ **chain_id tracking** — уникальный идентификатор для отслеживания цепочки обработки
- ✅ **Новые инструменты**: `log_client_journey`, `generate_chain_id`
- ✅ **Новая быстрая команда**: `/воронка` — анализ воронки продаж

**Ключевые изменения в SYSTEM prompt**:
```
ВОРОНКА КЛИЕНТА (CUSTOMER JOURNEY):
  Стадия 1: ЛИДИРОВАНИЕ (intake-form)
  Стадия 2: КОНСУЛЬТАЦИЯ/ДИАГНОСТИКА
  Стадия 3: ПАКЕТ СЕССИЙ
  Стадия 4: FOLLOW-UP & ПОВТОРНЫЕ КОНСУЛЬТАЦИИ

КОНТЕКСТ ЗАПРОСА (from_agent):
  - Если от Лера → новый лид, first-contact профиль
  - Если от Людмилы → подготовка к сессии или анализ прогресса
  - Если от других → учитывать их контекст
```

### 2. message_handler.py (обновлен)
**Файл**: `mila-office/message_handler.py`

**Что добавлено**:
- ✅ **Алина в pipeline**: добавлена CRM цепь `lera → alina`

```python
def get_pipeline_order() -> dict:
    return {
        # контент цепь
        "olya": "marina",
        "marina": "victoria",
        "victoria": "vasya",
        "vasya": "rita",
        "rita": None,
        
        # CRM цепь (новая)
        "lera": "alina",
        "alina": None,
    }
```

### 3. system_prompt_builder.py (обновлен)
**Файл**: `mila-office/system_prompt_builder.py`

**Что добавлено**:
- ✅ **__all__ экспорт** — функции доступны из base.py

```python
__all__ = [
    "build_system_prompt",
    "extract_context_from_message",
    "get_agent_chain_info",
    "_build_context_section",
    # ...
]
```

### 4. ALINA_CRM.md (новый)
**Файл**: `mila-office/ALINA_CRM.md`

Полная документация:
- Роль Алины в воронке
- Все 4 стадии customer journey
- Интеграция с другими агентами (Лера, Людмила, Дима)
- Инструменты и быстрые команды
- Структура данных профилей и заметок
- Примеры взаимодействия
- Best practices

---

## Как это работает

### Поток 1: Новый лид от Леры

```
┌─────────────────────────────────────────────────────────────────┐
│ ЛЕРА (SALES) находит нового клиента                            │
│ → заполняет intake-форму в 03-clients/intake-forms/           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓ [from: lera] [chain_id: journey_xxx]
┌──────────────────────────────────────────────────────────────────┐
│ АЛИНА (CRM)                                                      │
│ 1. Читает intake-форму                                           │
│ 2. Определяет паттерн (Спасатель/Угодница/Избегание)           │
│ 3. Создает/обновляет профиль в 03-clients/profiles/           │
│ 4. Логирует: log_client_journey("лид", stage="intake", ...)    │
│ 5. Отвечает: готов профиль к первой сессии                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓ [VERDICT: ready_next] [→ user]
                    ГОТОВО К ПЕРЕДАЧЕ ЛЮДМИЛЕ НА КОНСУЛЬТАЦИЮ
```

### Поток 2: Постсессионная обработка

```
┌──────────────────────────────────────────────────────────────────┐
│ ЛЮДМИЛА проводит сессию → пишет заметки в:                     │
│ 03-clients/session-notes/Клиентка_session_N_20260608.md        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓ "вот заметки из сессии"
┌──────────────────────────────────────────────────────────────────┐
│ АЛИНА (CRM)                                                      │
│ 1. Читает session-notes                                          │
│ 2. Структурирует: инсайты, блоки, домашние задания            │
│ 3. Обновляет профиль: sessions_completed++, key_insights=[...] │
│ 4. Логирует: log_client_journey(..., stage="package", ...)     │
│ 5. Определяет: готова ли клиентка продолжить?                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ↓ [VERDICT: ready_next]
                    ПРОФИЛЬ ОБНОВЛЕН, ГОТОВ К СЛЕДУЮЩЕЙ СЕССИИ
```

### Поток 3: Анализ воронки

```
Пользователь: "/воронка"
   ↓
АЛИНА читает все профили → распределяет по stage:
  - intake: Мария, Таня (новые)
  - consultation: Ольга (прошла диагностику, решает пакет)
  - package: Анна (3/4), Лена (5/8)
  - followup: Таисия (пакет закончился 2 недели назад)
   ↓
ОТЧЕТ: "Ольга не подтверждала пакет → нужна мотивирующая сессия"
```

---

## Контекст запроса (from_agent)

Алина всегда получает информацию о **источнике запроса**:

```python
context = {
    "from_agent": "lera",          # запрос от Леры (новый лид)
    "to_agent": "alina",            # адресовано Алине
    "chain_id": "journey_20260608_143015_abc123"  # ID цепочки
}
```

Это позволяет Алине адаптировать свой ответ:

| from_agent | Контекст | Действие Алины |
|----------|----------|----------|
| `lera` | новый клиент | создать first-contact профиль |
| `user` | пользователь запрашивает | анализ воронки, подготовка к сессии |
| `dima` | финансовый запрос | LTV, retention, паттерны покупок |
| `victoria` | редактор | рекомендация контента по паттернам |

---

## Chain ID для отслеживания

Каждая цепочка взаимодействия имеет уникальный ID:

```
journey_20260608_143015_abc123
  ├─ intake форма от Леры
  ├─ консультация (сессия 1)
  ├─ пакет 4 сессии (сессии 2-4)
  └─ follow-up (через 2 недели)
```

**Где используется**:
- В логах (`logs/chain.log`) — полная история
- В профилях клиенток (`profiles/`) — список chain_ids
- В сообщениях между агентами — `[chain_id: ...]`

**Автоматическое логирование**:
```python
log_client_journey(
    client_name="Анна",
    stage="package",
    notes="сессия 3/4 пройдена успешно",
    chain_id="journey_20260608_143015_abc123"
)
```

---

## Инструменты Алины

### Базовые (наследованы из base.py)
```python
read_file(path)      # читать анкету, заметки, профили
write_file(path)     # сохранять профили и сводки
list_files(path)     # показывать список файлов
```

### Специальные для CRM (в alina.py)
```python
find_clients_by_pattern(pattern)  # поиск по паттерну
get_client_list()                  # все клиентки
log_client_journey(...)            # логировать веху customer journey
generate_chain_id(prefix)          # создать новый chain_id
```

### Быстрые команды
```
/клиентки   → список + статусы
/анкета     → последняя intake-форма + профиль
/сводка     → структурированная сводка из session-notes
/прогресс   → сравнение: начало vs сейчас
/воронка    → анализ воронки: кто на каком этапе
```

---

## Структура данных

### Профиль клиентки (JSON)
```json
{
  "name": "Анна",
  "pattern": "Спасатель",
  "intake_date": "2026-06-01",
  "stage": "package",
  "package_type": "4_sessions",
  "sessions_completed": 3,
  "total_sessions": 4,
  "key_insights": ["не берет ответственность"],
  "blocks": ["страх одиночества"],
  "motivation": "high",
  "chain_ids": ["journey_20260608_143015_abc123"],
  "ltv": 600
}
```

### Session Notes (Markdown)
```markdown
# Сессия 3 с Анной — 2026-06-08

## Инсайты
- Осознала связь между спасением других и игнорированием себя
- Впервые произнесла: "я имею право на свои потребности"

## Домашнее задание
- Три дня в неделю спрашивать себя: "Чего я хочу?"
- Записать три потребности, которые игнорировала

## Блоки
- Вина перед мамой (из детства)
- Страх быть эгоисткой

## Готовность к продолжению
- ДА, готова к 4-й сессии
```

---

## Логирование

### logs/client_journey.log
```
[2026-06-08 14:30] CLIENT=Анна STAGE=intake NOTES=Спасатель, мотивирована CHAIN=journey_20260608_143015_abc123
[2026-06-08 14:31] CLIENT=Анна STAGE=consultation NOTES=Диагностика пройдена CHAIN=journey_20260608_143015_abc123
[2026-06-08 15:00] CLIENT=Анна STAGE=package NOTES=сессия 1/4 CHAIN=journey_20260608_143015_abc123
```

### logs/chain.log
```
[2026-06-08 14:30] agent=alina from=lera verdict=ready_next next=user chain=journey_20260608_143015_abc123
[2026-06-08 14:31] agent=alina from=user verdict=done next=None chain=journey_20260608_143015_abc123
```

---

## Тестирование

### Проверить, что alina.py корректно загружается
```bash
cd "E:\MILA GOLD\mila-office"
python -c "import alina; print('✓ OK')"
```

### Проверить контекст
```bash
python << 'EOF'
import base
from alina import SYSTEM

context = {
    "from_agent": "lera",
    "chain_id": "journey_20260608_143015_abc123"
}

composed = base.compose_system("alina", SYSTEM, context)
assert "КОНТЕКСТ ЗАПРОСА" in composed
assert "цепочки" in composed.lower()
print("✓ Context composition works")
EOF
```

### Проверить pipeline
```bash
python << 'EOF'
from message_handler import get_pipeline_order, get_agent_chain_info

pipeline = get_pipeline_order()
assert pipeline.get("lera") == "alina"
assert pipeline.get("alina") is None

info = get_agent_chain_info("alina")
assert info["is_final"] == True
print("✓ Pipeline integration OK")
EOF
```

---

## Внедрение в продакшен

1. ✅ **Обновлена alina.py** — CRM контекст + инструменты + быстрые команды
2. ✅ **Обновлена message_handler.py** — Алина в pipeline
3. ✅ **Обновлена system_prompt_builder.py** — экспорт функций
4. ✅ **Документация** — ALINA_CRM.md + INTEGRATION_GUIDE.md
5. ✅ **Тестирование** — загрузка, контекст, pipeline проверены

**Готово к использованию!** Запусти webapp.py и попробуй:
```bash
cd "E:\MILA GOLD\mila-office"
python webapp.py
```

Откроется http://127.0.0.1:5000 — перейди на вкладку **Алина** и попробуй команды:
- `/клиентки` — список всех
- `/воронка` — анализ
- Отправь: `[from: lera] новый лид заполнила анкету` — Алина поймет контекст

---

## Что дальше

### Рекомендуемые улучшения
1. **Supabase интеграция** — профили клиенток в `consultations` table
2. **Auto-reminders** — напоминания о follow-up через cron
3. **LTV dashboard** — визуализация lifetime value по клиентке
4. **Metrics** — отслеживание конверсии: intake → package (%)

### Автоматизация в n8n
1. **When intake form submitted** → вызови алину через API → профиль готов
2. **Weekly client status** → Алина анализирует всех → Telegram report Людмиле
3. **Follow-up reminders** → автоматические напоминания через 2 недели/месяц

### Документирование в improvement_log
После первого месяца использования в Supabase обновляй `05-analytics/improvement_log.md`:
```markdown
## Алина CRM (P0 Ready)
- [x] from_agent awareness
- [x] chain_id tracking
- [x] customer journey logging
- [ ] Supabase integration (P1)
- [ ] Auto follow-up reminders (P2)
- [ ] LTV dashboard (P3)
```
