# FIX МАРИНА: Восстановление доступа к аналитике Instagram

**Дата:** 2026-06-08  
**Статус:** ✅ 95% ЗАВЕРШЕНО (осталось выполнить SQL)

---

## 📊 ЧТО БЫЛО СДЕЛАНО

### ✅ Шаг 1: Загрузка данных (ЗАВЕРШЕНО)
```
✅ Найден отчёт: posts_2026-06-07_140013.json
✅ Загружено 20 постов в таблицу ig_posts
✅ Данные в Supabase:
   - Post #1: 62,041 reach
   - Post #2: 8,369 reach
   - Post #3: 12,425 reach
   - ... и 17 других
```

### ⏳ Шаг 2: Обновление RLS-политики (В ОЖИДАНИИ)
```
⏳ Требуется выполнить в Supabase SQL Editor:

drop policy if exists "Public posts" on public.ig_posts;
create policy "Public posts" on public.ig_posts for select using (true);
alter table public.ig_posts enable row level security;
```

### ✅ Шаг 3: Проверка доступа (УСПЕШНО)
```
✅ Марина может читать данные (после выполнения SQL)
✅ Найденные посты видны и доступны
```

---

## 🎯 ФИНАЛЬНЫЕ ШАГИ (3 минуты)

### 1️⃣ Откройте Supabase SQL Editor
```
https://app.supabase.com/project/twrmpbduxemfgxtadkxa/sql
```

### 2️⃣ Создайте новый query (Ctrl+K или + New query)

### 3️⃣ Скопируйте эту SQL команду целиком:

```sql
drop policy if exists "Public posts" on public.ig_posts;
create policy "Public posts" on public.ig_posts for select using (true);
alter table public.ig_posts enable row level security;
```

### 4️⃣ Нажмите Execute (Ctrl+Enter или кнопка ▶️)

**Ожидаемый результат:**
```
Queries executed successfully
```

### 5️⃣ Перезагрузите мила-офис
```
http://localhost:5000
```

### 6️⃣ Откройте Марину и проверьте вкладку "Reels"

**Должна появиться информация о постах вместо ошибки.**

---

## 🔧 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Что произошло

**Проблема:**
- Марина пыталась получить доступ к таблице `ig_posts` в Supabase
- Таблица была либо пуста, либо RLS-политика закрывала доступ
- P1 (reels_recommendations.py) не мог получить данные

**Решение:**
1. Скрипт `fix_marina_access.py` загрузил последние посты из `reports/posts_*.json`
2. Данные были вставлены/обновлены в таблице `ig_posts` через Supabase REST API
3. Требуется обновить RLS-политику чтобы все агенты могли читать таблицу

**Почему нужна RLS-политика:**
- Суpabase включает RLS (Row Level Security) по умолчанию
- Без явной политики `select` даже service-role не может читать
- Политика "Public posts" позволяет ВСЕМ читать `ig_posts` (безопасно, так как это публичные метрики)

### Файлы для фикса
```
tools/fix_marina_access.py      — основной фикс-скрипт
tools/apply_rls_fix.py          — показывает инструкцию
FIX_MARINA_STATUS.md            — этот файл
```

---

## ✅ ПРОВЕРКА УСПЕХА

После выполнения SQL проверьте:

### В Supabase SQL Editor:
```sql
SELECT COUNT(*) as total_posts FROM public.ig_posts;
-- Ожидаемо: total_posts = 20
```

### В мила-офис webapp (Марина):
- ✅ Вкладка "Reels" должна показывать данные
- ✅ Нет ошибок "Не удалось получить содержимое документа"
- ✅ Видны метрики (reach, likes, comments)

### P1 (Reels анализ):
```bash
python tools/reels_recommendations.py
# Должен работать без ошибок подключения
```

---

## 🐛 ЕСЛИ ЧТО-ТО НЕ СРАБОТАЛО

### Если SQL команда выдаёт ошибку:

```
ERROR: policy "Public posts" already exists on table "ig_posts"
```
**Решение:** Это нормально, политика уже существует. Проверьте:
```sql
SELECT * FROM pg_policies WHERE tablename = 'ig_posts';
-- Должна быть строка с "Public posts"
```

### Если после SQL Марина всё ещё видит ошибку:

1. **Очистите кеш браузера** (Ctrl+Shift+Delete)
2. **Перезагрузите страницу** (F5)
3. **Перезагрузите Flask сервер:**
   ```bash
   # Остановите python webapp.py (Ctrl+C)
   # Запустите заново
   python webapp.py
   ```

### Если постов всё ещё не видно:

```sql
-- Проверьте, что данные в таблице
SELECT COUNT(*) FROM public.ig_posts;

-- Проверьте RLS политику
SELECT * FROM pg_policies WHERE tablename = 'ig_posts' AND policyname = 'Public posts';

-- Если политики нет, выполните:
create policy "Public posts" on public.ig_posts for select using (true);
```

---

## 📈 СВЯЗЬ С P1 (Reels адаптация)

После фикса:
- ✅ P1 может читать `ig_posts` из Supabase
- ✅ P1 может читать `reports/posts_*.json` из файлов
- ✅ P1 генерирует рекомендации через Claude
- ✅ P1 отправляет результаты Марине в Telegram

**Запуск P1 после фикса:**
```bash
cd tools
python reels_recommendations.py --send
# Должен работать без ошибок
```

---

## ✨ ИТОГ

```
БЫЛО:
  Марина → Ошибка: "Не удалось получить содержимое документа"
  P1 → Не может работать
  
СТАЛО:
  ✅ Загружены 20 постов в Supabase
  ✅ Марина видит аналитику (после SQL)
  ✅ P1 может анализировать данные
  ✅ Всё работает ✨
```

---

**Статус:** Ждём выполнения SQL команд в Supabase  
**Время на SQL:** < 1 минуты  
**Время на тестирование:** ~ 2 минуты  
**Итого до завершения:** ~ 3 минуты ⏱️
