# -*- coding: utf-8 -*-
"""
chain_retry.py — Управление сбоями и повторами цепочек агентов.

Функции:
  retry_chain(chain_id, failed_agent, reason)      — перезапустить цепь с агента после сбоя
  escalate_chain(chain_id, new_agent)              — переdirigirect на другого агента
  split_chain(chain_id, to_agents[])               — послать на нескольких агентов параллельно
  merge_results(chain_id, results[])               — объединить результаты из параллельных веток
  get_chain_history(chain_id)                      — получить историю цепочки
  get_chain_stats()                                — статистика по цепочкам

Состояние цепочки отслеживается в JSON, логирование ошибок через error_monitor.
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import error_monitor
except ImportError:
    error_monitor = None

# === CONFIG ===

MILA_FOLDER = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
LOG_DIR = MILA_FOLDER / "logs"
CHAINS_DIR = LOG_DIR / "chains"
CHAINS_DIR.mkdir(parents=True, exist_ok=True)

CHAIN_LOG = LOG_DIR / "chain_events.jsonl"
RETRY_LOG = LOG_DIR / "chain_retries.jsonl"

# === Логирование ===

logger = logging.getLogger("chain_retry")
handler = logging.FileHandler(LOG_DIR / "chain_retry.log", encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# === ENUMS ===

class ChainStatus(str, Enum):
    """Статусы цепочки."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    ESCALATED = "escalated"
    SPLIT = "split"
    MERGED = "merged"
    CANCELLED = "cancelled"


class RetryReason(str, Enum):
    """Причины повтора."""
    AGENT_ERROR = "agent_error"
    TIMEOUT = "timeout"
    API_FAILURE = "api_failure"
    VALIDATION_FAILED = "validation_failed"
    MANUAL_RETRY = "manual_retry"
    TASK_COMPLEXITY = "task_complexity"
    ESCALATION = "escalation"


# === DATACLASSES ===

@dataclass
class ChainNode:
    """Один шаг в цепочке."""
    agent_key: str
    status: str  # "pending", "running", "success", "failed", "skipped"
    reply: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class ChainEvent:
    """Событие в жизни цепочки."""
    timestamp: str
    event_type: str  # "start", "node_done", "node_failed", "retry", "escalate", "split", "merge", "success", "cancel"
    chain_id: str
    agent_key: str
    details: Dict[str, Any]


# === ГЛОБАЛЬНОЕ СОСТОЯНИЕ ===

_chains: Dict[str, Dict[str, Any]] = {}
_chains_lock = threading.RLock()


# === ОСНОВНЫЕ ФУНКЦИИ ===

def create_chain(chain_id: str, agents: List[str], context: Optional[Dict] = None) -> Dict[str, Any]:
    """Создать новую цепочку агентов.

    Args:
        chain_id: Уникальный ID цепочки
        agents: Список ключей агентов в порядке выполнения
        context: Дополнительный контекст (metadata)

    Returns:
        Объект цепочки
    """
    with _chains_lock:
        chain = {
            "id": chain_id,
            "status": ChainStatus.RUNNING.value,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "completed_at": None,
            "agents": agents,
            "nodes": {agent: ChainNode(agent_key=agent, status="pending") for agent in agents},
            "current_agent_idx": 0,
            "retry_count": 0,
            "max_retries": 3,
            "context": context or {},
            "history": [],
            "split_branches": {},  # Для параллельных веток
            "merged_results": None,
        }
        _chains[chain_id] = chain
        logger.info(f"Created chain {chain_id} with agents: {agents}")
        _log_chain_event(chain_id, agents[0], "start", {"agents": agents})
        return chain


def get_chain(chain_id: str) -> Optional[Dict[str, Any]]:
    """Получить цепочку по ID."""
    with _chains_lock:
        return _chains.get(chain_id)


def update_node_status(chain_id: str, agent_key: str, status: str,
                       reply: Optional[str] = None, error: Optional[str] = None):
    """Обновить статус шага цепочки.

    Args:
        chain_id: ID цепочки
        agent_key: Ключ агента
        status: "running", "success", "failed", "skipped"
        reply: Результат работы агента
        error: Описание ошибки (если status="failed")
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found")
            return

        chain = _chains[chain_id]
        if agent_key not in chain["nodes"]:
            logger.warning(f"Node {agent_key} not found in chain {chain_id}")
            return

        node = chain["nodes"][agent_key]
        node.status = status

        if status == "running":
            node.started_at = datetime.utcnow().isoformat() + "Z"
        elif status in ["success", "failed", "skipped"]:
            node.completed_at = datetime.utcnow().isoformat() + "Z"
            if node.started_at:
                start = datetime.fromisoformat(node.started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(node.completed_at.replace("Z", "+00:00"))
                node.duration_seconds = (end - start).total_seconds()

        if reply is not None:
            node.reply = reply
        if error is not None:
            node.error = error

        event_type = "node_done" if status == "success" else "node_failed" if status == "failed" else "node_running"
        _log_chain_event(chain_id, agent_key, event_type, {
            "status": status,
            "has_reply": reply is not None,
            "has_error": error is not None
        })

        logger.info(f"Chain {chain_id} node {agent_key}: {status}")


def retry_chain(chain_id: str, failed_agent: str, reason: str,
                max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Перезапустить цепь со сбойного агента.

    Логика:
    1. Проверить, не превышен ли лимит повторов
    2. Сбросить все ноды после failed_agent в статус "pending"
    3. Обновить current_agent_idx на failed_agent
    4. Залогировать попытку повтора

    Args:
        chain_id: ID цепочки
        failed_agent: Ключ агента, с которого перезапустить
        reason: Причина повтора (см. RetryReason)
        max_retries: Максимум повторов (по умолчанию 3)

    Returns:
        Обновленная цепочка или None если лимит превышен
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for retry")
            return None

        chain = _chains[chain_id]
        chain["retry_count"] += 1

        if chain["retry_count"] > max_retries:
            logger.error(f"Chain {chain_id} exceeded max retries ({max_retries})")
            chain["status"] = ChainStatus.FAILED.value
            _log_chain_event(chain_id, failed_agent, "retry", {
                "reason": reason,
                "retry_count": chain["retry_count"],
                "max_retries": max_retries,
                "action": "failed - limit exceeded"
            })

            # Логируем в error_monitor
            if error_monitor:
                error_context = {
                    "chain_id": chain_id,
                    "failed_agent": failed_agent,
                    "reason": reason,
                    "retry_count": chain["retry_count"],
                    "max_retries": max_retries
                }
                try:
                    error_monitor.log_error(
                        Exception(f"Chain retry limit exceeded: {reason}"),
                        context=error_context,
                        alert=True,
                        level="CRITICAL"
                    )
                except Exception as e:
                    logger.error(f"Failed to log error: {e}")

            return None

        # Найти индекс failed_agent
        try:
            failed_idx = chain["agents"].index(failed_agent)
        except ValueError:
            logger.error(f"Agent {failed_agent} not in chain {chain_id}")
            return None

        # Сбросить все ноды со сбойного агента в "pending"
        for i, agent in enumerate(chain["agents"]):
            if i >= failed_idx:
                chain["nodes"][agent].status = "pending"
                chain["nodes"][agent].started_at = None
                chain["nodes"][agent].completed_at = None
                chain["nodes"][agent].duration_seconds = None

        chain["current_agent_idx"] = failed_idx
        chain["status"] = ChainStatus.RETRYING.value
        chain["nodes"][failed_agent].retry_count += 1

        # Логируем попытку
        _log_chain_event(chain_id, failed_agent, "retry", {
            "reason": reason,
            "retry_count": chain["retry_count"],
            "max_retries": max_retries,
            "action": "retrying from this agent"
        })

        # Записываем в retry log
        _log_retry_attempt(chain_id, failed_agent, reason, chain["retry_count"], max_retries)

        logger.info(f"Chain {chain_id} retrying from {failed_agent} (attempt {chain['retry_count']}/{max_retries})")
        return chain


def escalate_chain(chain_id: str, new_agent: str, reason: str = "") -> Optional[Dict[str, Any]]:
    """Переправить цепь на другого агента (escalate).

    Логика:
    1. Отметить текущего агента как завершенного
    2. Заменить оставшихся агентов на нового
    3. Обновить статус на ESCALATED

    Args:
        chain_id: ID цепочки
        new_agent: Ключ нового агента
        reason: Причина эскалации

    Returns:
        Обновленная цепочка или None если цепь не найдена
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for escalation")
            return None

        chain = _chains[chain_id]
        current_idx = chain["current_agent_idx"]
        current_agent = chain["agents"][current_idx] if current_idx < len(chain["agents"]) else "unknown"

        # Отметить остальных агентов как "skipped"
        for i in range(current_idx + 1, len(chain["agents"])):
            skipped_agent = chain["agents"][i]
            chain["nodes"][skipped_agent].status = "skipped"

        # Заменить оставшихся агентов на нового
        chain["agents"] = chain["agents"][:current_idx + 1] + [new_agent]
        if new_agent not in chain["nodes"]:
            chain["nodes"][new_agent] = ChainNode(agent_key=new_agent, status="pending")

        chain["status"] = ChainStatus.ESCALATED.value
        chain["current_agent_idx"] = current_idx + 1

        _log_chain_event(chain_id, current_agent, "escalate", {
            "from_agent": current_agent,
            "to_agent": new_agent,
            "reason": reason
        })

        logger.info(f"Chain {chain_id} escalated from {current_agent} to {new_agent}")
        return chain


def split_chain(chain_id: str, to_agents: List[str], context: Optional[Dict] = None) -> Dict[str, Any]:
    """Отправить цепь на несколько агентов параллельно (split).

    Логика:
    1. Создать параллельные ветки для каждого агента
    2. Отметить их как "pending"
    3. Обновить статус цепи на SPLIT

    Args:
        chain_id: ID цепочки
        to_agents: Список ключей агентов для параллельной обработки
        context: Дополнительный контекст

    Returns:
        Обновленная цепочка
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for split")
            return None

        chain = _chains[chain_id]
        current_agent = chain["agents"][chain["current_agent_idx"]] if chain["current_agent_idx"] < len(chain["agents"]) else "unknown"

        # Создаем параллельные ветки
        split_id = datetime.utcnow().isoformat()
        chain["split_branches"] = {
            agent: {
                "agent_key": agent,
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": split_id
            }
            for agent in to_agents
        }

        for agent in to_agents:
            if agent not in chain["nodes"]:
                chain["nodes"][agent] = ChainNode(agent_key=agent, status="pending")

        chain["status"] = ChainStatus.SPLIT.value

        _log_chain_event(chain_id, current_agent, "split", {
            "to_agents": to_agents,
            "count": len(to_agents),
            "split_id": split_id,
            "context": context or {}
        })

        logger.info(f"Chain {chain_id} split into {len(to_agents)} branches: {to_agents}")
        return chain


def merge_results(chain_id: str, results: List[Dict[str, Any]],
                  merge_strategy: str = "union") -> Optional[Dict[str, Any]]:
    """Объединить результаты из параллельных веток.

    Стратегии слияния:
    - "union": Объединить все результаты в список
    - "consensus": Выбрать результаты с наибольшей "уверенностью"
    - "first_success": Первый успешный результат

    Args:
        chain_id: ID цепочки
        results: Список результатов [{agent_key, result, error, ...}, ...]
        merge_strategy: Стратегия слияния

    Returns:
        Обновленная цепочка или None если цепь не найдена
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for merge")
            return None

        chain = _chains[chain_id]

        # Обновляем статусы ветвей
        for result in results:
            agent_key = result.get("agent_key")
            if agent_key in chain["split_branches"]:
                branch = chain["split_branches"][agent_key]
                branch["status"] = "success" if not result.get("error") else "failed"
                branch["result"] = result.get("result")
                branch["error"] = result.get("error")
                branch["completed_at"] = datetime.utcnow().isoformat() + "Z"

        # Применяем стратегию слияния
        merged = None
        if merge_strategy == "union":
            merged = [r.get("result") for r in results if not r.get("error")]
        elif merge_strategy == "consensus":
            # Выбираем результат с наибольшей уверенностью (если есть confidence)
            results_with_conf = [r for r in results if r.get("confidence", 0) > 0]
            if results_with_conf:
                merged = max(results_with_conf, key=lambda r: r.get("confidence", 0)).get("result")
        elif merge_strategy == "first_success":
            for r in results:
                if not r.get("error"):
                    merged = r.get("result")
                    break

        chain["merged_results"] = {
            "strategy": merge_strategy,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "results_count": len(results),
            "merged_data": merged,
            "raw_results": results
        }

        chain["status"] = ChainStatus.MERGED.value

        _log_chain_event(chain_id, "merge", "merge", {
            "strategy": merge_strategy,
            "results_count": len(results),
            "merged": merged is not None
        })

        logger.info(f"Chain {chain_id} merged {len(results)} results with strategy '{merge_strategy}'")
        return chain


def complete_chain(chain_id: str, final_result: Optional[str] = None) -> bool:
    """Завершить цепочку успешно.

    Args:
        chain_id: ID цепочки
        final_result: Финальный результат

    Returns:
        True если успешно, False если цепь не найдена
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for completion")
            return False

        chain = _chains[chain_id]
        chain["status"] = ChainStatus.SUCCESS.value
        chain["completed_at"] = datetime.utcnow().isoformat() + "Z"
        chain["final_result"] = final_result

        _log_chain_event(chain_id, "system", "success", {
            "final_result": final_result is not None,
            "total_nodes": len(chain["agents"]),
            "total_retries": chain["retry_count"]
        })

        logger.info(f"Chain {chain_id} completed successfully")
        return True


def cancel_chain(chain_id: str, reason: str = "") -> bool:
    """Отменить цепочку.

    Args:
        chain_id: ID цепочки
        reason: Причина отмены

    Returns:
        True если успешно, False если цепь не найдена
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for cancellation")
            return False

        chain = _chains[chain_id]
        chain["status"] = ChainStatus.CANCELLED.value
        chain["completed_at"] = datetime.utcnow().isoformat() + "Z"
        chain["cancel_reason"] = reason

        _log_chain_event(chain_id, "system", "cancel", {"reason": reason})

        logger.info(f"Chain {chain_id} cancelled: {reason}")
        return True


# === ИСТОРИЯ И СТАТИСТИКА ===

def get_chain_history(chain_id: str) -> List[Dict[str, Any]]:
    """Получить историю событий цепочки.

    Returns:
        Список событий в хронологическом порядке
    """
    with _chains_lock:
        if chain_id not in _chains:
            return []

        chain = _chains[chain_id]
        return chain.get("history", [])


def get_chain_stats(hours: int = 24) -> Dict[str, Any]:
    """Получить статистику по цепочкам за последние N часов.

    Returns:
        {
            "period": "last 24 hours",
            "total_chains": 10,
            "by_status": {"success": 7, "failed": 2, "running": 1},
            "total_retries": 5,
            "avg_duration_seconds": 45.3,
            "chains": [{id, status, agents, retry_count, ...}, ...]
        }
    """
    stats = {
        "period": f"last {hours} hours",
        "total_chains": 0,
        "by_status": {},
        "total_retries": 0,
        "avg_duration_seconds": 0,
        "chains": []
    }

    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    total_duration = 0
    chain_count = 0

    with _chains_lock:
        for chain_id, chain in _chains.items():
            created_at = datetime.fromisoformat(chain["created_at"].replace("Z", "+00:00"))
            if created_at < cutoff_time:
                continue

            status = chain.get("status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["total_retries"] += chain.get("retry_count", 0)

            # Вычисляем длительность
            if chain.get("completed_at"):
                completed_at = datetime.fromisoformat(chain["completed_at"].replace("Z", "+00:00"))
                duration = (completed_at - created_at).total_seconds()
                total_duration += duration
                chain_count += 1

            stats["chains"].append({
                "id": chain_id,
                "status": status,
                "agents": chain.get("agents", []),
                "retry_count": chain.get("retry_count", 0),
                "created_at": chain.get("created_at"),
                "completed_at": chain.get("completed_at"),
            })

        stats["total_chains"] = len(stats["chains"])
        if chain_count > 0:
            stats["avg_duration_seconds"] = round(total_duration / chain_count, 2)

    return stats


def get_all_chains() -> Dict[str, Dict[str, Any]]:
    """Получить все цепочки (для отладки)."""
    with _chains_lock:
        return dict(_chains)


def clear_old_chains(hours: int = 24):
    """Удалить цепочки старше N часов (очистка памяти)."""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    with _chains_lock:
        to_remove = []
        for chain_id, chain in _chains.items():
            if chain.get("status") in [ChainStatus.SUCCESS.value, ChainStatus.FAILED.value, ChainStatus.CANCELLED.value]:
                completed_at = chain.get("completed_at")
                if completed_at:
                    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                    if completed < cutoff_time:
                        to_remove.append(chain_id)

        for chain_id in to_remove:
            del _chains[chain_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old chains")


# === ВНУТРЕННИЕ ФУНКЦИИ ЛОГИРОВАНИЯ ===

def _log_chain_event(chain_id: str, agent_key: str, event_type: str,
                     details: Optional[Dict] = None):
    """Логировать событие цепочки (внутренняя функция)."""
    event = ChainEvent(
        timestamp=datetime.utcnow().isoformat() + "Z",
        event_type=event_type,
        chain_id=chain_id,
        agent_key=agent_key,
        details=details or {}
    )

    with _chains_lock:
        if chain_id in _chains:
            _chains[chain_id]["history"].append(asdict(event))

    # Пишем в JSONL лог
    try:
        with open(CHAIN_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.error(f"Failed to write chain event log: {e}")


def _log_retry_attempt(chain_id: str, agent_key: str, reason: str,
                       attempt: int, max_retries: int):
    """Логировать попытку повтора в отдельный файл."""
    retry_record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "chain_id": chain_id,
        "agent_key": agent_key,
        "reason": reason,
        "attempt": attempt,
        "max_retries": max_retries
    }

    try:
        with open(RETRY_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(retry_record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to write retry log: {e}")


# === UTILITIES ===

def export_chain_to_json(chain_id: str, filepath: Optional[Path] = None) -> Optional[str]:
    """Экспортировать цепочку в JSON файл.

    Args:
        chain_id: ID цепочки
        filepath: Путь для сохранения (если None, использует CHAINS_DIR/chain_id.json)

    Returns:
        Путь к файлу или None если цепь не найдена
    """
    with _chains_lock:
        if chain_id not in _chains:
            logger.warning(f"Chain {chain_id} not found for export")
            return None

        chain = _chains[chain_id]

        # Конвертируем ChainNode в dict
        nodes_dict = {}
        for agent, node in chain["nodes"].items():
            nodes_dict[agent] = asdict(node)

        export_data = {
            **chain,
            "nodes": nodes_dict
        }

    if filepath is None:
        filepath = CHAINS_DIR / f"{chain_id}.json"

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Chain {chain_id} exported to {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to export chain {chain_id}: {e}")
        return None


def load_chain_from_json(filepath: Path) -> Optional[Dict[str, Any]]:
    """Загрузить цепочку из JSON файла.

    Args:
        filepath: Путь к JSON файлу

    Returns:
        Объект цепочки или None если файл не найден
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Восстанавливаем ChainNode объекты
        nodes_dict = {}
        for agent, node_data in data.get("nodes", {}).items():
            nodes_dict[agent] = ChainNode(**node_data)

        data["nodes"] = nodes_dict

        with _chains_lock:
            chain_id = data.get("id")
            if chain_id:
                _chains[chain_id] = data

        logger.info(f"Chain loaded from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Failed to load chain from {filepath}: {e}")
        return None


if __name__ == "__main__":
    # Тестирование
    print("=== Chain Retry Module Test ===\n")

    # Создаем тестовую цепь
    test_chain_id = "test_chain_001"
    agents = ["victoria", "alina", "dima"]

    chain = create_chain(test_chain_id, agents, context={"test": True})
    print(f"[OK] Created chain: {chain['id']}\n")

    # Обновляем статусы
    update_node_status(test_chain_id, "victoria", "running")
    update_node_status(test_chain_id, "victoria", "success", reply="Отредактировано")
    print("[OK] Victoria completed successfully\n")

    # Симулируем ошибку
    update_node_status(test_chain_id, "alina", "running")
    update_node_status(test_chain_id, "alina", "failed",
                       error="Connection timeout")
    print("[OK] Alina failed\n")

    # Повторяем
    retry_chain(test_chain_id, "alina", "timeout", max_retries=3)
    print("[OK] Retrying from alina\n")

    # Статистика
    stats = get_chain_stats(hours=24)
    print("Chain stats:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print()

    # История
    history = get_chain_history(test_chain_id)
    print(f"Chain history ({len(history)} events):")
    for event in history[:3]:
        print(f"  - {event['timestamp']}: {event['event_type']} ({event['agent_key']})")
