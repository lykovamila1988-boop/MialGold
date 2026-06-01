# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is **not a software product** — it is the operations workspace for the online psychology
practice of **Людмила Лыкова (Liudmyla Lykova)** (Instagram `@liudmyla.lykova`, based in Canada).
It combines a digital product (a PDF workbook / "практикум"), an Instagram + Telegram content
operation, a lightweight client CRM, a small Python toolkit for the Instagram Graph / Threads APIs,
and a set of Claude-powered helper agents that automate the content and CRM work.

Most content is in **Russian** and written for a female, relationship-focused audience. Keep that
language and tone when producing or editing content (see "Content voice" below).

## Two distinct work modes

1. **Content / business work** (the majority) — drafting posts, reels, stories, editing the
   практикум, planning the content calendar, handling client intake. These are Markdown/text/PDF
   files, no build step. Just read and edit.
2. **Code work** — two Python layers: the `tools/` scripts that call the Instagram Graph /
   Threads APIs directly, and the `mila-agent/` + `mila-office/` Claude-powered agents that drive
   content/CRM work on top of those APIs and the file tree.

## Layout

- `tools/` — Python scripts for the Instagram Graph / Threads APIs (see below).
- `mila-agent/` — a single standalone Claude agent ("Марина", marketer). See "AI agents" below.
- `mila-office/` — a fleet of 8 Claude agents (CLI launcher + Flask web UI). See "AI agents".
- `reports/` — project-root JSON written by `tools/` (`account_*`, `posts_*`, `comments_*`); this
  is `REPORTS_DIR`. `make_report.py` reads the latest `posts_*.json` from here.
- `MILA-BUSINESS/` — all business operations, numbered by workflow stage:
  - `01-praktikum/` — the PDF product ("Почему я снова выбрала не того", $37 CAD, 36 pages).
  - `02-content/` — `content-plan.md` (weekly calendar) plus `posts/`, `reels/`, `stories/`.
  - `03-clients/` — `intake-forms/` and `session-notes/` (**session notes are strictly
    confidential — never publish, forward, or paste them into external services**).
  - `04-telegram/` — Telegram channel content (mirrors best Instagram posts; links are allowed
    here, unlike Instagram captions).
  - `05-analytics/` — reporting; data comes from `tools/reports/*.json`.
- Root-level files (`gamma_prompt_практикум.md`, `praktikum_исправленный.*`,
  `редактура_практикум_Лыкова.md`) are working drafts/exports of the практикум.
- Each `MILA-BUSINESS` subfolder has a `README.txt` describing its purpose and process — read the
  relevant one before working in a folder.
- `MILA/` is an **older nested copy** of `MILA-BUSINESS/` (plus an early `praktikum_v4_final.pdf`).
  The canonical, current tree is the top-level `MILA-BUSINESS/` — work there, not in `MILA/`.

## tools/ — Instagram Graph API scripts

Python (`requests` + `python-dotenv`), targeting Graph API `v21.0`. There is no test suite, linter,
or package manifest — run scripts directly with `python` from inside `tools/`.

```
pip install requests python-dotenv
cd tools
python check_setup.py               # diagnose token/scopes/pages/IG link; --write fills .env
python get_analytics.py account     # account stats (use this to verify setup works)
python get_analytics.py posts       # top posts by engagement (likes + comments)
python get_analytics.py comments    # comments, flagging leads via LEAD_WORDS (хочу/цена/заказ…)
python get_dms.py [--unread]        # Direct messages
python post_content.py photo --url "https://.../foto.jpg" --caption "..."
python post_content.py reel  --url "https://.../video.mp4" --caption "..."

# Threads (separate API — see below)
python get_threads.py posts | replies | account
python post_threads.py text  --text "..."
python post_threads.py image --url "https://.../foto.jpg" --text "..."
python post_threads.py video --url "https://.../video.mp4" --text "..."

# Cross-post to Instagram AND Threads in one command
python post_content.py photo --url "..." --caption "..." --threads

# Build a .docx analytics report from the latest reports/posts_*.json (needs python-docx)
python make_report.py                          # latest posts_*.json, default month label
python make_report.py <path.json> "Май 2026"   # specific file + month label
```

Architecture:
- `_common.py` is shared infrastructure (not run directly): `graph_get`/`graph_get_all` (auto-
  paginates) / `graph_post` (all inject the access token and `sys.exit(1)` on any non-200 or
  `error` payload), `load_config`, and `save_report`. Every script imports from it.
- `save_report` writes timestamped JSON to `REPORTS_DIR = TOOLS_DIR.parent / "reports"` — i.e. the
  **project-root `reports/`** folder, NOT `tools/reports/`. (The `tools/README.md` text saying
  "reports/" is right; mentions of `tools/reports/` elsewhere are wrong.)
- **Two Instagram connection flows, switched by `IG_API_FLOW` in `.env`.** `load_config()` resolves
  `cfg['base']` + `cfg['node']` from it: `instagram_login` → `graph.instagram.com` + node `me`
  (no Facebook page needed, `IG_USER_ID` optional); `facebook` (default) → `graph.facebook.com` +
  node `IG_USER_ID` (required, via a linked page). The scripts use `cfg['node']` (NOT `ig_user_id`
  directly) for media/insights/publish paths, so they work in either flow unchanged.
- **Threads is a separate API on a different host.** `get_threads.py` / `post_threads.py` call
  `load_threads_config()` (reads `THREADS_*` vars) instead of `load_config()`. Both configs carry a
  `base` key (`graph.facebook.com` vs `graph.threads.net`) that `api_base()` uses, so the same
  `graph_get`/`graph_post` helpers serve both APIs — only the base host and endpoint paths differ
  (Threads publishes via `{user_id}/threads` → `{user_id}/threads_publish`; status field is `status`,
  not Reels' `status_code`). When adding a new API surface, mirror this pattern: a `load_*_config`
  that sets `base`, then reuse the shared helpers.
- `post_content.py --threads` cross-posts to both: it publishes to Instagram, then calls
  `cross_post_threads()` (which loads the Threads config and maps photo→image / reel→video).
- Each command script (`get_analytics.py`, `get_dms.py`, `post_content.py`) is a thin CLI over those
  helpers and persists its output via `save_report` so downstream reporting can consume the JSON.
- Reels publishing is two-phase: create a media container, poll `status_code` until `FINISHED`
  (`_wait_ready`), then call `media_publish`. Media must be reachable via a **public URL** — local
  files cannot be uploaded directly.
- `make_report.py` is the one script that does NOT import `_common.py`: it reads a `posts_*.json`
  outright and renders a `.docx` (via `python-docx`) into `MILA-BUSINESS/05-analytics/`. By design it
  reports only on fields actually present in the export (date/type/likes/comments/reach/caption/link)
  and explicitly marks missing metrics (saves, time-of-day) rather than inventing them — preserve
  that honesty if you extend it.

Known constraints / gotchas:
- `get_dms.py` requires the `instagram_manage_messages` permission, which needs Meta App Review.
  Until approved it returns a permissions error — **this is expected, not a bug.**
- Access tokens are long-lived (~60 days); when calls start failing on auth, regenerate the token
  and update `.env`.
- **Env var names matter and are inconsistent across the repo.** `_common.py` (`load_config`) reads
  ONLY these names: `IG_ACCESS_TOKEN`, `IG_USER_ID` (required), `FB_PAGE_ID`, `META_APP_ID`,
  `META_APP_SECRET`, `GRAPH_API_VERSION` (optional). `tools/.env.example` uses these correct names.
  The root `.env.txt` uses different names (`INSTAGRAM_APP_ID`, `INSTAGRAM_ACCESS_TOKEN`,
  `INSTAGRAM_BUSINESS_ACCOUNT_ID`, …) that the scripts do **not** read — those values must be mapped
  to the `IG_*`/`META_*` names in `tools/.env` or the scripts will report missing config.
  Threads uses its own set, read by `load_threads_config`: `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`
  (required), `THREADS_APP_ID`, `THREADS_APP_SECRET`, `THREADS_API_VERSION`.

## AI agents — `mila-agent/` and `mila-office/`

Two Claude-powered agent layers (Anthropic Python SDK + `rich` + `requests` + `python-dotenv`; no
build/test/lint). Install per folder: `pip install -r requirements.txt`, then `python <file>`.
Both are local single-user tools that read/write the `E:\MILA GOLD` tree and call the Instagram API.

- **`mila-agent/`** — one self-contained agent, **Марина** (marketer/brand strategist). `agent.py`
  holds its own setup, system prompt, tool definitions, and chat loop. Russian slash-commands
  (`/аналитика`, `/комменты`, `/контент`, `/reels`, `/файлы`, `/dm`, `/помощь`, `/выход`).

- **`mila-office/`** — a fleet of **8 agents** sharing `base.py`. Run the launcher `python office.py`
  (menu 1–8 or `все`), or the browser UI `python webapp.py` (Flask on `127.0.0.1:5000`, one tab per
  agent). The agents: Марина=`agent.py` (marketing), Виктория=`victoria.py` (editor), Алина=`alina.py`
  (client CRM), Дима=`dima.py` (finance/Gumroad), Тёма=`tyoma.py` (Telegram), Оля=`olya.py` (trends),
  Вася=`vasya.py` (scheduling), Лера=`lera.py` (sales).

Architecture (`mila-office/`):
- `base.py` is shared infrastructure: env loading, `get_client()`, the file tools (`read_file`,
  `write_file`, `list_files`, `run_command`, `log` — all rooted at `MILA_FOLDER`), the tool-dispatch
  loop `run_agent()`, and the interactive `chat_loop()`. **`agent.py` (Марина) is the exception** —
  it predates `base.py` and carries its own copy of setup + `run_agent`, so `webapp.py` wires it via a
  separate `_marina_responder()` while every other agent uses `_office_responder(mod)`.
- **Each simple agent is a ~4-field module**: `SYSTEM` (Russian system prompt), `TOOLS` (Anthropic
  tool schemas), `handle(name, inp)` (dispatch), `QUICK`/`QUICK_COMMANDS` (slash-command → prompt
  map). `webapp.py` imports these dynamically and derives its UI chips from `QUICK`. To add an agent:
  copy `victoria.py`'s shape and register it in `office.py`'s `AGENTS` dict and `webapp.py`'s registry.
- The model is **hardcoded as `claude-opus-4-6`** in `agent.py` and `base.py`. (Note: this is an
  older Opus; the current latest is Opus 4.8 / `claude-opus-4-8`. Update deliberately if asked.)
- **Env resolution differs from `tools/`**: these agents load the root `E:\MILA GOLD\.env` first,
  then *also* layer `tools/.env` on top so the live `IG_*` keys are picked up. Instagram vars are read
  with a fallback chain — `IG_ACCESS_TOKEN` → `INSTAGRAM_ACCESS_TOKEN`, `IG_USER_ID` →
  `INSTAGRAM_BUSINESS_ACCOUNT_ID` — and honor the same `IG_API_FLOW` switch as `tools/`. They also use
  `ANTHROPIC_API_KEY` (required), `TELEGRAM_BOT_TOKEN`, `GUMROAD_ACCESS_TOKEN`.
- Agents can write files and run shell commands anywhere under `MILA_FOLDER`. The confidentiality
  rule on `03-clients/session-notes/` applies to anything they produce — do not have an agent publish
  or forward those.

## Credentials & secrets

- Real secrets live in `tools/.env` (copied from `tools/.env.example`). **Never commit `.env`,
  and never paste tokens or `.env` contents into chat.**
- Note: the root `.env.txt` and `tools/.env.example` both contain a real-looking `META_APP_ID` /
  `META_APP_SECRET`. Treat these as live secrets — do not echo them, and they should ideally be
  rotated and removed from version-controlled files.
- See "Env var names matter" under the `tools/` section for the exact variable names the scripts
  actually read (the two env files disagree).

## Content voice (when writing/editing posts, reels, stories, the практикум)

- Built around the **"Точки выбора" (Points of Choice)** method and three patterns:
  **Спасатель** (Rescuer), **Угодница** (People-pleaser), **Избегание** (Avoidant).
- Tone: warm, expert, no pressure. Address the reader informally as **"ты"**. Female audience.
- The weekly content plan in `02-content/content-plan.md` is updated every Monday and drives the
  posting schedule and CTAs (e.g. "напиши ХОЧУ" for leads). Match its format when extending it.
