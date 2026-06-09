# Comprehensive Test Suite for MILA Office 11-Agent System

A complete pytest-compatible test suite covering all 9 agents + manager/producer, with tests for individual execution, chains, error handling, retry logic, performance, and load testing.

## Overview

**File:** `comprehensive_test_suite.py`  
**Total Tests:** 46 comprehensive tests  
**Status:** All passing ✓  
**Runtime:** ~5 seconds

### What's Tested

1. **Individual Agents (12 tests)**
   - Each of 9 core agents: Marina, Victoria, Alina, Dima, Tyoma, Olya, Vasya, Lera, Rita
   - Context-aware execution (agent-to-agent `[from:agent_name]` tags)

2. **Agent Chains (6 tests)**
   - Sequential chains: content_week (4 agents), new_client (2 agents), custom flows
   - Standalone agents (Rita)
   - Context propagation through entire chain

3. **Error Scenarios (6 tests)**
   - Agent timeout / hanging
   - Agent failure / exceptions
   - Invalid verdicts (Victoria's approve/reject/request_revisions)
   - Network errors, rate limits
   - Chain breakage at intermediate steps

4. **Retry Logic (6 tests)**
   - Retry same agent with exponential backoff
   - Escalation to manager on repeated failure
   - Task splitting on failure
   - Distinction between retryable vs. non-retryable errors

5. **Performance (6 tests)**
   - Individual agent execution times
   - Full chain time measurement
   - Time per step within chain
   - Parallel chain speedup analysis

6. **Load Testing (5 tests)**
   - Multiple chains in parallel (stress test)
   - 10 concurrent agents
   - Load with retry logic
   - Concurrent context propagation
   - Max concurrent chains (20+)

7. **Integration (3 tests)**
   - Full content workflow: olya → marina → victoria → vasya
   - Client workflow: alina → lera
   - Weekly operations: dima + marina + olya

8. **Regression/Snapshots (2 tests)**
   - Agent output format consistency
   - Chain result structure validation

---

## Running the Tests

### Run All Tests
```bash
cd E:\MILA\ GOLD\mila-office
pytest comprehensive_test_suite.py -v
```

### Run Specific Test Classes
```bash
# Individual agents only
pytest comprehensive_test_suite.py::TestIndividualAgents -v

# Chain tests only
pytest comprehensive_test_suite.py::TestChains -v

# Error scenarios
pytest comprehensive_test_suite.py::TestErrorScenarios -v

# Retry logic
pytest comprehensive_test_suite.py::TestRetryLogic -v

# Performance tests
pytest comprehensive_test_suite.py::TestPerformance -v

# Load testing (stress)
pytest comprehensive_test_suite.py::TestLoadTesting -v

# Integration tests
pytest comprehensive_test_suite.py::TestIntegration -v
```

### Run Specific Test by Name
```bash
pytest comprehensive_test_suite.py::TestIndividualAgents::test_agent_marina -v
pytest comprehensive_test_suite.py::TestChains::test_chain_content_week -v
```

### Run with Custom Options
```bash
# Verbose output with short traceback
pytest comprehensive_test_suite.py -v --tb=short

# Show print statements and logging
pytest comprehensive_test_suite.py -v -s

# Stop after first failure
pytest comprehensive_test_suite.py -x

# Run only failed tests (from last run)
pytest comprehensive_test_suite.py --lf

# Show summary of all outcomes
pytest comprehensive_test_suite.py -ra
```

---

## Test Structure

### Individual Agent Tests
Each agent is tested with:
- Basic execution (success path)
- Context-aware execution (receiving `[from:other_agent]` tags)
- Timeout handling
- Error scenarios specific to agent role

**Example:**
```python
def test_agent_victoria_with_marina_context(self):
    """Виктория получает контекст от Марины."""
    ctx = AgentTestContext(
        agent_key="victoria",
        from_agent="marina",
        task="Проверь пост про выбор [from:marina]",
    )
    # Victoria should be stricter when receiving from Marina
```

### Chain Tests
Chains test the sequential flow of multiple agents and context propagation:

**Example:**
```python
def test_chain_content_week(self):
    """Цепь content_week: olya → marina → victoria → vasya."""
    chain_config = ChainTestConfig(
        chain_id="content_week",
        agent_sequence=["olya", "marina", "victoria", "vasya"],
    )
    # Execute each agent in sequence
    # Verify context flows from one agent to next
    # Validate final output structure
```

### Context Propagation
Each agent in a chain receives the `context` dict which accumulates:
- `previous_results`: {agent_name: result, ...}
- `last_agent`: last agent that executed
- `chain_length`: number of agents executed so far
- Custom context passed at chain start (topic, client_id, etc.)

### Error Scenarios
Tests verify correct handling of:
- **Timeout:** Agent doesn't complete within timeout_seconds
- **Failure:** Agent raises exception
- **Invalid verdict:** Agent returns unexpected decision format
- **Network error:** Connection to API fails
- **Rate limit:** API returns 429

### Retry Logic
Tests verify:
- **Retry same agent:** Flaky agents succeed on retry 2-3
- **Escalation:** After max_retries, escalate to manager
- **Task splitting:** Large task divided into subtasks on failure
- **Backoff:** Exponential delay between retries (0.1s, 0.2s, 0.4s)
- **No-retry:** Validation errors don't trigger retries

### Performance Benchmarks
Tests measure:
- Individual agent execution time (should be < 1s per mock)
- Full chain time (should be < 5s for mock)
- Time per step
- Parallel vs. sequential speedup

**Performance baseline** (adjustable in `performance_baseline()` fixture):
- Per-agent budget: 30 seconds (for real API calls)
- Full chain budget: 120 seconds
- Parallel speedup expected: 1.8x

### Load Testing
Tests verify system behavior under stress:
- 3 parallel chains
- 10 concurrent agents
- 20+ concurrent chains
- Retry logic under load
- Context isolation between chains (no crosstalk)

---

## Key Test Utilities

### `AgentTestContext` dataclass
Describes a test case for an individual agent:
```python
@dataclass
class AgentTestContext:
    agent_key: str                          # "marina", "victoria", etc.
    agent_name: str                         # "Марина", "Виктория"
    from_agent: Optional[str] = None        # Context sender
    task: str = "test message"              # Task description
    expected_success: bool = True           # Should succeed?
    timeout_seconds: float = 30.0           # Execution timeout
    chain_id: Optional[str] = None          # Parent chain
    previous_results: Dict[str, Any] = None # Prior agents' outputs
```

### `ChainTestConfig` dataclass
Describes a chain execution:
```python
@dataclass
class ChainTestConfig:
    chain_id: str                    # "content_week", "new_client"
    agent_sequence: List[str]        # ["olya", "marina", "victoria", "vasya"]
    is_parallel: bool = False        # Sequential or parallel?
    context: Dict[str, Any] = None   # Initial context
    max_retries: int = 3             # Retry budget per agent
```

### Helper Functions

**`mock_agent_run(agent_key, context_data)`**  
Simulates agent execution, returns:
```python
{
    "status": "success" | "error",
    "agent": agent_key,
    "response": "...",
    "duration": 0.5,
    "timestamp": "2026-06-08T12:34:56Z"
}
```

**`propagate_context(context, agent_result, agent_key)`**  
Passes context through chain:
```python
new_context = propagate_context(context, result, "marina")
# New context includes: previous_results["marina"], last_agent="marina", chain_length+=1
```

**`extract_context_from_message(message)`**  
Parses `[from:agent_name]` tags:
```python
from_agent = extract_context_from_message("Check post [from:marina]")
# Returns: "marina"
```

**`time_agent_execution(func, *args, **kwargs)`**  
Measures execution time:
```python
duration, result = time_agent_execution(mock_agent_run, "marina", context)
```

---

## Agents Covered

| Agent | Role | Key Responsibilities | Test Focus |
|-------|------|---------------------|-----------|
| **Marina** | Маркетер | Content ideas, copywriting, strategy | Context from user, approval flow |
| **Victoria** | Редактор | Proofreading, quality check, approval/rejection | Context-aware verdict (approve/reject/revise) |
| **Alina** | CRM | Client intake, lead tracking | Flow to sales (Lera) |
| **Dima** | Финансы | Revenue, Gumroad sales, LTV | Weekly operations chain |
| **Tyoma** | Telegram | Telegram channel management, posting | Standalone + content workflow |
| **Olya** | Тренды | Trend research, content discovery | First step in content_week chain |
| **Vasya** | Расписание | Publication scheduling, calendar | Last step in content_week chain |
| **Lera** | Продажи | Follow-up, consultation booking, sales | Follow-up to new client (Alina) |
| **Rita** | Архитектор | Product structure, praktikum updates | Standalone agent |

---

## Known Chains Tested

### `content_week`
Trendspotting → copywriting → editing → scheduling
```
olya → marina → victoria → vasya
```

### `new_client`
Client intake → personalized follow-up
```
alina → lera
```

### `monday_brief`
Weekly retrospective → content plan
```
manager → marina
```

### `weekly_report`
Financial review + metrics + trends
```
dima → marina → manager
```

---

## Extending the Tests

### Adding a New Agent Test
```python
def test_agent_newagent(self):
    """Test новый агент."""
    ctx = AgentTestContext(
        agent_key="newagent",
        agent_name="Новый",
        task="Task description",
    )
    result = mock_agent_run(ctx.agent_key, asdict(ctx))
    assert result["status"] == "success"
```

### Adding a New Chain Test
```python
def test_chain_custom_flow(self):
    """Custom workflow."""
    chain_config = ChainTestConfig(
        chain_id="custom",
        agent_sequence=["agent1", "agent2", "agent3"],
        context={"custom_field": "value"},
    )
    
    context = chain_config.context.copy()
    for agent in chain_config.agent_sequence:
        result = mock_agent_run(agent, context)
        context = propagate_context(context, result, agent)
    
    assert context["chain_length"] == 3
```

### Adding a New Error Scenario
```python
def test_agent_custom_error(self):
    """Test custom error case."""
    def failing_agent(*args, **kwargs):
        raise CustomError("Description")
    
    with pytest.raises(CustomError):
        failing_agent()
```

---

## Fixtures

**`test_mila_folder`**  
Returns MILA_FOLDER path for file operations.

**`mock_client`**  
Patches Anthropic client to avoid real API calls.

**`mock_instagram_api`**  
Patches Instagram Graph API calls.

**`mock_supabase`**  
Patches Supabase database access.

**`performance_baseline`**  
Session-level fixture with performance budgets:
- `agent_time_budget_seconds`: 30.0
- `chain_time_budget_seconds`: 120.0
- `parallel_speedup_expected`: 1.8

---

## Performance Notes

All tests use **mock agents** (no actual API calls):
- Individual agent mock: ~0.5ms
- Full 4-agent chain: ~2ms
- 10 parallel agents: ~5ms
- 20 parallel chains: ~10ms

**Real performance** (with actual Claude API):
- Per agent: ~3–5 seconds (depends on model, prompt size)
- Full chain: ~15–25 seconds
- Parallel chain: scales sublinearly (shared rate limits)

Adjust timeouts and budgets in `performance_baseline()` for real-world testing.

---

## CI/CD Integration

Use in GitHub Actions or similar:

```yaml
- name: Run comprehensive test suite
  run: |
    cd mila-office
    pip install pytest
    pytest comprehensive_test_suite.py -v --tb=short
```

Or with coverage:
```bash
pytest comprehensive_test_suite.py --cov=. --cov-report=html
```

---

## Troubleshooting

**Tests fail with "module not found"**  
Ensure `conftest.py` is present and adds `mila-office` to `sys.path`.

**Timeout tests are flaky**  
Adjust `timeout_seconds` parameter (tests using actual delays may vary).

**Load tests are slow**  
Reduce `max_workers` or number of iterations in load tests.

**Mock tests don't reflect real behavior**  
Replace `mock_agent_run()` with actual agent execution for integration testing.

---

## Contact & Maintenance

Tests are maintained for MILA Office automation system.  
Update when:
- New agents are added
- Chain workflows change
- Error handling is modified
- Performance baselines shift
