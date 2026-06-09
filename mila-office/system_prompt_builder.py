# -*- coding: utf-8 -*-
"""Конструктор system prompts с контекстом запроса."""
import logging
from message_handler import get_agent_chain_info

logger = logging.getLogger("mila.system_prompt_builder")

# Экспортируем функции для доступа из base.py и других модулей
__all__ = [
    "build_system_prompt",
    "add_context_to_prompt",
    "extract_context_from_message",
    "format_context_tags",
    "get_agent_chain_info",
    "_build_context_section",
]

def build_system_prompt(agent_key: str, base_prompt: str, context: dict = None) -> str:
    """Построить system prompt с контекстом запроса.

    Args:
        agent_key: Ключ агента (marina, victoria, итд)
        base_prompt: Основной system prompt
        context: Контекст запроса {from_agent, to_agent, chain_id}

    Returns:
        System prompt с добавленным контекстом
    """
    if not context:
        return base_prompt

    chain_info = get_agent_chain_info(agent_key)

    context_section = _build_context_section(agent_key, context, chain_info)

    return f"{base_prompt}\n\n{context_section}"

def _build_context_section(agent_key: str, context: dict, chain_info: dict) -> str:
    """Построить раздел с контекстом для system prompt."""
    from_agent = context.get("from_agent", "user")
    to_agent = context.get("to_agent")
    chain_id = context.get("chain_id")

    previous = chain_info.get("previous")
    next_agent = chain_info.get("next")
    position = chain_info.get("position", -1)
    is_final = chain_info.get("is_final", False)

    lines = [
        "=== КОНТЕКСТ ЗАПРОСА ===",
        f"✓ Ты получила запрос от: {from_agent}",
    ]

    if chain_id:
        lines.append(f"✓ ID цепочки обработки: {chain_id}")

    if to_agent:
        lines.append(f"✓ Результат адресован: {to_agent}")

    if position >= 0:
        lines.append(f"✓ Твоя позиция в цепочке: #{position + 1}")

    if previous:
        lines.append(f"✓ Предыдущий агент: {previous}")

    if next_agent and not is_final:
        lines.append(f"✓ Следующий агент: {next_agent}")

    if is_final:
        lines.append(f"✓ ТЫ ПОСЛЕДНЯЯ В ЦЕПОЧКЕ — это финальный результат")

    # Инструкция по действиям
    lines.append("\n=== КАК ДЕЙСТВОВАТЬ ===")

    if from_agent == "user":
        lines.append(f"Запрос пришел непосредственно от пользователя.")
    else:
        lines.append(f"Запрос пришел от {from_agent.capitalize()}. Это может быть результат их работы, требующий твоей обработки.")

    if to_agent:
        lines.append(f"Результат нужно адресовать {to_agent} — учитывай это в своей работе.")
    elif next_agent:
        lines.append(f"После твоей работы результат пойдет {next_agent} — подготавливай под его требования.")
    else:
        lines.append(f"Это финальный результат — проверь качество перед завершением.")

    if chain_id:
        lines.append(f"Все сообщения связаны ID '{chain_id}' — это помогает отслеживать работу.")

    return "\n".join(lines)

def add_context_to_prompt(base_prompt: str, context: dict) -> str:
    """Добавить контекст к существующему prompt."""
    if not context:
        return base_prompt

    from_agent = context.get("from_agent", "user")
    to_agent = context.get("to_agent")
    chain_id = context.get("chain_id")

    parts = []
    parts.append(base_prompt)
    parts.append("\n---\n")

    if from_agent != "user":
        parts.append(f"[КОНТЕКСТ] Запрос пришел от {from_agent}.")

    if to_agent:
        parts.append(f"[КОНТЕКСТ] Результат адресован {to_agent}.")

    if chain_id:
        parts.append(f"[КОНТЕКСТ] Цепочка: {chain_id}")

    return "\n".join(parts)

def extract_context_from_message(message: str) -> dict:
    """Извлечь контекст из входящего сообщения."""
    import re

    from_match = re.search(r'\[from:\s*(\w+)\]', message)
    to_match = re.search(r'\[to:\s*(\w+)\]', message)
    chain_match = re.search(r'\[chain_id:\s*(\w+)\]', message)

    return {
        "from_agent": from_match.group(1).lower() if from_match else "user",
        "to_agent": to_match.group(1).lower() if to_match else None,
        "chain_id": chain_match.group(1) if chain_match else None,
    }

def format_context_tags(context: dict) -> str:
    """Форматировать контекст в теги для сообщения."""
    if not context:
        return ""

    parts = []

    if context.get("from_agent"):
        parts.append(f"[from: {context['from_agent']}]")

    if context.get("to_agent"):
        parts.append(f"[to: {context['to_agent']}]")

    if context.get("chain_id"):
        parts.append(f"[chain_id: {context['chain_id']}]")

    return " ".join(parts)
