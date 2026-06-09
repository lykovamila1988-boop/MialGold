# -*- coding: utf-8 -*-
"""
test_chain_retry.py — Unit tests for chain_retry.py

Run with: python -m pytest test_chain_retry.py -v
Or simply: python test_chain_retry.py
"""

import json
import unittest
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

import chain_retry
from chain_retry import (
    create_chain, get_chain, update_node_status,
    retry_chain, escalate_chain, split_chain, merge_results,
    complete_chain, cancel_chain, get_chain_history, get_chain_stats,
    get_all_chains, clear_old_chains, export_chain_to_json,
    ChainStatus, RetryReason
)


class TestChainCreation(unittest.TestCase):
    """Test chain creation."""

    def test_create_chain(self):
        """Test creating a new chain."""
        chain = create_chain("test_001", ["victoria", "alina", "dima"])

        self.assertEqual(chain["id"], "test_001")
        self.assertEqual(chain["status"], ChainStatus.RUNNING.value)
        self.assertEqual(chain["agents"], ["victoria", "alina", "dima"])
        self.assertEqual(chain["retry_count"], 0)
        self.assertIsNotNone(chain["created_at"])

    def test_create_chain_with_context(self):
        """Test creating chain with metadata context."""
        context = {"document": "test.md", "user_id": "123"}
        chain = create_chain("test_002", ["victoria"], context=context)

        self.assertEqual(chain["context"], context)

    def test_get_chain(self):
        """Test retrieving a chain."""
        create_chain("test_003", ["alina"])
        chain = get_chain("test_003")

        self.assertIsNotNone(chain)
        self.assertEqual(chain["id"], "test_003")

    def test_get_nonexistent_chain(self):
        """Test retrieving non-existent chain."""
        chain = get_chain("nonexistent")
        self.assertIsNone(chain)


class TestNodeStatus(unittest.TestCase):
    """Test updating node status."""

    def setUp(self):
        self.chain_id = "status_test_001"
        create_chain(self.chain_id, ["victoria", "alina"])

    def test_update_to_running(self):
        """Test updating node to running."""
        update_node_status(self.chain_id, "victoria", "running")
        chain = get_chain(self.chain_id)

        node = chain["nodes"]["victoria"]
        self.assertEqual(node.status, "running")
        self.assertIsNotNone(node.started_at)

    def test_update_to_success(self):
        """Test updating node to success."""
        update_node_status(self.chain_id, "victoria", "running")
        update_node_status(self.chain_id, "victoria", "success", reply="Done")

        chain = get_chain(self.chain_id)
        node = chain["nodes"]["victoria"]

        self.assertEqual(node.status, "success")
        self.assertEqual(node.reply, "Done")
        self.assertIsNotNone(node.completed_at)
        self.assertIsNotNone(node.duration_seconds)

    def test_update_to_failed(self):
        """Test updating node to failed."""
        update_node_status(self.chain_id, "victoria", "running")
        update_node_status(self.chain_id, "victoria", "failed", error="Timeout")

        chain = get_chain(self.chain_id)
        node = chain["nodes"]["victoria"]

        self.assertEqual(node.status, "failed")
        self.assertEqual(node.error, "Timeout")

    def test_history_logged(self):
        """Test that events are logged to history."""
        update_node_status(self.chain_id, "victoria", "running")
        update_node_status(self.chain_id, "victoria", "success")

        history = get_chain_history(self.chain_id)
        self.assertGreater(len(history), 0)

        # Should have start + node events
        events = [e["event_type"] for e in history]
        self.assertIn("node_running", events)


class TestRetry(unittest.TestCase):
    """Test retry functionality."""

    def setUp(self):
        self.chain_id = "retry_test_001"
        create_chain(self.chain_id, ["victoria", "alina", "dima"])

    def test_retry_chain_success(self):
        """Test successful retry."""
        update_node_status(self.chain_id, "victoria", "success")
        update_node_status(self.chain_id, "alina", "failed", error="Timeout")

        result = retry_chain(self.chain_id, "alina", "timeout", max_retries=3)

        self.assertIsNotNone(result)
        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["status"], ChainStatus.RETRYING.value)

        # Check that alina was reset
        node = result["nodes"]["alina"]
        self.assertEqual(node.status, "pending")

        # Check that dima is also reset (downstream)
        node_dima = result["nodes"]["dima"]
        self.assertEqual(node_dima.status, "pending")

    def test_retry_count_increments(self):
        """Test retry count increments with each attempt."""
        update_node_status(self.chain_id, "victoria", "success")
        update_node_status(self.chain_id, "alina", "failed", error="Error 1")

        retry_chain(self.chain_id, "alina", "agent_error", max_retries=3)
        chain = get_chain(self.chain_id)
        self.assertEqual(chain["retry_count"], 1)

        # Fail again and retry
        update_node_status(self.chain_id, "alina", "failed", error="Error 2")
        retry_chain(self.chain_id, "alina", "agent_error", max_retries=3)
        chain = get_chain(self.chain_id)
        self.assertEqual(chain["retry_count"], 2)

    def test_max_retries_exceeded(self):
        """Test that retries are limited."""
        update_node_status(self.chain_id, "victoria", "success")
        update_node_status(self.chain_id, "alina", "failed", error="Error")

        # Fail max_retries+1 times
        for i in range(4):
            update_node_status(self.chain_id, "alina", "failed", error=f"Error {i}")
            result = retry_chain(self.chain_id, "alina", "agent_error", max_retries=3)

            if i < 3:
                self.assertIsNotNone(result)
            else:
                # Should fail after 3 retries
                self.assertIsNone(result)

        chain = get_chain(self.chain_id)
        self.assertEqual(chain["status"], ChainStatus.FAILED.value)

    def test_node_retry_count(self):
        """Test that individual node retry_count increments."""
        update_node_status(self.chain_id, "alina", "failed", error="Error")

        chain = get_chain(self.chain_id)
        self.assertEqual(chain["nodes"]["alina"].retry_count, 0)

        retry_chain(self.chain_id, "alina", "agent_error")
        chain = get_chain(self.chain_id)
        self.assertEqual(chain["nodes"]["alina"].retry_count, 1)


class TestEscalate(unittest.TestCase):
    """Test escalation."""

    def setUp(self):
        self.chain_id = "escalate_test_001"
        create_chain(self.chain_id, ["victoria", "alina", "dima"])

    def test_escalate_chain(self):
        """Test escalating to different agent."""
        update_node_status(self.chain_id, "victoria", "success")
        update_node_status(self.chain_id, "alina", "failed", error="Complex task")

        result = escalate_chain(self.chain_id, "manager", reason="Too complex")

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], ChainStatus.ESCALATED.value)

        # Check that downstream agents are skipped
        self.assertEqual(result["nodes"]["dima"].status, "skipped")

        # Check that manager is added
        self.assertIn("manager", result["agents"])

    def test_escalate_agents_list_updated(self):
        """Test that agents list is updated after escalation."""
        update_node_status(self.chain_id, "victoria", "success")

        escalate_chain(self.chain_id, "lera")
        chain = get_chain(self.chain_id)

        # Should be [victoria, alina, lera] (alina replaced, dima skipped)
        self.assertIn("lera", chain["agents"])


class TestSplit(unittest.TestCase):
    """Test splitting into parallel branches."""

    def setUp(self):
        self.chain_id = "split_test_001"
        create_chain(self.chain_id, ["victoria"])

    def test_split_chain(self):
        """Test splitting chain into parallel agents."""
        result = split_chain(self.chain_id, ["olya", "rita", "manager"])

        self.assertEqual(result["status"], ChainStatus.SPLIT.value)
        self.assertEqual(len(result["split_branches"]), 3)

        # Check branch statuses
        for agent in ["olya", "rita", "manager"]:
            self.assertEqual(result["split_branches"][agent]["status"], "pending")

    def test_split_creates_nodes(self):
        """Test that split creates nodes for new agents."""
        split_chain(self.chain_id, ["olya", "rita"])

        chain = get_chain(self.chain_id)
        self.assertIn("olya", chain["nodes"])
        self.assertIn("rita", chain["nodes"])


class TestMerge(unittest.TestCase):
    """Test merging parallel results."""

    def setUp(self):
        self.chain_id = "merge_test_001"
        create_chain(self.chain_id, ["victoria"])
        split_chain(self.chain_id, ["olya", "rita", "manager"])

    def test_merge_union(self):
        """Test union merge strategy."""
        results = [
            {"agent_key": "olya", "result": "Analysis A", "error": None, "confidence": 0.9},
            {"agent_key": "rita", "result": "Analysis B", "error": None, "confidence": 0.8},
        ]

        merge_results(self.chain_id, results, merge_strategy="union")

        chain = get_chain(self.chain_id)
        merged = chain["merged_results"]["merged_data"]

        # Union should contain both results
        self.assertIsInstance(merged, list)
        self.assertEqual(len(merged), 2)

    def test_merge_consensus(self):
        """Test consensus merge strategy."""
        results = [
            {"agent_key": "olya", "result": "Analysis A", "error": None, "confidence": 0.95},
            {"agent_key": "rita", "result": "Analysis B", "error": None, "confidence": 0.7},
        ]

        merge_results(self.chain_id, results, merge_strategy="consensus")

        chain = get_chain(self.chain_id)
        merged = chain["merged_results"]["merged_data"]

        # Consensus should pick highest confidence
        self.assertEqual(merged, "Analysis A")

    def test_merge_first_success(self):
        """Test first_success merge strategy."""
        results = [
            {"agent_key": "olya", "result": "Analysis A", "error": None},
            {"agent_key": "rita", "result": "Analysis B", "error": None},
            {"agent_key": "manager", "result": None, "error": "Timeout"},
        ]

        merge_results(self.chain_id, results, merge_strategy="first_success")

        chain = get_chain(self.chain_id)
        merged = chain["merged_results"]["merged_data"]

        # Should pick first successful
        self.assertEqual(merged, "Analysis A")

    def test_merge_with_errors(self):
        """Test merge handles errors gracefully."""
        results = [
            {"agent_key": "olya", "result": "Analysis A", "error": None},
            {"agent_key": "rita", "result": None, "error": "Timeout"},
        ]

        merge_results(self.chain_id, results, merge_strategy="union")

        chain = get_chain(self.chain_id)
        merged = chain["merged_results"]["merged_data"]

        # Should only include successful results
        self.assertEqual(len(merged), 1)


class TestCompletion(unittest.TestCase):
    """Test chain completion."""

    def setUp(self):
        self.chain_id = "completion_test_001"
        create_chain(self.chain_id, ["victoria", "alina"])

    def test_complete_chain(self):
        """Test completing chain successfully."""
        update_node_status(self.chain_id, "victoria", "success")
        update_node_status(self.chain_id, "alina", "success")

        result = complete_chain(self.chain_id, final_result="All done")

        self.assertTrue(result)

        chain = get_chain(self.chain_id)
        self.assertEqual(chain["status"], ChainStatus.SUCCESS.value)
        self.assertIsNotNone(chain["completed_at"])
        self.assertEqual(chain["final_result"], "All done")

    def test_cancel_chain(self):
        """Test cancelling chain."""
        update_node_status(self.chain_id, "victoria", "running")

        result = cancel_chain(self.chain_id, reason="User cancelled")

        self.assertTrue(result)

        chain = get_chain(self.chain_id)
        self.assertEqual(chain["status"], ChainStatus.CANCELLED.value)
        self.assertEqual(chain["cancel_reason"], "User cancelled")


class TestStats(unittest.TestCase):
    """Test statistics and querying."""

    def test_get_chain_history(self):
        """Test getting chain history."""
        chain_id = "history_test_001"
        create_chain(chain_id, ["victoria"])
        update_node_status(chain_id, "victoria", "running")
        update_node_status(chain_id, "victoria", "success")

        history = get_chain_history(chain_id)

        self.assertGreater(len(history), 0)

        # Check event types
        event_types = [e["event_type"] for e in history]
        self.assertIn("start", event_types)

    def test_get_chain_stats(self):
        """Test getting aggregate statistics."""
        # Create a few chains
        create_chain("stats_001", ["victoria"])
        create_chain("stats_002", ["alina"])

        stats = get_chain_stats(hours=24)

        self.assertGreaterEqual(stats["total_chains"], 2)
        self.assertIn("by_status", stats)
        self.assertIn("total_retries", stats)

    def test_get_all_chains(self):
        """Test getting all chains."""
        create_chain("all_001", ["victoria"])
        create_chain("all_002", ["alina"])

        chains = get_all_chains()

        self.assertGreaterEqual(len(chains), 2)

    def test_empty_history(self):
        """Test querying non-existent chain history."""
        history = get_chain_history("nonexistent")

        self.assertEqual(history, [])


class TestExport(unittest.TestCase):
    """Test exporting and loading chains."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_chain(self):
        """Test exporting chain to JSON."""
        chain_id = "export_test_001"
        create_chain(chain_id, ["victoria", "alina"])
        update_node_status(chain_id, "victoria", "success", reply="Done")

        filepath = Path(self.temp_dir) / f"{chain_id}.json"
        result = export_chain_to_json(chain_id, filepath=filepath)

        self.assertIsNotNone(result)
        self.assertTrue(filepath.exists())

        # Verify JSON structure
        with open(filepath) as f:
            data = json.load(f)

        self.assertEqual(data["id"], chain_id)
        self.assertIn("nodes", data)

    def test_load_chain(self):
        """Test loading chain from JSON."""
        chain_id = "load_test_001"
        create_chain(chain_id, ["victoria"])
        update_node_status(chain_id, "victoria", "success")

        # Export
        filepath = Path(self.temp_dir) / f"{chain_id}.json"
        export_chain_to_json(chain_id, filepath=filepath)

        # Clear memory
        chain_retry._chains.clear()

        # Load
        loaded = chain_retry.load_chain_from_json(filepath)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], chain_id)

        # Verify it's accessible
        chain = get_chain(chain_id)
        self.assertEqual(chain["id"], chain_id)


class TestConcurrency(unittest.TestCase):
    """Test thread safety."""

    def test_thread_safe_update(self):
        """Test that updates are thread-safe."""
        import threading

        chain_id = "thread_test_001"
        create_chain(chain_id, ["v1", "v2", "v3"])

        def update_node(agent, status):
            update_node_status(chain_id, agent, status)

        threads = [
            threading.Thread(target=update_node, args=("v1", "running")),
            threading.Thread(target=update_node, args=("v2", "running")),
            threading.Thread(target=update_node, args=("v3", "running")),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        chain = get_chain(chain_id)

        # All should have been updated
        self.assertEqual(chain["nodes"]["v1"].status, "running")
        self.assertEqual(chain["nodes"]["v2"].status, "running")
        self.assertEqual(chain["nodes"]["v3"].status, "running")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
