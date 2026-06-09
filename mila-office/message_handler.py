# -*- coding: utf-8 -*-
"""Обработка сообщений и логика цепочки агентов."""
import logging
import re

logger = logging.getLogger("mila.message_handler")

def extract_next_agent(reply: str) -> str:
    """Извлечь рекомендацию [→ agent] из ответа."""
    m = re.search(r'\[→\s*(\w+)\]', reply)
    if m:
        return m.group(1).lower()
    return ""

def get_pipeline_order() -> dict:
    """Цепочка передачи между агентами.

    Основная цепь контента: тренды → маркетолог → редактор → планировщик → дизайнер
    Параллельная цепь CRM: новые лиды → менеджер клиентов (при необходимости)
    """
    return {
        "olya": "marina",      # Тренды → Маркетолог
        "marina": "victoria",  # Маркетолог → Редактор
        "victoria": "vasya",   # Редактор → Планировщик
        "vasya": "rita",       # Планировщик → Дизайнер
        "rita": None,          # Конец цепочки контента
        "lera": "alina",       # Продажи → Менеджер клиентов (CRM)
        "alina": None,         # Конец цепочки CRM
    }

def should_auto_switch(verdict: str) -> bool:
    """Должны ли мы автоматически переключиться на следующего агента?"""
    return verdict in ["ready_next", "pass"]

def extract_verdict(reply: str) -> str:
    """Извлечь [VERDICT: xxx] из ответа."""
    match = re.search(r'\[VERDICT:\s*(\w+)\]', reply)
    if match:
        return match.group(1).lower()
    return "ready_next"

def process_agent_response(reply: str, current_agent: str, from_agent: str = None, chain_id: str = None) -> dict:
    """Обработать ответ агента и вернуть инструкции для UI.

    Args:
        reply: Ответ агента (может содержать [VERDICT] и [→ agent])
        current_agent: Текущий агент (кто обрабатывает)
        from_agent: Агент который отправил первоначальный запрос (опционально)
        chain_id: ID цепочки обработки (для логирования)
    """
    verdict = extract_verdict(reply)
    next_agent_explicit = extract_next_agent(reply)
    next_agent = next_agent_explicit or None

    if not next_agent and should_auto_switch(verdict):
        pipeline = get_pipeline_order()
        next_agent = pipeline.get(current_agent)

    clean_reply = reply
    clean_reply = re.sub(r'\[VERDICT:\s*\w+\]', '', clean_reply)
    clean_reply = re.sub(r'\[→\s*\w+\]', '', clean_reply)
    clean_reply = clean_reply.strip()

    # Логируем цепочку обработки
    _log_chain_step(current_agent, from_agent, verdict, next_agent, chain_id)

    return {
        "should_switch": next_agent is not None and next_agent != current_agent,
        "next_agent": next_agent,
        "verdict": verdict,
        "clean_reply": clean_reply,
        "from_agent": from_agent,  # ← НОВОЕ: от кого пришел запрос
        "chain_id": chain_id,  # ← НОВОЕ: ID цепочки
    }

def _log_chain_step(agent: str, from_agent: str = None, verdict: str = None, next_agent: str = None, chain_id: str = None):
    """Логировать шаг в цепочке обработки."""
    try:
        from base import log
        from datetime import datetime

        chain_id = chain_id or "unknown"
        from_agent = from_agent or "user"
        next_agent = next_agent or "END"

        log_msg = f"agent={agent} from={from_agent} verdict={verdict} next={next_agent} chain={chain_id}"
        log("chain", log_msg)

        # Также выводим в консоль для наглядности
        logger.info(f"Chain step: {log_msg}")
    except Exception as e:
        logger.error(f"Failed to log chain step: {e}")

def get_agent_chain_info(agent_key: str) -> dict:
    """Получить информацию о позиции агента в цепочке.

    Возвращает:
    {
        "agent": "victoria",
        "position": 2,  # 0-indexed
        "previous": "marina",
        "next": "vasya",
        "is_final": False
    }
    """
    pipeline = get_pipeline_order()
    agents = list(pipeline.keys())

    if agent_key not in agents:
        return {"agent": agent_key, "position": -1, "error": "Agent not in pipeline"}

    position = agents.index(agent_key)
    previous = agents[position - 1] if position > 0 else None
    next_agent = pipeline.get(agent_key)

    return {
        "agent": agent_key,
        "position": position,
        "total_in_chain": len(agents),
        "previous": previous,
        "next": next_agent,
        "is_final": next_agent is None,
    }

def extract_request_context(message: str) -> dict:
    """Извлечь контекст запроса из сообщения.

    Может содержать служебные теги:
    - [from: marina] — запрос от Марины
    - [to: victoria] — результат для Виктории
    - [chain_id: abc123] — ID цепочки обработки
    """
    from_match = re.search(r'\[from:\s*(\w+)\]', message)
    to_match = re.search(r'\[to:\s*(\w+)\]', message)
    chain_match = re.search(r'\[chain_id:\s*(\w+)\]', message)

    return {
        "from_agent": from_match.group(1).lower() if from_match else None,
        "to_agent": to_match.group(1).lower() if to_match else None,
        "chain_id": chain_match.group(1) if chain_match else None,
    }

def build_agent_message(content: str, from_agent: str, to_agent: str = None, chain_id: str = None) -> str:
    """Построить сообщение для агента с контекстом.

    Args:
        content: Основной контент сообщения
        from_agent: От какого агента (может быть 'user' если от пользователя)
        to_agent: Кому адресовано (опционально)
        chain_id: ID цепочки обработки (опционально)

    Returns:
        Сообщение с контекстом
    """
    parts = [f"[from: {from_agent}]"]

    if to_agent:
        parts.append(f"[to: {to_agent}]")

    if chain_id:
        parts.append(f"[chain_id: {chain_id}]")

    parts.append("\n")
    parts.append(content)

    return " ".join(parts[:2]) + " " + " ".join(parts[2:])
