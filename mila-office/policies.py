# -*- coding: utf-8 -*-
"""Execution policy for MILA Office pipelines.

This module is the single place for operational rules: priority, direct-run
permissions, approval gates, retry limits, and backoff timing.
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

MEM_DIR = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD")) / "mila-office" / "memory"
POLICY_OVERRIDES = MEM_DIR / "policies_override.json"

TERMINAL_STATUSES = {"done", "awaiting_approval", "blocked", "cancelled"}
RETRYABLE_STATUSES = {"failed", "locked", "rate_limited"}

DEFAULT_POLICY = {
    "requires_approval": False,
    "default_priority": 5,
    "max_retries": 2,
    "retry_backoff_seconds": [300, 900, 1800],
    "allowed_direct": False,
    "rate_limit_key": None,
    "notify_on_status": ["failed", "awaiting_approval", "done"],
}

PIPELINE_POLICIES = {
    "new_client": {
        "default_priority": 1,
        "max_retries": 3,
        "allowed_direct": False,
        "notify_on_status": ["failed", "done"],
    },
    "content_week": {
        "requires_approval": True,
        "default_priority": 2,
        "max_retries": 2,
        "allowed_direct": False,
        "notify_on_status": ["failed", "awaiting_approval", "done"],
    },
    "monday_brief": {
        "default_priority": 3,
        "max_retries": 2,
        "allowed_direct": False,
    },
    "weekly_report": {
        "default_priority": 4,
        "max_retries": 2,
        "allowed_direct": False,
    },
    "competitive_analysis": {
        "default_priority": 5,
        "max_retries": 1,
        "allowed_direct": False,
    },
    "product_research": {
        "default_priority": 3,
        "max_retries": 2,
        "allowed_direct": False,
        "rate_limit_key": "instagram_api",
    },
    "new_product": {
        "requires_approval": True,
        "default_priority": 2,
        "max_retries": 1,
        "allowed_direct": False,
        "notify_on_status": ["failed", "awaiting_approval", "done"],
    },
}


def get_policy(pipeline: str) -> dict:
    policy = DEFAULT_POLICY.copy()
    policy.update(PIPELINE_POLICIES.get(pipeline, {}))
    overrides = load_overrides()
    policy.update(overrides.get("default", {}))
    policy.update(overrides.get(pipeline, {}))
    return policy


def load_overrides() -> dict:
    try:
        data = json.loads(POLICY_OVERRIDES.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def default_priority(pipeline: str) -> int:
    return int(get_policy(pipeline).get("default_priority", 5))


def can_run_direct(pipeline: str) -> bool:
    return bool(get_policy(pipeline).get("allowed_direct"))


def max_retries(pipeline: str) -> int:
    return int(get_policy(pipeline).get("max_retries", 0))


def retry_delay_seconds(pipeline: str, attempts: int, status: str = "failed",
                        result: dict | None = None) -> int:
    result = result or {}
    if status == "rate_limited":
        try:
            retry_after = int(result.get("retry_after") or result.get("result", {}).get("retry_after") or 0)
        except (TypeError, ValueError):
            retry_after = 0
        if retry_after > 0:
            return retry_after

    backoff = get_policy(pipeline).get("retry_backoff_seconds") or []
    if not backoff:
        return 300
    idx = max(0, min(int(attempts or 1) - 1, len(backoff) - 1))
    return int(backoff[idx])


def status_from_result(result: dict | None) -> str:
    result = result or {}
    status = (result.get("status") or "").strip().lower()
    if status in {"awaiting_approval", "approval_required"}:
        return "awaiting_approval"
    if status in {"locked", "blocked", "rate_limited", "cancelled"}:
        return status
    if result.get("ok") is False:
        return status or "failed"
    return "done"


def should_retry(pipeline: str, status: str, attempts: int) -> bool:
    if status not in RETRYABLE_STATUSES:
        return False
    return int(attempts or 0) <= max_retries(pipeline)


def _slug(value: str, fallback: str = "item") -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9а-яё]+", "_", text, flags=re.IGNORECASE).strip("_")
    return text[:80] or fallback


def default_dedupe_key(pipeline: str, data: dict | None = None) -> str | None:
    data = data or {}
    now = datetime.now(timezone.utc)
    if pipeline == "content_week":
        year, week, _ = now.isocalendar()
        return f"content_week:{year}-W{week:02d}"
    if pipeline == "monday_brief":
        return f"monday_brief:{now.date().isoformat()}"
    if pipeline == "new_client":
        lead = data.get("lead_id") or data.get("telegram") or data.get("tg_username") or data.get("name")
        return f"new_client:{_slug(str(lead), 'lead')}"
    if pipeline == "new_product":
        idea = data.get("idea") or data.get("title") or "product"
        return f"new_product:{_slug(str(idea), 'product')}"
    return None
