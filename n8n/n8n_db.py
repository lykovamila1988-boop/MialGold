"""Find n8n sqlite DB for a user folder."""
from pathlib import Path


def db_path(user_folder: str | Path) -> Path | None:
    base = Path(user_folder)
    for candidate in (base / ".n8n" / "database.sqlite", base / "database.sqlite"):
        if candidate.exists():
            return candidate
    return None
