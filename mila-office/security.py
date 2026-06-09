# -*- coding: utf-8 -*-
"""Безопасность: CSRF protection, валидация, защита."""
import logging
import os
import re
import secrets
from pathlib import Path

logger = logging.getLogger("mila.security")

def get_persistent_secret() -> str:
    """Получить или создать персистентный Flask secret key."""
    env = os.getenv("FLASK_SECRET_KEY")
    if env:
        return env

    # Сохраняем secret в файл чтобы переиспользовать при перезагрузке
    secret_file = Path(__file__).resolve().parent / ".secret_key"
    try:
        if secret_file.exists():
            return secret_file.read_text(encoding="utf-8").strip()
        key = secrets.token_hex(32)
        secret_file.write_text(key, encoding="utf-8")
        logger.info("Created persistent Flask secret key")
        return key
    except OSError as e:
        logger.warning(f"Could not persist secret key: {e}")
        return secrets.token_hex(32)

def generate_csrf_token() -> str:
    """Генерировать новый CSRF token."""
    return secrets.token_urlsafe(32)

def validate_agent_key(agent_key: str) -> bool:
    """Проверить что имя агента валидно."""
    # Только буквы и нижний регистр
    return bool(re.fullmatch(r"[a-z_]+", agent_key or ""))

def validate_session_id(session_id: str) -> bool:
    """Проверить что ID сессии валидно."""
    # Hex или URL-safe characters
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]+", session_id or ""))

def validate_job_id(job_id: str) -> bool:
    """Проверить что ID задания валидно."""
    return bool(re.fullmatch(r"[a-f0-9]{16,}", job_id or ""))

def validate_doc_id(doc_id: str) -> bool:
    """Проверить что ID документа валидно."""
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{4,80}", doc_id or ""))

def is_safe_origin(origin: str, host_url: str) -> bool:
    """Проверить что origin из того же сайта (same-origin policy)."""
    if not origin:
        return True
    host_url = host_url.rstrip("/")
    return origin.startswith(host_url)

def extract_csrf_token_from_header(headers: dict) -> str:
    """Извлечь CSRF token из заголовков запроса."""
    return headers.get("X-CSRF-Token", "").strip()

def safe_message_text(text: str) -> str:
    """Очистить текст сообщения от опасных символов."""
    if not isinstance(text, str):
        return ""
    # Основная очистка - убираем нулевые байты и контроль-символы
    return "".join(c for c in text if ord(c) >= 32 or c in "\t\n\r")

def safe_file_name(filename: str) -> str:
    """Сделать имя файла безопасным."""
    # Убираем пути и опасные символы
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w.\-]", "_", filename)
    # Лимит длины
    return filename[:255]

def mask_sensitive_data(text: str) -> str:
    """Замаскировать чувствительные данные в логах (tokens, keys, etc)."""
    # Маскируем tokens и keys
    text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "sk-***MASKED***", text)
    text = re.sub(r"Bearer\s+\S+", "Bearer ***MASKED***", text)
    text = re.sub(r"token['\"]?\s*[:=]\s*['\"]?\S+", "token=***MASKED***", text)
    return text

def rate_limit_key(client_ip: str, endpoint: str) -> str:
    """Генерировать ключ для rate limiting."""
    return f"{client_ip}:{endpoint}"

def should_rate_limit(request_count: int, max_requests: int = 100, time_window: int = 60) -> bool:
    """Проверить нужно ли ограничивать запросы (примитивный rate limiting)."""
    # На продакшене использовать Redis или memcached
    return request_count > max_requests
