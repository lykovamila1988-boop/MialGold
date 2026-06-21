# -*- coding: utf-8 -*-
"""Batch PDF processor - обработка множества PDF файлов с OCR и feedback."""

import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("mila.batch_pdf_processor")

try:
    import pypdf
    import fitz  # PyMuPDF
except ImportError:
    pypdf = None
    fitz = None

try:
    import pytesseract
    from PIL import Image
    import io
except ImportError:
    pytesseract = None
    Image = None


class PDFProcessor:
    """Обработка одного PDF с автоматическим выбором метода."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = None
        self.metadata = {}
        self.confidence = 0.0
        self.method_used = None
        self.warnings = []

    def extract_text_pypdf(self) -> str:
        """Извлечь текст используя pypdf (встроенный парсер)."""
        if not pypdf:
            return None

        try:
            text = ""
            with open(self.file_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"

            if text.strip():
                self.method_used = "pypdf"
                self.confidence = 0.85  # 85% уверенность встроенного парсера
                return text
            else:
                self.warnings.append("pypdf извлек пустой текст")
                return None
        except Exception as e:
            logger.warning(f"pypdf error: {e}")
            self.warnings.append(f"pypdf ошибка: {str(e)[:100]}")
            return None

    def extract_text_pdfplumber(self) -> str:
        """Извлечь текст используя pdfplumber (более точный)."""
        try:
            import pdfplumber
        except ImportError:
            return None

        try:
            text = ""
            with pdfplumber.open(self.file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
                    text += "\n"

            if text.strip():
                self.method_used = "pdfplumber"
                self.confidence = 0.90  # 90% уверенность
                return text
            else:
                self.warnings.append("pdfplumber извлек пустой текст")
                return None
        except Exception as e:
            logger.warning(f"pdfplumber error: {e}")
            self.warnings.append(f"pdfplumber ошибка: {str(e)[:100]}")
            return None

    def extract_text_fitz(self) -> str:
        """Извлечь текст используя PyMuPDF (самый быстрый)."""
        if not fitz:
            return None

        try:
            text = ""
            doc = fitz.open(self.file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text += page.get_text() + "\n"
            doc.close()

            if text.strip():
                self.method_used = "fitz"
                self.confidence = 0.88
                return text
            else:
                self.warnings.append("fitz извлек пустой текст")
                return None
        except Exception as e:
            logger.warning(f"fitz error: {e}")
            self.warnings.append(f"fitz ошибка: {str(e)[:100]}")
            return None

    def extract_text_ocr(self) -> str:
        """Извлечь текст используя OCR (Tesseract) для битых PDF."""
        if not pytesseract or not Image:
            return None

        try:
            text = ""
            if fitz:
                # Конвертируем PDF в изображения через PyMuPDF
                doc = fitz.open(self.file_path)
                for page_num in range(min(len(doc), 20)):  # Лимит на 20 страниц
                    page = doc[page_num]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x увеличение
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                    # Распознавание текста
                    page_text = pytesseract.image_to_string(img, lang='rus+eng')
                    text += page_text + "\n"

                doc.close()

            if text.strip():
                self.method_used = "ocr"
                self.confidence = 0.70  # 70% для OCR
                return text
            else:
                self.warnings.append("OCR не нашел текст")
                return None
        except Exception as e:
            logger.warning(f"OCR error: {e}")
            self.warnings.append(f"OCR ошибка: {str(e)[:100]}")
            return None

    def detect_encoding_issues(self, text: str) -> bool:
        """Определить если текст имеет проблемы с кодировкой."""
        if not text:
            return False

        # Проверяем на странные символы или кракозябры
        strange_count = 0
        for char in text[:500]:  # Проверяем первые 500 символов
            if ord(char) > 127 and not self._is_cyrillic(char):
                strange_count += 1

        return strange_count > len(text[:500]) * 0.3  # Если > 30% странных символов

    @staticmethod
    def _is_cyrillic(char: str) -> bool:
        """Проверить кириллица ли это."""
        return 'Ѐ' <= char <= 'ӿ'

    def process(self) -> Dict:
        """Обработать PDF с автоматическим выбором лучшего метода."""
        result = {
            "file": self.file_path.name,
            "status": "error",
            "content": None,
            "metadata": {},
            "confidence": 0,
            "method": None,
            "warnings": [],
            "suggestions": []
        }

        # Проверяем что файл существует
        if not self.file_path.exists():
            result["warnings"].append(f"Файл не найден: {self.file_path}")
            return result

        # Пытаемся несколько методов в порядке приоритета
        methods = [
            self.extract_text_pdfplumber,  # Самый точный
            self.extract_text_fitz,         # Быстрый
            self.extract_text_pypdf,        # Встроенный
            self.extract_text_ocr,          # OCR как последняя попытка
        ]

        for method in methods:
            text = method()
            if text and text.strip():
                # Проверяем на проблемы кодировки
                if self.detect_encoding_issues(text):
                    self.warnings.append("Обнаружены проблемы с кодировкой")
                    result["suggestions"].append("Может потребоваться переконвертирование PDF")
                    # Пробуем следующий метод
                    continue

                # Успех!
                result["status"] = "success"
                result["content"] = text[:5000]  # Первые 5000 символов
                result["metadata"] = {
                    "size": self.file_path.stat().st_size,
                    "pages": self._count_pages()
                }
                result["confidence"] = self.confidence
                result["method"] = self.method_used
                result["warnings"] = self.warnings

                return result

        # Если ничего не сработало
        result["warnings"] = self.warnings
        result["suggestions"] = [
            "PDF может быть поврежден - попробуйте переконвертировать",
            "Если в PDF только изображения - требуется OCR (установить tesseract)",
            "Для защищенных PDF может потребоваться пароль"
        ]

        return result

    def _count_pages(self) -> int:
        """Посчитать страницы в PDF."""
        try:
            if fitz:
                doc = fitz.open(self.file_path)
                count = len(doc)
                doc.close()
                return count
            elif pypdf:
                with open(self.file_path, 'rb') as f:
                    reader = pypdf.PdfReader(f)
                    return len(reader.pages)
        except:
            pass
        return 0


class BatchPDFProcessor:
    """Обработка множества PDF файлов параллельно."""

    def __init__(self, max_parallel: int = 3):
        self.max_parallel = max_parallel
        self.results = []

    async def process_file(self, file_path: str) -> Dict:
        """Обработать один файл асинхронно."""
        processor = PDFProcessor(file_path)
        return processor.process()

    async def process_batch(self, file_paths: List[str]) -> Dict:
        """Обработать batch файлов параллельно."""
        tasks = []
        for file_path in file_paths:
            task = self.process_file(file_path)
            tasks.append(task)

        # Обрабатываем параллельно
        self.results = await asyncio.gather(*tasks)

        return self._compile_report()

    def process_batch_sync(self, file_paths: List[str]) -> Dict:
        """Синхронная версия для простого использования."""
        self.results = []
        for file_path in file_paths:
            processor = PDFProcessor(file_path)
            self.results.append(processor.process())

        return self._compile_report()

    def _compile_report(self) -> Dict:
        """Скомпилировать отчет по всем файлам."""
        successful = [r for r in self.results if r["status"] == "success"]
        failed = [r for r in self.results if r["status"] == "error"]

        report = {
            "total": len(self.results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self.results) * 100 if self.results else 0,
            "files": self.results,
            "summary": {
                "methods_used": self._count_methods(),
                "avg_confidence": self._avg_confidence(),
                "total_warnings": sum(len(r.get("warnings", [])) for r in self.results)
            }
        }

        return report

    def _count_methods(self) -> Dict[str, int]:
        """Посчитать какие методы использовались."""
        methods = {}
        for result in self.results:
            method = result.get("method", "unknown")
            methods[method] = methods.get(method, 0) + 1
        return methods

    def _avg_confidence(self) -> float:
        """Средняя уверенность."""
        confidences = [r.get("confidence", 0) for r in self.results if r.get("status") == "success"]
        return sum(confidences) / len(confidences) if confidences else 0


def main():
    """Демонстрация использования."""
    import sys

    if len(sys.argv) < 2:
        print("Использование: python batch_pdf_processor.py file1.pdf file2.pdf ...")
        return

    processor = BatchPDFProcessor()
    report = processor.process_batch_sync(sys.argv[1:])

    print("\n" + "="*60)
    print("📊 ОТЧЕТ ПО ОБРАБОТКЕ PDF")
    print("="*60)
    print(f"\nВсего файлов: {report['total']}")
    print(f"Успешно: {report['successful']} ({report['success_rate']:.1f}%)")
    print(f"Ошибок: {report['failed']}")
    print(f"\nМетоды: {report['summary']['methods_used']}")
    print(f"Средняя уверенность: {report['summary']['avg_confidence']:.1f}%")
    print(f"Всего предупреждений: {report['summary']['total_warnings']}")

    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ ПО ФАЙЛАМ:")
    print("="*60)

    for file_result in report['files']:
        status = "✅" if file_result['status'] == "success" else "❌"
        print(f"\n{status} {file_result['file']}")
        if file_result['status'] == "success":
            print(f"   Метод: {file_result['method']}")
            print(f"   Уверенность: {file_result['confidence']:.0f}%")
            print(f"   Страниц: {file_result['metadata'].get('pages', '?')}")
            print(f"   Размер: {file_result['metadata'].get('size', 0) // 1024}KB")

        if file_result['warnings']:
            print(f"   ⚠️  Предупреждения: {', '.join(file_result['warnings'])}")

        if file_result['suggestions']:
            print(f"   💡 Предложения: {', '.join(file_result['suggestions'])}")

    # Сохраняем результаты в JSON
    output_file = Path("pdf_processing_report.json")
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n✅ Отчет сохранен в {output_file}")


if __name__ == "__main__":
    main()
