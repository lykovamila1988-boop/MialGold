# -*- coding: utf-8 -*-
"""Batch upload handler для web интерфейса - обработка множества файлов."""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import hashlib

from batch_pdf_processor import BatchPDFProcessor, PDFProcessor

logger = __import__("logging").getLogger("mila.batch_upload_handler")

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Максимум 100MB per batch
MAX_BATCH_SIZE = 100 * 1024 * 1024
# Максимум 20 файлов за раз
MAX_FILES_PER_BATCH = 20


class BatchUploadHandler:
    """Обработка batch загрузок с прогрессом и feedback."""

    def __init__(self):
        self.current_batch_id = None
        self.batch_info = {}

    def generate_batch_id(self) -> str:
        """Генерировать уникальный ID для batch."""
        timestamp = datetime.now().isoformat()
        batch_hash = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"batch_{batch_hash}"

    def validate_files(self, files: List[Tuple[str, bytes]]) -> Tuple[bool, List[str], List[str]]:
        """Проверить файлы перед обработкой.

        Returns:
            (is_valid, valid_files, errors)
        """
        valid_files = []
        errors = []
        total_size = 0

        if len(files) > MAX_FILES_PER_BATCH:
            errors.append(f"Максимум {MAX_FILES_PER_BATCH} файлов за раз, загружено {len(files)}")
            return False, [], errors

        for filename, content in files:
            # Проверяем расширение
            if not filename.lower().endswith('.pdf'):
                errors.append(f"❌ {filename} - только PDF файлы поддерживаются")
                continue

            # Проверяем размер
            file_size = len(content)
            if file_size > 50 * 1024 * 1024:  # 50MB per file
                errors.append(f"❌ {filename} - файл слишком большой (>{50}MB)")
                continue

            # Проверяем минимальный размер
            if file_size < 1024:  # 1KB
                errors.append(f"❌ {filename} - файл слишком маленький (<1KB)")
                continue

            total_size += file_size
            valid_files.append(filename)

        # Проверяем общий размер
        if total_size > MAX_BATCH_SIZE:
            errors.append(f"❌ Общий размер превышен (максимум {MAX_BATCH_SIZE // 1024 // 1024}MB)")
            return False, [], errors

        is_valid = len(errors) == 0 or len(valid_files) > 0
        return is_valid, valid_files, errors

    def save_uploaded_files(self, batch_id: str, files: List[Tuple[str, bytes]]) -> List[str]:
        """Сохранить загруженные файлы на диск."""
        batch_dir = UPLOAD_DIR / batch_id
        batch_dir.mkdir(exist_ok=True)

        saved_paths = []
        for filename, content in files:
            file_path = batch_dir / filename
            file_path.write_bytes(content)
            saved_paths.append(str(file_path))

        return saved_paths

    def process_batch(self, batch_id: str, file_paths: List[str]) -> Dict:
        """Обработать batch файлов."""
        processor = BatchPDFProcessor()
        report = processor.process_batch_sync(file_paths)

        # Добавляем batch info
        report["batch_id"] = batch_id
        report["timestamp"] = datetime.now().isoformat()
        report["upload_dir"] = str(UPLOAD_DIR / batch_id)

        # Сохраняем отчет
        report_path = UPLOAD_DIR / batch_id / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

        return report

    def handle_upload(self, files: List[Tuple[str, bytes]]) -> Dict:
        """Главная функция обработки загрузки.

        Args:
            files: List[(filename, content_bytes), ...]

        Returns:
            {
                "status": "success|error",
                "batch_id": "...",
                "message": "...",
                "report": {...},
                "download_url": "..."
            }
        """
        # Валидация
        is_valid, valid_files, errors = self.validate_files(files)

        if not valid_files:
            return {
                "status": "error",
                "message": "Нет валидных файлов",
                "errors": errors,
                "batch_id": None
            }

        # Генерируем batch ID
        batch_id = self.generate_batch_id()

        try:
            # Сохраняем файлы
            file_tuples = [(f, c) for f, c in files if f in valid_files]
            saved_paths = self.save_uploaded_files(batch_id, file_tuples)

            # Обрабатываем batch
            report = self.process_batch(batch_id, saved_paths)

            # Подготавливаем ответ
            response = {
                "status": "success",
                "batch_id": batch_id,
                "message": f"Обработано {report['successful']}/{report['total']} файлов",
                "errors": errors,  # Ошибки валидации
                "report": report,
                "download_url": f"/api/download-batch/{batch_id}"
            }

            return response

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return {
                "status": "error",
                "batch_id": batch_id,
                "message": f"Ошибка обработки: {str(e)}",
                "errors": [str(e)]
            }

    def get_batch_report(self, batch_id: str) -> Dict:
        """Получить отчет batch обработки."""
        report_path = UPLOAD_DIR / batch_id / "report.json"

        if not report_path.exists():
            return {"error": f"Batch {batch_id} не найден"}

        return json.loads(report_path.read_text(encoding="utf-8"))

    def cleanup_old_batches(self, days: int = 7):
        """Удалить старые batch файлы (старше N дней)."""
        import time

        cutoff_time = time.time() - (days * 24 * 3600)
        cleaned = 0

        for batch_dir in UPLOAD_DIR.iterdir():
            if batch_dir.is_dir():
                if batch_dir.stat().st_mtime < cutoff_time:
                    import shutil
                    shutil.rmtree(batch_dir)
                    cleaned += 1

        return cleaned


# Flask integration
def register_batch_upload_routes(app):
    """Регистрировать routes для batch upload."""
    from flask import request, jsonify

    handler = BatchUploadHandler()

    @app.post("/api/batch-upload")
    def batch_upload():
        """Загрузить и обработать batch PDF файлов."""
        try:
            # Получаем файлы из request
            files = request.files.getlist('files')

            if not files:
                return jsonify({"error": "Нет файлов"}), 400

            # Конвертируем в нужный формат
            file_data = [(f.filename, f.read()) for f in files]

            # Обрабатываем
            result = handler.handle_upload(file_data)

            status_code = 200 if result["status"] == "success" else 400
            return jsonify(result), status_code

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.get("/api/batch-report/<batch_id>")
    def batch_report(batch_id):
        """Получить отчет batch обработки."""
        try:
            report = handler.get_batch_report(batch_id)
            if "error" in report:
                return jsonify(report), 404
            return jsonify(report), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/download-batch/<batch_id>")
    def download_batch(batch_id):
        """Скачать обработанные результаты batch."""
        from flask import send_file

        try:
            report_path = UPLOAD_DIR / batch_id / "report.json"

            if not report_path.exists():
                return jsonify({"error": "Batch не найден"}), 404

            return send_file(
                report_path,
                mimetype="application/json",
                as_attachment=True,
                download_name=f"batch_{batch_id}_report.json"
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    logger.info("Batch upload routes registered")


# CLI Usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование: python batch_upload_handler.py file1.pdf file2.pdf ...")
        sys.exit(1)

    handler = BatchUploadHandler()

    # Читаем файлы
    files = []
    for file_path in sys.argv[1:]:
        path = Path(file_path)
        if path.exists():
            files.append((path.name, path.read_bytes()))
        else:
            print(f"Файл не найден: {file_path}")

    if not files:
        print("Нет файлов для обработки")
        sys.exit(1)

    # Обрабатываем
    result = handler.handle_upload(files)

    print("\n" + "="*60)
    print("📊 РЕЗУЛЬТАТ BATCH ЗАГРУЗКИ")
    print("="*60)
    print(f"Статус: {result['status']}")
    print(f"Batch ID: {result['batch_id']}")
    print(f"Сообщение: {result['message']}")

    if "report" in result:
        report = result["report"]
        print(f"\nОбработано: {report['successful']}/{report['total']}")
        print(f"Успешность: {report['success_rate']:.1f}%")

    if result.get("errors"):
        print(f"\nОшибки:")
        for error in result["errors"]:
            print(f"  - {error}")

    print(f"\nОтчет: {result.get('download_url', 'N/A')}")
