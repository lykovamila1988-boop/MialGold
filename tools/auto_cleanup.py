#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_cleanup.py — архивация старых отчётов из reports/ в reports/archive/.

Зачем: reports/ растёт (account_*/posts_*/comments_*/digest_*/kpi_*/alerts_*).
Старые файлы засоряют папку и путают агентов. Этот скрипт перемещает отчёты
старше N дней в reports/archive/, НЕ трогая служебные файлы состояния.

ЗАЩИЩЕНЫ (никогда не архивируются):
  .alert_state.json, office_actions.json, tg_offset.txt, pipeline_state_*.json,
  всё, что не похоже на timestamped-отчёт.

Архивирует ТОЛЬКО файлы вида <тип>_<дата>...  (account/posts/comments/digest/kpi/alerts).

Запуск:
  python auto_cleanup.py              # DRY-RUN: только показать, что переместит
  python auto_cleanup.py --apply      # реально переместить
  python auto_cleanup.py --days 14 --apply
"""
import os
import re
import sys
import shutil
import argparse
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
REPORTS = ROOT / "reports"
ARCHIVE = REPORTS / "archive"

# Архивируем только реальные отчёты (timestamped). Префиксы — как в save_report.
_REPORT_RE = re.compile(r"^(account|posts|comments|digest|digest_week|kpi|kpi_week|alerts)_", re.I)
# Служебное состояние — НЕ трогаем никогда.
_PROTECTED = {".alert_state.json", "office_actions.json", "tg_offset.txt"}
_PROTECTED_RE = re.compile(r"^(pipeline_state_|\.)", re.I)  # состояния пайплайнов и скрытые


def _is_report(name: str) -> bool:
    if name in _PROTECTED or _PROTECTED_RE.match(name):
        return False
    return bool(_REPORT_RE.match(name))


def main():
    ap = argparse.ArgumentParser(description="Архивация старых отчётов reports/ → reports/archive/")
    ap.add_argument("--days", type=int, default=30, help="старше скольких дней архивировать (по умолч. 30)")
    ap.add_argument("--apply", action="store_true", help="реально переместить (без флага — dry-run)")
    args = ap.parse_args()

    if not REPORTS.exists():
        print(f"Нет папки {REPORTS}")
        return
    cutoff = datetime.now() - timedelta(days=args.days)

    moved, skipped_fresh, protected = [], 0, 0
    for f in sorted(REPORTS.iterdir()):
        if not f.is_file():
            continue
        if not _is_report(f.name):
            protected += 1
            continue
        if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff:
            skipped_fresh += 1
            continue
        moved.append(f)

    mode = "ПЕРЕМЕЩАЮ" if args.apply else "DRY-RUN (показываю, не трогаю)"
    print(f"=== auto_cleanup: {mode} | порог: старше {args.days} дн. ===")
    print(f"кандидатов на архив: {len(moved)} | свежих оставлено: {skipped_fresh} | "
          f"служебных пропущено: {protected}")

    if not moved:
        print("Нечего архивировать — папка чистая.")
        return

    if args.apply:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
    for f in moved:
        dst = ARCHIVE / f.name
        if args.apply:
            # не перезаписываем, если такой уже в архиве
            if dst.exists():
                dst = ARCHIVE / f"{f.stem}_dup{f.suffix}"
            shutil.move(str(f), str(dst))
            print(f"  → archive/{dst.name}")
        else:
            print(f"  (would move) {f.name}")

    if args.apply:
        print(f"\n✓ Перемещено в {ARCHIVE}: {len(moved)} файл(ов).")
    else:
        print(f"\nЭто был dry-run. Запусти с --apply, чтобы реально переместить.")


if __name__ == "__main__":
    main()
