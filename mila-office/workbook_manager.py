# -*- coding: utf-8 -*-
"""
Workbook Manager - Complete lifecycle management for writing projects.

Handles: create, write, edit, analyse, version control, export, download.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib
import uuid
from enum import Enum

import base

logger = logging.getLogger("mila.workbook_manager")

WORKBOOKS_DIR = base.MILA_FOLDER / "mila-office" / "_workbooks"
WORKBOOKS_DIR.mkdir(parents=True, exist_ok=True)


class AgentType(Enum):
    VICTORIA = "victoria"
    MARINA = "marina"
    ALINA = "alina"
    USER = "user"


class WorkbookStatus(Enum):
    DRAFT = "draft"
    EDITING = "editing"
    REVIEWING = "reviewing"
    READY = "ready"
    PUBLISHED = "published"


class Workbook:
    """Complete workbook with version history and multi-agent editing."""

    def __init__(self, workbook_id: str = None):
        self.workbook_id = workbook_id or self._generate_id()
        self.path = WORKBOOKS_DIR / f"{self.workbook_id}.json"
        self.data = {
            "workbook_id": self.workbook_id,
            "title": "Untitled Workbook",
            "created_at": datetime.utcnow().isoformat(),
            "status": WorkbookStatus.DRAFT.value,
            "versions": [],
            "metadata": {
                "total_edits": 0,
                "contributors": set(),
                "word_count": 0,
                "pages": 0
            },
            "content": "",
            "images": [],
            "analytics": {
                "quality_score": 0,
                "readability_score": 0,
                "market_fit_score": 0
            }
        }

    @staticmethod
    def _generate_id() -> str:
        """Generate unique workbook ID."""
        return f"wb_{uuid.uuid4().hex[:12]}"

    def load(self) -> bool:
        """Load workbook from disk."""
        if not self.path.exists():
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            logger.error(f"Failed to load workbook {self.workbook_id}: {e}")
            return False

    def save(self) -> bool:
        """Save workbook to disk."""
        try:
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info(f"Saved workbook {self.workbook_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save workbook: {e}")
            return False

    def add_version(self, content: str, editor: str, notes: str = "", agent: AgentType = None) -> str:
        """Create new version after edit."""
        version = {
            "version_id": f"v{len(self.data['versions']) + 1}",
            "timestamp": datetime.utcnow().isoformat(),
            "editor": agent.value if agent else editor,
            "notes": notes,
            "content": content,
            "word_count": len(content.split()),
            "character_count": len(content),
            "hash": hashlib.sha256(content.encode()).hexdigest()[:12]
        }

        self.data["versions"].append(version)
        self.data["content"] = content
        self.data["metadata"]["total_edits"] += 1

        if agent:
            if agent.value not in self.data["metadata"]["contributors"]:
                self.data["metadata"]["contributors"].append(agent.value)

        self.save()
        return version["version_id"]

    def get_version(self, version_id: str) -> Optional[Dict]:
        """Get specific version."""
        for v in self.data["versions"]:
            if v["version_id"] == version_id:
                return v
        return None

    def get_version_diff(self, v1_id: str, v2_id: str) -> Dict:
        """Compare two versions."""
        v1 = self.get_version(v1_id)
        v2 = self.get_version(v2_id)

        if not v1 or not v2:
            return {"error": "Version not found"}

        # Simple diff: show what changed
        return {
            "from": v1_id,
            "to": v2_id,
            "from_editor": v1["editor"],
            "to_editor": v2["editor"],
            "from_timestamp": v1["timestamp"],
            "to_timestamp": v2["timestamp"],
            "word_count_delta": v2["word_count"] - v1["word_count"],
            "char_count_delta": v2["character_count"] - v1["character_count"]
        }

    def add_images(self, image_paths: List[str]) -> List[str]:
        """Add images to workbook (e.g., PNG pages)."""
        image_records = []
        for path in image_paths:
            p = Path(path)
            if p.exists():
                image_records.append({
                    "filename": p.name,
                    "path": str(p),
                    "size": p.stat().st_size,
                    "added_at": datetime.utcnow().isoformat()
                })

        self.data["images"].extend(image_records)
        self.data["metadata"]["pages"] = len(self.data["images"])
        self.save()
        return [img["filename"] for img in image_records]

    def analyse(self, analysis_result: Dict, analyser: AgentType) -> None:
        """Store analysis results."""
        if "analytics" not in self.data:
            self.data["analytics"] = {}

        self.data["analytics"][analyser.value] = {
            "timestamp": datetime.utcnow().isoformat(),
            "result": analysis_result
        }
        self.save()

    def export_text(self) -> str:
        """Export as plain text with metadata."""
        lines = [
            f"═══════════════════════════════════════════",
            f"📖 {self.data['title']}",
            f"═══════════════════════════════════════════",
            f"",
            f"ID: {self.workbook_id}",
            f"Status: {self.data['status']}",
            f"Created: {self.data['created_at']}",
            f"Edits: {self.data['metadata']['total_edits']}",
            f"Contributors: {', '.join(self.data['metadata']['contributors'])}",
            f"Word Count: {self.data['metadata']['word_count']}",
            f"",
            f"═══════════════════════════════════════════",
            f"CONTENT",
            f"═══════════════════════════════════════════",
            f"",
            self.data["content"],
            f"",
            f"═══════════════════════════════════════════",
            f"VERSION HISTORY",
            f"═══════════════════════════════════════════"
        ]

        for v in self.data["versions"]:
            lines.append(f"\n{v['version_id']} · {v['editor']} · {v['timestamp']}")
            if v.get("notes"):
                lines.append(f"  📝 {v['notes']}")

        if self.data.get("analytics"):
            lines.append(f"\n═══════════════════════════════════════════")
            lines.append(f"ANALYTICS")
            lines.append(f"═══════════════════════════════════════════")
            for agent, analysis in self.data["analytics"].items():
                lines.append(f"\n{agent.upper()}:")
                if isinstance(analysis.get("result"), dict):
                    for key, val in analysis["result"].items():
                        lines.append(f"  {key}: {val}")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        data = self.data.copy()
        if isinstance(data["metadata"].get("contributors"), set):
            data["metadata"]["contributors"] = list(data["metadata"]["contributors"])
        return data


class WorkbookManager:
    """High-level workbook management."""

    @staticmethod
    def create(title: str, content: str = "") -> Workbook:
        """Create new workbook."""
        wb = Workbook()
        wb.data["title"] = title
        if content:
            wb.add_version(content, "system", "Initial content")
        wb.save()
        logger.info(f"Created workbook: {wb.workbook_id}")
        return wb

    @staticmethod
    def get(workbook_id: str) -> Optional[Workbook]:
        """Load workbook by ID."""
        wb = Workbook(workbook_id)
        if wb.load():
            return wb
        return None

    @staticmethod
    def list_all() -> List[Dict]:
        """List all workbooks."""
        workbooks = []
        for path in WORKBOOKS_DIR.glob("wb_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    workbooks.append({
                        "workbook_id": data["workbook_id"],
                        "title": data.get("title", "Untitled"),
                        "status": data.get("status", "draft"),
                        "created_at": data.get("created_at"),
                        "edits": data["metadata"].get("total_edits", 0),
                        "contributors": data["metadata"].get("contributors", []),
                        "word_count": data["metadata"].get("word_count", 0)
                    })
            except Exception as e:
                logger.warning(f"Failed to load workbook metadata: {e}")

        return sorted(workbooks, key=lambda x: x.get("created_at", ""), reverse=True)

    @staticmethod
    def delete(workbook_id: str) -> bool:
        """Delete workbook."""
        wb = Workbook(workbook_id)
        if wb.path.exists():
            wb.path.unlink()
            logger.info(f"Deleted workbook: {workbook_id}")
            return True
        return False

    @staticmethod
    def export(workbook_id: str, format: str = "txt") -> Optional[str]:
        """Export workbook in format."""
        wb = WorkbookManager.get(workbook_id)
        if not wb:
            return None

        if format == "txt":
            return wb.export_text()
        elif format == "json":
            return json.dumps(wb.to_dict(), ensure_ascii=False, indent=2)
        elif format == "md":
            return wb._export_markdown()

        return None

    @staticmethod
    def update_word_count(workbook_id: str) -> int:
        """Update metadata word count."""
        wb = WorkbookManager.get(workbook_id)
        if wb:
            wb.data["metadata"]["word_count"] = len(wb.data["content"].split())
            wb.save()
            return wb.data["metadata"]["word_count"]
        return 0
