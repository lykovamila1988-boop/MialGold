# MILA Office Comprehensive Test Suite — Complete Index

## Overview

Complete pytest-compatible test suite for the 11-agent MILA Office system. Covers all 9 core agents (Marina, Victoria, Alina, Dima, Tyoma, Olya, Vasya, Lera, Rita) plus manager/producer roles.

**Status:** ✅ All 46 tests passing  
**Execution Time:** ~5 seconds (mock mode)  
**Coverage:** Individual agents, chains, errors, retry logic, performance, load testing, integration

---

## Files Included

### 1. Main Test Suite
**`comprehensive_test_suite.py`** (1,116 lines, 46 KB)

Complete, production-ready pytest file with:
- 46 test methods across 8 test classes
- Mock-based testing (no real API calls required)
- Fixtures for agents, contexts, performance baselines
- Helper functions for context propagation and timing
- Ready to integrate with CI/CD

**Structure:**
```
comprehensive_test_suite.py
├── TestIndividualAgents (12 tests)
│   ├── 9 core agents
│   └── 3 context-aware scenarios
├── TestChains (6 tests)
│   ├── Known chains (content_week, new_client)
│   └── Custom chains + context propagation
├── TestErrorScenarios (6 tests)
│   ├── Timeout, failure, invalid verdict
│   └── Network error, rate limit
├── TestRetryLogic (6 tests)
│   ├── Retry same agent
│   ├── Escalation, task-split
│   └── Backoff, error classification
├── TestPerformance (6 tests)
│   ├── Individual agent times
│   ├── Chain total time
│   └── Per-step breakdown
├── TestLoadTesting (5 tests)
│   ├── 3, 10, 20 concurrent chains
│   └── Retry under load, context isolation
├── TestIntegration (3 tests)
│   ├── Content workflow
│   ├── Sales workflow
│   └── Operations workflow
└── TestSnapshots (2 tests)
    ├── Output format consistency
    └── Chain structure validation
```

---

### 2. Documentation Files

**`QUICKSTART_TESTS.md`** (295 lines, 8.4 KB)
- Quick reference for running tests
- Common commands (pytest, specific tests, patterns)
- Test categories at a glance
- Troubleshooting tips
- **Read this first** for quick start

**`TEST_SUITE_README.md`** (436 lines, 13 KB)
- Comprehensive guide
- How to run, extend, debug
- Detailed test structure explanation
- Performance notes & CI/CD integration
- Fixture and helper function reference

**`COMPREHENSIVE_TEST_MATRIX.md`** (367 lines, 13 KB)
- Coverage matrix (agents × categories)
- Test-by-test breakdown
- Expected behaviors & assertions
- Performance baselines
- Future enhancements

**`TEST_SUITE_INDEX.md`** (this file)
- Navigation guide for all test suite files
- What to read for different needs

---

## Quick Start

### 1. Run All Tests
```bash
cd "E:\MILA GOLD\mila-office"
pytest comprehensive_test_suite.py -v
```

**Expected output:**
```
============================== 46 passed in 5.17s ==============================
```

### 2. Run Specific Category
```bash
# Individual agents
pytest comprehensive_test_suite.py::TestIndividualAgents -v

# Chain workflows
pytest comprehensive_test_suite.py::TestChains -v

# Load testing
pytest comprehensive_test_suite.py::TestLoadTesting -v
```

### 3. Run Single Test
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_content_week -v
```

---

## What Each File Does

### If You Want To...

| Goal | Read | Command |
|------|------|---------|
| **Start testing immediately** | `QUICKSTART_TESTS.md` | `pytest comprehensive_test_suite.py -v` |
| **Understand test structure** | `TEST_SUITE_README.md` | `pytest comprehensive_test_suite.py::TestChains -v` |
| **See coverage breakdown** | `COMPREHENSIVE_TEST_MATRIX.md` | `pytest comprehensive_test_suite.py --collect-only` |
| **Navigate files** | `TEST_SUITE_INDEX.md` | This file |
| **Run the tests** | `comprehensive_test_suite.py` | `pytest comprehensive_test_suite.py -v` |

### Documentation Reading Order

**New to the tests?**
1. Start: `QUICKSTART_TESTS.md` (3 min read)
2. Run: `pytest comprehensive_test_suite.py -v` (5 sec)
3. Deep dive: `TEST_SUITE_README.md` (10 min read)

**Need to extend tests?**
1. Read: `TEST_SUITE_README.md` section "Extending the Tests"
2. Reference: `COMPREHENSIVE_TEST_MATRIX.md` for patterns
3. Edit: `comprehensive_test_suite.py` and add your test

**Want coverage details?**
1. Review: `COMPREHENSIVE_TEST_MATRIX.md`
2. Correlate: with `comprehensive_test_suite.py` line numbers

---

## Test Categories Explained

### Individual Agents (12 tests)
Tests each of 9 agents independently:
- Marina (Маркетер) — Copywriting
- Victoria (Редактор) — Editing & approval
- Alina (CRM) — Client intake
- Dima (Финансы) — Revenue
- Tyoma (Telegram) — Channel management
- Olya (Тренды) — Trend research
- Vasya (Расписание) — Scheduling
- Lera (Продажи) — Sales follow-up
- Rita (Архитектор) — Product updates

Plus 3 context-aware tests (agent receiving from another agent).

**File:** `comprehensive_test_suite.py` lines 259–345

### Chains (6 tests)
Tests multi-agent workflows:
- `content_week`: olya → marina → victoria → vasya (trend → copy → edit → schedule)
- `new_client`: alina → lera (intake → follow-up)
- Custom chains: marina → victoria → vasya
- Standalone: rita
- Context propagation through entire chain
- [from:agent] tag parsing

**File:** `comprehensive_test_suite.py` lines 364–525

### Error Scenarios (6 tests)
Tests robustness:
- Timeout / hanging agent
- Agent failure / exception
- Invalid verdict (Victoria's approve/reject/request_revisions)
- Chain failure at step 2
- Network unreachable
- Rate limit (429)

**File:** `comprehensive_test_suite.py` lines 537–630

### Retry Logic (6 tests)
Tests resilience & recovery:
- Retry same agent (flaky agent succeeds on retry)
- Escalate to manager (max_retries exceeded)
- Split task on failure (large task → subtasks)
- Exponential backoff (0.1s → 0.2s → 0.4s)
- Retry counter increments
- No-retry on validation errors

**File:** `comprehensive_test_suite.py` lines 648–741

### Performance (6 tests)
Tests execution speed:
- Individual agent time (all < 1s for mock)
- All 9 agents performance table
- Full 4-agent chain time (< 5s for mock)
- Parallel vs. sequential speedup
- Per-step timing breakdown
- Performance benchmarks

**File:** `comprehensive_test_suite.py` lines 758–832

### Load Testing (5 tests)
Tests concurrent execution:
- 3 parallel chains
- 10 concurrent agents
- 10 agents with 30% failure rate + retry
- Context isolation (no crosstalk)
- 20+ concurrent chains (max stress)

**File:** `comprehensive_test_suite.py` lines 845–939

### Integration (3 tests)
Tests real workflows end-to-end:
- Content workflow: olya → marina → victoria → vasya
- Sales workflow: alina → lera
- Operations workflow: dima → marina → olya

**File:** `comprehensive_test_suite.py` lines 957–1008

### Snapshots (2 tests)
Tests consistency & regressions:
- Agent output format (all return status, agent, timestamp)
- Chain result structure (chain_length, previous_results, last_agent)

**File:** `comprehensive_test_suite.py` lines 1024–1050

---

## Key Concepts Tested

### Context Propagation
Context flows through chains:
```python
context = {
    "chain_id": "content_week",
    "initiator": "human_user",
    "previous_results": {
        "olya": {...},
        "marina": {...},
        ...
    },
    "last_agent": "vasya",
    "chain_length": 4
}
```

### Agent-to-Agent Communication
Messages use `[from:agent_name]` tags:
```
"Проверь пост [from:marina]"  # Victoria knows Marina is sender
```

### Retry Strategies
- Exponential backoff: 0.1s → 0.2s → 0.4s
- Retry retryable errors (timeout, rate limit)
- Don't retry validation errors
- Escalate after max_retries exceeded

### Performance Baselines (Mock)
- Per-agent: ~0.5ms
- Full chain: ~2ms
- 10 parallel: ~5ms
- 20 parallel: ~10ms

---

## Test Data

### 9 Agents
```python
AGENTS_11 = [
    ("marina", "Марина", marina_module),
    ("victoria", "Виктория", victoria),
    ("alina", "Алина", alina),
    ("dima", "Дима", dima),
    ("tyoma", "Тёма", tyoma),
    ("olya", "Оля", olya),
    ("vasya", "Вася", vasya),
    ("lera", "Лера", lera),
    ("rita", "Рита", rita),
]
```

### 4 Known Chains
```python
KNOWN_CHAINS = {
    "content_week": ["olya", "marina", "victoria", "vasya"],
    "new_client": ["alina", "lera"],
    "monday_brief": ["manager", "marina"],
    "weekly_report": ["dima", "marina", "manager"],
}
```

---

## Commands Reference

### Run Everything
```bash
pytest comprehensive_test_suite.py -v                    # All 46 tests
pytest comprehensive_test_suite.py -q                    # Quiet (just summary)
pytest comprehensive_test_suite.py --tb=short            # Short traceback
```

### Run by Category
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents -v
pytest comprehensive_test_suite.py::TestChains -v
pytest comprehensive_test_suite.py::TestErrorScenarios -v
pytest comprehensive_test_suite.py::TestRetryLogic -v
pytest comprehensive_test_suite.py::TestPerformance -v
pytest comprehensive_test_suite.py::TestLoadTesting -v
pytest comprehensive_test_suite.py::TestIntegration -v
pytest comprehensive_test_suite.py::TestSnapshots -v
```

### Run by Pattern
```bash
pytest comprehensive_test_suite.py -k "context" -v       # Context tests
pytest comprehensive_test_suite.py -k "chain" -v         # Chain tests
pytest comprehensive_test_suite.py -k "parallel" -v      # Parallel tests
pytest comprehensive_test_suite.py -k "timeout" -v       # Timeout tests
```

### Run Single Test
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_content_week -v
```

### Run with Options
```bash
pytest comprehensive_test_suite.py -v -s                 # Show output
pytest comprehensive_test_suite.py -v --tb=long          # Full traceback
pytest comprehensive_test_suite.py -x                    # Stop on first failure
pytest comprehensive_test_suite.py --lf                  # Last failed
pytest comprehensive_test_suite.py -ra                   # Result summary
```

---

## Fixtures Available

| Fixture | Purpose | Scope |
|---------|---------|-------|
| `test_mila_folder` | MILA_FOLDER path | function |
| `mock_client` | Mock Anthropic client | function |
| `mock_instagram_api` | Mock Instagram API | function |
| `mock_supabase` | Mock Supabase | function |
| `performance_baseline` | Performance budgets | session |

---

## Helper Functions in Test Suite

```python
mock_agent_run(agent_key, context_data)         # Simulate agent execution
propagate_context(context, result, agent_key)   # Pass context through chain
extract_context_from_message(message)           # Parse [from:agent] tags
time_agent_execution(func, *args, **kwargs)     # Measure execution time
```

---

## Extensions & CI/CD

### GitHub Actions
```yaml
- name: Run test suite
  run: |
    cd mila-office
    pip install pytest
    pytest comprehensive_test_suite.py -v
```

### GitLab CI
```yaml
test:
  image: python:3.13
  script:
    - pip install pytest
    - cd mila-office
    - pytest comprehensive_test_suite.py -v
```

---

## File Location Map

```
E:\MILA GOLD\mila-office\
├── comprehensive_test_suite.py          ← Main test file (1,116 lines)
├── TEST_SUITE_README.md                 ← Full documentation (436 lines)
├── COMPREHENSIVE_TEST_MATRIX.md         ← Coverage breakdown (367 lines)
├── QUICKSTART_TESTS.md                  ← Quick reference (295 lines)
├── TEST_SUITE_INDEX.md                  ← This file (navigation guide)
└── conftest.py                          ← pytest configuration (already exists)
```

---

## How to Use This Index

**Want to run tests?** → Go to `QUICKSTART_TESTS.md`

**Want detailed info?** → Read `TEST_SUITE_README.md`

**Want to see coverage?** → Check `COMPREHENSIVE_TEST_MATRIX.md`

**Want to run a test?** → Use commands in "Commands Reference" section above

**Want to extend tests?** → See `TEST_SUITE_README.md` → "Extending the Tests"

---

## Maintenance & Updates

### When to Update Tests
- New agents added
- Chain workflows changed
- Error handling modified
- Performance SLAs updated
- Context structure extended

### How to Update
1. Edit `comprehensive_test_suite.py`
2. Add new test class or test method
3. Run `pytest comprehensive_test_suite.py -v`
4. Update documentation files

---

## Summary

| Aspect | Details |
|--------|---------|
| **Total Tests** | 46 |
| **Test Classes** | 8 |
| **Agents Covered** | 9 |
| **Known Chains** | 4 |
| **Execution Time** | ~5 seconds |
| **Status** | ✅ All passing |
| **Lines of Code** | 1,116 |
| **File Size** | 46 KB |
| **Documentation** | ~1,100 lines |

---

**Ready to test?** Run: `pytest comprehensive_test_suite.py -v`

**Need help?** Read: `QUICKSTART_TESTS.md`

**Want details?** See: `TEST_SUITE_README.md`
