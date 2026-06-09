#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHAIN_DASHBOARD_EXAMPLE.py — практический пример интеграции логирования цепочек.

Демонстрирует, как добавить логирование к pipeline.py для мониторинга
цепочек агентов через дашборд.

Использование:
  1. Скопировать функции из этого файла в pipeline.py
  2. Обёрнуть run_chain() в логирование
  3. Запустить дашборд: http://127.0.0.1:5000/chains
"""

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import json
import time
import importlib
from pathlib import Path
from datetime import datetime

# Импорты из проекта
import base
import memory

# ВАЖНО: импортируем функции логирования из chain_dashboard
try:
    from chain_dashboard import log_chain_start, log_chain_step, log_chain_end
except ImportError:
    print("❌ chain_dashboard.py не найден. Установи его в mila-office/")
    sys.exit(1)

# ─── Пример: интеграция в pipeline.py ──────────────────────────────

def run_chain_with_logging(chain_key: str, context_override=None, notify=False) -> dict:
    """
    Запустить цепочку с полным логированием для дашборда.

    Args:
        chain_key: ключ цепочки из CHAINS (напр. "content_week")
        context_override: переопределить контекст из memory.read_context()
        notify: отправить сигнал в n8n после завершения

    Returns:
        {"status": "ok"|"failed", "chain_id": "...", "result": "..."}
    """

    # ─── Инициализация ───
    t_chain_start = time.time()
    chain_id = f"{chain_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    from_agent = "n8n"  # или "user" / "external"

    # Загружаем конфиг цепочки
    from pipeline import CHAINS, AGENT_MODULE, _load_agent, run_agent_with_retry

    if chain_key not in CHAINS:
        error_msg = f"Неизвестная цепочка: {chain_key}"
        log_chain_end(chain_id, "failed", 0, error=error_msg)
        return {"status": "failed", "chain_id": chain_id, "error": error_msg}

    chains_config = CHAINS[chain_key]
    agents = [agent_key for agent_key, _ in chains_config]

    # ─── Логируем начало цепочки ───
    log_chain_start(
        chain_id=chain_id,
        from_agent=from_agent,
        agents=agents,
        description=f"Цепочка {chain_key}"
    )

    # ─── Инициализируем контекст ───
    ctx = context_override or memory.read_context()
    prev_reply = ctx.get("input") or ""

    # ─── Запускаем все агенты в цепочке ───
    try:
        client = base.get_client()

        for step_num, (agent_key, prompt_template) in enumerate(chains_config, 1):
            t0 = time.time()

            print(f"\n[Шаг {step_num}/{len(chains_config)}] {agent_key.upper()}")

            try:
                # Подготавливаем промпт (подставляем {prev} и {context})
                msg = prompt_template.format(
                    prev=prev_reply,
                    context=json.dumps(ctx)
                )

                # Загружаем агента
                agent = _load_agent(agent_key)

                # Запускаем с retry
                reply, _ = run_agent_with_retry(
                    client,
                    base.compose_system(agent_key, agent["system"]),
                    agent["tools"],
                    agent["handle"],
                    msg,
                    [],
                    agent_key=agent_key
                )

                elapsed_ms = (time.time() - t0) * 1000

                # ─── Логируем шаг как успешный ───
                log_chain_step(
                    chain_id=chain_id,
                    agent=agent_key,
                    step_num=step_num,
                    status="done",
                    elapsed_ms=elapsed_ms,
                    input_text=msg[:500],  # первые 500 символов
                    output_text=reply[:500]  # первые 500 символов
                )

                print(f"  ✓ {_format_ms(elapsed_ms)}")

                # Передаём результат следующему агенту
                prev_reply = reply

            except Exception as e:
                elapsed_ms = (time.time() - t0) * 1000

                # ─── Логируем шаг как ошибку ───
                log_chain_step(
                    chain_id=chain_id,
                    agent=agent_key,
                    step_num=step_num,
                    status="failed",
                    elapsed_ms=elapsed_ms
                )

                # ─── Логируем конец цепочки как ошибка ───
                total_ms = (time.time() - t_chain_start) * 1000
                log_chain_end(
                    chain_id=chain_id,
                    status="failed",
                    total_ms=total_ms,
                    error=f"Агент {agent_key}: {str(e)[:100]}"
                )

                error_msg = f"Агент {agent_key} упал на шаге {step_num}: {type(e).__name__}"
                print(f"  ❌ {error_msg}")
                print(f"  📊 Логирование: {chain_id}")

                return {
                    "status": "failed",
                    "chain_id": chain_id,
                    "error": error_msg,
                    "agent": agent_key,
                    "step": step_num,
                }

        # ─── Все шаги прошли успешно ───
        total_ms = (time.time() - t_chain_start) * 1000
        log_chain_end(
            chain_id=chain_id,
            status="ok",
            total_ms=total_ms
        )

        print(f"\n✅ Цепочка завершена за {_format_ms(total_ms)}")
        print(f"📊 ID: {chain_id}")
        print(f"🔗 Дашборд: http://127.0.0.1:5000/chains/api/details/{chain_id}")

        # Опционально отправляем сигнал в n8n
        if notify:
            _notify_n8n(chain_id, "ok", prev_reply)

        return {
            "status": "ok",
            "chain_id": chain_id,
            "result": prev_reply,
            "elapsed_ms": total_ms,
        }

    except Exception as e:
        # Непредвиденная ошибка (не в agentе, а до них)
        total_ms = (time.time() - t_chain_start) * 1000
        log_chain_end(
            chain_id=chain_id,
            status="failed",
            total_ms=total_ms,
            error=str(e)[:100]
        )

        print(f"❌ Критическая ошибка: {e}")
        return {
            "status": "failed",
            "chain_id": chain_id,
            "error": str(e),
        }


def _format_ms(ms: float) -> str:
    """Отформатировать миллисекунды."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        return f"{ms / 60000:.1f}m"


def _notify_n8n(chain_id: str, status: str, result: str):
    """Отправить сигнал в n8n webhook по завершении цепочки."""
    webhook = os.getenv("N8N_DONE_WEBHOOK", "")
    if not webhook:
        return

    try:
        import requests
        requests.post(webhook, json={
            "chain_id": chain_id,
            "status": status,
            "result": result[:2000],
            "ts": datetime.now().isoformat(),
        }, timeout=5)
    except Exception as e:
        print(f"⚠️ Не удалось уведомить n8n: {e}")


# ─── Примеры вызовов ────────────────────────────────────────────────

def example_run_content_week():
    """Пример 1: запустить еженедельный контент-план с логированием."""
    print("\n=== ПРИМЕР 1: Еженедельный контент-план ===\n")

    result = run_chain_with_logging(
        chain_key="content_week",
        notify=True
    )

    print(f"\nРезультат: {result['status']}")
    if result['status'] == 'ok':
        print(f"Цепочка {result['chain_id']}")
        print(f"Время: {result.get('elapsed_ms', 0) / 1000:.1f}s")


def example_run_new_client():
    """Пример 2: запустить обработку новой клиентки."""
    print("\n=== ПРИМЕР 2: Обработка новой клиентки ===\n")

    # Подготавливаем контекст с данными новой клиентки
    context = {
        "input": "Имя: Оля, возраст: 32, проблема: тревожная привязанность, заполнила анкету на сайте",
        "client_id": "client_20260608_001",
        "intake_form": {
            "name": "Оля",
            "age": 32,
            "issue": "Выбираю не тех мужчин, потом страдаю",
            "pattern": None,
        }
    }

    result = run_chain_with_logging(
        chain_key="new_client",
        context_override=context,
        notify=True
    )

    print(f"\nРезультат: {result['status']}")
    if result['status'] == 'ok':
        print(f"Рекомендация Леры следует выше в логе")


def example_check_dashboard():
    """Пример 3: проверить дашборд."""
    print("\n=== ПРИМЕР 3: Проверить дашборд ===\n")

    import requests

    try:
        # Проверяем метрики
        resp = requests.get("http://127.0.0.1:5000/chains/api/metrics")
        if resp.status_code == 200:
            metrics = resp.json()["overall"]
            print(f"✅ Дашборд доступен")
            print(f"   Успешность: {metrics['success_rate']:.1f}%")
            print(f"   Всего задач: {metrics['total_tasks']}")
        else:
            print(f"❌ Дашборд вернул {resp.status_code}")
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        print(f"   Запустить: python webapp.py")


def example_list_active_chains():
    """Пример 4: вывести активные цепочки."""
    print("\n=== ПРИМЕР 4: Активные цепочки ===\n")

    import requests

    try:
        resp = requests.get("http://127.0.0.1:5000/chains/api/active")
        if resp.status_code == 200:
            data = resp.json()
            chains = data.get("chains", [])

            if chains:
                print(f"Всего активных: {len(chains)}")
                for chain in chains[:5]:
                    print(f"  • {chain['chain_id']}")
                    print(f"    От: {chain['from_agent']}")
                    print(f"    Прошло: {chain['elapsed_human']}")
                    print()
            else:
                print("Активных цепочек нет")
        else:
            print(f"Ошибка: {resp.status_code}")
    except Exception as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    """Демонстрация всех примеров."""

    print("""
╔════════════════════════════════════════════════════════════╗
║  CHAIN_DASHBOARD — Примеры использования                  ║
╚════════════════════════════════════════════════════════════╝
    """)

    print("ШАГИ:")
    print("  1. Убедиться, что webapp.py запущен: python webapp.py")
    print("  2. Выбрать пример ниже")
    print("  3. Посмотреть дашборд: http://127.0.0.1:5000/chains")
    print()

    # Раскомментировать нужный пример:

    # Пример 1: еженедельный контент
    # example_run_content_week()

    # Пример 2: новая клиентка
    # example_run_new_client()

    # Пример 3: проверить дашборд
    # example_check_dashboard()

    # Пример 4: активные цепочки
    # example_list_active_chains()

    # Или все примеры автоматически:
    print("⏳ Демонстрация...\n")
    example_check_dashboard()
    example_list_active_chains()

    print("""
╔════════════════════════════════════════════════════════════╗
║  Следующие шаги:                                         ║
║  1. Отредактировать main-блок в этом файле               ║
║  2. Запустить: python CHAIN_DASHBOARD_EXAMPLE.py          ║
║  3. Посмотреть результаты в дашборде                      ║
╚════════════════════════════════════════════════════════════╝
    """)
