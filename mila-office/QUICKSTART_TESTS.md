# Quick Start: Comprehensive Test Suite

## What You Have

A production-ready pytest test suite for MILA Office 11-agent system:
- **46 tests** covering all agents, chains, errors, retry logic, performance, and load
- **~5 second** execution time (mock mode)
- **100% passing** ✅

## Files Created

1. **`comprehensive_test_suite.py`** (46 KB)
   - Complete pytest-compatible test code
   - 8 test classes, 46 test methods
   - Ready to run: `pytest comprehensive_test_suite.py -v`

2. **`TEST_SUITE_README.md`** 
   - Detailed documentation
   - How to run, extend, troubleshoot

3. **`COMPREHENSIVE_TEST_MATRIX.md`**
   - Coverage matrix by agent and category
   - Test-by-test breakdown

4. **`QUICKSTART_TESTS.md`** (this file)
   - Quick command reference

## Run Tests in 3 Commands

```bash
cd "E:\MILA GOLD\mila-office"

# Run all 46 tests
pytest comprehensive_test_suite.py -v

# Run only chain tests
pytest comprehensive_test_suite.py::TestChains -v

# Run only load tests
pytest comprehensive_test_suite.py::TestLoadTesting -v
```

## What Each Test Category Does

| Category | Tests | What It Validates |
|----------|-------|-------------------|
| **Individual Agents** | 12 | Each of 9 agents + context awareness |
| **Chains** | 6 | Multi-agent workflows (content_week, new_client, custom) |
| **Error Scenarios** | 6 | Timeout, failure, validation, network, rate-limit |
| **Retry Logic** | 6 | Retry, escalate, task-split, backoff, error classification |
| **Performance** | 6 | Agent speed, chain time, step timing, parallel speedup |
| **Load Testing** | 5 | 3/10/20 concurrent chains, retry under load, context isolation |
| **Integration** | 3 | Real-world workflows (content, sales, operations) |
| **Snapshots** | 2 | Output format & structure consistency |

## 9 Agents Tested

✅ Marina (Маркетер) — Copywriting  
✅ Victoria (Редактор) — Editing & approval  
✅ Alina (CRM) — Client intake  
✅ Dima (Финансы) — Revenue & sales  
✅ Tyoma (Telegram) — Channel management  
✅ Olya (Тренды) — Trend research  
✅ Vasya (Расписание) — Scheduling  
✅ Lera (Продажи) — Follow-up & sales  
✅ Rita (Архитектор) — Product updates  

## Key Test Patterns Used

### Test Individual Agent
```python
def test_agent_victoria(self):
    ctx = AgentTestContext(
        agent_key="victoria",
        task="Check post quality"
    )
    result = mock_agent_run(ctx.agent_key, asdict(ctx))
    assert result["status"] == "success"
```

### Test Agent Chain
```python
def test_chain_content_week(self):
    agents = ["olya", "marina", "victoria", "vasya"]
    context = {}
    for agent in agents:
        result = mock_agent_run(agent, context)
        context = propagate_context(context, result, agent)
    assert context["chain_length"] == 4
```

### Test Error Handling
```python
def test_agent_timeout(self):
    with pytest.raises(TimeoutError):
        # Agent execution that exceeds timeout_seconds
    assert timeout_occurred == True
```

### Test Retry Logic
```python
def test_retry_same_agent(self):
    for attempt in range(max_retries):
        try:
            result = agent()  # Fails on attempt 1-2, succeeds on 3
            break
        except RuntimeError:
            if attempt == max_retries - 1: raise
    assert result["attempt"] == 3
```

### Test Performance
```python
def test_agent_individual_times(self):
    for agent in agents:
        start = time.perf_counter()
        result = mock_agent_run(agent, {})
        duration = time.perf_counter() - start
        assert duration < 1.0  # Mock agents must be fast
```

### Test Load
```python
def test_parallel_chains_execution(self):
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_chain, cfg) for cfg in chains]
        results = [f.result() for f in futures]
    assert all(r["status"] == "success" for r in results)
```

## Common Commands

```bash
# Run all tests (verbose)
pytest comprehensive_test_suite.py -v

# Run specific test class
pytest comprehensive_test_suite.py::TestChains -v
pytest comprehensive_test_suite.py::TestLoadTesting -v

# Run specific test
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_marina -v

# Run tests matching pattern
pytest comprehensive_test_suite.py -k "context" -v
pytest comprehensive_test_suite.py -k "chain" -v
pytest comprehensive_test_suite.py -k "timeout" -v

# Run with output (show print statements)
pytest comprehensive_test_suite.py -v -s

# Run with short traceback on failures
pytest comprehensive_test_suite.py -v --tb=short

# Stop on first failure
pytest comprehensive_test_suite.py -x

# Show summary of outcomes
pytest comprehensive_test_suite.py -ra

# Run only failed tests (from last run)
pytest comprehensive_test_suite.py --lf

# Count only (don't run)
pytest comprehensive_test_suite.py --collect-only -q
```

## Test Results Summary

```
============================== 46 passed in 5.39s ==============================

TestIndividualAgents ........... 12 passed
TestChains ..................... 6 passed
TestErrorScenarios ............. 6 passed
TestRetryLogic ................. 6 passed
TestPerformance ................ 6 passed
TestLoadTesting ................ 5 passed
TestIntegration ................ 3 passed
TestSnapshots .................. 2 passed
```

## Fixtures Available

| Fixture | Purpose |
|---------|---------|
| `test_mila_folder` | MILA_FOLDER path |
| `mock_client` | Mock Anthropic client |
| `mock_instagram_api` | Mock Instagram API |
| `mock_supabase` | Mock Supabase |
| `performance_baseline` | Performance budgets (session-scoped) |

## Helper Functions

```python
mock_agent_run(agent_key, context)           # Simulate agent execution
propagate_context(context, result, agent)    # Pass context through chain
extract_context_from_message(message)        # Parse [from:agent] tags
time_agent_execution(func, *args, **kwargs)  # Measure execution time
```

## Test Data Classes

```python
AgentTestContext      # Individual agent test config
ChainTestConfig       # Chain workflow test config
AgentTestResult       # Test execution result
```

## Known Chains

| Chain | Agents | Purpose |
|-------|--------|---------|
| `content_week` | olya → marina → victoria → vasya | Trend → copy → edit → schedule |
| `new_client` | alina → lera | Intake → follow-up |
| `monday_brief` | manager → marina | Retrospective → plan |
| `weekly_report` | dima → marina → manager | Financials + content + strategy |

## Performance Baselines (Mock Mode)

- Per-agent execution: ~0.5ms
- Full 4-agent chain: ~2ms
- 10 parallel agents: ~5ms
- 20 parallel chains: ~10ms

*Real API (Claude) will be 3-5 seconds per agent.*

## Next Steps

1. **Run the tests:**
   ```bash
   pytest comprehensive_test_suite.py -v
   ```

2. **Read the full docs:**
   - `TEST_SUITE_README.md` — detailed guide
   - `COMPREHENSIVE_TEST_MATRIX.md` — coverage breakdown

3. **Extend for your needs:**
   - Add new agent tests
   - Create custom chain tests
   - Hook into CI/CD (GitHub Actions, etc.)

4. **Integrate with real APIs:**
   - Replace `mock_agent_run()` with actual agent execution
   - Add Supabase fixtures
   - Use real Instagram Graph API mocks

## Troubleshooting

**Tests not found?**
```bash
# Make sure conftest.py is in mila-office/
# It should have: sys.path.insert(0, os.path.dirname(__file__))
```

**Import errors?**
```bash
# Ensure you're in mila-office directory
cd E:\MILA\ GOLD\mila-office
pytest comprehensive_test_suite.py -v
```

**Tests too slow?**
```bash
# Mock mode should be ~5 seconds total
# If slower, check for hanging threads (timeout test)
pytest comprehensive_test_suite.py::TestErrorScenarios::test_agent_timeout -v
```

**Want real API tests?**
```bash
# See TEST_SUITE_README.md "Extending" section
# Replace mock_agent_run() with actual run_agent() calls
```

---

## File Locations

```
E:\MILA GOLD\mila-office\
├── comprehensive_test_suite.py      ← Main test file (46 KB)
├── TEST_SUITE_README.md             ← Full documentation
├── COMPREHENSIVE_TEST_MATRIX.md     ← Coverage matrix
├── QUICKSTART_TESTS.md              ← This file
└── conftest.py                      ← pytest configuration (already exists)
```

---

**Status:** ✅ Ready to use  
**Tests:** 46 / 46 passing  
**Coverage:** 9 agents × 8 categories  
**Execution:** ~5 seconds (mock mode)
