# -*- coding: utf-8 -*-
"""Управление очередью асинхронных задач (jobs) для агентов."""
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger("mila.job_queue")

# Глобальное хранилище заданий: {job_id: {status, reply, error, ...}}
_jobs = {}
_jobs_lock = threading.Lock()

def create_job(job_id: str, session_id: str, agent_key: str) -> Dict[str, Any]:
    """Создать новое задание."""
    job = {
        "id": job_id,
        "sid": session_id,
        "agent_key": agent_key,
        "status": "pending",
        "reply": None,
        "error": None,
        "verdict": None,
        "next_agent": None,
        "doc_id": None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    logger.info(f"Created job {job_id} for {agent_key}")
    return job

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Получить задание по ID."""
    with _jobs_lock:
        return _jobs.get(job_id)

def update_job(job_id: str, **kwargs):
    """Обновить поля задания."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
            logger.debug(f"Updated job {job_id}: {kwargs}")

def complete_job(job_id: str, reply: str, doc_id: str = None, verdict: str = None, next_agent: str = None):
    """Завершить задание с результатом."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update({
                "status": "done",
                "reply": reply,
                "doc_id": doc_id,
                "verdict": verdict or "ready_next",
                "next_agent": next_agent,
            })
            logger.info(f"Completed job {job_id}")

def fail_job(job_id: str, error: str):
    """Пометить задание как ошибка."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update({
                "status": "error",
                "error": error,
            })
            logger.error(f"Failed job {job_id}: {error}")

def remove_job(job_id: str):
    """Удалить задание из памяти (результат был прочитан)."""
    with _jobs_lock:
        _jobs.pop(job_id, None)
        logger.debug(f"Removed job {job_id}")

def get_all_jobs() -> Dict[str, Dict[str, Any]]:
    """Получить все задания (для отладки)."""
    with _jobs_lock:
        return dict(_jobs)

def clear_old_jobs(max_age_seconds: int = 3600):
    """Очистить старые задания (опционально вызывать периодически)."""
    with _jobs_lock:
        to_remove = []
        for job_id, job in _jobs.items():
            if job.get("status") != "pending":
                to_remove.append(job_id)

        for job_id in to_remove:
            del _jobs[job_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")
