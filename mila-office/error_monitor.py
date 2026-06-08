# -*- coding: utf-8 -*-
"""
error_monitor.py — Централизованный механизм логирования ошибок с Telegram alerts.

Используется: webapp.py, агенты, pipeline.py

Функции:
  log_error(error, context={}, alert=False)  — логирует с traceback
  get_error_stats(hours=24)                  — статистика за период
  get_recent_errors(limit=10)               — последние ошибки
"""
import json
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys

try:
    import requests
except ImportError:
    requests = None

# === Пути и конфигурация ===

MILA_FOLDER = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
LOG_DIR = MILA_FOLDER / "logs"
ERROR_LOG = LOG_DIR / "errors.jsonl"  # Структурированный лог ошибок
ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

# === Логирование ===

logger = logging.getLogger("error_monitor")
handler = logging.FileHandler(ERROR_LOG.parent / "error_monitor.log", encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# === Telegram ===

TELEGRAM_TOKEN = (
    os.getenv("TELEGRAM_API") or
    os.getenv("TELEGRAM_BOT_TOKEN") or
    os.getenv("TELEGRAM_TOKEN") or
    ""
).strip()
TELEGRAM_ADMIN_CHAT_ID = (
    os.getenv("TELEGRAM_ADMIN_CHAT_ID") or
    os.getenv("TELEGRAM_ALERT_CHAT_ID") or
    ""
).strip()


def log_error(error, context=None, alert=False, level="ERROR"):
    """Логировать ошибку с полным traceback и контекстом.

    Args:
        error (Exception): Объект исключения
        context (dict): Дополнительный контекст (agent, endpoint, user_action)
        alert (bool): Отправить Telegram alert (для критических ошибок)
        level (str): "ERROR" или "CRITICAL"

    Returns:
        str: ID записи в логе (для ссылки в ответе пользователю)
    """
    context = context or {}

    # Форматируем информацию об ошибке
    error_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "context": context,
    }

    # Пишем структурированный лог
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_data, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Не смог написать в error log: {e}")

    # Логируем в стандартный лог
    logger.log(
        logging.CRITICAL if level == "CRITICAL" else logging.ERROR,
        f"{error_data['error_type']}: {error_data['error_message']} | Context: {context}"
    )

    # Отправляем Telegram alert если нужно
    if alert and TELEGRAM_TOKEN and TELEGRAM_ADMIN_CHAT_ID:
        _send_telegram_alert(error_data)

    return error_data["timestamp"]


def _send_telegram_alert(error_data):
    """Отправить сообщение об ошибке в Telegram Людмиле."""
    if not requests:
        return

    level = error_data.get("level", "ERROR")
    error_type = error_data.get("error_type", "Unknown")
    message_text = error_data.get("error_message", "")
    context = error_data.get("context", {})

    # Форматируем message для Telegram
    alert_msg = (
        f"⚠️ **{level}: {error_type}**\n\n"
        f"Message: {message_text[:100]}\n"
    )

    if context:
        alert_msg += f"\n**Context:**\n"
        for key, value in context.items():
            val_str = str(value)[:50]
            alert_msg += f"• {key}: {val_str}\n"

    alert_msg += f"\n**Time:** {error_data.get('timestamp', 'unknown')}"

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_ADMIN_CHAT_ID,
                "text": alert_msg,
                "parse_mode": "Markdown"
            },
            timeout=5
        )
        if not response.ok:
            logger.warning(f"Telegram alert failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"Не смог отправить Telegram alert: {e}")


def get_error_stats(hours=24):
    """Получить статистику ошибок за последние N часов.

    Returns:
        dict: {
            "period": "last 24 hours",
            "total_errors": 5,
            "by_type": {"ValueError": 2, "TimeoutError": 1, ...},
            "by_level": {"ERROR": 4, "CRITICAL": 1},
            "by_context": {"webapp": 3, "pipeline": 2}
        }
    """
    if not ERROR_LOG.exists():
        return {
            "period": f"last {hours} hours",
            "total_errors": 0,
            "by_type": {},
            "by_level": {},
            "by_context": {}
        }

    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    errors_by_type = {}
    errors_by_level = {}
    errors_by_context = {}
    total = 0

    try:
        with open(ERROR_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record_time = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))

                    if record_time < cutoff_time:
                        continue

                    total += 1
                    error_type = record.get("error_type", "Unknown")
                    level = record.get("level", "ERROR")
                    context_source = record.get("context", {}).get("source", "unknown")

                    errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
                    errors_by_level[level] = errors_by_level.get(level, 0) + 1
                    errors_by_context[context_source] = errors_by_context.get(context_source, 0) + 1
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        logger.error(f"Ошибка при чтении error log: {e}")

    return {
        "period": f"last {hours} hours",
        "total_errors": total,
        "by_type": errors_by_type,
        "by_level": errors_by_level,
        "by_context": errors_by_context
    }


def get_recent_errors(limit=10):
    """Получить последние N ошибок с полной информацией.

    Returns:
        list: [
            {
                "timestamp": "2026-06-08T14:05:32Z",
                "error_type": "ValueError",
                "error_message": "invalid literal for int()",
                "context": {"agent": "lera", "endpoint": "/api/..."}
            },
            ...
        ]
    """
    if not ERROR_LOG.exists():
        return []

    errors = []
    try:
        with open(ERROR_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    errors.append({
                        "timestamp": record.get("timestamp"),
                        "level": record.get("level"),
                        "error_type": record.get("error_type"),
                        "error_message": record.get("error_message"),
                        "context": record.get("context", {})
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        logger.error(f"Ошибка при чтении error log: {e}")

    # Возвращаем последние N (обратный порядок)
    return errors[-limit:][::-1]


def clear_old_errors(days=30):
    """Удалить ошибки старше N дней (очистка лога)."""
    if not ERROR_LOG.exists():
        return

    cutoff_time = datetime.utcnow() - timedelta(days=days)
    kept_errors = []
    deleted_count = 0

    try:
        with open(ERROR_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    record_time = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
                    if record_time >= cutoff_time:
                        kept_errors.append(line.rstrip("\n"))
                    else:
                        deleted_count += 1
                except (json.JSONDecodeError, ValueError):
                    kept_errors.append(line.rstrip("\n"))

        # Перезаписываем файл
        with open(ERROR_LOG, "w", encoding="utf-8") as f:
            for line in kept_errors:
                f.write(line + "\n")

        logger.info(f"Cleaned {deleted_count} old error records")
    except Exception as e:
        logger.error(f"Ошибка при очистке error log: {e}")


if __name__ == "__main__":
    # Тестирование
    print("=== Error Monitor Test ===\n")

    # Логируем тестовую ошибку
    try:
        1 / 0
    except ZeroDivisionError as e:
        error_id = log_error(e, context={"source": "test", "action": "division"}, alert=False)
        print("[OK] Error logged with ID: {}\n".format(error_id))

    # Статистика
    stats = get_error_stats(hours=24)
    print("Error stats (last 24h):")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print()

    # Последние ошибки
    recent = get_recent_errors(limit=3)
    print("Recent errors (last 3):")
    for err in recent:
        print("  - {}: {} ({})".format(err['timestamp'], err['error_type'], err['context'].get('source', 'unknown')))
