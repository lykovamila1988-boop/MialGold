#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
conductor.py — Background daemon that orchestrates agent chains.

This is the MISSING PIECE that executes queued tasks.
Polls the task queue, runs each task via pipeline.py worker,
handles errors, and keeps running forever.

Run as: python conductor.py
Or schedule in Windows Task Scheduler to start on system boot.
"""
import subprocess
import time
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
import signal
import os

# ─── SETUP ───────────────────────────────────────────────────────
MILA_FOLDER = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
OFFICE_DIR = MILA_FOLDER / "mila-office"
LOGS_DIR = MILA_FOLDER / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "conductor.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("conductor")

# Global state for graceful shutdown
_running = True
_current_task = None


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global _running
    logger.info("Shutdown signal received, waiting for current task to complete...")
    _running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def read_queue():
    """Read current queue to check if tasks exist"""
    try:
        queue_file = MILA_FOLDER / "logs" / "task_queue.json"
        if queue_file.exists():
            with open(queue_file, "r", encoding="utf-8") as f:
                queue_data = json.load(f)
                return queue_data.get("tasks", [])
    except Exception as e:
        logger.debug(f"Could not read queue: {e}")
    return []


def run_worker():
    """
    Execute ONE task from the queue via pipeline.py worker.
    Returns: (success: bool, task_info: dict)
    """
    global _current_task

    try:
        logger.debug("Polling queue for pending tasks...")

        # Call worker, capture output
        result = subprocess.run(
            [sys.executable, "pipeline.py", "worker"],
            cwd=str(OFFICE_DIR),
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max per task
            encoding="utf-8"
        )

        # Parse output
        output_text = result.stdout.strip()
        task_info = {}

        try:
            # Worker returns JSON on success
            output_json = json.loads(output_text)
            task_info = output_json

            if result.returncode == 0:
                status = output_json.get("status", "unknown")

                if status == "empty":
                    # No tasks in queue
                    logger.debug("Queue is empty")
                    return (False, {"status": "empty"})

                elif status == "retry_scheduled":
                    pipeline = output_json.get("pipeline", "unknown")
                    retry_after = output_json.get("retry_after", "?")
                    logger.warning(
                        f"[RETRY] Task scheduled for retry: {pipeline} (retry in {retry_after}s)"
                    )
                    return (False, task_info)

                else:
                    # Task executed successfully
                    pipeline = output_json.get("pipeline", "unknown")
                    raw_status = output_json.get("raw_status", "unknown")
                    logger.info(f"[OK] Task completed: {pipeline} [{raw_status}]")
                    return (True, task_info)

            else:
                # Non-zero exit code
                error = output_json.get("error", "unknown error")
                logger.error(f"[FAIL] Task failed: {error}")
                return (False, task_info)

        except json.JSONDecodeError:
            # Output wasn't JSON, check returncode
            if result.returncode == 0:
                logger.info("[OK] Worker completed")
                return (True, {"raw_output": output_text[:200]})
            else:
                stderr = result.stderr.strip()
                logger.error(f"[ERROR] Worker error: {stderr[:500]}")
                return (False, {"error": stderr[:500]})

    except subprocess.TimeoutExpired:
        logger.error("[ERROR] Worker timeout (exceeded 1 hour)")
        return (False, {"error": "timeout"})

    except FileNotFoundError:
        logger.error(f"[ERROR] Cannot find pipeline.py at {OFFICE_DIR}")
        return (False, {"error": "pipeline.py not found"})

    except Exception as e:
        logger.error(f"[ERROR] Worker exception: {e}")
        return (False, {"error": str(e)[:200]})


def wait_or_poll(interval=5):
    """
    Sleep for interval seconds, but wake up early on signal.
    Returns True if should continue running.
    """
    global _running
    time.sleep(interval)
    return _running


def main():
    """Main conductor loop"""
    logger.info("=" * 80)
    logger.info("CONDUCTOR STARTED")
    logger.info("=" * 80)
    logger.info(f"MILA Folder: {MILA_FOLDER}")
    logger.info(f"Office Dir: {OFFICE_DIR}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info(f"Poll Interval: 5 seconds")
    logger.info("")
    logger.info("Conductor will:")
    logger.info("  1. Poll queue every 5 seconds")
    logger.info("  2. Run pending tasks via pipeline.py worker")
    logger.info("  3. Log all activity to conductor.log")
    logger.info("  4. Handle errors and keep running")
    logger.info("")
    logger.info("Press Ctrl+C to stop gracefully.")
    logger.info("=" * 80)
    logger.info("")

    # Verify office directory exists
    if not OFFICE_DIR.exists():
        logger.error(f"FATAL: Office directory not found: {OFFICE_DIR}")
        sys.exit(1)

    # Verify pipeline.py exists
    pipeline_py = OFFICE_DIR / "pipeline.py"
    if not pipeline_py.exists():
        logger.error(f"FATAL: pipeline.py not found: {pipeline_py}")
        sys.exit(1)

    logger.info("[OK] Office directory verified")
    logger.info("[OK] pipeline.py found")
    logger.info("")

    # Main loop
    cycle_count = 0
    consecutive_empty = 0
    consecutive_errors = 0

    while _running:
        cycle_count += 1

        try:
            # Check queue before running worker
            queue = read_queue()
            queue_size = len(queue)

            if queue_size > 0:
                logger.info(f"[Cycle {cycle_count}] Queue has {queue_size} pending task(s)")

            # Run worker
            success, task_info = run_worker()

            # Handle results
            if success:
                consecutive_empty = 0
                consecutive_errors = 0

                # Small delay between tasks (gives time for state to settle)
                if _running:
                    time.sleep(1)

            else:
                status = task_info.get("status", "")

                if status == "empty":
                    consecutive_empty += 1
                    consecutive_errors = 0

                    # Log every 5th idle cycle
                    if consecutive_empty % 5 == 1:
                        logger.debug(f"Queue empty (idle {consecutive_empty} cycles)")

                    # Wait before next poll
                    if not wait_or_poll(5):
                        break

                else:
                    consecutive_empty = 0
                    consecutive_errors += 1

                    # Back off on errors
                    backoff = min(10, consecutive_errors * 2)
                    logger.warning(f"Error #{consecutive_errors}, backing off {backoff}s")

                    if not wait_or_poll(backoff):
                        break

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt (Ctrl+C)")
            break

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            if not wait_or_poll(5):
                break

    # Graceful shutdown
    logger.info("")
    logger.info("=" * 80)
    logger.info("CONDUCTOR SHUTTING DOWN")
    logger.info(f"Processed {cycle_count} cycles")
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
