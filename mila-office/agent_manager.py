# -*- coding: utf-8 -*-
"""Управление агентами, реестр, метаданные."""
import importlib
import logging

logger = logging.getLogger("mila.agent_manager")

# Загружаем Марину (офис-версия со своим run_agent)
marina = importlib.import_module("agent")

# Остальные агенты
AGENTS_MODULES = {
    "victoria": importlib.import_module("victoria"),
    "alina":    importlib.import_module("alina"),
    "dima":     importlib.import_module("dima"),
    "tyoma":    importlib.import_module("tyoma"),
    "olya":     importlib.import_module("olya"),
    "vasya":    importlib.import_module("vasya"),
    "lera":     importlib.import_module("lera"),
    "rita":     importlib.import_module("rita"),
    "manager":  importlib.import_module("manager"),
    "producer": importlib.import_module("producer"),
}

def get_agent_module(key: str):
    """Получить модуль агента по ключу."""
    if key == "marina":
        return marina
    return AGENTS_MODULES.get(key)

def list_agents() -> list:
    """Список всех агентов."""
    agents = ["marina"] + list(AGENTS_MODULES.keys())
    return agents

def get_quick_commands(key: str) -> dict:
    """Получить быстрые команды агента."""
    mod = get_agent_module(key)
    if mod and hasattr(mod, "QUICK"):
        return mod.QUICK
    return {}
