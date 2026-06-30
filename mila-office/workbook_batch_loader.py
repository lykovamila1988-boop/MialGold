# -*- coding: utf-8 -*-
"""
Workbook Batch Loader - Load all pages from folder and send to agent for analysis.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
import base

logger = logging.getLogger("mila.workbook_batch_loader")

TETRAD_DIR = base.MILA_FOLDER / "Tetrad" / "Kogda-lyubov-stanovitsya-zerkalom"


def get_all_png_files() -> List[Path]:
    """Get all PNG files from workbook folder, sorted by number."""
    if not TETRAD_DIR.exists():
        logger.warning(f"Workbook directory not found: {TETRAD_DIR}")
        return []

    files = list(TETRAD_DIR.glob("*.png"))
    # Sort by numeric prefix (1_, 2_, etc.)
    files.sort(key=lambda x: int(x.stem.split('_')[0]) if x.stem[0].isdigit() else 0)
    return files


def prepare_batch_analysis(custom_prompt: str = None) -> Dict:
    """Prepare batch of PNG files for agent analysis."""
    files = get_all_png_files()

    if not files:
        return {
            "ok": False,
            "error": "No PNG files found in workbook folder",
            "folder": str(TETRAD_DIR)
        }

    default_prompt = (
        "это моя тетрадь на продажу проверь подходит ли она к моей целевой аудитории "
        "для кого она что она даст немного ли там чего то и скажи если что то нужно "
        "исправить добавить или убрать"
    )

    prompt = custom_prompt or default_prompt

    return {
        "ok": True,
        "total_pages": len(files),
        "files": [str(f) for f in files],
        "prompt": prompt,
        "folder": str(TETRAD_DIR),
        "file_list": [f.name for f in files]
    }


def format_analysis_request(file_paths: List[str], prompt: str) -> str:
    """Format request for agent to analyze images."""
    file_list = "\n".join([f"  {i+1}. {Path(f).name}" for i, f in enumerate(file_paths)])

    return f"""
Проанализируй эту рабочую тетрадь (всего {len(file_paths)} страниц):

СТРАНИЦЫ:
{file_list}

ЗАДАЧА:
{prompt}

ПОДРОБНЫЙ АНАЛИЗ:
1. Целевая аудитория - для кого эта тетрадь?
2. Ценность - что получит пользователь?
3. Структура - логична ли она?
4. Содержание - достаточно ли материала?
5. Упражнения - полезны ли они?
6. Оформление - привлекательно ли выглядит?
7. Цена - справедлива ли цена за такой объем?
8. Рекомендации - что добавить, убрать или изменить?

Дай конкретные рекомендации по улучшению.
"""


def get_workbook_info() -> Dict:
    """Get information about the workbook."""
    files = get_all_png_files()

    if not files:
        return {"error": "Workbook folder not found"}

    total_size = sum(f.stat().st_size for f in files)

    return {
        "folder": str(TETRAD_DIR),
        "title": "Когда любовь становится зеркалом",
        "total_pages": len(files),
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "status": "ready for analysis",
        "first_page": files[0].name if files else None,
        "last_page": files[-1].name if files else None
    }
