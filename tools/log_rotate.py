#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log_rotate.py — ротация логов MILA, чтобы файлы не росли бесконечно.

Без ротации logs/*.log и mila-office/memory/events.jsonl за месяцы вырастают в
гигабайты: чтение тормозит, диск заполняется. Скрипт переименовывает файл,
переваливший лимит, в <name>.1, <name>.2 … (старые сдвигаются), держит не более
KEEP архивов, и архивы старше DELETE_DAYS удаляет.

Запуск:
    python log_rotate.py            # ротировать всё, что переросло лимит
    python log_rotate.py --status   # показать размеры без изменений

Вызывается n8n по расписанию (раз в сутки/неделю) через мост: /v1/tools/log_rotate.
Идемпотентно и безопасно — только перемещает/удаляет собственные лог-файлы.
"""
import os
import sys
import gzip
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
LOGS = ROOT / "logs"
MEM = ROOT / "mila-office" / "memory"

MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 МБ
KEEP = int(os.getenv("LOG_KEEP", "5"))            # сколько архивов хранить
DELETE_DAYS = int(os.getenv("LOG_DELETE_DAYS", "180"))  # архивы старше — удалять

# Что ротируем: все *.log в logs/ + append-only журнал событий памяти.
def _targets():
    files = []
    if LOGS.exists():
        files += sorted(LOGS.glob("*.log"))
    if (MEM / "events.jsonl").exists():
        files.append(MEM / "events.jsonl")
    return files


def _rotate_one(f: Path):
    """Сдвигает .gz-архивы и архивирует текущий файл, очищая оригинал."""
    # удалить самый старый сверх KEEP
    oldest = f.with_suffix(f.suffix + f".{KEEP}.gz")
    if oldest.exists():
        oldest.unlink()
    # сдвиг N → N+1
    for i in range(KEEP - 1, 0, -1):
        src = f.with_suffix(f.suffix + f".{i}.gz")
        if src.exists():
            src.rename(f.with_suffix(f.suffix + f".{i + 1}.gz"))
    # текущий → .1.gz (сжимаем)
    arch = f.with_suffix(f.suffix + ".1.gz")
    with open(f, "rb") as fin, gzip.open(arch, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    # очистить оригинал (не удаляем — писатели держат путь открытым/ожидают файл)
    f.write_text("", encoding="utf-8")
    return arch


def _purge_old():
    """Удаляет .gz-архивы старше DELETE_DAYS."""
    cutoff = datetime.now() - timedelta(days=DELETE_DAYS)
    removed = 0
    for d in (LOGS, MEM):
        if not d.exists():
            continue
        for g in d.glob("*.gz"):
            if datetime.fromtimestamp(g.stat().st_mtime) < cutoff:
                g.unlink()
                removed += 1
    return removed


def status():
    print(f"Лимит ротации: {MAX_BYTES // 1024} КБ · хранить архивов: {KEEP} · "
          f"удалять старше: {DELETE_DAYS} дн.\n")
    for f in _targets():
        size = f.stat().st_size
        flag = "→ РОТИРОВАТЬ" if size > MAX_BYTES else "ok"
        print(f"  {f.name:28} {size // 1024:>8} КБ  {flag}")


def main():
    p = argparse.ArgumentParser(description="Ротация логов MILA")
    p.add_argument("--status", action="store_true", help="показать размеры, ничего не менять")
    args = p.parse_args()
    if args.status:
        status()
        return
    rotated = []
    for f in _targets():
        if f.stat().st_size > MAX_BYTES:
            arch = _rotate_one(f)
            rotated.append((f.name, arch.name))
    purged = _purge_old()
    if rotated:
        for name, arch in rotated:
            print(f"  ↻ {name} → {arch} (очищен)")
    else:
        print("Ротация не нужна — все логи в пределах лимита.")
    if purged:
        print(f"  🗑  удалено старых архивов: {purged}")


if __name__ == "__main__":
    main()
