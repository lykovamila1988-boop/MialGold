#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI для n8n: записать событие в memory/context.json перед pipeline."""
import sys
import json
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import memory


def main():
    p = argparse.ArgumentParser(description="Запись context.json для n8n → агенты")
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="write_context(event, data)")
    w.add_argument("--event", required=True)
    w.add_argument("--data", default="{}", help="JSON object")
    w.add_argument("--file", help="read JSON object from file instead of --data")

    sub.add_parser("read", help="read_context() → stdout JSON")

    args = p.parse_args()
    if args.cmd == "write":
        if args.file:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        else:
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError as e:
                sys.exit(f"Invalid --data JSON: {e}")
        ctx = memory.write_context(args.event, data)
        print(json.dumps({"ok": True, "context": ctx}, ensure_ascii=False))
    else:
        print(json.dumps(memory.read_context(), ensure_ascii=False))


if __name__ == "__main__":
    main()
