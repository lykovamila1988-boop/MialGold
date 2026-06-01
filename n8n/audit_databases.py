"""Find executeCommand nodes in any n8n database on this machine."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n8n_db import db_path

folders = [
    Path(r"E:/MILA GOLD/n8n-data"),
    Path.home() / ".n8n",
]

for folder in folders:
    db = db_path(folder)
    print(f"\n=== {folder} ===")
    if not db:
        print("  (no database)")
        continue
    c = sqlite3.connect(db)
    rows = c.execute("SELECT id, name, active, nodes FROM workflow_entity").fetchall()
    print(f"  {len(rows)} workflow(s)")
    for wid, name, active, nodes_json in rows:
        nodes = json.loads(nodes_json)
        types = [n.get("type") for n in nodes]
        bad = "executeCommand" in str(types)
        flag = " *** BROKEN executeCommand ***" if bad else ""
        print(f"  {'ON' if active else 'off'}  {name}{flag}")
        if bad:
            for n in nodes:
                if "executeCommand" in n.get("type", ""):
                    print(f"       node: {n.get('name')}")
