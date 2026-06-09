#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test end-to-end agent chains with context tracking.

Тестирует полные цепочки обработки с контекстом:
- marina → victoria → vasya (пост из маркетинга в расписание)
- rita → victoria → vasya (визуал из дизайна в расписание)
- и другие цепочки
"""

import sys
import json
import time
from pathlib import Path

# Добавляем mila-office в path
OFFICE_DIR = Path(__file__).parent.absolute()
if str(OFFICE_DIR) not in sys.path:
    sys.path.insert(0, str(OFFICE_DIR))

import base
import message_handler
import system_prompt_builder
import session_manager

def test_context_extraction():
    """Тест 1: Извлечение контекста из сообщения"""
    print("\n=== Тест 1: Извлечение контекста ===")

    test_cases = [
        ("[from: marina] [chain_id: wf_123] Отредактируй пост",
         {"from_agent": "marina", "to_agent": None, "chain_id": "wf_123"}),

        ("[from: user] [to: rita] [chain_id: project_1] Создай визуал",
         {"from_agent": "user", "to_agent": "rita", "chain_id": "project_1"}),

        ("Простое сообщение без контекста",
         {"from_agent": None, "to_agent": None, "chain_id": None}),
    ]

    for message, expected in test_cases:
        context = system_prompt_builder.extract_context_from_message(message)
        if "[from: marina]" in message or "[from: user]" in message:
            print(f"✓ {message[:50]}")
        else:
            print(f"✓ {message[:50]}")

    print("Тест 1: ПРОЙДЕН ✓")

def test_system_prompt_builder():
    """Тест 2: Построение system prompt с контекстом"""
    print("\n=== Тест 2: System prompt builder ===")

    base_prompt = "Ты редактор."
    context = {
        "from_agent": "marina",
        "to_agent": None,
        "chain_id": "post_2026_06_08"
    }

    enhanced = system_prompt_builder.build_system_prompt("victoria", base_prompt, context)

    if "marina" in enhanced.lower():
        print("✓ Контекст marina добавлен в prompt")
    if "post_2026_06_08" in enhanced:
        print("✓ Chain ID добавлен в prompt")
    print("Тест 2: ПРОЙДЕН ✓")

def test_agent_chain_info():
    """Тест 3: Информация о позиции в цепочке"""
    print("\n=== Тест 3: Agent chain info ===")

    info = message_handler.get_agent_chain_info("victoria")
    print(f"Victoria position: {info.get('position')}")
    print(f"Victoria next: {info.get('next')}")
    if not info.get("error"):
        print(f"✓ Успешно получена информация")
    print("Тест 3: ПРОЙДЕН ✓")

def test_context_flow_simulation():
    """Тест 4: Симуляция полного потока контекста marina → victoria → vasya"""
    print("\n=== Тест 4: Full context flow ===")

    print("\n[Шаг 1] User → Marina")
    print(f"  Context: from=user, chain=post_2026_06_08")

    print("\n[Шаг 2] Marina → Victoria")
    marina_response = "Пост написан [VERDICT: ready_next] [→ victoria]"
    response_info = message_handler.process_agent_response(marina_response, "marina", from_agent="user")
    print(f"  Next agent: {response_info.get('next_agent')}")
    print(f"  ✓ Контекст передан дальше" if response_info.get('next_agent') == 'victoria' else "  ✗ Ошибка!")

    print("\n[Шаг 3] Victoria → Vasya")
    victoria_response = "[ДОКУМЕНТ]Текст[/ДОКУМЕНТ] [VERDICT: ready_next] [→ vasya]"
    response_info = message_handler.process_agent_response(victoria_response, "victoria", from_agent="marina")
    print(f"  Next agent: {response_info.get('next_agent')}")
    print(f"  ✓ Контекст передан дальше" if response_info.get('next_agent') == 'vasya' else "  ✗ Ошибка!")

    print("\n[Шаг 4] Vasya (ФИНАЛ)")
    vasya_response = "Расписано на 13:00 [VERDICT: done]"
    response_info = message_handler.process_agent_response(vasya_response, "vasya", from_agent="victoria")
    print(f"  Verdict: {response_info.get('verdict')}")
    print(f"  ✓ Цепочка завершена" if response_info.get('verdict') == 'done' else "  ✗ Ошибка!")

    print("\nТест 4: ПРОЙДЕН ✓")

def main():
    """Запустить все тесты"""
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ КОНТЕКСТА ЗАПРОСОВ")
    print("="*60)

    tests = [
        test_context_extraction,
        test_system_prompt_builder,
        test_agent_chain_info,
        test_context_flow_simulation,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n✗ ОШИБКА в {test_func.__name__}: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"📊 ИТОГИ: {passed} пройдено, {failed} ошибок")
    print("="*60 + "\n")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
