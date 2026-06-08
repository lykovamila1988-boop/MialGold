# P2: Динамический дашборд воронки продаж

**Статус:** Готов к развёртыванию  
**Срок:** 2026-06-18 (10 дней)  
**Исполнитель:** Developer + Дима  
**Результат:** Интерактивный дашборд для мониторинга воронки продаж в реальном времени

---

## 📊 Что это делает

**Визуализирует полную воронку:**
```
Reels (15,200 reach) 
  ↓ (5-10% engaged)
Instagram followers (1,520)
  ↓ (25% -> telegram)
Telegram leads (380)
  ↓ (40% -> покупают)
Workbook purchases ($37) (150 → $5,550)
  ↓ (20% -> консультация)
Consultations booked (30)
  ↓ (60% -> пакет)
Packages ($420-750) (18 → $7,650)
```

**На дашборде видно:**
- ✅ Количество пользователей на каждом этапе
- ✅ Конверсия между этапами (%)
- ✅ Доход по дням, по продуктам
- ✅ Повторные покупатели (LTV)
- ✅ Среднее время между этапами (дни)
- ✅ Сравнение с целями бизнеса

---

## 🛠️ Компоненты

### Вариант A: Supabase Dashboard (быстрый, встроенный)
- ✅ Встроенная визуализация в Supabase UI
- ✅ Не нужно ничего устанавливать
- ✅ Автоматически обновляется в реальном времени
- ❌ Базовые возможности визуализации

### Вариант B: Собственный Flask dashboard (мощный, кастомный)
- ✅ Полный контроль над дизайном
- ✅ Интеграция с mila-office/webapp.py (один UI для всех агентов)
- ✅ Расширенные фильтры (по датам, источникам)
- ❌ Требует Python + HTML/CSS

**РЕКОМЕНДУЕТСЯ:** Вариант A для быстрого старта + Вариант B для длительного использования.

---

## 🚀 ВАРИАНТ A: Supabase Dashboard (быстро за 30 мин)

### Шаг 1: Откройте Supabase Console

1. Перейдите в: https://app.supabase.com/project/twrmpbduxemfgxtadkxa
2. Откройте вкладку **SQL Editor**
3. Создайте новый query

### Шаг 2: Создайте views для дашборда

Скопируйте каждый query из `tools/sales_funnel_queries.sql` и выполните его в Supabase:

```sql
-- 1. Общая воронка
SELECT ... -- (см. sales_funnel_queries.sql, запрос #1)

-- 2. Конверсия по периодам
SELECT ... -- (запрос #2)

-- и т.д.
```

### Шаг 3: Включите визуализацию

1. В каждом query результата нажмите кнопку **Visualize** (область над таблицей)
2. Выберите тип диаграммы:
   - **Запрос #1** (общая воронка) → **Bar chart** или **Funnel**
   - **Запрос #2** (по дням) → **Line chart** (для тренда дохода)
   - **Запрос #3** (по источникам) → **Pie chart**
   - **Запрос #5** (доход по дням) → **Area chart**

### Шаг 4: Создайте Dashboard

1. Нажмите **Dashboards** в левом меню
2. Создайте новый: **+ New Dashboard**
3. Назовите: "Sales Funnel Analytics"
4. Добавьте каждый query как карточку:
   - Нажмите **+ Add card**
   - Выберите сохранённый query
   - Выберите тип визуализации

### 🎯 Результат:
Дашборд доступен по URL:
```
https://app.supabase.com/project/twrmpbduxemfgxtadkxa/sql/dashboards/...
```

**Преимущество:** работает в реальном времени, не нужно ничего устанавливать.

---

## 🚀 ВАРИАНТ B: Собственный Flask Dashboard (мощный, кастомный)

### Компоненты

| Файл | Назначение |
|------|-----------|
| `tools/sales_funnel_queries.sql` | SQL queries для воронки |
| `mila-office/dashboard_funnel.py` | Flask blueprint для дашборда |
| `mila-office/static/css/funnel.css` | Стили для дашборда |
| `mila-office/templates/dashboard_funnel.html` | HTML шаблон |

### Шаг 1: Создайте Python module

```python
# mila-office/dashboard_funnel.py
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import supa

bp = Blueprint('funnel', __name__, url_prefix='/dashboard/funnel')

@bp.route('/')
def index():
    """Главная страница дашборда."""
    # Загружаем данные из Supabase
    funnel = supa.select('purchases', limit=100)
    consultations = supa.select('consultations', limit=100)
    
    return render_template('dashboard_funnel.html', 
                           funnel_data=funnel,
                           consultations=consultations)

@bp.route('/api/funnel')
def api_funnel():
    """API для динамического обновления дашборда."""
    days = request.args.get('days', default=30, type=int)
    # Выполняем SQL queries (можно кешировать результаты)
    return jsonify({...})
```

### Шаг 2: Подключите к основному app

```python
# mila-office/webapp.py
from dashboard_funnel import bp as funnel_bp
app.register_blueprint(funnel_bp)

# Теперь доступно по http://127.0.0.1:5000/dashboard/funnel
```

### Шаг 3: Создайте шаблон

```html
<!-- mila-office/templates/dashboard_funnel.html -->
<div class="funnel-dashboard">
  <h1>Воронка продаж</h1>
  
  <div class="metrics-row">
    <div class="card">
      <h3>Telegram лиды</h3>
      <p class="metric">{{ leads_count }}</p>
    </div>
    <div class="card">
      <h3>Конверсия в покупку</h3>
      <p class="metric">{{ conversion_rate }}%</p>
    </div>
    <div class="card">
      <h3>Доход (месяц)</h3>
      <p class="metric">${{ revenue }}</p>
    </div>
  </div>
  
  <div class="chart-container">
    <canvas id="funnel-chart"></canvas>
  </div>
</div>

<script>
// Используем Chart.js или D3.js для визуализации
</script>
```

---

## 📊 Примеры метрик на дашборде

### 1. Воронка (день за днём)
```
| Date | Reels | Telegram | Purchases | Revenue |
|------|-------|----------|-----------|---------|
| 2026-06-08 | 5,200 | 520 | 45 | $1,665 |
| 2026-06-07 | 4,800 | 480 | 38 | $1,406 |
```

### 2. Конверсия по источникам
```
| Source | Leads | Purchases | Rate |
|--------|-------|-----------|------|
| instagram | 380 | 150 | 39% |
| word_of_mouth | 120 | 60 | 50% |
| telegram | 80 | 32 | 40% |
```

### 3. Расчёт LTV (lifetime value)
```
Повторные покупатели: 18 (12% от всех)
Средний доход на клиента: $47.30
Доход от repeat customers: $8,514
```

---

## ✅ Критерий приёмки

- [ ] **TODO:** Суммирование queries из `sales_funnel_queries.sql`
- [ ] **TODO:** Визуализация воронки (минимум: бар-чарт или таблица)
- [ ] **TODO:** Фильтры по датам и источникам
- [ ] **TODO:** Метрики сравниваются с целями бизнеса ($5,000/мес, 100 лидов)
- [ ] **TODO:** Дашборд доступен команде (Дима, Лера, Марина)
- [ ] **TODO:** Обновляется в реальном времени (или с интервалом)

---

## 🐛 Отладка

| Проблема | Решение |
|---------|---------|
| Query не работает в Supabase | Проверьте синтаксис SQL, названия таблиц (используйте `public.purchases`, не просто `purchases`) |
| Нет данных в дашборде | Убедитесь, что в таблицах есть данные (SELECT COUNT(*) FROM purchases) |
| Медленное обновление | Добавьте индексы: `CREATE INDEX idx_purchases_created ON purchases(created_at)` |
| Graph.js не загружается | Включите CDN в HTML: `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>` |

---

## 🔗 Связанные компоненты

- **P1** (Reels анализ) → данные в `content` таблице для воронки
- **P3** (Брошенные корзины) → видны как `pending` покупки
- **Instagram API** (tools/) → загружает reach/engagement в `content` таблицу

---

## 📈 Развитие дашборда (Phase 2)

После базового дашборда можно добавить:

1. **Прогнозы** (forecast) — машинное обучение для предсказания конверсии
2. **А/B тестирование** — сравнение двух версий контента
3. **Когортный анализ** — какие когорты лучше конвертируют?
4. **Автоматические алерты** — когда конверсия упадёт ниже 30%
5. **Экспорт отчётов** — еженедельный PDF для Людмилы

---

**Контакты:** @developer, Дима (финансы)  
**Обновлено:** 2026-06-08
