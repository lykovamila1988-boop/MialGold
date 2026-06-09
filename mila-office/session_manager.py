# -*- coding: utf-8 -*-
"""Управление сессиями и историей чатов."""
import json
import logging
from pathlib import Path

import base

logger = logging.getLogger("mila.session_manager")

SESSIONS_DIR = base.MILA_FOLDER / "mila-office" / "_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _session_file(session_id: str, agent_key: str) -> Path:
    """Путь к файлу истории для сессии и агента."""
    return SESSIONS_DIR / f"{session_id}_{agent_key}.json"

def save_message(session_id: str, agent_key: str, role: str, content: str, metadata: dict = None):
    """Сохранить сообщение в историю."""
    path = _session_file(session_id, agent_key)
    path.parent.mkdir(parents=True, exist_ok=True)

    history = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            history = []

    msg = {"role": role, "content": content}
    if metadata:
        msg.update(metadata)
    history.append(msg)

    try:
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except IOError as e:
        logger.error(f"Failed to save message: {e}")

def load_history(session_id: str, agent_key: str) -> list:
    """Загрузить историю чата для агента."""
    path = _session_file(session_id, agent_key)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []

def trim_history(history: list) -> list:
    """Обрезать историю до разумного размера."""
    return history[-10:] if len(history) > 10 else history
