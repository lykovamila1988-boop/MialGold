# TEST_COMMANDS.md — Comprehensive Testing Guide for MILA Office

Complete reference for running tests, benchmarking performance, load testing, and CI/CD integration for the 11-agent MILA Office system.

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Running All Tests](#running-all-tests)
3. [Testing Specific Agents](#testing-specific-agents)
4. [Testing Specific Chains](#testing-specific-chains)
5. [Performance Benchmarking](#performance-benchmarking)
6. [Load Testing](#load-testing)
7. [Adding New Tests](#adding-new-tests)
8. [CI/CD Integration](#cicd-integration)
9. [Test Environment Setup](#test-environment-setup)
10. [Troubleshooting](#troubleshooting)

---

## Quick Reference

### Setup
```bash
cd "E:\MILA GOLD\mila-office"
pip install -r requirements.txt  # If not already installed
pip install pytest pytest-cov pytest-timeout pytest-xdist
```

### Run All Tests
```bash
pytest comprehensive_test_suite.py -v
```

### Run by Category
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents -v         # 12 tests
pytest comprehensive_test_suite.py::TestChains -v                   # 6 tests
pytest comprehensive_test_suite.py::TestErrorScenarios -v           # 6 tests
pytest comprehensive_test_suite.py::TestRetryLogic -v               # 6 tests
pytest comprehensive_test_suite.py::TestPerformance -v              # 6 tests
pytest comprehensive_test_suite.py::TestLoadTesting -v              # 5 tests
pytest comprehensive_test_suite.py::TestIntegration -v              # 3 tests
pytest comprehensive_test_suite.py::TestSnapshots -v                # 2 tests
```

### Run Specific Agent Test
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_marina -v
```

### Run Specific Chain Test
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_content_week -v
```

---

## Running All Tests

### 1. Basic Test Run (46 tests total)
```bash
cd "E:\MILA GOLD\mila-office"
pytest comprehensive_test_suite.py -v
```

**Expected output:**
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

### 2. Verbose with All Output
```bash
pytest comprehensive_test_suite.py -v -s
```
Shows print statements and logging output during test execution.

### 3. With Short Traceback
```bash
pytest comprehensive_test_suite.py -v --tb=short
```
Useful for debugging failures — shows cleaner error messages.

### 4. Stop on First Failure
```bash
pytest comprehensive_test_suite.py -x
```
Halts test execution immediately when a test fails.

### 5. Run Only Failed Tests (from last run)
```bash
pytest comprehensive_test_suite.py --lf -v
```
Reruns only tests that failed in the previous test run.

### 6. Run Only Tests That Changed Files
```bash
pytest comprehensive_test_suite.py --changed-files -v
```
Only runs tests for files that have been modified since last commit.

### 7. Generate Test Report Summary
```bash
pytest comprehensive_test_suite.py -ra
```
Shows a summary of all outcomes (passed, failed, skipped, xfailed, xpassed, error).

### 8. Count Tests Without Running
```bash
pytest comprehensive_test_suite.py --collect-only -q
```
Lists all 46 tests without executing them.

---

## Testing Specific Agents

Each agent is tested individually with context awareness. 9 agents covered:

### Marina (Маркетер) — Content Strategy & Copywriting
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_marina -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_marina_with_context -v
```

### Victoria (Редактор) — Editing & Quality Approval
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_victoria -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_victoria_with_marina_context -v
```

### Alina (CRM) — Client Intake & Lead Management
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_alina -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_alina_with_context -v
```

### Dima (Финансы) — Revenue & Gumroad Sales
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_dima -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_dima_with_context -v
```

### Tyoma (Telegram) — Channel Management & Posting
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_tyoma -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_tyoma_with_context -v
```

### Olya (Тренды) — Trend Research & Discovery
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_olya -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_olya_with_context -v
```

### Vasya (Расписание) — Publication Scheduling
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_vasya -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_vasya_with_context -v
```

### Lera (Продажи) — Follow-up & Sales Consultation
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_lera -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_lera_with_context -v
```

### Rita (Архитектор) — Product Structure & Praktikum Updates
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_rita -v
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_rita_with_context -v
```

### All Individual Agents Together
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents -v
```

### Run Tests by Agent Name Pattern
```bash
pytest comprehensive_test_suite.py -k "marina" -v              # Marina only
pytest comprehensive_test_suite.py -k "victoria" -v            # Victoria only
pytest comprehensive_test_suite.py -k "context" -v             # All context tests
pytest comprehensive_test_suite.py -k "agent_" -v              # All agent tests
```

---

## Testing Specific Chains

Chains represent multi-agent workflows with context propagation.

### 1. Content Week Chain
**Workflow:** Trend research → Copywriting → Editing → Scheduling
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_content_week -v
```

Agents: olya → marina → victoria → vasya

### 2. New Client Chain
**Workflow:** Client intake → Personalized follow-up
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_new_client -v
```

Agents: alina → lera

### 3. Monday Brief Chain
**Workflow:** Weekly retrospective → Content plan
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_monday_brief -v
```

Agents: manager → marina

### 4. Weekly Report Chain
**Workflow:** Financial review → Content metrics → Strategy
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_weekly_report -v
```

Agents: dima → marina → manager

### 5. Custom Chain Flow
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_custom_flow -v
```

### 6. Parallel Chains
```bash
pytest comprehensive_test_suite.py::TestChains::test_parallel_chains_execution -v
```

### Run All Chain Tests
```bash
pytest comprehensive_test_suite.py::TestChains -v
```

### Run Chain Tests by Name Pattern
```bash
pytest comprehensive_test_suite.py -k "chain" -v
pytest comprehensive_test_suite.py -k "content_week" -v
pytest comprehensive_test_suite.py -k "parallel" -v
```

### Test Chain Context Propagation
To verify that context flows correctly through each agent in a chain:

```bash
pytest comprehensive_test_suite.py::TestChains -k "chain" -v -s
```

The `-s` flag shows context at each step.

---

## Performance Benchmarking

Measure agent execution speed, chain performance, and parallel speedup.

### 1. Individual Agent Performance
```bash
pytest comprehensive_test_suite.py::TestPerformance::test_agent_individual_times -v
```

Measures execution time for each of 9 agents:
- Marina (Маркетер)
- Victoria (Редактор)
- Alina (CRM)
- Dima (Финансы)
- Tyoma (Telegram)
- Olya (Тренды)
- Vasya (Расписание)
- Lera (Продажи)
- Rita (Архитектор)

**Expected results (mock mode):**
- Per agent: ~0.5ms
- Should all pass threshold (< 30s per agent with real API)

### 2. Full Chain Performance
```bash
pytest comprehensive_test_suite.py::TestPerformance::test_full_chain_execution_time -v
```

Measures total time for complete 4-agent chain (olya → marina → victoria → vasya).

**Expected results (mock mode):**
- Full chain: ~2ms
- Should pass threshold (< 120s with real API)

### 3. Per-Step Timing Within Chain
```bash
pytest comprehensive_test_suite.py::TestPerformance::test_chain_time_per_step -v
```

Breaks down timing for each step in the chain.

**Example output:**
```
olya:    0.5ms
marina:  0.5ms
victoria: 0.5ms
vasya:   0.5ms
Total:   2.0ms
```

### 4. Parallel Chain Speedup
```bash
pytest comprehensive_test_suite.py::TestPerformance::test_parallel_chain_speedup -v
```

Compares sequential vs. parallel execution:
- Sequential 3 chains: ~6ms
- Parallel 3 chains: ~3ms
- Speedup factor: 2.0x (expected 1.8x)

### 5. Concurrent Agent Performance
```bash
pytest comprehensive_test_suite.py::TestPerformance::test_concurrent_agent_execution -v
```

Tests 10 agents running in parallel.

**Expected results:**
- ~5ms total (not 5ms per agent)
- Good parallelization

### 6. All Performance Tests
```bash
pytest comprehensive_test_suite.py::TestPerformance -v
```

Runs all 6 performance benchmarks.

### Custom Performance Analysis

To measure real API performance (with actual Claude calls):

```bash
# Disable mock mode (if your test suite supports it)
export MOCK_MODE=false
pytest comprehensive_test_suite.py::TestPerformance -v

# Or use pytest markers:
pytest comprehensive_test_suite.py -m "not mock" -v
```

### Performance Report with Profiling
```bash
pytest comprehensive_test_suite.py::TestPerformance -v --durations=10
```

Shows the 10 slowest test functions.

### Performance Baselines (Mock Mode vs. Real API)

| Operation | Mock | Real API |
|-----------|------|----------|
| Single agent | 0.5ms | 3–5s |
| 4-agent chain | 2ms | 15–25s |
| 10 parallel agents | 5ms | 30–50s |
| 20 parallel chains | 10ms | 120–300s |

---

## Load Testing

Stress-test the system with concurrent agents and chains.

### 1. Three Parallel Chains
```bash
pytest comprehensive_test_suite.py::TestLoadTesting::test_parallel_chains_execution -v
```

Runs 3 chains concurrently (content_week, new_client, weekly_report).

**Expected results:**
- All 3 chains complete successfully
- Context isolation verified (no crosstalk)

### 2. Ten Concurrent Agents
```bash
pytest comprehensive_test_suite.py::TestLoadTesting::test_concurrent_agents -v
```

Spawns 10 agents at the same time.

**Expected results:**
- All 10 agents complete
- Thread safety verified
- No race conditions

### 3. Retry Logic Under Load
```bash
pytest comprehensive_test_suite.py::TestLoadTesting::test_load_with_retry_logic -v
```

3 parallel chains where some agents fail and retry.

**Expected results:**
- Retries work without deadlock
- Load doesn't prevent retry backoff

### 4. Context Isolation Under Load
```bash
pytest comprehensive_test_suite.py::TestLoadTesting::test_context_isolation_under_load -v
```

Verifies each chain's context stays isolated (no cross-contamination).

**Expected results:**
- Each chain has unique context
- No context leakage between parallel chains

### 5. Maximum Concurrent Chains
```bash
pytest comprehensive_test_suite.py::TestLoadTesting::test_max_concurrent_chains -v
```

Pushes the system to its limit (20+ chains).

**Expected results:**
- System handles 20+ concurrent chains
- Performance degrades gracefully
- No crashes or deadlocks

### All Load Tests
```bash
pytest comprehensive_test_suite.py::TestLoadTesting -v
```

Runs all 5 load tests sequentially.

### Progressive Load Testing

To gradually increase load and find breaking point:

```bash
# Test 3 chains
pytest comprehensive_test_suite.py::TestLoadTesting::test_parallel_chains_execution -v

# Test 10 chains (custom)
pytest comprehensive_test_suite.py -k "concurrent" -v

# Test 20 chains (custom)
pytest comprehensive_test_suite.py -k "max_concurrent" -v
```

### Load Test with Monitoring
```bash
pytest comprehensive_test_suite.py::TestLoadTesting -v -s
```

Shows real-time output during concurrent execution.

### Stress Test with Duration
```bash
# Run all tests with 30-second timeout (catch hanging threads)
pytest comprehensive_test_suite.py::TestLoadTesting -v --timeout=30
```

---

## Error Scenario Testing

Verify the system handles failures gracefully.

### 1. Agent Timeout
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_agent_timeout -v
```

Simulates an agent that exceeds timeout.

**Expected result:** TimeoutError caught, chain aborts gracefully.

### 2. Agent Failure
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_agent_failure -v
```

Simulates an agent raising an exception.

**Expected result:** Error caught, logged, and propagated to next agent in chain.

### 3. Invalid Verdict
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_invalid_verdict_handling -v
```

Victoria returns unexpected decision format (not approve/reject/revise).

**Expected result:** Validation error caught, request for revision.

### 4. Network Error
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_network_error -v
```

API call fails (e.g., connection refused).

**Expected result:** Error handled, retry triggered.

### 5. Rate Limit Error
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_rate_limit_error -v
```

API returns 429 (rate limit exceeded).

**Expected result:** Backoff triggered, retry with exponential delay.

### 6. Chain Breakage at Intermediate Step
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_chain_breakage -v
```

An agent in the middle of a 4-agent chain fails.

**Expected result:** Chain stops at that point, error logged with context from prior agents.

### All Error Tests
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios -v
```

---

## Retry Logic Testing

Verify that retries work correctly.

### 1. Retry Same Agent
```bash
pytest comprehensive_test_suite.py::TestRetryLogic::test_retry_same_agent -v
```

An agent fails on attempt 1-2, succeeds on attempt 3.

**Expected result:** Success after 3 attempts, backoff delays observed.

### 2. Escalation to Manager
```bash
pytest comprehensive_test_suite.py::TestRetryLogic::test_escalation_to_manager -v
```

After max_retries (3), escalate to manager.

**Expected result:** Manager called, problem noted, alternative solution found.

### 3. Task Splitting on Failure
```bash
pytest comprehensive_test_suite.py::TestRetryLogic::test_task_splitting -v
```

Large task divided into subtasks when a single attempt fails.

**Expected result:** Subtasks executed, combined back together.

### 4. Exponential Backoff
```bash
pytest comprehensive_test_suite.py::TestRetryLogic::test_exponential_backoff -v
```

Delays between retries: 0.1s → 0.2s → 0.4s.

**Expected result:** Backoff timing correct.

### 5. No-Retry on Validation Error
```bash
pytest comprehensive_test_suite.py::TestRetryLogic::test_no_retry_validation_error -v
```

Validation errors (e.g., bad input format) don't trigger retries.

**Expected result:** Validation error fails immediately, no retries.

### 6. Retry with Context Propagation
```bash
pytest comprehensive_test_suite.py::TestRetryLogic::test_retry_with_context_propagation -v
```

Context carries through retry attempts.

**Expected result:** Retried agent receives previous context.

### All Retry Tests
```bash
pytest comprehensive_test_suite.py::TestRetryLogic -v
```

---

## Adding New Tests

### 1. Add a New Agent Test

When a new agent is created:

```python
# In comprehensive_test_suite.py, TestIndividualAgents class:

def test_agent_newagent(self):
    """Test новый агент (Новый)."""
    ctx = AgentTestContext(
        agent_key="newagent",
        agent_name="Новый",
        task="Task description for new agent",
    )
    result = mock_agent_run(ctx.agent_key, asdict(ctx))
    assert result["status"] == "success"
    assert result["agent"] == "newagent"

def test_agent_newagent_with_context(self):
    """Новый получает контекст от Марины."""
    ctx = AgentTestContext(
        agent_key="newagent",
        agent_name="Новый",
        from_agent="marina",
        task="Task [from:marina]",
    )
    result = mock_agent_run(ctx.agent_key, asdict(ctx))
    assert result["status"] == "success"
    assert "from_agent" in result.get("context", {})
```

Then run:
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_newagent -v
```

### 2. Add a New Chain Test

When a new workflow is created:

```python
# In comprehensive_test_suite.py, TestChains class:

def test_chain_custom_workflow(self):
    """Custom workflow: agent1 → agent2 → agent3."""
    chain_config = ChainTestConfig(
        chain_id="custom_workflow",
        agent_sequence=["agent1", "agent2", "agent3"],
        context={"workflow_type": "custom"},
    )
    
    context = chain_config.context.copy()
    results = []
    for agent in chain_config.agent_sequence:
        result = mock_agent_run(agent, context)
        results.append(result)
        context = propagate_context(context, result, agent)
    
    assert len(results) == 3
    assert context["chain_length"] == 3
    assert all(r["status"] == "success" for r in results)
```

Then run:
```bash
pytest comprehensive_test_suite.py::TestChains::test_chain_custom_workflow -v
```

### 3. Add an Error Scenario Test

When a new error condition should be handled:

```python
# In comprehensive_test_suite.py, TestErrorScenarios class:

def test_custom_error_handling(self):
    """Test handling of CustomError."""
    def failing_agent(*args, **kwargs):
        raise CustomError("Description of error")
    
    with pytest.raises(CustomError):
        failing_agent()
    
    # Or test graceful handling:
    try:
        failing_agent()
    except CustomError as e:
        assert "Description" in str(e)
```

Then run:
```bash
pytest comprehensive_test_suite.py::TestErrorScenarios::test_custom_error_handling -v
```

### 4. Add a Performance Test

When you need to measure a new component:

```python
# In comprehensive_test_suite.py, TestPerformance class:

def test_new_component_performance(self):
    """Measure performance of new component."""
    start = time.perf_counter()
    result = mock_agent_run("newagent", {})
    duration = time.perf_counter() - start
    
    assert duration < 1.0  # Mock should be < 1s
    assert result["status"] == "success"
```

Then run:
```bash
pytest comprehensive_test_suite.py::TestPerformance::test_new_component_performance -v
```

### 5. Add a Load Test

When stress-testing a new feature:

```python
# In comprehensive_test_suite.py, TestLoadTesting class:

def test_new_load_scenario(self):
    """Load test with new scenario."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(mock_agent_run, f"agent_{i}", {})
            for i in range(10)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert len(results) == 10
    assert all(r["status"] == "success" for r in results)
```

Then run:
```bash
pytest comprehensive_test_suite.py::TestLoadTesting::test_new_load_scenario -v
```

### 6. Running Your New Test

After adding test code:

```bash
# Run just your new test
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_newagent -v

# Run all tests to verify no regressions
pytest comprehensive_test_suite.py -v
```

### Tips for Adding Tests

1. **Name tests clearly:** `test_agent_X`, `test_chain_Y`, `test_error_Z`
2. **Add docstrings:** Describe what's being tested
3. **Use fixtures:** Don't repeat setup code
4. **Verify assertions:** Each test should have at least 2 assertions
5. **Test both success and failure paths**
6. **Include context/edge cases**

---

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/tests.yml`:

```yaml
name: Run MILA Office Test Suite

on:
  push:
    branches: [main, develop]
    paths:
      - 'mila-office/**'
      - '.github/workflows/tests.yml'
  pull_request:
    branches: [main]
    paths:
      - 'mila-office/**'

jobs:
  test:
    runs-on: windows-latest  # Windows 11 Pro
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd mila-office
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-timeout pytest-xdist
      
      - name: Run comprehensive test suite
        run: |
          cd mila-office
          pytest comprehensive_test_suite.py -v --tb=short
      
      - name: Generate coverage report
        run: |
          cd mila-office
          pytest comprehensive_test_suite.py --cov=. --cov-report=xml
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./mila-office/coverage.xml
          flags: unittests
          fail_ci_if_error: false
```

### Azure Pipelines

Create `azure-pipelines.yml`:

```yaml
trigger:
  - main
  - develop

pool:
  vmImage: 'windows-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'
    displayName: 'Use Python 3.11'
  
  - script: |
      cd mila-office
      pip install -r requirements.txt
      pip install pytest pytest-cov pytest-timeout
    displayName: 'Install dependencies'
  
  - script: |
      cd mila-office
      pytest comprehensive_test_suite.py -v --tb=short
    displayName: 'Run test suite'
  
  - task: PublishTestResults@2
    inputs:
      testResultsFiles: 'mila-office/test-results.xml'
      testRunTitle: 'MILA Office Tests'
    condition: succeededOrFailed()
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test

test:
  stage: test
  image: python:3.11
  script:
    - cd mila-office
    - pip install -r requirements.txt
    - pip install pytest pytest-cov
    - pytest comprehensive_test_suite.py -v
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

### Local Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
cd mila-office
pytest comprehensive_test_suite.py -x --tb=short
if [ $? -ne 0 ]; then
  echo "Tests failed. Commit aborted."
  exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

### Jenkins Pipeline

Create `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    stages {
        stage('Setup') {
            steps {
                sh '''
                    cd mila-office
                    python -m pip install -r requirements.txt
                    python -m pip install pytest pytest-cov
                '''
            }
        }
        
        stage('Test') {
            steps {
                sh '''
                    cd mila-office
                    pytest comprehensive_test_suite.py -v --tb=short
                '''
            }
        }
        
        stage('Coverage') {
            steps {
                sh '''
                    cd mila-office
                    pytest comprehensive_test_suite.py --cov=. --cov-report=html
                '''
                publishHTML([
                    reportDir: 'mila-office/htmlcov',
                    reportFiles: 'index.html',
                    reportName: 'Coverage Report'
                ])
            }
        }
    }
    
    post {
        always {
            junit 'mila-office/test-results.xml'
        }
    }
}
```

---

## Test Environment Setup

### Local Development Setup

```bash
# 1. Clone repository (if needed)
git clone <repo> "E:\MILA GOLD"
cd "E:\MILA GOLD\mila-office"

# 2. Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install test dependencies
pip install pytest pytest-cov pytest-timeout pytest-xdist

# 5. Verify setup
pytest --version
```

### Environment Variables

Create or update `.env` in `mila-office/`:

```bash
# For testing, these can be dummy values (tests use mocks)
ANTHROPIC_API_KEY=sk-test-dummy-key
IG_ACCESS_TOKEN=test-token
IG_USER_ID=123456789
TELEGRAM_BOT_TOKEN=test-token
GUMROAD_ACCESS_TOKEN=test-token
```

### Test Database Setup (for integration tests)

If using Supabase:

```bash
# Install Supabase CLI
npm install -g supabase

# Start local Supabase
supabase start

# Run migrations (if any)
supabase db push
```

### Mock vs. Real API Testing

**Mock mode (default, ~5 seconds):**
- No API calls
- Fast, reliable
- Good for CI/CD

**Real API mode:**
- Set `MOCK_MODE=false` in environment
- Real Claude API calls (uses ANTHROPIC_API_KEY)
- Real Instagram API calls (uses IG_* tokens)
- Slow (~15–25 seconds per agent)

### Parallel Test Execution

```bash
# Run tests in parallel (uses all CPU cores)
pip install pytest-xdist
pytest comprehensive_test_suite.py -n auto

# Or specify number of workers
pytest comprehensive_test_suite.py -n 4
```

---

## Troubleshooting

### Tests Not Found

**Problem:** `ERROR collecting comprehensive_test_suite.py`

**Solution:**
```bash
# Make sure conftest.py exists in mila-office/
ls conftest.py

# It should contain:
# import sys, os
# sys.path.insert(0, os.path.dirname(__file__))

# Verify path is correct
pwd  # Should be: e:\MILA GOLD\mila-office
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'base'`

**Solution:**
```bash
# Ensure you're in the right directory
cd "E:\MILA GOLD\mila-office"

# Run from here
pytest comprehensive_test_suite.py -v
```

### Tests Too Slow

**Problem:** Tests taking > 10 seconds (mock mode should be ~5s)

**Solution:**
```bash
# Check for hanging threads (timeout test)
pytest comprehensive_test_suite.py::TestErrorScenarios::test_agent_timeout -v

# Run with timeout enforcement
pytest comprehensive_test_suite.py --timeout=10

# Profile slow tests
pytest comprehensive_test_suite.py --durations=10
```

### Flaky Tests

**Problem:** Same test passes/fails inconsistently

**Solution:**
```bash
# Run test multiple times
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_marina -v --count=5

# Run with increased timeout (for concurrency issues)
pytest comprehensive_test_suite.py -v --timeout=30

# Run in isolation
pytest comprehensive_test_suite.py::TestLoadTesting::test_parallel_chains_execution -v
```

### API Rate Limiting

**Problem:** Real API tests hit rate limits

**Solution:**
```bash
# Use longer delays between retries
export RETRY_BACKOFF_MULTIPLIER=2.0

# Run fewer concurrent tests
pytest comprehensive_test_suite.py::TestLoadTesting -n 1

# Or use mock mode (default)
pytest comprehensive_test_suite.py -v
```

### Out of Memory

**Problem:** Load tests consuming too much RAM

**Solution:**
```bash
# Reduce number of concurrent chains
pytest comprehensive_test_suite.py::TestLoadTesting::test_max_concurrent_chains -v
# Then modify max_workers in the test

# Or skip heaviest load test
pytest comprehensive_test_suite.py::TestLoadTesting -k "not max_concurrent" -v
```

### Failed Fixtures

**Problem:** `fixture 'performance_baseline' not found`

**Solution:**
```bash
# Fixtures are defined in comprehensive_test_suite.py
# Make sure you haven't renamed the file

# Check fixture list
pytest comprehensive_test_suite.py --fixtures
```

### Windows Path Issues

**Problem:** `FileNotFoundError` with backslashes

**Solution:**
```bash
# Use raw strings or forward slashes
path = r"E:\MILA GOLD\mila-office"
# or
path = "E:/MILA GOLD/mila-office"

# Or use pathlib
from pathlib import Path
path = Path("E:\MILA GOLD\mila-office")
```

### CI/CD Failures

**Problem:** Tests pass locally but fail in GitHub Actions

**Solution:**
```bash
# Check Python version matches (3.11)
python --version

# Check dependencies match
pip list | grep -E "anthropic|flask|requests"

# Run exact CI command locally
cd mila-office
pip install -r requirements.txt
pip install pytest
pytest comprehensive_test_suite.py -v --tb=short
```

### Coverage Report Issues

**Problem:** `No data to report` with coverage

**Solution:**
```bash
# Install coverage plugin
pip install pytest-cov

# Run with coverage
pytest comprehensive_test_suite.py --cov=. --cov-report=html

# Check HTML report
start htmlcov\index.html  # Windows
open htmlcov/index.html   # Mac/Linux
```

---

## Test Status Dashboard

### Check Test Count
```bash
pytest comprehensive_test_suite.py --collect-only -q | tail -1
# Expected: "46 tests collected in 0.01s"
```

### Quick Health Check
```bash
# Run all tests with minimal output
pytest comprehensive_test_suite.py -q
# Expected: "46 passed in 5.39s"
```

### Detailed Status
```bash
# Show all test names and results
pytest comprehensive_test_suite.py -v --tb=no
```

### Test Timing Summary
```bash
# Show slowest tests
pytest comprehensive_test_suite.py --durations=5
```

---

## Test Maintenance

### Monthly Review

1. Run full test suite: `pytest comprehensive_test_suite.py -v`
2. Check coverage: `pytest comprehensive_test_suite.py --cov=.`
3. Update baselines if needed: edit `performance_baseline()` fixture
4. Review failure logs
5. Update TEST_COMMANDS.md if workflow changes

### When Adding New Features

1. Write test first (TDD)
2. Run: `pytest comprehensive_test_suite.py -x`
3. Implement feature
4. Verify tests pass
5. Commit with test code

### When Fixing Bugs

1. Add test that reproduces bug
2. Verify test fails
3. Fix bug
4. Verify test passes
5. Run full suite to check for regressions: `pytest comprehensive_test_suite.py -v`

---

## Summary

| Category | Command | Tests |
|----------|---------|-------|
| **All Tests** | `pytest comprehensive_test_suite.py -v` | 46 |
| **Individual Agents** | `pytest comprehensive_test_suite.py::TestIndividualAgents -v` | 12 |
| **Chains** | `pytest comprehensive_test_suite.py::TestChains -v` | 6 |
| **Errors** | `pytest comprehensive_test_suite.py::TestErrorScenarios -v` | 6 |
| **Retry** | `pytest comprehensive_test_suite.py::TestRetryLogic -v` | 6 |
| **Performance** | `pytest comprehensive_test_suite.py::TestPerformance -v` | 6 |
| **Load** | `pytest comprehensive_test_suite.py::TestLoadTesting -v` | 5 |
| **Integration** | `pytest comprehensive_test_suite.py::TestIntegration -v` | 3 |
| **Snapshots** | `pytest comprehensive_test_suite.py::TestSnapshots -v` | 2 |

**Runtime:** ~5 seconds (mock mode), ~120–300 seconds (real API)  
**Status:** ✅ All passing  
**Maintenance:** Monthly review recommended

---

**Last Updated:** 2026-06-08  
**Maintained by:** MILA Office Development Team  
**Documentation:** See TEST_SUITE_README.md for detailed guide
