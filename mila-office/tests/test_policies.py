import importlib
import sys


def test_policy_defaults_are_pipeline_specific():
    policies = importlib.import_module("policies")
    assert policies.default_priority("new_client") == 1
    assert policies.default_priority("content_week") == 2
    assert policies.can_run_direct("content_week") is False


def test_policy_does_not_retry_approval_blocks():
    policies = importlib.import_module("policies")
    result = {"status": "awaiting_approval"}
    status = policies.status_from_result(result)
    assert status == "awaiting_approval"
    assert policies.should_retry("new_product", status, attempts=1) is False


def test_policy_retries_rate_limit_after_retry_after():
    policies = importlib.import_module("policies")
    result = {"status": "rate_limited", "retry_after": 42}
    assert policies.status_from_result(result) == "rate_limited"
    assert policies.should_retry("product_research", "rate_limited", attempts=1) is True
    assert policies.retry_delay_seconds("product_research", 1, "rate_limited", result) == 42


def test_policy_override_json(monkeypatch, tmp_path):
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    sys.modules.pop("policies", None)
    policies = importlib.import_module("policies")
    override = tmp_path / "mila-office" / "memory" / "policies_override.json"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text('{"content_week": {"default_priority": 9, "allowed_direct": true}}', encoding="utf-8")
    assert policies.default_priority("content_week") == 9
    assert policies.can_run_direct("content_week") is True
