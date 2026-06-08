-- ============================================================
-- SALES FUNNEL QUERIES — для дашборда воронки продаж
-- Используются для визуализации: Reels → подписка → Telegram → практикум → пакеты
-- ============================================================

-- 1. ОБЩАЯ ВОРОНКА (aggregated metrics)
-- Показывает, сколько клиентов на каждом этапе
WITH funnel_stages AS (
  SELECT
    'reels' as stage,
    COUNT(DISTINCT id) as users,
    'exposure' as funnel_type
  FROM public.content
  WHERE platform = 'instagram'
    AND content_type = 'reel'
    AND published_at >= NOW() - INTERVAL '30 days'
    AND reach > 0

  UNION ALL
  SELECT
    'telegram_subscribers',
    COUNT(DISTINCT id),
    'engagement'
  FROM public.telegram_leads
  WHERE created_at >= NOW() - INTERVAL '30 days'

  UNION ALL
  SELECT
    'workbook_purchases',
    COUNT(DISTINCT user_id),
    'conversion'
  FROM public.purchases
  WHERE status = 'completed'
    AND amount_cad = 37  -- практикум $37
    AND created_at >= NOW() - INTERVAL '30 days'

  UNION ALL
  SELECT
    'consultations_booked',
    COUNT(DISTINCT user_id),
    'conversion'
  FROM public.consultations
  WHERE status IN ('scheduled', 'completed')
    AND created_at >= NOW() - INTERVAL '30 days'

  UNION ALL
  SELECT
    'packages_purchased',
    COUNT(DISTINCT user_id),
    'high_value'
  FROM public.purchases
  WHERE status = 'completed'
    AND amount_cad >= 420  -- пакеты 4+ сессий
    AND created_at >= NOW() - INTERVAL '30 days'
)
SELECT stage, users, funnel_type FROM funnel_stages;


-- 2. КОНВЕРСИЯ ПО ПЕРИОДАМ (для графика)
-- День за днём: сколько новых клиентов на каждом этапе
SELECT
  DATE_TRUNC('day', p.created_at)::date as date,
  COUNT(DISTINCT p.user_id) as new_purchases,
  SUM(p.amount_cad) as revenue,
  CASE
    WHEN p.amount_cad = 37 THEN 'workbook'
    WHEN p.amount_cad BETWEEN 120 AND 200 THEN 'single_consultation'
    WHEN p.amount_cad >= 420 THEN 'package'
    ELSE 'other'
  END as product_type
FROM public.purchases p
WHERE p.status = 'completed'
  AND p.created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', p.created_at), product_type
ORDER BY date DESC;


-- 3. ВОРОНКА ПО ИСТОЧНИКАМ (откуда приходят клиенты)
SELECT
  COALESCE(tl.source, 'direct') as source,
  COUNT(DISTINCT tl.user_id) as telegram_leads,
  COUNT(DISTINCT CASE WHEN p.status = 'completed' THEN p.user_id END) as converted_to_purchase,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN p.status = 'completed' THEN p.user_id END)
        / NULLIF(COUNT(DISTINCT tl.user_id), 0), 1) as conversion_rate
FROM public.telegram_leads tl
LEFT JOIN public.purchases p ON tl.user_id = p.user_id AND p.created_at >= tl.created_at
WHERE tl.created_at >= NOW() - INTERVAL '30 days'
GROUP BY source
ORDER BY telegram_leads DESC;


-- 4. KPI: СРЕДНЕЕ ВРЕМЯ МЕЖДУ ЭТАПАМИ ВОРОНКИ
-- Сколько дней уходит от лида к первой покупке?
WITH customer_journey AS (
  SELECT
    tl.user_id,
    tl.created_at as lead_date,
    MIN(p.created_at) as first_purchase_date,
    EXTRACT(DAY FROM MIN(p.created_at) - tl.created_at) as days_to_purchase
  FROM public.telegram_leads tl
  LEFT JOIN public.purchases p ON tl.user_id = p.user_id AND p.status = 'completed'
  WHERE tl.created_at >= NOW() - INTERVAL '30 days'
  GROUP BY tl.user_id, tl.created_at
)
SELECT
  ROUND(AVG(days_to_purchase), 1) as avg_days_to_first_purchase,
  MIN(days_to_purchase) as min_days,
  MAX(days_to_purchase) as max_days,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_purchase) as median_days
FROM customer_journey
WHERE days_to_purchase IS NOT NULL;


-- 5. ДОХОД ПО ДНЯМ (для графика тренда)
SELECT
  DATE_TRUNC('day', created_at)::date as date,
  COUNT(*) as transactions,
  SUM(amount_cad) as revenue,
  ROUND(AVG(amount_cad), 2) as avg_order_value
FROM public.purchases
WHERE status = 'completed'
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;


-- 6. REPEAT CUSTOMERS (повторные покупки)
-- Кто купил больше одного продукта?
SELECT
  COUNT(DISTINCT user_id) as repeat_customers,
  AVG(purchase_count) as avg_purchases_per_customer,
  MAX(purchase_count) as max_purchases,
  SUM(total_spent) as total_ltv
FROM (
  SELECT
    user_id,
    COUNT(*) as purchase_count,
    SUM(amount_cad) as total_spent
  FROM public.purchases
  WHERE status = 'completed'
    AND created_at >= NOW() - INTERVAL '90 days'
  GROUP BY user_id
  HAVING COUNT(*) > 1
) repeat_buyers;


-- 7. СТАТУС КОНСУЛЬТАЦИЙ (диагностика → пакет)
-- Сколько клиентов дошли до консультаций?
SELECT
  type,
  status,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY type), 1) as percentage
FROM public.consultations
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY type, status
ORDER BY type, status;


-- 8. СРАВНЕНИЕ С ЦЕЛЯМИ (monthly targets)
-- Прогресс к целям бизнеса
SELECT
  'Revenue' as metric,
  SUM(amount_cad) as actual,
  5000 as target,  -- $5,000 CAD в месяц
  ROUND(100.0 * SUM(amount_cad) / 5000, 1) as progress_pct
FROM public.purchases
WHERE status = 'completed'
  AND created_at >= DATE_TRUNC('month', NOW())

UNION ALL

SELECT
  'New Telegram Leads',
  COUNT(DISTINCT id),
  100,  -- target: 100 лидов в месяц
  ROUND(100.0 * COUNT(DISTINCT id) / 100, 1)
FROM public.telegram_leads
WHERE created_at >= DATE_TRUNC('month', NOW())

UNION ALL

SELECT
  'Consultations',
  COUNT(DISTINCT id),
  10,  -- target: 10 консультаций
  ROUND(100.0 * COUNT(DISTINCT id) / 10, 1)
FROM public.consultations
WHERE created_at >= DATE_TRUNC('month', NOW())
  AND status IN ('completed', 'scheduled');
