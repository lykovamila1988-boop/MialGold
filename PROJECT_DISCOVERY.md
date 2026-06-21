# E:\MILA GOLD — Complete Project Discovery

## 🎯 What This Project Is

**MILA Gold** is a fully-automated AI operations workspace for **Людмила Лыкова** (Liudmyla Lykova), a Canadian-based psychology coach specializing in relationship patterns and choice psychology ("Точки выбора" method).

It's **not** a software product — it's an integrated ops system combining:
- **Social media automation** (Instagram + Threads API)
- **Client management** (CRM, intake forms, session tracking)
- **Content production** (posts, reels, stories, email)
- **8 AI agents** powered by Claude (marketing, editing, CRM, finance, Telegram, trends, scheduling, sales)
- **Analytics & reporting** (engagement, lead tracking, monthly reports)
- **N8N workflow automation** (cross-system orchestration)

---

## 📁 Project Structure

### **MILA-BUSINESS/** — The Core Operations (7.53 MB)
Numbered by workflow stage:

```
01-praktikum/          → PDF workbook ($37 CAD, 36 pages)
                         "Почему я снова выбрала не того"
                         
02-content/            → Weekly content calendar + assets
  ├── content-plan.md    (Monday–Friday schedule, weekly)
  ├── posts/             (static posts with text + image)
  ├── reels/             (video scripts and media)
  └── stories/           (interactive stories, polls)

03-clients/            → CONFIDENTIAL client data
  ├── intake-forms/      (new lead forms)
  ├── session-notes/     (session notes — NEVER publish)
  └── profiles/          (client journey tracking)

04-telegram/           → Telegram channel content
                         (mirrors best Instagram posts; links OK here)

05-analytics/          → Monthly reports
                         (JSON → .docx reports, engagement metrics)
```

**Naming convention:** `2026-06_post_01_тема.txt` or `2026-06_reel_03_название.mp4`

---

### **tools/** — Instagram & Threads API Scripts (0.59 MB)

Pure Python automation without test suite. Install: `pip install requests python-dotenv`

**Key commands:**
```bash
# Instagram analytics
python check_setup.py                          # verify token setup
python get_analytics.py account                # account stats
python get_analytics.py posts                  # top posts by engagement
python get_analytics.py comments               # leads (хочу/цена/заказ)
python get_dms.py [--unread]                   # direct messages

# Publishing
python post_content.py photo --url "..." --caption "..."
python post_content.py reel --url "..." --caption "..."

# Threads (separate API)
python get_threads.py posts|replies|account
python post_threads.py text --text "..."

# Cross-post to Instagram + Threads
python post_content.py photo --url "..." --caption "..." --threads

# Analytics reporting
python make_report.py [<path.json> "Month"]    # .docx from JSON
```

**Architecture:**
- `_common.py` — shared infrastructure (token injection, pagination, error handling)
- Each script imports from `_common` (except `make_report.py`)
- Reports save to `reports/` (project root, not `tools/reports/`)
- **Two Instagram flows** switchable via `IG_API_FLOW`:
  - `instagram_login` → graph.instagram.com (no FB page needed)
  - `facebook` (default) → graph.facebook.com + `IG_USER_ID`

**Known constraints:**
- `get_dms.py` needs `instagram_manage_messages` permission (requires Meta App Review)
- Tokens are long-lived (~60 days); regenerate when auth fails
- Env vars matter: tools read `IG_ACCESS_TOKEN`, `IG_USER_ID`, `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`

---

### **mila-office/** — AI Agent Fleet (3.3 MB)

**8 Claude-powered agents**, all Russian-language:

| Agent | Role | Commands | CLI |
|-------|------|----------|-----|
| **Марина** | Marketing strategist | `/аналитика`, `/комменты`, `/контент`, `/reels` | `agent.py` |
| **Виктория** | Editor & proofreader | `/редактура`, `/проверка`, `/правки` | `victoria.py` |
| **Алина** | Client CRM | `/клиентки`, `/анкета`, `/сессия`, `/профиль` | `alina.py` |
| **Дима** | Finance/Gumroad | `/финансы`, `/продажи`, `/чеки` | `dima.py` |
| **Тёма** | Telegram automation | `/телеграм`, `/рассылка`, `/канал` | `tyoma.py` |
| **Оля** | Trends researcher | `/тренды`, `/анализ`, `/виральное` | `olya.py` |
| **Вася** | Scheduling | `/календарь`, `/публикация`, `/планирование` | `vasya.py` |
| **Лера** | Sales | `/продажи`, `/лиды`, `/воронка` | `lera.py` |

**Run options:**
```bash
# CLI: menu 1–8 or all
cd mila-office && python office.py

# Web UI: browser at http://127.0.0.1:5000
cd mila-office && python webapp.py
```

**Architecture:**
- `base.py` — shared infrastructure (env loading, file tools, chat loop)
- `agent.py` (Марина) — predates `base.py`, has own setup (legacy exception)
- Each agent is ~4-field module: `SYSTEM` (prompt), `TOOLS` (schemas), `handle()`, `QUICK_COMMANDS`
- `agent_manager.py` — registry & metadata loader
- `message_handler.py` — agent-to-agent routing, verdict extraction
- `session_manager.py` — chat history per agent
- Model: hardcoded to `claude-opus-4-6` (note: latest is 4.8)

**Environment:**
- Loads root `.env` first, then layers `tools/.env` on top
- Reads `ANTHROPIC_API_KEY` (required), `TELEGRAM_BOT_TOKEN`, `GUMROAD_ACCESS_TOKEN`
- Instagram vars: same fallback chain as tools (`IG_ACCESS_TOKEN` → `INSTAGRAM_ACCESS_TOKEN`)

---

### **mila-agent/** — Standalone Marketer Agent (0.03 MB)

Single self-contained agent (Марина) before the office was built. Mostly superseded by `mila-office/agent.py` but kept as legacy.

---

### **Other Key Directories**

**reports/** — JSON analytics
- Timestamped: `account_2026-06-08_173201.json`, `posts_*.json`, `comments_*.json`
- Written by `tools/*.py` scripts
- Read by `make_report.py` → .docx exports

**n8n/** — N8N workflow files
- Separate automation layer (not Python)
- Bridges to agents via `n8n_bridge.py` (port 5051) and `n8n_webhook.py` (port 5052)

**docs/** — Project documentation
- `DEEP_CONTENT_SYSTEM.md` — autonomous daily content loops
- `CHAIN_EXAMPLES.md` — agent handoff examples
- `SUPABASE_ACCESS.md` — database access (Supabase for scaling)

**scripts/** — Windows startup helpers
- `start-mila.bat`, `stop-mila.bat`

---

## 🔐 Security & Confidentiality

⚠️ **CRITICAL RULES:**

1. **Session notes** (`03-clients/session-notes/`) are **strictly confidential**
   - Never publish, forward, or paste into external services
   - This applies to anything agents produce here

2. **Secrets management:**
   - Real `.env` files live in `tools/.env` and root `.env` (never committed)
   - Use `tools/.env.example` and `env.template` as references
   - `.env.txt` and `tools/.env.example` contain real-looking `META_APP_ID`/`SECRET` — treat as live
   - **Never echo tokens or paste `.env` into chat**
   - Access tokens: long-lived (~60 days), regenerate when needed

3. **Content voice rules:**
   - Written for female, relationship-focused Russian audience
   - Tone: warm, expert, no pressure
   - Address as informal "ты" (you)
   - Built on "Точки выбора" method: Спасатель (Rescuer) / Угодница (People-pleaser) / Избегание (Avoidant)

---

## 📊 How It Works End-to-End

### **Content Pipeline:**
```
Оля (trends research)
    ↓
Марина (marketing copy)
    ↓
Виктория (editing)
    ↓
Вася (scheduling)
    ↓ [→ N8N for cross-posting]
Instagram + Threads (via tools/)
    ↓
Тёма (Telegram mirror)
```

### **Client Journey:**
```
Instagram DM / Telegram / Web
    ↓
Лера (sales intake)
    ↓
Алина (CRM profiling)
    ↓
Людмила (consultation/session)
    ↓
Алина (session notes → follow-up)
    ↓
Repeat: upsell packs, offer workbook
```

### **Analytics Loop:**
```
tools/get_analytics.py
    ↓
reports/*.json
    ↓
Марина (interprets metrics)
    ↓
Оля (adjusts trends for next week)
    ↓
tools/make_report.py
    ↓
05-analytics/ (.docx report)
```

---

## 🚀 Recent Work (from git log)

**Latest commits show:**
- Deep content system: 2 high-quality posts/day (300 + 800 words)
- Autonomous loops: daily content generation without manual input
- Full pipeline automation: Олы → Марины → Виктории → Васи (+ Риты/дизайнера)
- N8N integration: orchestration between workflows and agents
- Supabase integration: database layer for scaling client tracking
- TELEGRAM_CHANNEL_ID: automated mirroring to Telegram

---

## 🛠️ Tech Stack

| Layer | Tech | Notes |
|-------|------|-------|
| **Content** | Markdown, PDF, Canva | No build step |
| **APIs** | Instagram Graph v21.0, Threads, Telegram | via Python + requests |
| **Agents** | Claude (Opus 4.6), Anthropic Python SDK | Russian prompts |
| **Backend** | Flask, Python 3.10+ | Lightweight, local-first |
| **Web UI** | Flask templates, JS | http://127.0.0.1:5000 |
| **Workflows** | N8N | Separate automation engine |
| **Database** | Supabase (optional scaling) | JSON files for now |
| **CLI** | Rich (Python) | Russian slash-commands |

---

## 📋 Quick Start Checklist

- [ ] **Set up environment:** Copy `.env.example` → `tools/.env`, fill Instagram tokens
- [ ] **Test tools:** `python tools/check_setup.py --write` to verify API access
- [ ] **Run agents:** `python mila-office/office.py` (CLI) or `python mila-office/webapp.py` (web)
- [ ] **Check content plan:** Review `MILA-BUSINESS/02-content/content-plan.md` (weekly schedule)
- [ ] **Start automation:** `python mila-office/autonomous_daily_loop.py` for daily content gen
- [ ] **Monitor:** Check reports in `reports/` and analytics in `05-analytics/`

---

## 🎓 Content Voice Reference

**Three psychological patterns (used in all content):**
- **Спасатель (Rescuer)** — chooses those who need saving, feels needed
- **Угодница (People-pleaser)** — does everything to please, fears saying no
- **Избегание (Avoidant)** — attracted to unavailable, avoids stability

**Content format:**
- **Hook** (first 2 lines) — "Did you notice...?"
- **Body** — personal story, framework, examples
- **CTA** — question or "напиши ХОЧУ" (write WANT)
- **Hashtags** — 6–8 relevant (#психологияотношений, #тревожнаяпривязанность, etc.)

---

## 📚 Key Documentation Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Full project guide (same as above, more detail) |
| `N8N_INTEGRATION.md` | How to trigger agents from N8N workflows |
| `ARCHITECTURE.md` | mila-office module breakdown |
| `mila-office/ALINA_CRM.md` | Client journey & CRM logic |
| `mila-office/CHAIN_DASHBOARD_README.md` | Monitoring multi-agent chains |
| `docs/DEEP_CONTENT_SYSTEM.md` | Autonomous content generation |

---

## 🔗 External Resources

- **Instagram:** @liudmyla.lykova
- **Telegram:** (channel for content mirrors)
- **Gumroad:** (sells praktikum + workbook)
- **N8N docs:** https://docs.n8n.io/
- **Meta Graph API:** https://developers.facebook.com/docs/instagram-api/

---

## 📝 Next Steps

**What you can do:**
1. **Edit content** — modify `02-content/posts/`, `reels/`, `stories/` directly (no build needed)
2. **Analyze metrics** — run `tools/get_analytics.py` to pull engagement data
3. **Manage clients** — review intake forms in `03-clients/`, add session notes
4. **Run agents** — `python office.py` to draft posts, edit, schedule, publish
5. **Automate** — start `autonomous_daily_loop.py` for hands-off daily content
6. **Monitor** — check N8N dashboard or chain monitoring in webapp.py

---

**Date discovered:** 2026-06-17  
**Project maturity:** Production (autonomous loops running daily)  
**Maintenance:** Requires weekly content planning, occasional API token refresh, monthly analytics review
