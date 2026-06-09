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
    """Цепочка передачи между агентами."""
    return {
        "olya": "marina",      # Тренды → Маркетолог
        "marina": "victoria",  # Маркетолог → Редактор
        "victoria": "vasya",   # Редактор → Планировщик
        "vasya": "rita",       # Планировщик → Дизайнер
        "rita": None,          # Конец цепочки
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

def process_agent_response(reply: str, current_agent: str) -> dict:
    """Обработать ответ агента и вернуть инструкции для UI."""
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

    return {
        "should_switch": next_agent is not None and next_agent != current_agent,
        "next_agent": next_agent,
        "verdict": verdict,
        "clean_reply": clean_reply,
    }
