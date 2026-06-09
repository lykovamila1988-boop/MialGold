# -*- coding: utf-8 -*-
"""Управление документами в офисе."""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import base

logger = logging.getLogger("mila.document_manager")

DOCUMENTS_DIR = base.MILA_FOLDER / "mila-office" / "_documents"
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

def safe_doc_id(doc_id: str) -> str:
    """Валидировать и очистить ID документа."""
    doc_id = (doc_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", doc_id):
        raise ValueError(f"Invalid doc_id: {doc_id}")
    return doc_id

def doc_path(doc_id: str) -> Path:
    """Путь к JSON-файлу документа."""
    return DOCUMENTS_DIR / f"{safe_doc_id(doc_id)}.json"

def doc_export_path(doc_id: str) -> Path:
    """Путь к TXT-файлу для скачивания."""
    return DOCUMENTS_DIR / f"{safe_doc_id(doc_id)}.txt"

def plain_msg_text(item) -> str:
    """Извлечь текст из элемента истории."""
    if isinstance(item, dict):
        return str(item.get("content") or item.get("text") or item.get("message") or "")
    return str(item or "")

def extract_doc_ids(text: str) -> set:
    """Найти все ID документов в тексте."""
    text = text or ""
    ids = set(re.findall(r"\[doc_id:([A-Za-z0-9_-]{4,80})\]", text))
    ids.update(re.findall(r"/api/document/([A-Za-z0-9_-]{4,80})", text))
    return sorted(ids)

def extract_final_document(reply: str) -> str:
    """Извлечь готовый документ из маркеров [ДОКУМЕНТ] … [/ДОКУМЕНТ]."""
    match = re.search(r"\[ДОКУМЕНТ\](.*?)\[/ДОКУМЕНТ\]", reply, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

def strip_doc_block(reply: str) -> str:
    """Удалить блоки документов из текста."""
    return re.sub(r"\[ДОКУМЕНТ\](.*?)\[/ДОКУМЕНТ\]", "", reply, flags=re.DOTALL).strip()

def document_to_text(doc: dict) -> str:
    """Преобразовать документ в чистый текст для скачивания."""
    lines = []

    if doc.get("file_name"):
        lines.append(f"📄 {doc['file_name']}")

    if doc.get("created_at"):
        lines.append(f"📅 {doc['created_at']}")

    if doc.get("original_content"):
        lines.append("\n" + "="*60)
        lines.append("ИСХОДНЫЙ КОНТЕНТ")
        lines.append("="*60)
        lines.append(doc["original_content"])

    # Если есть финальная версия — показываем её первой
    if doc.get("final_content"):
        lines.append("\n" + "="*60)
        lines.append("✅ ФИНАЛЬНАЯ ВЕРСИЯ (готова к публикации)")
        lines.append("="*60)
        lines.append(doc["final_content"])

    # Стадии редактуры
    if doc.get("stages"):
        lines.append("\n" + "="*60)
        lines.append("📝 СТАДИИ РЕДАКТУРЫ")
        lines.append("="*60)
        for i, stage in enumerate(doc["stages"], 1):
            agent = stage.get("agent", "?").upper()
            verdict = stage.get("verdict", "?")
            lines.append(f"\n[{i}] {agent} — {verdict}")
            if stage.get("output"):
                lines.append(stage["output"])

    return "\n".join(lines)

def download_text(doc: dict) -> str:
    """Текст для скачивания (только финальная версия или исходный контент)."""
    if doc.get("final_content"):
        return doc["final_content"]
    return doc.get("original_content", "")

def load_record(doc_id: str, histories: dict = None) -> dict:
    """Загрузить запись документа. Если нет — восстановить из истории."""
    path = doc_path(doc_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception(f"Document record unreadable: {path}")

    # Фолбэк: восстановить из истории чатов
    if histories:
        return _document_from_history(doc_id, histories)

    return _missing_document(doc_id)

def _document_from_history(doc_id: str, histories: dict) -> dict:
    """Восстановить документ из истории агентов."""
    doc_id = safe_doc_id(doc_id)
    hits = []

    for sid, agent_histories in list(histories.items()):
        if not agent_histories:
            continue
        for agent_key, hist in list(agent_histories.items()):
            for idx, item in enumerate(hist or []):
                text = plain_msg_text(item)
                if doc_id in text:
                    prev = plain_msg_text(hist[idx - 1]) if idx else ""
                    hits.append({
                        "agent": agent_key,
                        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
                        "verdict": "done" if "VERDICT: done" in text or "готов" in text.lower() else "ready_next",
                        "input": prev[-8000:],
                        "output": text[-20000:],
                    })

    if hits:
        return {
            "id": doc_id,
            "file_name": f"mila-document-{doc_id}.txt",
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
            "status": "ready",
            "original_content": hits[0].get("input", ""),
            "stages": hits,
            "feedback_chain": [],
        }

    return _missing_document(doc_id)

def _missing_document(doc_id: str) -> dict:
    """Документ не найден в истории."""
    return {
        "id": doc_id,
        "file_name": f"mila-document-{doc_id}.txt",
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "status": "missing_source",
        "original_content": "",
        "stages": [{
            "agent": "office",
            "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
            "verdict": "needs_revision",
            "input": "",
            "output": (
                f"Документ {doc_id} был упомянут, но исходный файл не сохранен. "
                "Отправьте его агенту ещё раз."
            ),
        }],
        "feedback_chain": [],
    }

def save_record(doc_id: str, agent_key: str, user_msg: str, reply: str, attachment: dict = None) -> dict:
    """Сохранить этап редактуры документа."""
    doc_id = safe_doc_id(doc_id)
    now = datetime.utcnow().isoformat(timespec="seconds")
    doc = load_record(doc_id)

    if not doc or doc.get("status") == "missing_source":
        doc = {
            "id": doc_id,
            "file_name": f"mila-document-{doc_id}.txt",
            "created_at": now,
            "status": "ready",
            "original_content": (attachment or {}).get("text") or user_msg or "",
            "stages": [],
            "feedback_chain": [],
        }

    doc["status"] = "ready"

    # Если агент вернул [ДОКУМЕНТ] … [/ДОКУМЕНТ], это готовая версия
    final = extract_final_document(reply)
    stage_output = strip_doc_block(reply) if final else (reply or "")

    if final:
        doc["final_content"] = final
        doc["final_by"] = agent_key
        doc["final_at"] = now

    doc.setdefault("stages", []).append({
        "agent": agent_key,
        "timestamp": now,
        "verdict": "done" if "VERDICT: done" in reply or "готов" in reply.lower() else "ready_next",
        "input": user_msg or "",
        "output": stage_output or "",
    })

    # Сохраняем обе версии (JSON для истории, TXT для скачивания)
    doc_path(doc_id).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    doc_export_path(doc_id).write_text(
        document_to_text(doc),
        encoding="utf-8"
    )

    logger.info(f"Saved document {doc_id} at stage {agent_key}")
    return doc
