# -*- coding: utf-8 -*-
"""
data_sanitizer.py — Удаление конфиденциальных данных из логов и отчётов.

Функции:
  sanitize_text(text)           — удалить email, phone, password, keys из текста
  sanitize_logs(log_file)       — очистить лог-файл от конфиденциальных данных
  mask_sensitive(value, key)    — замаскировать конфиденциальное значение
  is_sensitive_key(key)         — проверить что ключ содержит конфиденциальные данные

Используется в:
  - webapp.py перед логированием пользовательского input
  - error_monitor.py перед сохранением ошибок
  - Перед экспортом отчётов в PDF/Excel
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger("data_sanitizer")


# === Регулярные выражения для конфиденциальных данных ===

PATTERNS = {
    # Email адреса: user@example.com, user+tag@example.co.uk
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',

    # Телефоны: +1234567890, (123) 456-7890, 123-456-7890
    "phone": r'\b(?:\+\d{1,3}[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',

    # Credit cards: 4532-1234-5678-9010 или 4532123456789010
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b|\b[0-9]{16}\b',

    # API ключи: sk-xxx, AKIA...
    "api_key": r'\b(?:sk-|AKIA|secret_|private_|api_key)[A-Za-z0-9_\-]{20,}\b',

    # Пароли в URL: http://user:password@host.com
    "url_password": r'(?<=:)([A-Za-z0-9!@#$%^&*._-]+)(?=@)',

    # Bearer токены: Bearer eyJhbGciOiJIUzI1NiIs...
    "bearer_token": r'Bearer\s+[A-Za-z0-9_\-\.]+',

    # AWS credentials: AKIAIOSFODNN7EXAMPLE
    "aws_access_key": r'\bAKIA[0-9A-Z]{16}\b',

    # OAuth tokens: access_token=xxx, refresh_token=xxx
    "oauth_token": r'(?:access_token|refresh_token|id_token)=([A-Za-z0-9._\-]+)',

    # Суммы денег в сессиях клиентов: $XXX, CAD XXX
    "money": r'(?:\$|CAD|USD)\s*\d+(?:\.\d{2})?',

    # Session IDs / Auth cookies: sid=xxxxx, auth=xxxxx
    "session_id": r'\b(?:sid|sessionid|session_id|auth|token|jwt)=[A-Za-z0-9_\-\.]+\b',

    # Passport/ID номера (все цифры по 9-10): 123456789
    "id_number": r'\b[0-9]{9,10}\b',  # очень чувствительный, используется с контекстом
}

# === Ключи которые указывают на конфиденциальные данные ===

SENSITIVE_KEYS = {
    # Auth
    'password', 'passwd', 'pwd', 'secret', 'token', 'key', 'api_key', 'access_key',
    'private_key', 'secret_key', 'auth', 'authorization', 'bearer',

    # Database
    'db_password', 'db_user', 'database_url', 'connection_string',

    # API
    'api_token', 'api_secret', 'webhook_secret', 'signing_secret',

    # Cloud
    'aws_access_key_id', 'aws_secret_access_key', 'gcp_key', 'azure_key',

    # Third-party
    'stripe_key', 'gumroad_token', 'telegram_token', 'slack_webhook',

    # Personal
    'email', 'phone', 'mobile', 'ssn', 'credit_card', 'card_number',
    'passport', 'id_number', 'drivers_license', 'bank_account',

    # Session
    'session_id', 'session_token', 'cookie', 'sid', 'jwt', 'access_token',
}

# === Функции ===


def is_sensitive_key(key):
    """Проверить что ключ содержит конфиденциальные данные.

    Args:
        key (str): Название ключа (например, 'password', 'api_token')

    Returns:
        bool: True если этот ключ может содержать конфиденциальные данные
    """
    key_lower = str(key).lower()
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def mask_sensitive(value, key=None):
    """Замаскировать конфиденциальное значение.

    Args:
        value: Значение для маскирования
        key (str): Название ключа (для контекста)

    Returns:
        str: Замаскированное значение (например, '***' или 'key:***')
    """
    value_str = str(value)

    if not value_str:
        return "***"

    # Для очень длинных значений (токены, ключи) — показываем только начало/конец
    if len(value_str) > 20:
        return "{}...{}".format(value_str[:6], value_str[-4:])

    # Для коротких значений (пароли) — полностью замаскировать
    return "***"


def sanitize_text(text, patterns=None, aggressive=False):
    """Удалить конфиденциальные данные из текста.

    Args:
        text (str): Текст для очистки
        patterns (list): Какие паттерны использовать (по умолчанию все, кроме 'id_number')
        aggressive (bool): Если True, также удаляет деньги и ID номера (может быть слишком)

    Returns:
        str: Очищенный текст
    """
    if not text or not isinstance(text, str):
        return text

    result = text
    patterns_to_use = patterns or list(PATTERNS.keys())

    # Пропускаем чувствительные паттерны если не aggressive
    if not aggressive:
        patterns_to_use = [p for p in patterns_to_use if p not in ("money", "id_number")]

    for pattern_name in patterns_to_use:
        pattern = PATTERNS.get(pattern_name)
        if pattern:
            result = re.sub(pattern, "[REDACTED]", result, flags=re.IGNORECASE)

    return result


def sanitize_dict(data, aggressive=False):
    """Удалить конфиденциальные данные из словаря (JSON-like).

    Args:
        data (dict): Словарь для очистки
        aggressive (bool): Использовать aggressive режим

    Returns:
        dict: Очищенный словарь
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if is_sensitive_key(key):
            # Если это конфиденциальный ключ — замаскировать значение
            result[key] = mask_sensitive(value, key)
        elif isinstance(value, dict):
            # Рекурсивная очистка вложенных словарей
            result[key] = sanitize_dict(value, aggressive=aggressive)
        elif isinstance(value, list):
            # Рекурсивная очистка списков
            result[key] = [sanitize_dict(v, aggressive=aggressive) if isinstance(v, dict) else v for v in value]
        elif isinstance(value, str):
            # Очистить текст от известных паттернов
            result[key] = sanitize_text(value, aggressive=aggressive)
        else:
            result[key] = value

    return result


def sanitize_logs(log_file, output_file=None):
    """Очистить лог-файл от конфиденциальных данных.

    Args:
        log_file (str or Path): Путь к исходному лог-файлу
        output_file (str or Path): Путь для сохранения очищенного лога (по умолчанию перезаписывает)

    Returns:
        int: Количество строк обработано
    """
    log_file = Path(log_file)
    if not log_file.exists():
        logger.warning(f"Log file not found: {log_file}")
        return 0

    output_file = output_file or log_file
    output_file = Path(output_file)

    processed = 0
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        with open(output_file, "w", encoding="utf-8") as f:
            for line in lines:
                sanitized = sanitize_text(line)
                f.write(sanitized + "\n")
                processed += 1

        logger.info(f"Sanitized {processed} lines from {log_file}")
        return processed

    except Exception as e:
        logger.error(f"Error sanitizing log file: {e}")
        return 0


def check_file_for_sensitive_data(file_path):
    """Проверить файл на наличие конфиденциальных данных.

    Args:
        file_path (str or Path): Путь к файлу

    Returns:
        dict: {
            "has_sensitive": bool,
            "patterns_found": {pattern_name: [matches]},
            "total_matches": int
        }
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {"has_sensitive": False, "patterns_found": {}, "total_matches": 0}

    patterns_found = {}
    total_matches = 0

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        for pattern_name, pattern in PATTERNS.items():
            matches = re.findall(pattern, content, flags=re.IGNORECASE)
            if matches:
                patterns_found[pattern_name] = len(matches)
                total_matches += len(matches)

        return {
            "has_sensitive": total_matches > 0,
            "patterns_found": patterns_found,
            "total_matches": total_matches
        }

    except Exception as e:
        logger.error(f"Error checking file: {e}")
        return {"has_sensitive": False, "patterns_found": {}, "total_matches": 0, "error": str(e)}


if __name__ == "__main__":
    # === Тестирование ===
    print("=== Data Sanitizer Test ===\n")

    # Тест 1: Очистка текста
    test_text = "User john@example.com called +1234567890. API key is sk-abc123def456xyz."
    cleaned = sanitize_text(test_text)
    print(f"Original: {test_text}")
    print(f"Cleaned:  {cleaned}\n")

    # Тест 2: Очистка словаря
    test_dict = {
        "username": "john",
        "password": "SuperSecret123",
        "api_token": "sk-1234567890abcdef",
        "email": "john@example.com",
        "context": {"phone": "+1234567890"}
    }
    cleaned_dict = sanitize_dict(test_dict)
    print("Original dict:")
    print(test_dict)
    print("\nCleaned dict:")
    print(cleaned_dict)
    print()

    # Тест 3: Проверка чувствительных ключей
    print("Sensitive keys check:")
    for key in ["password", "username", "api_token", "action"]:
        is_sensitive = is_sensitive_key(key)
        print(f"  {key}: {'SENSITIVE' if is_sensitive else 'safe'}")
