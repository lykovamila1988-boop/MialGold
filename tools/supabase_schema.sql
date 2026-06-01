-- ============================================================
-- MILA Platform — полная схема для НОВОГО проекта Supabase
-- (twrmpbduxemfgxtadkxa). Перенесена 1:1 со старого проекта.
--
-- КАК ПРИМЕНИТЬ: Supabase → твой проект → SQL Editor → New query →
-- вставь весь этот файл → Run. Создаст все таблицы, связи, индексы,
-- RLS-политики и засеет прайс-лист. Безопасно повторно (IF NOT EXISTS /
-- ON CONFLICT). DDL через REST/anon-ключ невозможен — только здесь.
-- ============================================================

create extension if not exists "uuid-ossp";

-- ── users ───────────────────────────────────────────────
create table if not exists public.users (
  id         uuid primary key default uuid_generate_v4(),
  email      text unique not null,
  name       text,
  phone      text,
  instagram  text,
  telegram   text,
  country    text default 'Unknown',
  language   text default 'ru',
  role       text default 'client' check (role in ('client','admin')),
  notes      text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ── products ────────────────────────────────────────────
create table if not exists public.products (
  id              uuid primary key default uuid_generate_v4(),
  slug            text unique not null,
  name            text not null,
  description     text,
  type            text not null check (type in ('workbook','consultation','package','group','subscription')),
  price_cad       decimal(10,2) not null,
  duration_min    integer,
  sessions_count  integer,
  file_url        text,
  gumroad_id      text,
  stripe_price_id text,
  is_active       boolean default true,
  sort_order      integer default 0,
  created_at      timestamptz default now()
);

-- ─── digital_products (Gamma/Gumroad product pipeline) ───────────
create table if not exists public.digital_products (
  id          uuid primary key default uuid_generate_v4(),
  title       text not null,
  price_cad   decimal(10,2),
  gamma_url   text,
  pdf_url     text,
  gumroad_url text,
  lemon_url   text,
  status      text default 'draft',
  created_at  timestamptz default now()
);

-- ── purchases ───────────────────────────────────────────
create table if not exists public.purchases (
  id             uuid primary key default uuid_generate_v4(),
  user_id        uuid references public.users(id) on delete set null,
  product_id     uuid references public.products(id) on delete set null,
  amount_cad     decimal(10,2) not null,
  currency       text default 'CAD',
  payment_method text default 'gumroad' check (payment_method in ('gumroad','stripe','manual','other')),
  payment_id     text,
  status         text default 'completed' check (status in ('pending','completed','refunded','failed')),
  source         text,
  notes          text,
  created_at     timestamptz default now()
);

-- ── consultations ───────────────────────────────────────
create table if not exists public.consultations (
  id             uuid primary key default uuid_generate_v4(),
  user_id        uuid references public.users(id) on delete set null,
  purchase_id    uuid references public.purchases(id) on delete set null,
  type           text default 'single' check (type in ('diagnostic','single','package_4','package_8','group')),
  status         text default 'scheduled' check (status in ('scheduled','completed','cancelled','no_show')),
  session_number integer default 1,
  scheduled_at   timestamptz,
  completed_at   timestamptz,
  duration_min   integer default 60,
  platform       text default 'zoom',
  meeting_link   text,
  created_at     timestamptz default now()
);

-- ── session_notes (КОНФИДЕНЦИАЛЬНО) ──────────────────────
create table if not exists public.session_notes (
  id              uuid primary key default uuid_generate_v4(),
  consultation_id uuid references public.consultations(id) on delete cascade,
  user_id         uuid references public.users(id) on delete cascade,
  pattern_type    text check (pattern_type in ('savior','pleaser','avoidant','mixed','unknown')),
  notes_before    text,
  notes_after     text,
  insights        text,
  homework        text,
  next_topics     text,
  progress_score  integer check (progress_score between 1 and 10),
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

-- ── content ─────────────────────────────────────────────
create table if not exists public.content (
  id           uuid primary key default uuid_generate_v4(),
  platform     text not null check (platform in ('instagram','telegram','both')),
  content_type text default 'post' check (content_type in ('post','reel','story','carousel','message')),
  status       text default 'draft' check (status in ('draft','scheduled','published','archived')),
  title        text,
  body         text,
  hook         text,
  hashtags     text,
  image_url    text,
  scheduled_at timestamptz,
  published_at timestamptz,
  external_id  text,
  reach        integer default 0,
  impressions  integer default 0,
  likes        integer default 0,
  comments     integer default 0,
  saves        integer default 0,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- ── kpi_snapshots ───────────────────────────────────────
create table if not exists public.kpi_snapshots (
  id                    uuid primary key default uuid_generate_v4(),
  snapshot_date         date unique not null default current_date,
  ig_followers          integer default 0,
  ig_reach_week         integer default 0,
  tg_subscribers        integer default 0,
  monthly_sales         integer default 0,
  monthly_revenue_cad   decimal(10,2) default 0,
  total_revenue_cad     decimal(10,2) default 0,
  monthly_consultations integer default 0,
  created_at            timestamptz default now()
);

-- ── telegram_leads ──────────────────────────────────────
create table if not exists public.telegram_leads (
  id             uuid primary key default uuid_generate_v4(),
  tg_user_id     text unique,
  tg_username    text,
  tg_name        text,
  source         text,
  status         text default 'new' check (status in ('new','warm','hot','converted','inactive')),
  wrote_want     boolean default false,
  user_id        uuid references public.users(id) on delete set null,
  messages_count integer default 0,
  last_message   text,
  last_active    timestamptz,
  created_at     timestamptz default now()
);

-- ── ig_posts (метрики Instagram) ─────────────────────────
create table if not exists public.ig_posts (
  media_id   text primary key,
  post_date  date not null,
  media_type text,
  theme      text,
  reach      integer default 0,
  likes      integer default 0,
  comments   integer default 0,
  caption    text,
  permalink  text,
  created_at timestamptz default now()
);
comment on table public.ig_posts is 'Instagram post metrics for @liudmyla.lykova, fed by tools/upload_to_supabase.py';

-- ── индексы ──────────────────────────────────────────────
create index if not exists idx_purchases_user     on public.purchases(user_id);
create index if not exists idx_purchases_date      on public.purchases(created_at desc);
create index if not exists idx_digital_products_status on public.digital_products(status, created_at desc);
create index if not exists idx_consultations_user  on public.consultations(user_id);
create index if not exists idx_content_platform    on public.content(platform, status);
create index if not exists idx_content_scheduled   on public.content(scheduled_at) where status = 'scheduled';
create index if not exists idx_kpi_date            on public.kpi_snapshots(snapshot_date desc);
create index if not exists idx_tg_status           on public.telegram_leads(status);

-- ── RLS ──────────────────────────────────────────────────
-- Включаем RLS на всех таблицах. Политики — только безопасные SELECT'ы
-- (как в старом проекте). Запись лидов делает СЕРВЕР через service_role
-- (обходит RLS) — НЕ открываем anon-запись на PII.
alter table public.users          enable row level security;
alter table public.products       enable row level security;
alter table public.digital_products enable row level security;
alter table public.purchases      enable row level security;
alter table public.consultations  enable row level security;
alter table public.session_notes  enable row level security;
alter table public.content        enable row level security;
alter table public.kpi_snapshots  enable row level security;
alter table public.telegram_leads enable row level security;
alter table public.ig_posts       enable row level security;

drop policy if exists "Own profile" on public.users;
create policy "Own profile" on public.users for select using (auth.uid() = id);

drop policy if exists "Public products" on public.products;
create policy "Public products" on public.products for select using (is_active = true);

drop policy if exists "Public digital products" on public.digital_products;
create policy "Public digital products" on public.digital_products for select using (status in ('published','active'));

drop policy if exists "Own purchases" on public.purchases;
create policy "Own purchases" on public.purchases for select using (auth.uid() = user_id);

drop policy if exists "Own consultations" on public.consultations;
create policy "Own consultations" on public.consultations for select using (auth.uid() = user_id);

-- ── seed: прайс-лист ─────────────────────────────────────
insert into public.products (slug, name, type, price_cad, duration_min, sessions_count, sort_order, description) values
  ('diagnostic',   'Бесплатная диагностика',                    'consultation', 0,   20,   1,    1, 'Бесплатная 20-минутная диагностика. Разберём твою ситуацию без обязательств.'),
  ('workbook',     'Практикум «Почему я снова выбрала не того»', 'workbook',    37,   null, null, 2, '36 страниц. 4 шага. 5 упражнений. Авторская методология «Точки выбора».'),
  ('consultation', 'Разовая консультация',                      'consultation', 120, 60,   1,    3, 'Индивидуальная 60-минутная сессия. Zoom или Telegram.'),
  ('package_4',    'Пакет 4 сессии',                            'package',     420,  60,   4,    4, 'Пакет из 4 индивидуальных сессий. Экономия $60.'),
  ('package_8',    'Пакет 8 сессий',                            'package',     750,  60,   8,    5, 'Пакет из 8 индивидуальных сессий. Экономия $210.'),
  ('group',        'Групповой разбор',                          'group',        55,  90,   null, 6, 'Групповой разбор на 6-8 человек.')
on conflict (slug) do nothing;

-- ── lead capture: запись лидов через anon-ключ БЕЗ открытия чтения PII ──
-- ВКЛЮЧАЙ ТОЛЬКО ЕСЛИ нет service_role на сервере. Разрешает anon ТОЛЬКО
-- INSERT (не select/update) на users + telegram_leads — публичный ключ не
-- сможет ПРОЧИТАТЬ чужие данные. upsert-слияние при этом не работает (только вставка).
-- Раскомментируй при необходимости:
--   create policy "lead insert users" on public.users          for insert to anon with check (true);
--   create policy "lead insert leads" on public.telegram_leads for insert to anon with check (true);
