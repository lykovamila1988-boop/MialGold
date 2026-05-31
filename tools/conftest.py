"""Pytest config: добавляет tools/ в sys.path, чтобы тесты могли импортировать
_common, get_analytics, weekly_digest и т.д. из tools/tests/ (там нет __init__)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
