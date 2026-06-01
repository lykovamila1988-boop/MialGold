"""Delete MILA workflows from one or all n8n sqlite databases."""
import os
import sqlite3
import sys
from pathlib import Path

from n8n_db import db_path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FOLDERS = [
    ROOT / "n8n-data",
    Path.home() / ".n8n",
]


def clean_folder(user_folder: Path) -> int:
    db = db_path(user_folder)
    if not db:
        print(f"  skip {user_folder} (no database)")
        return 0
    c = sqlite3.connect(db)
    n = c.execute("DELETE FROM workflow_entity WHERE name LIKE 'MILA %'").rowcount
    c.commit()
    print(f"  {user_folder} -> deleted {n}")
    return n


def main():
    folders = DEFAULT_FOLDERS
    if len(sys.argv) > 1:
        folders = [Path(sys.argv[1])]
    total = 0
    for f in folders:
        total += clean_folder(f)
    print(f"Total deleted: {total}")


if __name__ == "__main__":
    main()
