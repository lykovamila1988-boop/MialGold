# -*- coding: utf-8 -*-
"""Работа с файлами: загрузки, сохранение, экспорт."""
import json
import logging
import mimetypes
from pathlib import Path
from typing import Tuple, Dict, Any

import base
import security

logger = logging.getLogger("mila.file_handler")

UPLOADS_DIR = base.MILA_FOLDER / "mila-office" / "_uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def save_uploaded_file(filename: str, content: bytes) -> Tuple[str, str]:
    """Сохранить загруженный файл. Возвращает (upload_id, safe_filename)."""
    safe_name = security.safe_file_name(filename)
    upload_id = __import__("secrets").token_hex(8)

    path = UPLOADS_DIR / f"{upload_id}_{safe_name}"
    try:
        path.write_bytes(content)
        logger.info(f"Saved upload {upload_id}: {safe_name} ({len(content)} bytes)")
        return upload_id, safe_name
    except IOError as e:
        logger.error(f"Failed to save upload: {e}")
        raise

def get_upload_path(upload_id: str) -> Path:
    """Получить путь к загруженному файлу."""
    # Защита от path traversal
    if not security.validate_session_id(upload_id):
        raise ValueError(f"Invalid upload_id: {upload_id}")
    return UPLOADS_DIR / upload_id

def delete_upload(upload_id: str):
    """Удалить загруженный файл."""
    try:
        path = get_upload_path(upload_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted upload {upload_id}")
    except Exception as e:
        logger.error(f"Failed to delete upload {upload_id}: {e}")

def save_json_file(filename: str, data: Dict[str, Any]) -> Path:
    """Сохранить JSON файл."""
    path = base.MILA_FOLDER / "mila-office" / "_data" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved JSON: {filename}")
        return path
    except IOError as e:
        logger.error(f"Failed to save {filename}: {e}")
        raise

def load_json_file(filename: str) -> Dict[str, Any]:
    """Загрузить JSON файл."""
    path = base.MILA_FOLDER / "mila-office" / "_data" / filename
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}

def get_mime_type(filename: str) -> str:
    """Определить MIME type по расширению файла."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"

def save_text_export(filename: str, content: str) -> Path:
    """Сохранить текстовый файл для экспорта."""
    export_dir = base.MILA_FOLDER / "mila-office" / "_exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    safe_name = security.safe_file_name(filename)
    path = export_dir / safe_name

    try:
        path.write_text(content, encoding="utf-8")
        logger.info(f"Saved export: {safe_name}")
        return path
    except IOError as e:
        logger.error(f"Failed to save export: {e}")
        raise

def list_uploads() -> list:
    """Получить список всех загруженных файлов."""
    try:
        uploads = []
        for path in UPLOADS_DIR.glob("*"):
            if path.is_file():
                uploads.append({
                    "id": path.name,
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                })
        return sorted(uploads, key=lambda x: x["modified"], reverse=True)
    except Exception as e:
        logger.error(f"Failed to list uploads: {e}")
        return []

def cleanup_old_uploads(max_age_days: int = 7):
    """Удалить старые загруженные файлы."""
    import time
    now = time.time()
    max_age_seconds = max_age_days * 86400

    try:
        removed = 0
        for path in UPLOADS_DIR.glob("*"):
            if path.is_file():
                age = now - path.stat().st_mtime
                if age > max_age_seconds:
                    path.unlink()
                    removed += 1
        if removed:
            logger.info(f"Cleaned up {removed} old uploads")
    except Exception as e:
        logger.error(f"Failed to cleanup uploads: {e}")
