MILA OFFICE — INTEGRATION DOCUMENTATION
========================================

NEW INTEGRATION GUIDES CREATED: 2026-06-08
==========================================

This directory now contains THREE comprehensive integration guides:

1. FULL_INTEGRATION_GUIDE.md (80 KB, 2,039 lines)
   ════════════════════════════════════════════════════
   THE MAIN GUIDE — Start here for everything.

   Sections:
   • System architecture overview (with diagrams)
   • How context flows through agents (real examples)
   • Dashboard usage & API endpoints
   • Retry & error handling strategies
   • n8n integration with code examples
   • Testing strategies (unit, integration, load)
   • Troubleshooting common issues
   • Performance tuning & optimization
   • Best practices for chain design

   Use this when:
     ✓ Understanding system architecture
     ✓ Designing new chains
     ✓ Debugging failures
     ✓ Integrating with n8n
     ✓ Deploying for production


2. ARCHITECTURE_DIAGRAMS.txt (38 KB, 614 lines)
   ════════════════════════════════════════════
   DETAILED ASCII DIAGRAMS — Visual reference guide.

   Includes:
   • System overview diagram (all components)
   • Data flow (interactive vs. n8n chains)
   • Agent-to-agent context propagation
   • Dashboard timeline view mockup
   • Error recovery with retry/escalation
   • n8n webhook integration timeline
   • File operations & path resolution
   • Memory sharing with locking
   • Error handling decision tree

   Use this when:
     ✓ Need visual understanding of flows
     ✓ Explaining system to new developers
     ✓ Designing complex chains
     ✓ Debugging sequence issues


3. INTEGRATION_GUIDE_SUMMARY.txt (6 KB)
   ══════════════════════════════════════
   QUICK REFERENCE — Navigation guide.

   Contains:
   • What's covered in each section
   • Quick start commands
   • File location reference
   • Environment variables
   • Debugging snippets
   • "When to read" guide by use case

   Use this when:
     ✓ Quick lookups (command cheat sheet)
     ✓ Finding which section covers your issue
     ✓ Environment variable reference


RECOMMENDED READING ORDER:
==========================

For ALL users:
  1. Read: ARCHITECTURE_DIAGRAMS.txt (get visual overview)
  2. Read: INTEGRATION_GUIDE_SUMMARY.txt (understand structure)

For Developers (building features):
  3a. → FULL_INTEGRATION_GUIDE.md Section 1 (architecture)
  3b. → FULL_INTEGRATION_GUIDE.md Section 9 (chain design)
  3c. → FULL_INTEGRATION_GUIDE.md Section 6 (testing)

For DevOps / Maintainers (running system):
  3a. → FULL_INTEGRATION_GUIDE.md Section 3 (dashboard)
  3b. → FULL_INTEGRATION_GUIDE.md Section 7 (troubleshooting)
  3c. → FULL_INTEGRATION_GUIDE.md Section 8 (performance)

For n8n Workflow Engineers:
  3a. → FULL_INTEGRATION_GUIDE.md Section 5 (n8n examples)
  3b. → ARCHITECTURE_DIAGRAMS.txt (webhook flow diagram)
  3c. → FULL_INTEGRATION_GUIDE.md Section 4 (error handling)

For Debugging Issues:
  3a. → FULL_INTEGRATION_GUIDE.md Section 7 (troubleshooting)
  3b. → ARCHITECTURE_DIAGRAMS.txt (error handling diagram)
  3c. → INTEGRATION_GUIDE_SUMMARY.txt (debug commands)


KEY TOPICS COVERED:
===================

✓ System Architecture (Section 1)
  - 11 agents + infrastructure overview
  - Data flow diagrams
  - Component responsibilities
  - File layout

✓ Context Flow (Section 2)
  - How metadata propagates between agents
  - Code examples for context extraction
  - Real "Content Week" chain walkthrough
  - Context tags in messages

✓ Dashboard (Section 3)
  - http://127.0.0.1:5000 usage
  - API endpoints (GET /chains/api/*)
  - Web UI features
  - Querying dashboard data

✓ Error Handling (Section 4)
  - Error detection & logging (errors.jsonl)
  - Retry strategies (agent, chain, tool level)
  - Error categorization (config, transient, agent)
  - Full error flow example

✓ n8n Integration (Section 5)
  - Setup & authentication
  - Triggering chains from n8n
  - Monitoring status (polling vs webhooks)
  - Real examples (Instagram analytics, New Client intake)
  - Error handling in workflows

✓ Testing (Section 6)
  - Unit testing single agents
  - Integration testing chains
  - Load testing (concurrent)
  - Error recovery testing
  - pytest commands
  - Mocking external services

✓ Troubleshooting (Section 7)
  - Common issues with solutions:
    * Agent doesn't respond
    * Instagram permission errors
    * Chain timeout
    * Memory locks
    * Session token issues
    * Retry loops
  - Debug commands (curl, pytest, Python)
  - Performance profiling

✓ Performance Tuning (Section 8)
  - LLM choice (Anthropic vs Gemini)
  - Input context reduction
  - Prompt caching
  - Parallel chains
  - File I/O optimization
  - Database queries
  - Memory management

✓ Best Practices (Section 9)
  - Chain design patterns (sequential, parallel, conditional)
  - Context design guidelines
  - Agent handoff checklist
  - Error handling degradation
  - Checkpoint & resume
  - Chain design testing
  - Monitoring & alerting


QUICK COMMANDS:
===============

Start system:
  cd mila-office && python webapp.py          # Browser UI (5000)
  cd mila-office && python n8n_webhook.py     # n8n bridge (5052)

Run chains:
  python pipeline.py content_week --notify    # Run manually
  python office.py                            # CLI menu

View status:
  curl http://localhost:5000/chains/api/active | jq
  curl http://localhost:5000/chains/api/metrics | jq

View logs:
  tail -f logs/webapp.log
  tail -f logs/errors.jsonl
  tail -f mila-office/logs/chain_*.log

Test:
  pytest tests/ -v
  pytest comprehensive_test_suite.py -v


EXISTING INTEGRATION DOCS (for reference):
===========================================

These docs already exist in the repo:
  • N8N_INSTAGRAM_REPORTS.md — n8n analytics workflow
  • CHAIN_DASHBOARD_INTEGRATION.md — dashboard blueprint
  • N8N_INTEGRATION_EXAMPLES.md — webhook examples
  • MODULAR_ARCHITECTURE.md — agent module structure

The NEW guides (FULL_INTEGRATION_GUIDE.md, ARCHITECTURE_DIAGRAMS.txt)
consolidate and expand on these, providing unified reference.


FILE ORGANIZATION:
===================

mila-office/
├─ FULL_INTEGRATION_GUIDE.md              ← START HERE (80 KB)
├─ ARCHITECTURE_DIAGRAMS.txt              ← Visual guide (38 KB)
├─ INTEGRATION_GUIDE_SUMMARY.txt          ← Quick reference (6 KB)
├─ README_INTEGRATION_DOCS.txt            ← This file
│
├─ N8N_INSTAGRAM_REPORTS.md               (existing)
├─ CHAIN_DASHBOARD_INTEGRATION.md         (existing)
├─ N8N_INTEGRATION_EXAMPLES.md            (existing)
├─ MODULAR_ARCHITECTURE.md                (existing)
│
├─ base.py                                (core infra)
├─ memory.py                              (shared state)
├─ pipeline.py                            (chain runner)
├─ webapp.py                              (browser UI)
├─ n8n_webhook.py                         (n8n bridge)
├─ chain_dashboard.py                     (dashboard)
├─ error_monitor.py                       (error logging)
├─ comprehensive_test_suite.py            (test suite)
│
└─ [11 agent modules]
   ├─ agent.py (marina)
   ├─ victoria.py
   ├─ rita.py
   └─ ... etc


WHAT'S NEXT?
============

1. Read FULL_INTEGRATION_GUIDE.md (main guide)
   → Understand full system architecture

2. Use ARCHITECTURE_DIAGRAMS.txt for visual reference
   → Bookmark for complex topics

3. Keep INTEGRATION_GUIDE_SUMMARY.txt handy
   → Quick command/variable lookups

4. When building/deploying:
   → Section 9 (Best Practices)
   → Section 6 (Testing)

5. When debugging:
   → Section 7 (Troubleshooting)
   → Appendix (Debug Commands)

6. For n8n work:
   → Section 5 (n8n Integration)
   → ARCHITECTURE_DIAGRAMS.txt (webhook flow)


FEEDBACK & UPDATES:
===================

If you find:
  • Missing sections
  • Confusing explanations
  • Outdated information
  • Examples that don't work

Please update the guide or create an issue.
The goal is to keep this as THE authoritative reference
for MILA Office system integration & operations.


Questions?
==========
  → Start with INTEGRATION_GUIDE_SUMMARY.txt (quick lookup)
  → Find section in FULL_INTEGRATION_GUIDE.md
  → Use ARCHITECTURE_DIAGRAMS.txt for visual explanation
  → Check logs/ directory for actual error details
  → Run debug commands from Appendix

Last Updated: 2026-06-08
Created by: Claude Code Haiku 4.5
Status: Production Ready
