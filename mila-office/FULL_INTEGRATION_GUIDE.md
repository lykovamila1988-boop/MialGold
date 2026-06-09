# FULL INTEGRATION GUIDE — MILA OFFICE 11-Agent System

Complete documentation covering architecture, context flow, dashboard usage, error handling, n8n integration, testing strategies, troubleshooting, and performance optimization.

**Version**: 3.0 (Updated 2026-06-08)  
**Status**: Production-ready  
**Target Audience**: Developers, n8n workflow engineers, DevOps maintainers

---

## TABLE OF CONTENTS

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Context Flow Through Agents](#2-context-flow-through-agents)
3. [Dashboard Usage Guide](#3-dashboard-usage-guide)
4. [Retry & Error Handling](#4-retry--error-handling)
5. [n8n Integration Examples](#5-n8n-integration-examples)
6. [Testing Strategies](#6-testing-strategies)
7. [Troubleshooting](#7-troubleshooting)
8. [Performance Tuning](#8-performance-tuning)
9. [Best Practices for Chain Design](#9-best-practices-for-chain-design)

---

## 1. SYSTEM ARCHITECTURE OVERVIEW

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SYSTEMS                           │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  n8n Flows   │  Instagram   │  Gumroad    │  Telegram Bot     │
│  (webhooks)  │  Graph API   │  (sales)    │  (notifications)  │
└──────────────┴──────────────┴──────────────┴────────────────────┘
                              ▲
                              │ (HTTP requests)
                              │
┌──────────────────────────────────────────────────────────────────┐
│                  MILA OFFICE (Flask + Python)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  WEBAPP (port 5000)  — Flask web UI (browser)           │  │
│  │  • 11 agent tabs with chat history                      │  │
│  │  • Chain dashboard (monitor real-time chains)           │  │
│  │  • File upload / document management                    │  │
│  │  • Session management (security tokens)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  N8N_WEBHOOK (port 5052)  — n8n → agents bridge         │  │
│  │  • POST /api/n8n/trigger-chain — start a chain          │  │
│  │  • Status callbacks back to n8n webhook                 │  │
│  │  • Chain execution monitoring                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SHARED INFRASTRUCTURE                                   │  │
│  │  ┌─ base.py (core utilities)                            │  │
│  │  │  • get_client() — Anthropic/Gemini LLM client       │  │
│  │  │  • run_agent() — agent loop with tool use           │  │
│  │  │  • compose_system() — system prompt + context       │  │
│  │  │  • read_file/write_file/list_files (sandboxed)     │  │
│  │  │  • run_command() (python tools/ only)               │  │
│  │  │  • create_gamma_document() (AI-generated PDFs)      │  │
│  │  └─ memory.py (inter-process shared state)             │  │
│  │     • context.json (latest event from n8n)              │  │
│  │     • profile.json (office profile + phase)             │  │
│  │     • events.jsonl (audit log of all interactions)     │  │
│  │     • File-based locking for safe concurrent access    │  │
│  │  └─ system_prompt_builder.py (context injection)       │  │
│  │     • extract_context_from_message()                    │  │
│  │     • build_system_prompt() with agent-to-agent info   │  │
│  │  └─ error_monitor.py (centralized error logging)       │  │
│  │     • Telegram alerts for critical failures             │  │
│  │     • Structured error logs (errors.jsonl)              │  │
│  │  └─ chain_dashboard.py (Flask blueprint)                │  │
│  │     • /chains/api/active — active chains               │  │
│  │     • /chains/api/history — completed chains           │  │
│  │     • /chains/api/details/<id> — full chain logs       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AGENT MODULES (11 agents)                               │  │
│  │  ┌─ Марина (MARINA/agent.py) — marketer                │  │
│  │  │  • Content planning, post writing                   │  │
│  │  │  • Instagram API calls (get_analytics, post)        │  │
│  │  │  • Cross-posting to Threads                         │  │
│  │  ├─ Виктория (VICTORIA) — editor/proof-reader          │  │
│  │  │  • Quality control, spell-check                     │  │
│  │  │  • Voice consistency & brand guidelines              │  │
│  │  ├─ Рита (RITA) — content analyst                      │  │
│  │  │  • Audience analysis from reports                    │  │
│  │  │  • Content performance evaluation                    │  │
│  │  ├─ Алина (ALINA) — CRM / client intake                 │  │
│  │  │  • Client forms, intake notes                        │  │
│  │  │  • Session notes management (confidential)          │  │
│  │  ├─ Лера (LERA) — sales / presentation                 │  │
│  │  │  • Sales funnel, product positioning                │  │
│  │  │  • Client conversation prep                         │  │
│  │  ├─ Дима (DIMA) — financials / Gumroad                 │  │
│  │  │  • Product catalog, sales metrics                    │  │
│  │  │  • Revenue tracking & funnel analysis               │  │
│  │  ├─ Тёма (TYOMA) — Telegram operations                 │  │
│  │  │  • Telegram channel content (mirrors Instagram)     │  │
│  │  │  • Bot automation                                   │  │
│  │  ├─ Оля (OLYA) — trends & research                     │  │
│  │  │  • Weekly trend analysis                            │  │
│  │  │  • Content calendar planning                        │  │
│  │  ├─ Вася (VASYA) — scheduling & publishing             │  │
│  │  │  • Post scheduling, publishing workflows            │  │
│  │  │  • Cross-platform coordination                      │  │
│  │  ├─ Стас (MANAGER/manager.py) — analytics/chief         │  │
│  │  │  • System metrics & performance review              │  │
│  │  │  • Agent improvement suggestions (prompt_overrides) │  │
│  │  │  • Phase transitions (cold_start → learning → ....) │  │
│  │  ├─ Кирилл (PRODUCER/producer.py) — orchestrator        │  │
│  │  │  • High-level workflow direction                    │  │
│  │  │  • Inter-agent handoffs                             │  │
│  │  └─ Лев (LERA_SALES variant) — specialized sales       │  │
│  │                                                           │  │
│  │  Common to all agents:                                  │  │
│  │  • SYSTEM (Russian prompt)                             │  │
│  │  • TOOLS (Anthropic JSON schema)                       │  │
│  │  • handle(name, inp) — tool dispatch                   │  │
│  │  • QUICK_COMMANDS {cmd → prompt map}                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ORCHESTRATION & FLOW CONTROL                            │  │
│  │  ┌─ pipeline.py (non-interactive chain runner)          │  │
│  │  │  • python pipeline.py <chain_name> [--notify]       │  │
│  │  │  • Chains: new_client, content_week, etc.           │  │
│  │  │  • State checkpointing (resume on failure)          │  │
│  │  │  • Chain completion webhook to n8n                   │  │
│  │  ├─ chain_retry.py (failure recovery)                  │  │
│  │  │  • retry_chain(chain_id, failed_agent, reason)      │  │
│  │  │  • escalate_chain(chain_id, new_agent)              │  │
│  │  │  • split_chain(chain_id, [agents]) — parallel       │  │
│  │  │  • merge_results(chain_id, results)                 │  │
│  │  └─ chain_dashboard.py (browser-based monitoring)      │  │
│  │     • Real-time chain status                           │  │
│  │     • Performance timeline                             │  │
│  │     • Error drill-down                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AUXILIARY SYSTEMS                                       │  │
│  │  ├─ policies.py — agent capability restrictions         │  │
│  │  ├─ data_sanitizer.py — remove PII from logs           │  │
│  │  ├─ document_manager.py — file upload/download         │  │
│  │  ├─ upload_handler.py — multipart file handling        │  │
│  │  └─ session_manager.py — browser session security      │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │ (File I/O, subprocess)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LOCAL FILE SYSTEM (E:\MILA GOLD)                  │
├─────────────────────────────────────────────────────────────────┤
│  MILA-BUSINESS/                                                 │
│  ├─ 01-praktikum/     (PDF workbook files)                     │
│  ├─ 02-content/       (posts, reels, stories, content plan)    │
│  ├─ 03-clients/       (intake forms, session notes — SECRET)  │
│  ├─ 04-telegram/      (Telegram channel content)               │
│  └─ 05-analytics/     (analytics + prompt_overrides/)          │
│     └─ prompt_overrides/   (agent improvement instructions)    │
│  tools/                                                         │
│  ├─ _common.py        (shared Instagram/Threads API layer)    │
│  ├─ get_analytics.py  (fetch Instagram reports)               │
│  ├─ get_dms.py        (fetch direct messages)                 │
│  ├─ post_content.py   (publish Instagram/Threads)             │
│  └─ make_report.py    (generate Word reports from JSON)       │
│  mila-office/                                                   │
│  ├─ memory/           (shared JSON state, JSONL audit)         │
│  ├─ logs/             (errors.jsonl, chain_*.log, etc)         │
│  ├─ products/         (generated Gamma PDFs)                   │
│  └─ tests/            (pytest suite)                           │
│  reports/             (Instagram analytics JSON snapshots)     │
│  products/            (client workbooks, generated docs)       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | Purpose | Runs As | Critical |
|-----------|---------|---------|----------|
| `base.py` | Core agent infra (LLM, tools, system prompt) | shared lib | YES |
| `memory.py` | Inter-process shared state (n8n ↔ agents) | shared lib | YES |
| `webapp.py` | Browser UI + chat + dashboard | Flask app (5000) | YES |
| `n8n_webhook.py` | n8n ↔ agents bridge | Flask app (5052) | YES |
| `pipeline.py` | Non-interactive chain runner | CLI script | NO (batch only) |
| `chain_retry.py` | Failure recovery & escalation | shared lib | NO (optional) |
| `error_monitor.py` | Centralized error logging + Telegram alerts | shared lib | NO |
| Agent modules | Individual agent logic (marina, victoria, etc) | imported in webapp/pipeline | YES |

### 1.3 Data Flow Diagram

```
USER / n8n WORKFLOW
  │
  ├─→ [webapp.py] → Browser UI (chat, chain dashboard)
  │
  ├─→ [n8n_webhook.py] → POST /api/n8n/trigger-chain
  │                         │
  │                         ├→ [memory.py] write_context()
  │                         │
  │                         ├→ [pipeline.py] spawn subprocess
  │                         │    │
  │                         │    └→ Run chain: agent1 → agent2 → ...
  │                         │
  │                         └→ Call n8n status webhook (when done)
  │
  └─→ [office.py] (CLI menu) → Run agent interactively
       │
       └→ chat_loop(agent_key) → Read history from memory
           │
           ├→ [system_prompt_builder] build system prompt + context
           │
           ├→ [base.run_agent] (LLM call + tool loop)
           │   │
           │   ├→ [get_client] → Anthropic or Gemini
           │   │
           │   ├→ Agent.handle() → dispatch tool calls
           │   │    │
           │   │    ├→ [base.read_file / write_file]
           │   │    ├→ [shared_tools] (Gumroad, Telegram, etc)
           │   │    ├→ [graph_api] (Instagram)
           │   │    └→ [policies] (check capabilities)
           │   │
           │   └→ Tool result → append to messages
           │
           └→ [memory.py] log_event() → record in events.jsonl

MONITORING:
  User / n8n → [webapp.py] /chains/* routes
              → [chain_dashboard.py] read memory/events.jsonl
              → Display real-time chain progress + metrics
```

### 1.4 File Layout

```
E:\MILA GOLD\
├─ .env                          (secrets: IG token, Anthropic key, etc)
├─ .env.txt                      (legacy variable names, reference only)
├─ tools/
│  ├─ .env                       (IG_* / THREADS_* tokens)
│  ├─ .env.example               (template)
│  ├─ _common.py                 (graph_api.GraphError, graph_get/post helpers)
│  ├─ get_analytics.py           (python get_analytics.py account|posts|comments)
│  ├─ get_dms.py                 (python get_dms.py [--unread])
│  ├─ post_content.py            (python post_content.py photo|reel --url … --caption …)
│  ├─ get_threads.py
│  ├─ post_threads.py
│  └─ make_report.py             (python make_report.py [file.json] [month_label])
├─ mila-office/
│  ├─ base.py                    (core: get_client, run_agent, compose_system)
│  ├─ memory.py                  (shared state: context, profile, events)
│  ├─ system_prompt_builder.py   (context injection into prompts)
│  ├─ error_monitor.py           (centralized error logging + Telegram alerts)
│  ├─ data_sanitizer.py          (remove PII from logs)
│  ├─ policies.py                (agent capability restrictions)
│  ├─ agent.py                   (МАРИНА — old standalone agent, kept for compat)
│  ├─ victoria.py                (ВИКТОРИЯ — editor)
│  ├─ rita.py                    (РИТА — content analyst)
│  ├─ alina.py                   (АЛИНА — CRM)
│  ├─ lera.py                    (ЛЕРА — sales)
│  ├─ dima.py                    (ДИМА — financials)
│  ├─ tyoma.py                   (ТЁМА — Telegram)
│  ├─ olya.py                    (ОЛЯ — trends)
│  ├─ vasya.py                   (ВАСЯ — scheduling)
│  ├─ manager.py                 (СТАС — analytics/chief)
│  ├─ producer.py                (КИРИЛЛ — orchestrator)
│  ├─ webapp.py                  (Flask UI + agent chat, port 5000)
│  ├─ webapp_utils.py            (helpers for webapp)
│  ├─ agent_manager.py           (dynamic agent loading)
│  ├─ message_handler.py         (inter-agent message routing)
│  ├─ session_manager.py         (browser session tokens)
│  ├─ document_manager.py        (file upload/download)
│  ├─ upload_handler.py          (multipart file handling)
│  ├─ office.py                  (CLI menu launcher)
│  ├─ pipeline.py                (non-interactive chain runner)
│  ├─ chain_retry.py             (failure recovery + escalation)
│  ├─ chain_retry_integration.py (retry integration with pipeline)
│  ├─ chain_dashboard.py         (Flask blueprint for /chains/*)
│  ├─ n8n_webhook.py             (n8n ↔ agents bridge, port 5052)
│  ├─ n8n_bridge.py              (legacy n8n integration layer)
│  ├─ n8n_context.py             (context helpers for n8n)
│  ├─ shared_tools.py            (common tools: Gumroad, Telegram, etc)
│  ├─ job_queue.py               (background task queue)
│  ├─ memory/
│  │  ├─ context.json            (latest event from n8n/user)
│  │  ├─ profile.json            (office profile: brand, audience, phase)
│  │  ├─ agent_notes.json        (agent→agent message queue)
│  │  ├─ published.json          (posts published, for 48h metrics)
│  │  ├─ events.jsonl            (append-only audit log)
│  │  ├─ task_queue.json         (pending tasks)
│  │  ├─ agent_histories.json    (chat history by agent)
│  │  └─ ... (other JSON state)
│  ├─ logs/
│  │  ├─ webapp.log              (Flask app logs)
│  │  ├─ errors.jsonl            (structured error logs)
│  │  ├─ error_monitor.log       (error monitor logs)
│  │  ├─ chain_*.log             (per-chain detailed logs)
│  │  ├─ chain_events.jsonl      (chain execution events)
│  │  ├─ chain_retry.log         (retry decisions)
│  │  └─ n8n/
│  │     ├─ n8n_webhook.log      (n8n webhook server)
│  │     └─ chain_*.log          (per n8n-triggered chain)
│  ├─ products/                  (generated Gamma PDFs)
│  ├─ tests/
│  │  ├─ test_*.py               (pytest suite)
│  │  └─ conftest.py             (pytest fixtures)
│  ├─ comprehensive_test_suite.py (full 11-agent integration tests)
│  ├─ FULL_INTEGRATION_GUIDE.md   (this file)
│  ├─ N8N_INSTAGRAM_REPORTS.md    (n8n workflow for analytics)
│  └─ requirements.txt            (pip dependencies)
├─ MILA-BUSINESS/
│  ├─ 01-praktikum/              (PDF workbook + source files)
│  ├─ 02-content/
│  │  ├─ content-plan.md         (weekly calendar)
│  │  ├─ posts/                  (Instagram posts drafts)
│  │  ├─ reels/                  (Reel scripts)
│  │  └─ stories/                (Story scripts)
│  ├─ 03-clients/
│  │  ├─ intake-forms/           (client intake forms)
│  │  └─ session-notes/          (CONFIDENTIAL — never share)
│  ├─ 04-telegram/               (Telegram channel content)
│  └─ 05-analytics/
│     ├─ *.md                    (analytics reports)
│     └─ prompt_overrides/
│        ├─ marina.md            (Марина improvements)
│        ├─ victoria.md          (Виктория improvements)
│        ├─ _brand_voice.md      (common voice guide)
│        └─ ...
├─ reports/                      (Instagram analytics JSON snapshots)
│  ├─ posts_YYYY-MM-DD_HHMMSS.json
│  ├─ account_*.json
│  ├─ comments_*.json
│  └─ n8n_logs/                  (n8n webhook server logs)
└─ products/                     (client workbooks, generated PDFs)
```

---

## 2. CONTEXT FLOW THROUGH AGENTS

### 2.1 What is Context?

**Context** is metadata about a request that flows through agent chains to help each agent understand:
- **Who sent this request** (from_agent or user)
- **Where it's going next** (to_agent or next chain step)
- **Which chain it's part of** (chain_id for audit/retry)
- **Previous steps in the chain** (position, chain history)

Example context object:
```json
{
  "from_agent": "marina",
  "to_agent": "victoria",
  "chain_id": "content_week_2026_06_08_001",
  "position": 0
}
```

### 2.2 Context Extraction & Injection

**Step 1: Extraction** (in webapp or pipeline):
```python
# From message tags
import system_prompt_builder
context = system_prompt_builder.extract_context_from_message(user_message)
# Finds [from:marina] [to:victoria] [chain_id:...] tags

# Or from memory (n8n trigger)
import memory
ctx = memory.read_context()
# Returns current event context
```

**Step 2: System Prompt Injection** (in base.py):
```python
from base import compose_system

# compose_system adds context to system prompt automatically
enhanced_system = compose_system(
    agent_key="victoria",
    system=VICTORIA_BASE_SYSTEM,
    context={
        "from_agent": "marina",
        "to_agent": None,
        "chain_id": "content_week_2026_06_08_001"
    }
)
# Result: VICTORIA_BASE_SYSTEM + context section + phase info + overrides
```

**Step 3: Agent Awareness** (in agent's system prompt):
Victoria (or any agent) receives in system prompt:
```
=== КОНТЕКСТ ЗАПРОСА ===
✓ Ты получила запрос от: marina
✓ ID цепочки обработки: content_week_2026_06_08_001
✓ Твоя позиция в цепочке: #2
✓ Следующий агент: vasya
✓ ТЫ ПОСЛЕДНЯЯ В ЦЕПОЧКЕ — это финальный результат

=== КАК ДЕЙСТВОВАТЬ ===
Запрос пришел от marina. Это может быть результат их работы, требующий твоей обработки.
После твоей работы результат пойдет vasya — подготавливай под его требования.
Все сообщения связаны ID 'content_week_2026_06_08_001' — это помогает отслеживать работу.
```

### 2.3 Real-World Example: Content Week Chain

```
USER → n8n workflow "Weekly Content"
       └→ POST http://localhost:5052/api/n8n/trigger-chain
          {
            "chain_config": {
              "agents": ["olya", "marina", "victoria", "vasya"],
              "trigger": "monday_09:00"
            },
            "from_agent": "n8n",
            "to_agent": null,
            "chain_id": "content_week_2026_06_08_001"
          }

Step 1: OLYA (Trends Research)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: (none, automatic trigger)
  Context: from_agent="n8n", position=0, next="marina"
  System Prompt: 
    + Base OLYA system
    + "Ты первая в цепочке (position #1), результат пойдет marina"
    + Phase info: "Данных достаточно — опирайся на реальные метрики"
    + Brand voice
  Tools: read_file, write_file, list_files
  Output: Weekly trends analysis → saved to 02-content/trends_week.md
  Verdict: [VERDICT: ready_next] [→ marina]

Step 2: MARINA (Content Writer)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Read trends_week.md + user request "напиши 5 постов на тему..."
  Context: from_agent="olya", position=1, next="victoria"
  System Prompt:
    + Base MARINA system
    + "Ты получила результат от olya (trends), твоя задача написать контент"
    + "После тебя victoria будет редактировать"
    + Phase info: "Анализируй как обычно, но выводы помечай как предварительные"
    + Brand voice (special for MARINA)
    + Prompt overrides from prompt_overrides/marina.md
  Tools: read_file, write_file, run_command (python tools/post_content.py), list_files
  Output: 5 draft posts → saved to 02-content/posts/week_2026_06_08.md
  Verdict: [VERDICT: ready_next]

Step 3: VICTORIA (Editor)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Read week_2026_06_08.md (Marina's drafts)
  Context: from_agent="marina", position=2, next="vasya"
  System Prompt:
    + Base VICTORIA system
    + "Ты получила черновики от marina, твоя задача — отредактировать"
    + "После тебя vasya будет планировать публикации"
    + Brand voice (special for VICTORIA)
    + Phase info
    + Prompt overrides from prompt_overrides/victoria.md
  Tools: read_file, write_file, generate_image (Gamma API)
  Output: Edited posts + brand images → saved to 02-content/posts/ (marked ready)
  Verdict: [VERDICT: ready_next] [→ vasya]

Step 4: VASYA (Scheduler)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Input: Read edited posts from 02-content/posts/
  Context: from_agent="victoria", position=3, next=null (LAST)
  System Prompt:
    + Base VASYA system
    + "Ты получила готовые посты от victoria"
    + "ТЫ ПОСЛЕДНЯЯ В ЦЕПОЧКЕ — это финальный результат"
    + Phase info
  Tools: read_file, write_file, run_command (python tools/post_content.py --url ..., schedule webhooks)
  Output: Schedule posts → write scheduling info to 02-content/content-plan.md
  Verdict: [VERDICT: done]

COMPLETION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  n8n_webhook.py sees [VERDICT: done]
  → POST to N8N_STATUS_WEBHOOK_URL with {ok: true, chain_id, status: "success"}
  → memory.py logs event: chain:end {chain_id, status: "ok", total_ms: 47230}
  → chain_dashboard shows chain completed in timeline
```

### 2.4 Context Propagation Code

**In pipeline.py** (non-interactive chain):
```python
def run_chain(chain_name, chain_config):
    """Run a chain of agents sequentially."""
    agents = chain_config["agents"]
    chain_id = generate_chain_id()
    
    # Log chain start
    memory.log_event("chain:start", {
        "chain_id": chain_id,
        "agents": agents,
        "trigger": chain_config.get("trigger")
    })
    
    result = None
    for position, agent_key in enumerate(agents):
        next_agent = agents[position + 1] if position < len(agents) - 1 else None
        
        # Build context for this step
        context = {
            "from_agent": agents[position - 1] if position > 0 else "system",
            "to_agent": None,
            "chain_id": chain_id,
            "position": position,
            "is_final": position == len(agents) - 1
        }
        
        # Enhance system prompt with context
        system_prompt = compose_system(agent_key, BASE_SYSTEM[agent_key], context)
        
        # Run agent
        history = []
        client = get_client()
        reply, history = run_agent(
            client, system_prompt, TOOLS[agent_key],
            HANDLERS[agent_key],
            result or "Start processing",
            history,
            agent_key=agent_key,
            context=context
        )
        
        result = reply
        
        # Log step completion
        memory.log_event("chain:step", {
            "chain_id": chain_id,
            "agent": agent_key,
            "position": position,
            "status": "done",
            "result_preview": result[:200]
        })
    
    # Log chain completion
    memory.log_event("chain:end", {
        "chain_id": chain_id,
        "status": "ok" if "VERDICT: done" in result else "partial",
        "total_ms": (time.time() - start) * 1000
    })
```

**In webapp.py** (interactive agent):
```python
@app.post("/api/agent/<agent_key>/message")
def agent_message(agent_key):
    data = request.get_json()
    user_msg = data.get("message", "")
    
    # Extract context from message tags
    context = system_prompt_builder.extract_context_from_message(user_msg)
    if not context and "chain_id" in data:
        # Or from request data
        context = {
            "from_agent": data.get("from_agent"),
            "to_agent": data.get("to_agent"),
            "chain_id": data.get("chain_id")
        }
    
    # Get or create agent
    agent_mod = load_agent_module(agent_key)
    
    # Enhance system prompt
    system = base.compose_system(agent_key, agent_mod.SYSTEM, context)
    
    # Run agent with context
    history = session_manager.get_history(agent_key, session_id)
    reply, history = base.run_agent(
        client, system, agent_mod.TOOLS, agent_mod.handle,
        user_msg, history,
        agent_key=agent_key,
        context=context
    )
    
    # Save history & log
    session_manager.save_history(agent_key, session_id, history)
    memory.log_event("agent:message", {
        "agent": agent_key,
        "from_agent": context.get("from_agent", "user") if context else "user",
        "chain_id": context.get("chain_id") if context else None
    })
    
    return {"reply": reply, "context": context}
```

### 2.5 Context Tags in Messages

Agents can suggest context tags in their responses to guide the next step:

```markdown
Всё проверено и готово к публикации.

[VERDICT: ready_next]
[→ vasya]

<!-- Optional: explicit context tags -->
[from: victoria]
[to: vasya]
[chain_id: content_week_2026_06_08_001]
```

The webapp/pipeline parses these tags and passes them to the next agent.

---

## 3. DASHBOARD USAGE GUIDE

### 3.1 Accessing the Dashboard

```bash
cd mila-office
python webapp.py
# → http://127.0.0.1:5000 opens in browser

# Separate n8n webhook server (optional, for n8n triggers)
python n8n_webhook.py
# → http://127.0.0.1:5052 (API only, not a UI)
```

### 3.2 Dashboard Features

#### 3.2.1 Agent Tabs (Main UI)
- **Per-agent chat tabs** — одна вкладка на агента (11 total)
- **Chat history** — saved in memory by session
- **Quick commands** — /аналитика, /контент, /помощь (agent-specific)
- **File display** — agents can render Markdown, tables, images
- **Tool calls** — user sees [tool_name](args) in output

#### 3.2.2 Chain Dashboard (`/chains`)
Access via **"Chains" tab** in navbar or direct: `http://127.0.0.1:5000/chains`

**API Endpoints**:

```bash
# Active chains (currently running)
GET /chains/api/active
→ [{
    "chain_id": "content_week_2026_06_08_001",
    "from_agent": "n8n",
    "agents": ["olya", "marina", "victoria", "vasya"],
    "started_at": "2026-06-08T10:22:45Z",
    "elapsed_ms": 12340,
    "current_agent": "marina",
    "progress": 0.33
  }, ...]

# Completed chains (history)
GET /chains/api/history?limit=20&status=success
→ [{
    "chain_id": "content_week_2026_06_07_001",
    "status": "success",
    "agents": ["olya", "marina", "victoria", "vasya"],
    "started_at": "2026-06-07T10:22:45Z",
    "completed_at": "2026-06-07T10:35:12Z",
    "duration_ms": 747000,
    "result_preview": "5 posts scheduled..."
  }, ...]

# Timeline (what each agent is doing now)
GET /chains/api/timeline
→ {
    "marina": {
      "current_chain": "content_week_2026_06_08_001",
      "current_task": "Write 5 posts on trends",
      "started_at": "2026-06-08T10:27:30Z",
      "elapsed_ms": 2145
    },
    "victoria": {
      "current_chain": null,
      "status": "idle"
    },
    ...
  }

# Details of one chain (full logs)
GET /chains/api/details/content_week_2026_06_08_001
→ {
    "chain_id": "...",
    "events": [
      {
        "timestamp": "2026-06-08T10:22:45Z",
        "kind": "chain:start",
        "agent": "olya",
        "details": {...}
      },
      {
        "timestamp": "2026-06-08T10:25:12Z",
        "kind": "chain:step",
        "agent": "olya",
        "status": "done",
        "duration_ms": 147000,
        "result_preview": "..."
      },
      {
        "timestamp": "2026-06-08T10:27:30Z",
        "kind": "chain:step",
        "agent": "marina",
        "status": "running",
        "duration_ms": 2145
      }
    ]
  }

# Performance metrics
GET /chains/api/metrics
→ {
    "avg_chain_duration_ms": 524000,
    "total_chains_completed": 847,
    "success_rate": 0.96,
    "errors_24h": 12,
    "by_agent": {
      "marina": {
        "avg_duration_ms": 125000,
        "total_runs": 847,
        "success_rate": 0.98
      },
      ...
    }
  }
```

#### 3.2.3 Web UI Features

**Chain Timeline View**:
```
┌─────────────────────────────────────────────────────────────┐
│ CHAIN: content_week_2026_06_08_001                          │
│ Status: RUNNING (started 10:22, elapsed 12m 45s)           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ◆━ OLYA (10:22-10:25)  ✓ DONE       [3m 0s]              │
│  ──┃                                                        │
│  ◆━ MARINA (10:25-10:27) ► RUNNING   [2m 45s / est. 5m]   │
│  ──┃                                                        │
│  ◆━ VICTORIA (–) ⧗ PENDING                                 │
│  ──┃                                                        │
│  ◆━ VASYA (–) ⧗ PENDING                                    │
│                                                              │
│ Progress: 25%                                               │
│ Estimated total: ~13m                                       │
└─────────────────────────────────────────────────────────────┘
```

**Error Drill-Down** (if chain fails):
```
Click on failed agent → see:
  • Full traceback
  • Last input/output
  • Tool calls that failed
  • Retry options:
    [Retry from this agent]
    [Escalate to different agent]
    [Cancel chain]
```

**Performance Metrics View**:
```
AGENT PERFORMANCE (last 30 days)
┌──────────────┬──────┬──────────┬────────────┬──────────┐
│ Agent        │ Runs │ Avg Time │ Success %  │ Errors   │
├──────────────┼──────┼──────────┼────────────┼──────────┤
│ marina       │ 847  │ 125s     │ 98.2%      │ 15       │
│ victoria     │ 823  │ 42s      │ 99.5%      │ 4        │
│ olya         │ 156  │ 180s     │ 94.9%      │ 8        │
│ vasya        │ 823  │ 38s      │ 99.6%      │ 3        │
│ ... (others) │ ...  │ ...      │ ...        │ ...      │
└──────────────┴──────┴──────────┴────────────┴──────────┘

CHAIN TYPES (last 30 days)
┌──────────────────┬──────┬──────────┬────────────┬──────────┐
│ Chain            │ Runs │ Avg Time │ Success %  │ Errors   │
├──────────────────┼──────┼──────────┼────────────┼──────────┤
│ content_week     │ 4    │ 747s     │ 100%       │ 0        │
│ new_client       │ 12   │ 89s      │ 91.7%      │ 1        │
│ weekly_report    │ 4    │ 234s     │ 100%       │ 0        │
│ ... (others)     │ ...  │ ...      │ ...        │ ...      │
└──────────────────┴──────┴──────────┴────────────┴──────────┘
```

### 3.3 Reading Dashboard Data from Code

```python
import memory
import json

# Get current chain status
events = memory.read_events()  # Read events.jsonl
active_chains = {}
for event in events:
    if event["kind"] == "chain:start":
        active_chains[event["chain_id"]] = {
            "agents": event.get("agents"),
            "started": event["timestamp"],
            "status": "running"
        }
    elif event["kind"] == "chain:end":
        if event["chain_id"] in active_chains:
            active_chains[event["chain_id"]]["status"] = event.get("status")
            active_chains[event["chain_id"]]["completed"] = event["timestamp"]

# Get performance for one agent
marina_events = [e for e in events if e.get("agent") == "marina"]
success_count = len([e for e in marina_events if "success" in e.get("status", "")])
total = len(marina_events)
print(f"Marina: {success_count}/{total} ({100*success_count/total:.1f}%)")
```

---

## 4. RETRY & ERROR HANDLING

### 4.1 Error Detection & Logging

All errors are **centrally logged** to `logs/errors.jsonl`:

```python
# In any agent or tool:
import error_monitor

try:
    result = do_something()
except Exception as e:
    # Log with context
    error_monitor.log_error(
        e,
        context={
            "agent": "marina",
            "tool": "run_command",
            "command": "python tools/post_content.py ...",
            "user_message": "Опубликуй новый пост"
        },
        alert=True  # Send Telegram alert for critical errors
    )
```

**Error log entry** (`logs/errors.jsonl`):
```json
{
  "timestamp": "2026-06-08T10:45:23Z",
  "level": "ERROR",
  "error_type": "instagram_api.GraphError",
  "error_message": "Insufficient permissions to publish",
  "traceback": "...",
  "context": {
    "agent": "marina",
    "tool": "run_command",
    "command": "python tools/post_content.py photo --url ... --caption ..."
  }
}
```

### 4.2 Retry Strategies

#### 4.2.1 Agent-Level Retry (in pipeline.py)

```python
from pipeline import run_agent_with_retry

# Retry with exponential backoff
reply, history = run_agent_with_retry(
    client, system, tools, handle, msg, history,
    agent_key="marina",
    max_retries=3,           # Attempts 1, 2, 3
    initial_delay=1          # 1s → 2s → 4s
)
```

Logic:
```
Attempt 1 (0s): POST LLM request
  ↓ Error → wait 1s
Attempt 2 (1s): POST LLM request
  ↓ Error → wait 2s
Attempt 3 (3s): POST LLM request
  ↓ Success or final error
```

#### 4.2.2 Chain-Level Retry (chain_retry.py)

```python
from chain_retry import retry_chain, escalate_chain, split_chain

# Retry failed chain from the failed agent
retry_chain(
    chain_id="content_week_2026_06_08_001",
    failed_agent="marina",  # Marina failed
    reason="api_failure"    # Instagram API was down
)
# → Restarts chain from marina (with fresh state)

# Or escalate to a different agent
escalate_chain(
    chain_id="content_week_2026_06_08_001",
    new_agent="rita"  # Try Rita instead of Marina
)
# → victoria + rita + vasya (skip marina)

# Or split to parallel agents
split_chain(
    chain_id="content_week_2026_06_08_001",
    to_agents=["rita", "dima", "tyoma"]  # Do in parallel
)
# → Run all three simultaneously, then merge_results
```

**Chain state file** (`reports/pipeline_state_<chain>.json`):
```json
{
  "chain": "content_week",
  "chain_id": "content_week_2026_06_08_001",
  "started_at": "2026-06-08T10:22:45Z",
  "agents": ["olya", "marina", "victoria", "vasya"],
  "checkpoint": {
    "completed_steps": ["olya"],
    "current_step": 1,  // Next: marina
    "results": {
      "olya": {
        "status": "success",
        "output": "Weekly trends analysis..."
      }
    },
    "retry_count": 0,
    "last_error": null
  }
}
```

If marina fails, pipeline detects it and:
1. **Saves state** at current checkpoint
2. **Logs error** to `logs/errors.jsonl`
3. **Calls error_monitor** if alert=True (sends Telegram)
4. **Raises exception** (can be caught by supervisor)

If you call `retry_chain`, it:
1. **Reads checkpoint** from state file
2. **Resumes from failed_agent** (skips completed steps)
3. **Updates state** as it goes

#### 4.2.3 Tool-Level Retry (graph_api in tools/)

```python
# In tools/_common.py
def graph_get(path, **params):
    """Auto-retries transient errors (503, 429, network)."""
    for attempt in range(3):
        try:
            r = requests.get(
                f"{api_base()}/{path}",
                params={**params, "access_token": token},
                timeout=30
            )
            if r.status_code == 200:
                return r.json()
            elif r.status_code in (429, 503, 504):  # Transient
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
            else:
                raise GraphError(f"HTTP {r.status_code}: {r.text}")
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise GraphError(f"Network error: {e}")
    raise GraphError("Max retries exceeded")
```

### 4.3 Error Categorization

Errors are categorized by **type** and **severity**:

```python
class ErrorCategory(Enum):
    # Config errors (won't fix by retry)
    CONFIG_ERROR = "config"          # Missing .env variable
    POLICY_VIOLATION = "policy"      # Agent not allowed to do X
    
    # Transient errors (retry helps)
    API_RATE_LIMIT = "rate_limit"   # 429, wait and retry
    API_TIMEOUT = "timeout"         # 504, wait and retry
    NETWORK_ERROR = "network"       # Connection failed
    
    # Agent errors (escalate or manual fix)
    INVALID_OUTPUT = "invalid"      # Agent output didn't match schema
    AGENT_CRASH = "agent_crash"     # Agent process crashed
    
    # Business logic errors (chain failure)
    TASK_FAILED = "task_failed"     # Agent couldn't complete task
    ESCALATION = "escalation"       # Agent requested escalation
```

**Decision tree for handling**:
```
Error occurs
  │
  ├─ Is it CONFIG_ERROR or POLICY_VIOLATION?
  │  └─ NO RETRY — requires manual intervention (log, alert)
  │
  ├─ Is it API_RATE_LIMIT, TIMEOUT, or NETWORK_ERROR?
  │  └─ RETRY with exponential backoff (3 attempts)
  │
  ├─ Is it INVALID_OUTPUT?
  │  └─ If first time: RETRY with clearer prompt
  │     If 3rd retry: ESCALATE to different agent
  │
  └─ Is it AGENT_CRASH or TASK_FAILED?
     └─ LOG error, send alert, escalate_chain or manual review
```

### 4.4 Example: Full Error Flow

```python
# In webapp.py, user sends message to Marina
@app.post("/api/agent/marina/message")
def marina_message():
    try:
        reply, history = base.run_agent(...)
        return {"reply": reply}
    except base.GraphError as e:
        # API error (429, 503, etc) — user sees prompt to retry
        error_id = error_monitor.log_error(e, context={"agent": "marina"}, alert=False)
        return {
            "error": "Инстаграм API недоступен. Повтори через минуту.",
            "error_id": error_id
        }, 503
    except Exception as e:
        # Unknown error — log it, alert ops, show safe message
        error_id = error_monitor.log_error(
            e,
            context={"agent": "marina", "user_msg": msg},
            alert=True  # Send Telegram to Людмила
        )
        return {
            "error": "Техническая ошибка. Сообщи об ошибке оператору.",
            "error_id": error_id,
            "error_details": "See logs for details"
        }, 500
```

---

## 5. n8n INTEGRATION EXAMPLES

### 5.1 Setup

**Prerequisites**:
1. n8n running (docker or local)
2. `python n8n_webhook.py` running on port 5052
3. `.env` variables set:
   ```
   N8N_WEBHOOK_PORT=5052
   N8N_WEBHOOK_TOKEN=your_secret_token
   N8N_STATUS_WEBHOOK_URL=http://localhost:5678/webhook/office-done
   N8N_ERROR_WEBHOOK_URL=http://localhost:5678/webhook/office-error
   N8N_WEBHOOK_TIMEOUT=300
   ```

### 5.2 Triggering a Chain from n8n

**n8n Workflow Step**:
```
[Schedule Trigger (Monday 09:00)]
  ↓
[HTTP Request]
  Method: POST
  URL: http://localhost:5052/api/n8n/trigger-chain
  Headers:
    Authorization: Bearer your_secret_token
    Content-Type: application/json
  Body:
    {
      "chain_config": {
        "agents": ["olya", "marina", "victoria", "vasya"],
        "trigger": "monday_09:00",
        "name": "Weekly Content Calendar"
      },
      "from_agent": "n8n",
      "to_agent": null,
      "chain_id": "content_week_{{ $json.week_id }}"
    }
  ↓
  Response: {
    "ok": true,
    "chain_id": "content_week_2026_06_08_001",
    "status": "pending",
    "message": "Chain queued for execution"
  }
  ↓
[Wait for Webhook]
  URL: /webhook/office-done
  Timeout: 600s (10m)
  ↓
[Webhook received]
  Payload: {
    "ok": true,
    "chain_id": "content_week_2026_06_08_001",
    "status": "success",
    "progress": 100,
    "result": "5 posts scheduled for week",
    "timestamp": "2026-06-08T10:35:12Z"
  }
  ↓
[Next Steps (optional)]
  • Send Telegram notification
  • Update Google Sheet
  • Trigger Instagram posting workflow
```

### 5.3 Monitoring Chain Status from n8n

**Option 1: Polling** (check status every 10s)
```
[Loop] Do while status != "success"
  ↓
  [HTTP Request] GET /api/n8n/chain-status/{{ chain_id }}
    Response: {
      "chain_id": "...",
      "status": "running",
      "current_agent": "marina",
      "progress": 33,
      "elapsed_ms": 45230
    }
  ↓
  [Sleep 10s]
  ↓
  [Evaluate: if status == "success", break]
  ↓
[Process final result]
```

**Option 2: Webhook Callback** (n8n waits passively)
```
[Trigger chain with callback_url]
  POST /api/n8n/trigger-chain
  {
    "chain_config": {...},
    "callback_url": "http://localhost:5678/webhook/my-chain-done"
  }
  ↓
[n8n continues (other tasks)]
  ↓
[When chain completes, n8n_webhook.py calls callback_url]
  POST http://localhost:5678/webhook/my-chain-done
  {
    "ok": true,
    "chain_id": "...",
    "status": "success",
    "result": "..."
  }
  ↓
[Webhook endpoint processes result]
```

### 5.4 Instagram Analytics Report Flow

**Automated n8n Workflow** (every 24h):

```
[Cron Trigger: Daily at 00:00 UTC]
  ↓
[Python: Execute Command]
  cd tools
  python get_analytics.py posts
  → Saves reports/posts_2026-06-08_000000.json
  ↓
[HTTP: POST to n8n-webhook]
  URL: http://localhost:5052/api/n8n/trigger-chain
  {
    "chain_config": {
      "agents": ["rita", "dima", "manager"],
      "trigger": "auto:analytics"
    },
    "from_agent": "n8n",
    "input_file": "reports/posts_2026-06-08_000000.json"
  }
  ↓
[Chain runs]
  Rita:    Analyze reports/posts_*.json → audience insights
  Dima:    Correlate with Gumroad sales → funnel analysis
  Manager: Summary → metrics over time
  ↓
[Webhook: Chain completed]
  {
    "chain_id": "analytics_2026_06_08_001",
    "status": "success",
    "result": "Daily insights updated"
  }
  ↓
[Save to Database]
  POST to Supabase / Gumroad API
  Update: analytics table with metrics
  ↓
[Telegram Notification]
  Send summary to TELEGRAM_ADMIN_CHAT_ID
  "📊 Daily Report Ready (6 June 2026)"
```

### 5.5 Error Handling in n8n

**n8n Workflow with Error Branch**:

```
[HTTP: Trigger chain]
  ↓
  Error? YES → [Try/Catch]
    ├─ HTTP 429 (rate limited)
    │  └─ [Wait] 60s, then [Retry]
    ├─ HTTP 5xx (server error)
    │  └─ [Wait] 30s, then [Retry]
    ├─ HTTP 401 (auth error)
    │  └─ [Alert] "Chain auth failed" → manual review
    └─ Other
       └─ [Log] → error_monitor
          [Send Telegram] "Chain failed: {error}"
  ↓ (if success)
[Continue processing]
```

### 5.6 Example: "New Client" Chain (from Telegram form)

```
TELEGRAM USER
  │
  └─ Fills form in Telegram bot
     [Button: "Отправить заявку"]
     ↓
n8n Webhook
  │
  └─ Receives form data
     {
       "client_name": "Маша",
       "email": "masha@example.com",
       "phone": "+380...",
       "issue": "Я выбираю не того партнёра...",
       "situation": "Замужем, но влюблена в коллегу"
     }
     ↓
[HTTP: POST to mila-office]
  URL: http://localhost:5052/api/n8n/trigger-chain
  {
    "chain_config": {
      "agents": ["alina", "lera"],
      "trigger": "telegram:form"
    },
    "from_agent": "telegram",
    "form_data": {
      "client_name": "Маша",
      "email": "masha@example.com",
      ...
    },
    "chain_id": "new_client_2026_06_08_001"
  }
  ↓
MILA OFFICE Pipeline
  │
  Step 1: ALINA (intake processing)
    • Read form → validate
    • Create session notes (confidential)
    • Extract main issue
    • Output: intake summary
    ↓
  Step 2: LERA (sales funnel)
    • Read Alina's summary
    • Prepare offer for client
    • Draft email / consultation proposal
    • Output: email draft + next steps
    ↓
[When complete: POST to Telegram bot]
  {
    "chain_id": "new_client_2026_06_08_001",
    "status": "success",
    "next_step": "send_email_to_masha"
  }
  ↓
[Telegram bot sends follow-up message]
  "Спасибо, Маша! Наша команда рассмотрела твою заявку.
   Вот предложение консультации..."
```

---

## 6. TESTING STRATEGIES

### 6.1 Unit Testing: Single Agent

**File**: `tests/test_agent_victoria.py`

```python
import pytest
from unittest.mock import patch, MagicMock
import victoria
import base

@pytest.fixture
def victoria_agent():
    return {
        "system": victoria.SYSTEM,
        "tools": victoria.TOOLS,
        "handle": victoria.handle
    }

def test_victoria_spell_check(victoria_agent):
    """Victoria catches spelling errors in posts."""
    user_msg = "пост с опчиткой и ошибакми"
    history = []
    client = MagicMock()  # Mock LLM
    
    # Mock LLM response
    client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(type="text", text="Найдены ошибки: опчиткой → опечаткой, ошибакми → ошибками")
        ]
    )
    
    reply, history = base.run_agent(
        client, victoria_agent["system"], victoria_agent["tools"],
        victoria_agent["handle"], user_msg, history, agent_key="victoria"
    )
    
    assert "опечаткой" in reply or "ошибками" in reply

def test_victoria_context_aware():
    """Victoria knows when request is from Marina vs. Lera."""
    context_marina = {"from_agent": "marina"}
    context_lera = {"from_agent": "lera"}
    
    system_marina = base.compose_system("victoria", victoria.SYSTEM, context_marina)
    system_lera = base.compose_system("victoria", victoria.SYSTEM, context_lera)
    
    assert "marina" in system_marina.lower()
    assert "lera" in system_lera.lower()
    assert system_marina != system_lera
```

### 6.2 Integration Testing: Chain

**File**: `tests/test_chain_content_week.py`

```python
import pytest
from pathlib import Path
import json
import pipeline
import memory

@pytest.fixture
def test_chain_config():
    return {
        "name": "content_week",
        "agents": ["olya", "marina", "victoria", "vasya"],
        "trigger": "test"
    }

def test_content_week_chain(test_chain_config, tmp_path):
    """Full chain: trends → write → edit → schedule."""
    
    # Mock memory with test isolation
    with patch("memory.CONTEXT", tmp_path / "context.json"):
        with patch("memory.EVENTS", tmp_path / "events.jsonl"):
            chain_id = "test_content_week_001"
            
            # Run chain
            result = pipeline.run_chain("content_week", test_chain_config)
            
            # Assertions
            assert result is not None
            assert "VERDICT: done" in result or "scheduled" in result.lower()
            
            # Check memory was updated
            events = memory.read_events()
            assert any(e["kind"] == "chain:start" and e["chain_id"] == chain_id for e in events)
            assert any(e["kind"] == "chain:end" for e in events)

def test_context_propagation_through_chain():
    """Context flows from agent to agent."""
    context = {"from_agent": "n8n", "chain_id": "test_001"}
    
    # After olya completes
    messages = [
        {"kind": "chain:step", "agent": "olya", "chain_id": context["chain_id"]},
        # Marina receives context
        {"kind": "chain:step", "agent": "marina", "chain_id": context["chain_id"]},
    ]
    
    # Verify context in system prompt for each agent
    for msg in messages:
        agent = msg["agent"]
        sys = base.compose_system(agent, globals()[f"SYSTEM_{agent.upper()}"], context)
        assert context["chain_id"] in sys
```

### 6.3 Load Testing: Multiple Chains

**File**: `tests/test_load_parallel_chains.py`

```python
import pytest
import concurrent.futures
import time
import pipeline

def test_parallel_chains_10_concurrent():
    """Run 10 chains simultaneously, verify isolation."""
    chains = [
        ("content_week", {"agents": ["olya", "marina"]})
        for _ in range(10)
    ]
    
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(pipeline.run_chain, name, cfg) for name, cfg in chains]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    elapsed = time.time() - start
    
    assert len(results) == 10
    assert all(r is not None for r in results)
    assert elapsed < 120  # All 10 chains complete in <2 min (with Gemini fast-track)
    
    print(f"✓ Ran 10 chains in {elapsed:.1f}s (avg {elapsed/10:.1f}s per chain)")
```

### 6.4 Error Recovery Testing

**File**: `tests/test_chain_retry.py`

```python
import pytest
from unittest.mock import patch, MagicMock
import chain_retry
import pipeline

def test_retry_on_agent_error():
    """Chain recovers from agent error and retries."""
    chain_id = "test_retry_001"
    
    # Simulate: Marina fails first, succeeds on retry
    call_count = {"marina": 0}
    
    original_handle = marina.handle
    def handle_with_failure(name, inp):
        if name == "read_file" and call_count["marina"] == 0:
            call_count["marina"] += 1
            raise Exception("Network error: file not found")
        return original_handle(name, inp)
    
    with patch.object(marina, "handle", handle_with_failure):
        # Run with retry
        result = pipeline.run_agent_with_retry(
            client, marina.SYSTEM, marina.TOOLS, marina.handle,
            "Write 5 posts", [], agent_key="marina", max_retries=3
        )
    
    assert result is not None
    assert call_count["marina"] > 0  # Retried after first failure

def test_escalate_chain_on_repeated_failure():
    """After 3 retries, escalate to different agent."""
    chain_id = "test_escalate_001"
    
    # Marina fails 3 times
    def always_fail(*args, **kwargs):
        raise Exception("Persistent error")
    
    with patch("base.run_agent", side_effect=always_fail):
        # Try to run, then escalate
        try:
            pipeline.run_agent_with_retry(..., max_retries=3)
        except Exception:
            # Escalate to Rita
            result = chain_retry.escalate_chain(chain_id, "rita")
            assert result["escalated_to"] == "rita"
```

### 6.5 Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_agent_victoria.py -v

# Specific test function
pytest tests/test_agent_victoria.py::test_victoria_spell_check -v

# With coverage
pytest tests/ --cov=mila-office --cov-report=html

# Load test
pytest tests/test_load_parallel_chains.py -v -s

# Integration test (slower, full chains)
pytest tests/test_chain_content_week.py -v --timeout=600
```

### 6.6 Mocking External Services

```python
import pytest
from unittest.mock import patch

@pytest.fixture
def mock_instagram():
    """Mock Instagram API responses."""
    with patch("base.graph_api.graph_get") as mock_get:
        mock_get.return_value = {
            "insights": [
                {"name": "impressions", "value": 1500},
                {"name": "engagement", "value": 87}
            ]
        }
        yield mock_get

@pytest.fixture
def mock_gumroad():
    """Mock Gumroad sales API."""
    with patch("shared_tools.gumroad_sales") as mock_sales:
        mock_sales.return_value = json.dumps([
            {"id": "xyz", "price": 37, "date": "2026-06-08"}
        ])
        yield mock_sales

def test_with_mocked_apis(mock_instagram, mock_gumroad):
    """Test agent without hitting real APIs."""
    # ... test code ...
```

---

## 7. TROUBLESHOOTING

### 7.1 Common Issues & Solutions

#### Issue: Agent doesn't respond

**Symptom**: Browser shows spinning wheel, agent doesn't reply after 30s

**Solutions**:
1. **Check logs**:
   ```bash
   tail -f logs/webapp.log
   tail -f logs/errors.jsonl
   ```
   
2. **Check Anthropic API status**:
   ```bash
   # Verify token works
   python -c "import base; client = base.get_client(); print(client.models.list())"
   ```
   
3. **Check model availability**:
   ```bash
   # If using claude-opus-4-6, verify it's still available
   # Current: claude-opus-4-8, claude-haiku-4-5
   echo "MILA_MODEL=claude-opus-4-8" >> .env
   ```
   
4. **Check for stuck processes**:
   ```bash
   ps aux | grep python | grep mila-office
   # Kill stuck agents: kill -9 <pid>
   ```

#### Issue: "Insufficient permissions to publish"

**Symptom**: Marina can't post to Instagram

**Solutions**:
1. **Verify IG token**:
   ```bash
   cd tools
   python check_setup.py --write  # Updates .env with diagnostics
   ```
   
2. **Check token expiration**:
   - Instagram tokens expire after ~60 days
   - Generate new token from https://business.instagram.com
   
3. **Verify scopes**:
   - App must have: `instagram_business_content_publish`
   - Check Meta App Dashboard → Settings → Basic → App Roles

#### Issue: "Chain timeout after 300s"

**Symptom**: n8n webhook times out waiting for chain completion

**Solutions**:
1. **Check what's slow**:
   ```bash
   # View chain progress
   curl http://localhost:5000/chains/api/active | jq
   # Should show current_agent + elapsed_ms
   ```
   
2. **Increase timeout**:
   ```bash
   N8N_WEBHOOK_TIMEOUT=600  # 10 minutes instead of 5
   ```
   
3. **Optimize agent**:
   - Check if Marina's LLM calls are slow (switch to Gemini)
   - Check if tools are blocking (network, file I/O)
   - Profile with:
     ```python
     import cProfile, pstats
     profiler = cProfile.Profile()
     profiler.enable()
     pipeline.run_chain("content_week", {...})
     profiler.disable()
     stats = pstats.Stats(profiler)
     stats.sort_stats("cumulative").print_stats(20)
     ```

#### Issue: "Memory locked after crash"

**Symptom**: `.lock` file exists, can't write to memory/

**Solution**:
```bash
# Remove stale lock
rm mila-office/memory/.lock

# Or programmatically
import memory
memory._FileLock(timeout=1).__exit__(None, None, None)
```

#### Issue: "Session token invalid"

**Symptom**: Webapp says "Session expired" after 1 hour

**Solutions**:
1. **Check session manager**:
   ```bash
   tail -f logs/webapp.log | grep -i session
   ```
   
2. **Increase session timeout**:
   ```python
   # In webapp.py
   app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
   ```
   
3. **Clear browser cache**:
   - DevTools → Application → Clear Storage

#### Issue: "Agents stuck in retry loop"

**Symptom**: Error monitor logs show same error repeatedly

**Solutions**:
1. **Identify root cause**:
   ```bash
   tail -f logs/errors.jsonl | jq '.error_message' | sort | uniq -c | sort -rn
   ```
   
2. **Disable retry for config errors**:
   ```python
   # In pipeline.py
   if error_category == "config_error":
       raise  # Don't retry, fail fast
   ```
   
3. **Escalate manually**:
   ```bash
   python -c "from chain_retry import escalate_chain; escalate_chain('chain_id', 'different_agent')"
   ```

### 7.2 Debug Commands

```bash
# View active chains
curl http://localhost:5000/chains/api/active | jq '.[0]'

# View specific chain logs
curl http://localhost:5000/chains/api/details/content_week_2026_06_08_001 | jq '.events'

# Check agent performance
curl http://localhost:5000/chains/api/metrics | jq '.by_agent.marina'

# View recent errors
tail -20 logs/errors.jsonl | jq '.'

# View events log
tail -50 mila-office/memory/events.jsonl | jq '.kind' | sort | uniq -c

# Check memory state
python -c "import memory; print(json.dumps(memory.read_context(), indent=2))"

# Test Anthropic API
python -c "
import base
client = base.get_client()
msg = client.messages.create(
    model='claude-opus-4-6',
    max_tokens=100,
    messages=[{'role': 'user', 'content': 'Hello'}]
)
print('✓ Anthropic API works:', msg.content[0].text[:50])
"

# Test Instagram API
cd tools && python check_setup.py

# Test Telegram API
python -c "
import base
import shared_tools
result = shared_tools.telegram_send('test message', confirm=False)
print(result)
"
```

### 7.3 Performance Profiling

```python
# In any script
import time
import cProfile
import pstats
from io import StringIO

# Method 1: Timer
def profile_chain():
    start = time.time()
    pipeline.run_chain("content_week", {...})
    elapsed = time.time() - start
    print(f"Chain took {elapsed:.1f}s")

# Method 2: cProfile (detailed)
pr = cProfile.Profile()
pr.enable()
pipeline.run_chain("content_week", {...})
pr.disable()

s = StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(10)
print(s.getvalue())

# Method 3: Timeline from memory
import memory
events = memory.read_events()
for event in events:
    if event["kind"] == "chain:step":
        agent = event.get("agent")
        elapsed = event.get("elapsed_ms", 0)
        print(f"{agent}: {elapsed}ms")
```

---

## 8. PERFORMANCE TUNING

### 8.1 Agent Response Time

**Baseline** (what to expect):
- Anthropic Claude: 2-5 seconds per agent (network + LLM)
- Gemini: 1-3 seconds per agent (faster model)
- Full chain (4 agents): 8-20 seconds

**Optimization targets**:

1. **LLM Choice**:
   ```bash
   # Fast track (Gemini)
   MILA_LLM_PROVIDER=gemini
   MILA_GEMINI_MODEL=gemini-2.5-flash
   # → Victoria/Rita: <3s, entire chains: <10s
   
   # Balanced (Anthropic)
   MILA_LLM_PROVIDER=anthropic
   MILA_MODEL=claude-opus-4-8
   # → 3-5s per agent, 15-25s per chain
   ```

2. **Reduce Input Context**:
   ```python
   # In base.py
   _READ_MAX_CHARS = 20000  # Default 40000, reduce to speed up
   # Agents will request specific sections instead of full file
   ```

3. **Cache System Prompts**:
   ```python
   # base.run_agent already uses prompt caching with Anthropic
   # System prompt + tools are cached after first call
   # Subsequent messages reuse cache (10× cheaper, faster)
   ```

4. **Parallel Chains**:
   ```python
   # Instead of sequential: olya → marina → victoria → vasya
   # Consider parallel where possible: (rita + dima) → manager
   from concurrent.futures import ThreadPoolExecutor
   
   with ThreadPoolExecutor(max_workers=2) as executor:
       f1 = executor.submit(run_agent, "rita", ...)
       f2 = executor.submit(run_agent, "dima", ...)
       rita_result = f1.result()
       dima_result = f2.result()
   ```

### 8.2 File I/O Performance

**Slow patterns**:
- Reading large files (praktikum_редактура.html ~5 MB)
- Writing large JSON logs repeatedly

**Optimizations**:

```python
# BAD: Read entire file
content = read_file("01-praktikum/praktikum_редактура.html")  # 5 MB → 1.5M tokens!

# GOOD: Read specific section
content = read_file("01-praktikum/section_3.md")  # 50 KB → 15k tokens

# BETTER: Agent requests specific excerpt
user_msg = "Найди раздел 'Спасатель' в практикуме"
# Agent calls read_file("01-praktikum/praktikum..."), gets truncated at 40KB
# Agent then asks "Дай мне специально раздел Спасателя"
# Subsequent read_file("01-praktikum/section_spasatel.md") returns small file
```

**File Access Caching**:
```python
# In agent module
import functools

@functools.lru_cache(maxsize=10)
def cached_read_file(path: str) -> str:
    """Cache file contents for 1 agent run."""
    return base.read_file(path)

# Within same agent run, repeated reads use cache
# Cache clears when agent finishes
```

### 8.3 Database Query Optimization

If using Supabase for analytics:

```python
# BAD: Fetch all posts, filter in Python
import supa
posts = supa.table("ig_posts").select("*").execute()
hot_posts = [p for p in posts if p["likes"] > 100]

# GOOD: Filter in database
hot_posts = supa.table("ig_posts").select("*").gte("likes", 100).execute()

# BETTER: Aggregate in database
summary = supa.table("ig_posts").select("count(*) as total, avg(likes) as avg_likes")
```

### 8.4 Memory Management

**Potential leaks**:
- Chat history grows unbounded → trim old messages
- Events log grows unbounded → archive old events

**Mitigation**:

```python
# In webapp.py, trim history before saving
def save_history(agent_key, session_id, history):
    MAX_MESSAGES = 50  # Keep last 50 messages
    trimmed = history[-MAX_MESSAGES:]
    memory.save_history(agent_key, session_id, trimmed)

# In memory.py, archive old events
def archive_events(older_than_days=30):
    """Move events older than 30 days to archive."""
    cutoff = datetime.now() - timedelta(days=30)
    current_events = memory.read_events()
    to_archive = [e for e in current_events if e["timestamp"] < cutoff.isoformat()]
    
    if to_archive:
        archive_file = memory.EVENTS.with_suffix(".archive.jsonl")
        with open(archive_file, "a") as f:
            for event in to_archive:
                f.write(json.dumps(event) + "\n")
        
        # Keep only recent events
        recent = [e for e in current_events if e not in to_archive]
        memory.write_events(recent)
```

### 8.5 Monitoring Performance

**Metrics to track**:

```python
# Collect metrics after each chain
def log_metrics(chain_id, agents, total_ms):
    metrics = {
        "chain_id": chain_id,
        "agents": agents,
        "total_ms": total_ms,
        "avg_per_agent_ms": total_ms / len(agents),
        "timestamp": datetime.now().isoformat()
    }
    
    # Write to metrics file
    metrics_file = base.MILA_FOLDER / "reports" / "metrics.jsonl"
    with open(metrics_file, "a") as f:
        f.write(json.dumps(metrics) + "\n")

# Analyze trends
def analyze_performance(days=30):
    """Show performance trends over last 30 days."""
    metrics_file = base.MILA_FOLDER / "reports" / "metrics.jsonl"
    metrics = [json.loads(line) for line in metrics_file.read_text().splitlines()]
    
    # Filter to last 30 days
    cutoff = datetime.now() - timedelta(days=days)
    recent = [m for m in metrics if m["timestamp"] >= cutoff.isoformat()]
    
    # Group by agent
    by_agent = {}
    for m in recent:
        for agent in m["agents"]:
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(m["total_ms"] / len(m["agents"]))
    
    # Print averages
    for agent, times in by_agent.items():
        avg = sum(times) / len(times)
        print(f"{agent:15} avg {avg:6.0f}ms ({len(times)} chains)")
```

---

## 9. BEST PRACTICES FOR CHAIN DESIGN

### 9.1 Chain Design Patterns

**Pattern 1: Sequential Pipeline**
```
INPUT → [AGENT1] → [AGENT2] → [AGENT3] → OUTPUT
```
**When**: One agent's output is another's input
**Example**: Olya (trends) → Marina (write) → Victoria (edit) → Vasya (schedule)

**Pattern 2: Parallel Fanout**
```
       ┌→ [AGENT1] ┐
INPUT ─┤→ [AGENT2] ├→ [MERGE] → OUTPUT
       └→ [AGENT3] ┘
```
**When**: Multiple agents work on same input independently
**Example**: Rita + Dima (analyze reports) → Manager (synthesize)

**Pattern 3: Conditional Branching**
```
INPUT → [AGENT1] → Decision?
                    ├─ YES → [AGENT2] → OUTPUT
                    └─ NO  → [AGENT3] → OUTPUT
```
**When**: Different paths based on intermediate result
**Example**: New client form → If complex → Alina + Lera; If simple → Lera only

**Pattern 4: Retry with Escalation**
```
INPUT → [AGENT1] (MAX 3 RETRIES)
          ↓ FAIL
        [AGENT2] (Escalation)
          ↓ FAIL
        [MANUAL REVIEW]
```
**When**: Fallback to different agent on repeated failures
**Example**: Marina fails 3 times writing → Rita tries → Manual review by Людмила

### 9.2 Context Design

**Minimal context** (recommended):
```json
{
  "from_agent": "marina",
  "chain_id": "content_week_2026_06_08_001"
}
```
Agent knows: "Marina sent this, it's part of content_week chain"

**Rich context** (optional, for complex chains):
```json
{
  "from_agent": "marina",
  "to_agent": "victoria",
  "chain_id": "content_week_2026_06_08_001",
  "position": 1,
  "previous": "olya",
  "is_final": false,
  "metadata": {
    "trigger": "monday_09:00",
    "user_id": "liudmyla",
    "retry_count": 0
  }
}
```
Agent knows: Full chain topology, position, retry history

**Avoid**:
- Passing entire previous outputs in context (use files instead)
- Putting secrets in context (use env vars)
- Dynamic state that changes between retries (use memory.py)

### 9.3 Agent Handoff Guidelines

**Good handoff**:
```markdown
Вот три варианта контента для недели:

1. **Пост про спасателя** — 180 символов, готов к публикации
2. **Рील про выбор** — скрипт, нужна озвучка и видео
3. **История про установки** — 5 слайдов, нужно расширить до статьи

Рекомендую начать с поста (быстро), потом рель. Кирилл может помочь с производством видео.

[VERDICT: ready_next]
[→ victoria]
```

**Bad handoff**:
```
Готово.
```
(Victoria doesn't know what to review, what's the priority, what's missing)

**Handoff checklist**:
- [ ] Clear summary of what was done
- [ ] Expected next steps (agent knows what to do)
- [ ] Prioritization if multiple items
- [ ] Specific requests for next agent
- [ ] Links to files/resources
- [ ] VERDICT tag (ready_next / needs_revision / done)
- [ ] Next agent suggestion (→ agent_name)

### 9.4 Error Handling in Chains

**Graceful degradation**:
```python
# If Instagram API is down, don't fail entire chain
try:
    analytics = tools.get_analytics.py("posts")
except GraphError as e:
    if "rate_limit" in str(e):
        logger.warning("Instagram rate limited, using cached data")
        analytics = load_cached_analytics()
    else:
        raise
```

**Checkpoint and resume**:
```python
# Save state after each agent
def run_chain_with_checkpoint(chain_name, agents):
    state = load_checkpoint(chain_name)
    start_from = state.get("checkpoint", 0) if state else 0
    
    for idx, agent in enumerate(agents[start_from:], start=start_from):
        try:
            result = run_agent(agent, ...)
            save_checkpoint(chain_name, {"checkpoint": idx + 1, "results": {...}})
        except Exception as e:
            # Next retry will start from idx
            raise
```

**Notification on failure**:
```python
# Alert after 2 failures
if retry_count >= 2:
    telegram_send(
        TELEGRAM_ADMIN_CHAT_ID,
        f"⚠️ Chain {chain_id} failing repeatedly:\n{error}",
        confirm=False
    )
```

### 9.5 Testing Chain Design

Before deploying a new chain:

```python
def test_new_chain_design():
    """Validate chain design without hitting external APIs."""
    
    # 1. Check agents exist
    agents = ["olya", "rita", "dima", "manager"]
    for agent in agents:
        assert agent in AGENT_MODULES, f"Agent {agent} not found"
    
    # 2. Check context flows correctly
    for i, agent in enumerate(agents):
        next_agent = agents[i+1] if i < len(agents)-1 else None
        context = build_context(agent, next_agent, agents)
        assert context["chain_id"] is not None
        assert context["position"] == i
    
    # 3. Dry run with mocks
    with patch("base.run_agent") as mock_run:
        mock_run.return_value = ("mock output", [])
        pipeline.run_chain("new_chain", {"agents": agents})
        assert mock_run.call_count == len(agents)
    
    # 4. Check error handling
    with patch("base.run_agent", side_effect=Exception("Test error")):
        try:
            pipeline.run_chain_with_retry("new_chain", agents)
        except Exception as e:
            assert e is not None  # Should propagate or be handled
```

### 9.6 Chain Monitoring & Alerts

**Alerting rules**:
```python
# Alert if chain takes too long
if elapsed_ms > 600_000:  # >10 minutes
    alert(f"Chain {chain_id} took {elapsed_ms/1000:.0f}s (slow)")

# Alert if agent fails 3 times
if retry_count >= 3:
    alert(f"Chain {chain_id} agent {agent} failed {retry_count} times")

# Alert on configuration error (won't fix by retry)
if error_category == "config_error":
    alert(f"Configuration error in {chain_id}: {error}", priority="high")

# Alert on data validation failure
if "invalid_output" in error_category:
    alert(f"Agent {agent} produced invalid output in {chain_id}")
```

**Dashboard metrics**:
- Success rate per chain (target: >95%)
- Avg duration per chain (trend over time)
- Error frequency by type (identify patterns)
- Agent performance (who's slow, who's reliable)

---

## APPENDIX: Quick Reference

### Command Cheat Sheet

```bash
# Start webapp (browser UI)
cd mila-office && python webapp.py

# Start n8n webhook bridge
cd mila-office && python n8n_webhook.py

# Run chain manually
python pipeline.py content_week --notify

# Test single agent
python office.py  # Menu, select agent

# View logs
tail -f logs/webapp.log
tail -f logs/errors.jsonl
tail -f mila-office/logs/chain_*.log

# Check Instagram API
cd tools && python check_setup.py

# View chain status
curl http://localhost:5000/chains/api/active | jq

# View chain history
curl http://localhost:5000/chains/api/history?limit=10 | jq
```

### File Locations

| File | Purpose |
|------|---------|
| `base.py` | Core infrastructure (all agents use) |
| `memory.py` | Shared state (context, profile, events) |
| `pipeline.py` | Non-interactive chain runner |
| `n8n_webhook.py` | n8n ↔ agents bridge (port 5052) |
| `chain_retry.py` | Failure recovery & escalation |
| `error_monitor.py` | Centralized error logging |
| `logs/errors.jsonl` | All errors (structured JSON) |
| `logs/chain_*.log` | Per-chain detailed logs |
| `mila-office/memory/` | JSON state files (context, profile, events) |
| `reports/metrics.jsonl` | Performance metrics |

### Environment Variables

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...
MILA_MODEL=claude-opus-4-8

# Gemini (fallback)
GEMINI_KEY=AIza...
MILA_GEMINI_MODEL=gemini-2.5-flash

# Instagram
IG_ACCESS_TOKEN=...
IG_USER_ID=...
IG_API_FLOW=facebook  # or instagram_login

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
TELEGRAM_ADMIN_CHAT_ID=...

# n8n webhook
N8N_WEBHOOK_PORT=5052
N8N_WEBHOOK_TOKEN=...
N8N_STATUS_WEBHOOK_URL=http://localhost:5678/webhook/office-done
N8N_WEBHOOK_TIMEOUT=300

# Gamma API (PDF generation)
GAMMA_API_KEY=...
GAMMA_THEME_ID=...

# Gumroad
GUMROAD_ACCESS_TOKEN=...

# App tuning
MILA_READ_MAX_CHARS=40000    # Max file size in context
MILA_MAX_TOKENS=4096          # Max LLM output
MILA_GEMINI_THINKING_BUDGET=512  # Gemini thinking token limit
```

### Common API Calls

```bash
# Start a chain from n8n
curl -X POST http://localhost:5052/api/n8n/trigger-chain \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "chain_config": {"agents": ["marina", "victoria"]},
    "chain_id": "test_001"
  }'

# Check active chains
curl http://localhost:5000/chains/api/active

# Get chain details
curl http://localhost:5000/chains/api/details/test_001

# Get metrics
curl http://localhost:5000/chains/api/metrics

# Get agent performance
curl http://localhost:5000/chains/api/metrics | jq '.by_agent.marina'
```

### Debugging

```python
# In any Python script
import logging
logging.basicConfig(level=logging.DEBUG)

# In agent
user_input = "..."
context = system_prompt_builder.extract_context_from_message(user_input)
print("Context:", context)

# Check file paths
import base
p = base._safe_path("02-content/content-plan.md")
print("Resolved to:", p)

# List files
import base
base.list_files("02-content")

# Read raw event log
import memory
events = memory.read_events()
for e in events[-10:]:
    print(f"{e['timestamp']} {e['kind']} {e.get('agent', '')}")
```

---

## Summary

This guide covers:
1. **Architecture**: 11 agents + shared infrastructure + external integrations
2. **Context Flow**: How metadata propagates through chains
3. **Dashboard**: Real-time monitoring of chain execution
4. **Error Handling**: Retry strategies, escalation, alerts
5. **n8n Integration**: Triggering chains, webhooks, monitoring
6. **Testing**: Unit, integration, load tests
7. **Troubleshooting**: Common issues and debug commands
8. **Performance**: Optimization techniques and metrics
9. **Best Practices**: Chain design patterns, handoffs, validation

For production stability:
- ✓ Monitor `logs/errors.jsonl` daily
- ✓ Track chain success rate (target: >95%)
- ✓ Alert on configuration errors
- ✓ Archive old events monthly
- ✓ Test new chains with mocks before deploy
- ✓ Use n8n webhooks for async operations
- ✓ Keep agent system prompts focused (avoid >2 KB extra context)

**Questions?** Check chain_dashboard, error_monitor logs, or reach out to the development team.
