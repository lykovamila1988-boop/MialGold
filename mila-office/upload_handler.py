# -*- coding: utf-8 -*-
"""Обработка загруженных файлов (PDF, DOCX, изображения с OCR)."""
import base64
import io
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

import requests

import base

logger = logging.getLogger("mila.upload_handler")

def decode_text_file(raw: bytes) -> str:
    """Декодировать текстовый файл (автоматически определить кодировку)."""
    for enc in ("utf-8-sig", "utf-8", "cp1251", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")

def looks_garbled(text: str) -> bool:
    """Проверить выглядит ли PDF текст поломанным (bittet text layer из GAMMA).

    Признаки: кириллические слова перемешаны с латиницей/цифрами внутри слова
    (типа 'Поч<G', '6ы5иD4N').
    """
    tokens = re.findall(r"\S+", text or "")
    cyr_tokens = mixed = 0
    for t in tokens:
        if not re.search(r"[а-яёА-ЯЁ]", t):
            continue  # чисто латинские/числовые
        cyr_tokens += 1
        if re.search(r"[A-Za-z0-9]", t):  # смешанный токен
            mixed += 1

    if cyr_tokens < 10:
        return False  # слишком мало данных

    return (mixed / cyr_tokens) > 0.30

def extract_pdf_text(raw: bytes) -> Tuple[str, str]:
    """Извлечь текст из PDF. При необходимости использует OCR.

    Возвращает (text, note) где note — пояснение если что-то пошло не так.
    """
    import io
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return "", "PDF загружен, но библиотека pypdf не установлена."

    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = []
        for page in reader.pages[:30]:
            pages.append(page.extract_text() or "")
        text = "\n\n".join(pages).strip()

        # Проверяем битый ли текстовый слой
        garbled = looks_garbled(text)

        # Если нет текста или битый слой — пробуем OCR
        if (not text or garbled) and os.getenv("MILA_PDF_OCR", "1").lower() in ("1", "true", "yes"):
            ocr_text, ocr_note = _pdf_ocr_via_gemini(raw)
            if ocr_text and not looks_garbled(ocr_text):
                return ocr_text, ocr_note

        if not text:
            return "", "PDF загружен, но текст не найден. Возможно это скан."

        if garbled:
            note = (
                "⚠️ Текстовый слой этого PDF повреждён: извлечение даёт нечитаемую кодировочную кашу. "
                "Пришли это же в Markdown/.docx/текстом — тогда сможем оценить содержание."
            )
            return note, "Битый текстовый слой PDF"

        return text, ""
    except Exception as e:
        return "", f"Не удалось прочитать PDF: {type(e).__name__}"

def extract_docx_text(raw: bytes) -> Tuple[str, str]:
    """Извлечь текст из DOCX."""
    try:
        from docx import Document
    except ImportError:
        return "", "DOCX загружен, но библиотека python-docx не установлена."

    try:
        doc = Document(io.BytesIO(raw))
        paragraphs = [p.text for p in doc.paragraphs]
        text = "\n".join(paragraphs).strip()

        if not text:
            return "", "DOCX загружен, но текст не найден."

        return text, ""
    except Exception as e:
        return "", f"Не удалось прочитать DOCX: {type(e).__name__}"

def describe_image_with_claude(raw: bytes, mime: str) -> Tuple[str, str]:
    """Описать изображение через Claude vision API."""
    try:
        client = base.get_client()
        b64 = base64.standard_b64encode(raw).decode()
        msg = client.messages.create(
            model=base.MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Опиши что видишь на этом изображении кратко."},
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": b64,
                    }},
                ],
            }],
        )
        text = msg.content[0].text if msg.content else ""
        return text, ""
    except Exception as e:
        logger.error(f"Claude vision error: {e}")
        return "", f"Не удалось анализировать изображение: {type(e).__name__}"

def extract_upload(filename: str, raw: bytes, mime: str) -> Tuple[str, str]:
    """Универсальный обработчик загруженного файла.

    Возвращает (text, note) где text — извлеченный контент.
    """
    if not filename:
        return "", "Файл не назван"

    lower = filename.lower()

    # Текстовые файлы
    if lower.endswith((".txt", ".md")):
        return decode_text_file(raw), ""

    # PDF
    if lower.endswith(".pdf") or mime == "application/pdf":
        return extract_pdf_text(raw)

    # DOCX
    if lower.endswith(".docx") or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return extract_docx_text(raw)

    # Изображения
    if mime.startswith("image/"):
        return describe_image_with_claude(raw, mime)

    return "", f"Неподдерживаемый тип файла: {mime}"

def _ocr_one_page(args) -> str:
    """Распознать одну страницу PDF через Gemini API."""
    idx, png, url, key, prompt = args
    payload = {
        "contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png).decode()}},
        ]}],
        "generationConfig": {"maxOutputTokens": 2048},
    }

    for attempt in range(3):
        try:
            r = requests.post(url, params={"key": key}, json=payload, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return f"[стр. {idx+1}: ошибка {r.status_code}]"

            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
            return text or f"[стр. {idx+1}: пусто]"
        except Exception as e:
            if attempt == 2:
                return f"[стр. {idx+1}: сбой {type(e).__name__}]"
            import time
            time.sleep(1.5 * (attempt + 1))

    return f"[стр. {idx+1}: не удалось]"

def _pdf_ocr_via_gemini(raw: bytes) -> Tuple[str, str]:
    """OCR для PDF с битым текстовым слоем через Gemini.

    Возвращает (text, note).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", "OCR недоступен: не установлен PyMuPDF (pip install pymupdf)"

    key = getattr(base, "GEMINI_KEY", "")
    if not key:
        return "", "OCR недоступен: не задан GEMINI_KEY"

    max_pages = int(os.getenv("MILA_PDF_OCR_PAGES", "15"))
    model = getattr(base, "GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (
        "Перед тобой страница PDF — рабочая тетрадь на русском. "
        "Извлеки ВЕСЬ читаемый текст со страницы дословно: заголовки, списки, вопросы. "
        "Сохрани порядок. Ничего не добавляй."
    )

    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        return "", f"OCR: не удалось открыть PDF ({type(e).__name__})"

    total = len(doc)
    n = min(total, max_pages)

    # Рендер страниц в PNG
    jobs = []
    for i in range(n):
        try:
            png = doc[i].get_pixmap(dpi=130).tobytes("png")
            jobs.append((i, png, url, key, prompt))
        except Exception:
            jobs.append((i, b"", url, key, prompt))
    doc.close()

    # Параллельный OCR через Gemini
    results = [""] * n
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, txt in zip(range(n), ex.map(_ocr_one_page, jobs)):
            results[i] = txt

    text = "\n\n".join(results).strip()
    if not text:
        return "", "OCR не дал результата"

    if total > n:
        text += f"\n\n[…первые {n} из {total} страниц]"

    note = "Текст распознан через OCR (Gemini) — возможны мелкие неточности"
    return text, note
