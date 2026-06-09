# 📊 CHAIN LOGGING — Логирование цепочки обработки

## 📝 Что логируется

Каждый шаг в цепочке обработки записывается в `logs/chain.log`:

```
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_2026_06_08_1
[2026-06-08 14:31] agent=victoria from=marina verdict=ready_next next=vasya chain=post_2026_06_08_1
[2026-06-08 14:32] agent=vasya from=victoria verdict=done next=END chain=post_2026_06_08_1
```

---

## 🔍 Формат логирования

```
[TIMESTAMP] agent={agent} from={from_agent} verdict={verdict} next={next_agent} chain={chain_id}
```

### Значение полей:

| Поле | Значение | Пример |
|------|----------|--------|
| `agent` | Текущий агент | `marina`, `victoria`, `vasya` |
| `from` | От какого агента пришло | `user`, `marina`, `victoria` |
| `verdict` | Статус обработки | `ready_next`, `done`, `needs_revision` |
| `next` | Следующий агент или END | `victoria`, `vasya`, `END` |
| `chain` | ID цепочки | `post_2026_06_08_1`, `visual_project_2` |

---

## 📊 Примеры логов

### Пример 1: Успешная цепочка Post

```
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_2026_06_08
[2026-06-08 14:31] agent=victoria from=marina verdict=ready_next next=vasya chain=post_2026_06_08
[2026-06-08 14:32] agent=vasya from=victoria verdict=done next=END chain=post_2026_06_08
```

**Интерпретация:**
- Marina написала пост, готов для Victoria (редактуры)
- Victoria отредактировала, готово для Vasya (расписания)
- Vasya расписал, финально завершено

### Пример 2: Цепочка с ошибкой (needs_revision)

```
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=content_v2
[2026-06-08 14:31] agent=victoria from=marina verdict=needs_revision next=marina chain=content_v2
[2026-06-08 14:32] agent=marina from=victoria verdict=ready_next next=victoria chain=content_v2
[2026-06-08 14:33] agent=victoria from=marina verdict=done next=END chain=content_v2
```

**Интерпретация:**
- Marina написала, Victoria нашла ошибки
- Marina переделала, Victoria одобрила
- Работа завершена

### Пример 3: Параллельные задачи (один chain_id)

```
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=project_complete
[2026-06-08 14:30] agent=rita from=user verdict=ready_next next=END chain=project_complete
[2026-06-08 14:31] agent=victoria from=marina verdict=done next=END chain=project_complete
```

**Интерпретация:**
- Marina и Rita работали параллельно на один project_complete
- Victoria обработала Maria вход, Rita закончила независимо
- Обе ветки завершены

---

## 🔧 Где находятся логи

```
E:\MILA GOLD\
  └─ logs/
     └─ chain.log        ← Логи цепочки обработки
     └─ llm.log          ← Логи LLM вызовов
     └─ victoria.log     ← Логи Victoria агента
     └─ marina.log       ← Логи Marina агента
     └─ ... (другие агенты)
```

---

## 📖 Как читать логи

### Быстрая проверка статуса цепочки

```bash
# Найти все шаги цепочки с ID post_2026_06_08
grep "chain=post_2026_06_08" logs/chain.log

# Найти все завершенные цепочки (verdict=done)
grep "verdict=done" logs/chain.log

# Найти все ошибки (verdict=needs_revision)
grep "verdict=needs_revision" logs/chain.log
```

### Анализ времени обработки

```bash
# Посмотреть первый и последний шаг цепочки
head -1 logs/chain.log  # 14:30
tail -1 logs/chain.log  # 14:32
# Итого: 2 минуты на обработку
```

---

## 🎯 Отладка цепочек

### Проблема: Цепочка прервалась

```
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=post_xyz
# ... ничего нет для victoria
```

**Решение:**
- Проверить что victoria.py запущена
- Проверить логи victoria.log на ошибки
- Убедиться что chain_id передан правильно

### Проблема: Бесконечный цикл

```
[2026-06-08 14:30] agent=marina from=user verdict=ready_next next=victoria chain=loop_bug
[2026-06-08 14:31] agent=victoria from=marina verdict=needs_revision next=marina chain=loop_bug
[2026-06-08 14:32] agent=marina from=victoria verdict=ready_next next=victoria chain=loop_bug
[2026-06-08 14:33] agent=victoria from=marina verdict=needs_revision next=marina chain=loop_bug
# ...
```

**Решение:**
- Обычно это значит что Victoria всегда требует правки
- Проверить prompt Victoria на экстремальные требования
- Дать более четкие инструкции

---

## 📊 Анализ производительности

### Скрипт для анализа

```python
# analyze_chains.py
import re
from pathlib import Path
from datetime import datetime

def analyze_chain_log():
    log_path = Path("logs/chain.log")
    lines = log_path.read_text(encoding="utf-8").split("\n")
    
    chains = {}
    
    for line in lines:
        if not line.strip():
            continue
        
        # Парсим: [2026-06-08 14:30] agent=marina ...
        match = re.search(r'\[(\d+:\d+)\].*chain=(\S+)', line)
        if match:
            time_str, chain_id = match.groups()
            
            if chain_id not in chains:
                chains[chain_id] = {"start": time_str, "steps": []}
            
            chains[chain_id]["steps"].append(line)
            chains[chain_id]["end"] = time_str
    
    # Выводим статистику
    for chain_id, data in sorted(chains.items()):
        steps = len(data["steps"])
        print(f"{chain_id}: {steps} шагов ({data['start']} → {data['end']})")
```

---

## 🔐 Конфиденциальность в логах

**ВАЖНО:** Логи содержат только:
- ✅ Имена агентов
- ✅ ID цепочек
- ✅ Статусы обработки

**НЕ содержат:**
- ❌ Содержимое постов
- ❌ Пользовательские данные
- ❌ Приватную информацию

Логи безопасны для хранения и анализа!

---

## 📈 Мониторинг в реальном времени

### Просмотр новых логов

```bash
# Последние 20 строк
tail -20 logs/chain.log

# Следить за новыми (live streaming)
tail -f logs/chain.log

# С фильтром по chain_id
tail -f logs/chain.log | grep "chain=post_"
```

---

## 🎯 Интеграция с мониторингом

В webapp.py можно добавить эндпоинт для просмотра логов цепочки:

```python
@app.get("/api/logs/chain/<chain_id>")
def get_chain_logs(chain_id):
    """Получить все логи для цепочки"""
    from pathlib import Path
    
    log_path = Path("logs/chain.log")
    lines = log_path.read_text(encoding="utf-8").split("\n")
    
    chain_logs = [l for l in lines if f"chain={chain_id}" in l]
    
    return jsonify({
        "chain_id": chain_id,
        "steps": len(chain_logs),
        "logs": chain_logs
    })
```

---

## 📋 Чеклист для логирования

- ✅ Каждый agent.response() вызывает process_agent_response()
- ✅ process_agent_response() вызывает _log_chain_step()
- ✅ _log_chain_step() пишет в logs/chain.log
- ✅ chain_id передается через всю цепочку
- ✅ Логи содержат: agent, from_agent, verdict, next_agent, chain_id
- ✅ Логи регулярно архивируются (keep last 7 дней)

---

## 🎉 ЛОГИРОВАНИЕ ГОТОВО!

Теперь каждая цепочка полностью отслеживается и логируется! ✨
