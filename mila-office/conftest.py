"""Pytest config: добавляет папку mila-office в sys.path, чтобы `import base`
работал из tests/ (там нет __init__.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
