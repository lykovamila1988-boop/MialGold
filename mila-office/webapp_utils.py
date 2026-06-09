# -*- coding: utf-8 -*-
"""Утилиты для webapp."""
import logging
import re
import secrets

logger = logging.getLogger("mila.webapp_utils")

def generate_job_id() -> str:
    """Генерировать уникальный ID для задачи."""
    return secrets.token_hex(8)

def generate_session_id() -> str:
    """Генерировать уникальный ID для сессии."""
    return secrets.token_hex(8)

def clip_text(text: str, max_len: int = 500) -> str:
    """Обрезать текст если слишком длинный."""
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text

def safe_upload_name(name: str) -> str:
    """Сделать имя файла безопасным."""
    safe = re.sub(r"[^\w.\-]", "_", name)
    return safe[:200]

def looks_garbled(text: str) -> bool:
    """Проверить выглядит ли текст поломанным."""
    bad_chars = sum(1 for c in text if ord(c) in (0xFFFD, 0xFFFE, 0xFFFF) or ord(c) < 32)
    return bad_chars / max(len(text), 1) > 0.1

def decode_text_file(raw: bytes) -> str:
    """Декодировать текстовый файл."""
    for encoding in ["utf-8", "utf-16", "cp1251", "latin-1"]:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, AttributeError):
            continue
    return raw.decode("utf-8", errors="replace")
