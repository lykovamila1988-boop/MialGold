# -*- coding: utf-8 -*-
"""
chain_retry_integration.py — Интеграция chain_retry с агентами (examples).

Готовые паттерны для использования в webapp.py, office.py и других модулях.
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import traceback

try:
    import chain_retry
except ImportError:
    chain_retry = None

try:
    import error_monitor
except ImportError:
    error_monitor = None

logger = logging.getLogger("chain_integration")


# === ТИПЫ И KONSTANTS ===

class ChainExecutionConfig:
    """Конфигурация для выполнения цепи."""

    def __init__(self, chain_id: str, agents: List[str],
                 max_retries: int = 3, timeout_seconds: int = 300,
                 context: Optional[Dict] = None):
        self.chain_id = chain_id
        self.agents = agents
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.context = context or {}
        self.stop_on_error = False  # Продолжать ли при ошибке?
        self.escalate_agent = "manager"  # На кого эскалировать при сбое


# === HELPER FUNCTIONS ===

def should_retry(error: Exception, reason: str = "") -> bool:
    """Определить, стоит ли повторить ошибку."""
    error_msg = str(error).lower()

    # Не повторяем
    if any(x in error_msg for x in ["not found", "404", "invalid input", "validation"]):
        return False

    # Повторяем
    if any(x in error_msg for x in ["timeout", "rate limit", "temporarily unavailable", "connection"]):
        return True

    # Если указана причина, используем её
    if reason in ["timeout", "api_failure", "agent_error"]:
        return True

    return True  # По умолчанию — повторяем


def get_retry_reason(error: Exception) -> str:
    """Определить причину повтора по типу ошибки."""
    error_msg = str(error).lower()

    if "timeout" in error_msg:
        return "timeout"
    elif "rate limit" in error_msg or "429" in error_msg:
        return "api_failure"
    elif "401" in error_msg or "403" in error_msg:
        return "api_failure"
    else:
        return "agent_error"


# === PATTERN 1: Sequential Chain Execution ===

def execute_chain_sequential(
    config: ChainExecutionConfig,
    agent_runner: Callable[[str, Dict], str]  # Функция для запуска агента
) -> Dict[str, Any]:
    """Выполнить цепь агентов последовательно с повторами.

    Args:
        config: ChainExecutionConfig с параметрами
        agent_runner: Функция(agent_key, context) -> response

    Returns:
        {
            "chain_id": "...",
            "status": "success" | "failed" | "escalated",
            "final_result": "...",
            "total_retries": 3,
            "duration_seconds": 45.5
        }
    """
    if not chain_retry:
        logger.error("chain_retry module not available")
        return {"status": "error", "message": "chain_retry not available"}

    from datetime import datetime

    start_time = datetime.utcnow()

    # Создаем цепь
    chain = chain_retry.create_chain(
        config.chain_id,
        config.agents,
        context=config.context
    )

    logger.info(f"Starting chain {config.chain_id} with agents: {config.agents}")

    # Выполняем каждого агента
    for agent_key in config.agents:
        max_attempts = config.max_retries + 1
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                # Start
                chain_retry.update_node_status(config.chain_id, agent_key, "running")

                # Run agent
                response = agent_runner(agent_key, config.context)

                # Success
                chain_retry.update_node_status(config.chain_id, agent_key, "success",
                                                reply=response)
                logger.info(f"Agent {agent_key} succeeded on attempt {attempt}")
                break  # Move to next agent

            except Exception as e:
                logger.error(f"Agent {agent_key} failed on attempt {attempt}: {e}")
                chain_retry.update_node_status(config.chain_id, agent_key, "failed",
                                                error=str(e))

                # Should we retry?
                if not should_retry(e, get_retry_reason(e)):
                    logger.warning(f"Not retrying {agent_key}: {e}")
                    break

                if attempt < max_attempts:
                    # Retry
                    reason = get_retry_reason(e)
                    result = chain_retry.retry_chain(
                        config.chain_id, agent_key, reason, max_retries=config.max_retries
                    )

                    if result is None:
                        # Max retries exceeded
                        logger.error(f"Max retries exceeded for {agent_key}")
                        chain_retry.escalate_chain(
                            config.chain_id,
                            config.escalate_agent,
                            reason=f"Failed after {config.max_retries} retries: {e}"
                        )
                        break
                    else:
                        logger.info(f"Retrying {agent_key} (attempt {attempt + 1}/{max_attempts})")
                else:
                    # No more retries
                    logger.error(f"No more retries for {agent_key}")
                    chain_retry.escalate_chain(
                        config.chain_id,
                        config.escalate_agent,
                        reason=str(e)
                    )
                    break

            except KeyboardInterrupt:
                logger.warning(f"Chain {config.chain_id} cancelled by user")
                chain_retry.cancel_chain(config.chain_id, reason="User cancelled")
                return {
                    "chain_id": config.chain_id,
                    "status": "cancelled",
                    "message": "User cancelled",
                    "total_retries": chain_retry.get_chain(config.chain_id)["retry_count"]
                }

    # Finish
    final_chain = chain_retry.get_chain(config.chain_id)
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()

    result = {
        "chain_id": config.chain_id,
        "status": final_chain["status"],
        "total_retries": final_chain["retry_count"],
        "duration_seconds": round(duration, 2),
        "agents_completed": sum(1 for n in final_chain["nodes"].values() if n.status == "success"),
        "agents_failed": sum(1 for n in final_chain["nodes"].values() if n.status == "failed"),
    }

    if final_chain["status"] == "success":
        chain_retry.complete_chain(config.chain_id)
        result["final_result"] = "All agents completed successfully"
        logger.info(f"Chain {config.chain_id} completed successfully")
    elif final_chain["status"] == "escalated":
        result["message"] = "Chain escalated to higher-level agent"
        logger.warning(f"Chain {config.chain_id} escalated")
    else:
        result["message"] = "Chain failed"
        logger.error(f"Chain {config.chain_id} failed")

    return result


# === PATTERN 2: Parallel Split + Merge ===

def execute_chain_parallel(
    config: ChainExecutionConfig,
    agent_runner: Callable[[str, Dict], Dict],  # Returns {"result": "...", "confidence": 0.9}
    merge_strategy: str = "consensus"
) -> Dict[str, Any]:
    """Выполнить цепь параллельно (split на несколько агентов + merge).

    Args:
        config: ChainExecutionConfig
        agent_runner: Функция(agent_key, context) -> {result, confidence, ...}
        merge_strategy: "union", "consensus", "first_success"

    Returns:
        {
            "chain_id": "...",
            "status": "success" | "partial" | "failed",
            "merged_result": "...",
            "all_results": [...],
            "merge_strategy": "consensus"
        }
    """
    if not chain_retry:
        logger.error("chain_retry module not available")
        return {"status": "error", "message": "chain_retry not available"}

    # Split
    chain_retry.split_chain(
        config.chain_id,
        to_agents=config.agents,
        context=config.context
    )

    logger.info(f"Split chain {config.chain_id} to {len(config.agents)} agents")

    # Run all agents (in parallel conceptually; actual parallelism depends on caller)
    results = []
    for agent_key in config.agents:
        try:
            chain_retry.update_node_status(config.chain_id, agent_key, "running")

            response = agent_runner(agent_key, config.context)

            chain_retry.update_node_status(config.chain_id, agent_key, "success",
                                            reply=str(response.get("result", "")))

            results.append({
                "agent_key": agent_key,
                "result": response.get("result"),
                "confidence": response.get("confidence", 0.8),
                "error": None
            })

            logger.info(f"Agent {agent_key} completed (confidence: {response.get('confidence', 'N/A')})")

        except Exception as e:
            logger.error(f"Agent {agent_key} failed: {e}")

            chain_retry.update_node_status(config.chain_id, agent_key, "failed", error=str(e))

            results.append({
                "agent_key": agent_key,
                "result": None,
                "confidence": None,
                "error": str(e)
            })

    # Merge
    chain_retry.merge_results(config.chain_id, results, merge_strategy=merge_strategy)

    final_chain = chain_retry.get_chain(config.chain_id)

    merged_data = final_chain.get("merged_results", {})

    result = {
        "chain_id": config.chain_id,
        "status": "success" if merged_data.get("merged_data") else "partial",
        "merge_strategy": merge_strategy,
        "merged_result": merged_data.get("merged_data"),
        "all_results": results,
        "agents_completed": sum(1 for r in results if not r.get("error")),
        "agents_failed": sum(1 for r in results if r.get("error")),
    }

    logger.info(f"Chain {config.chain_id} merged with strategy '{merge_strategy}'")
    return result


# === PATTERN 3: Error Handler with Context ===

class ChainErrorHandler:
    """Обработчик ошибок цепи с контекстом и логированием."""

    def __init__(self, chain_id: str, escalate_to: str = "manager"):
        self.chain_id = chain_id
        self.escalate_to = escalate_to
        self.errors = []

    def handle(self, agent_key: str, error: Exception,
               context: Optional[Dict] = None) -> bool:
        """Обработать ошибку агента. Вернуть True если нужен повтор.

        Args:
            agent_key: Какой агент сбойнулся
            error: Исключение
            context: Дополнительный контекст

        Returns:
            True если нужен повтор, False если нужна эскалация
        """
        context = context or {}
        self.errors.append({
            "agent": agent_key,
            "error": str(error),
            "type": type(error).__name__,
            "context": context
        })

        # Log to error_monitor
        if error_monitor:
            error_monitor.log_error(
                error,
                context={
                    "chain_id": self.chain_id,
                    "agent": agent_key,
                    "source": "chain_execution",
                    **context
                },
                alert=isinstance(error, (RuntimeError, TimeoutError))
            )

        # Decide
        if should_retry(error):
            logger.info(f"Will retry {agent_key}: {error}")
            return True
        else:
            logger.warning(f"Will escalate (no retry) {agent_key}: {error}")
            chain_retry.escalate_chain(
                self.chain_id,
                self.escalate_to,
                reason=f"{type(error).__name__}: {str(error)[:100]}"
            )
            return False

    def summary(self) -> str:
        """Получить summary всех ошибок."""
        if not self.errors:
            return "No errors"
        return f"{len(self.errors)} errors: {'; '.join(e['error'] for e in self.errors[:3])}"


# === PATTERN 4: Chain with Fallback ===

def execute_chain_with_fallback(
    primary_config: ChainExecutionConfig,
    fallback_agents: List[str],
    agent_runner: Callable[[str, Dict], str]
) -> Dict[str, Any]:
    """Выполнить цепь с fallback-агентами если основная цепь сбойнулась.

    Args:
        primary_config: Основная цепь
        fallback_agents: Агенты для fallback
        agent_runner: Функция для запуска агента

    Returns:
        {
            "chain_id": "...",
            "status": "success" | "fallback" | "failed",
            "used_fallback": True | False,
            ...
        }
    """
    if not chain_retry:
        return {"status": "error", "message": "chain_retry not available"}

    # Пытаемся основную цепь
    result = execute_chain_sequential(primary_config, agent_runner)

    if result["status"] == "success":
        return {**result, "used_fallback": False}

    # Основная цепь не сработала, пробуем fallback
    logger.warning(f"Chain {primary_config.chain_id} failed, trying fallback")

    fallback_config = ChainExecutionConfig(
        chain_id=f"{primary_config.chain_id}_fallback",
        agents=fallback_agents,
        max_retries=2,  # Меньше попыток на fallback
        context={**primary_config.context, "is_fallback": True}
    )

    fallback_result = execute_chain_sequential(fallback_config, agent_runner)

    fallback_result["used_fallback"] = True
    fallback_result["primary_chain_id"] = primary_config.chain_id

    return fallback_result


# === PATTERN 5: Chain Monitor (Background) ===

class ChainMonitor:
    """Мониторить цепи и автоматически очищать старые."""

    def __init__(self, cleanup_hours: int = 24):
        self.cleanup_hours = cleanup_hours
        self.last_cleanup = None

    def maybe_cleanup(self):
        """Очистить старые цепи если нужно."""
        if not chain_retry:
            return

        from datetime import datetime, timedelta

        now = datetime.utcnow()

        if self.last_cleanup is None or (now - self.last_cleanup).total_seconds() > 3600:
            chain_retry.clear_old_chains(hours=self.cleanup_hours)
            self.last_cleanup = now
            logger.info("Cleanup completed")

    def get_status(self) -> Dict[str, Any]:
        """Получить текущий статус всех цепей."""
        if not chain_retry:
            return {}

        stats = chain_retry.get_chain_stats(hours=24)
        return {
            "total": stats["total_chains"],
            "by_status": stats["by_status"],
            "total_retries": stats["total_retries"],
            "avg_duration": stats.get("avg_duration_seconds"),
        }

    def export_failed_chains(self, export_dir: Path) -> List[str]:
        """Экспортировать все сбойнувшие цепи для анализа."""
        if not chain_retry:
            return []

        exported = []
        all_chains = chain_retry.get_all_chains()

        for chain_id, chain in all_chains.items():
            if chain.get("status") == "failed":
                path = chain_retry.export_chain_to_json(
                    chain_id,
                    filepath=export_dir / f"{chain_id}.json"
                )
                if path:
                    exported.append(path)

        logger.info(f"Exported {len(exported)} failed chains")
        return exported


# === TEST & DEMO ===

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Chain Retry Integration Patterns ===\n")

    # Demo 1: Sequential
    print("Demo 1: Sequential chain execution")
    print("-" * 50)

    def dummy_agent_runner(agent_key: str, context: Dict) -> str:
        """Simple mock agent."""
        return f"Response from {agent_key}"

    config = ChainExecutionConfig(
        chain_id="demo_sequential",
        agents=["victoria", "alina"],
        max_retries=2,
        context={"document": "test.md"}
    )

    if chain_retry:
        result = execute_chain_sequential(config, dummy_agent_runner)
        print(f"\nResult: {result}\n")
    else:
        print("chain_retry not available\n")

    # Demo 2: Parallel
    print("Demo 2: Parallel chain with merge")
    print("-" * 50)

    def dummy_agent_with_confidence(agent_key: str, context: Dict) -> Dict:
        """Mock agent returning confidence."""
        import random
        return {
            "result": f"Analysis from {agent_key}",
            "confidence": random.uniform(0.7, 1.0)
        }

    config2 = ChainExecutionConfig(
        chain_id="demo_parallel",
        agents=["olya", "rita", "manager"],
        context={"month": "June"}
    )

    if chain_retry:
        result2 = execute_chain_parallel(config2, dummy_agent_with_confidence)
        print(f"\nResult: {result2}\n")
    else:
        print("chain_retry not available\n")

    # Demo 3: Error handling
    print("Demo 3: Error handling")
    print("-" * 50)

    handler = ChainErrorHandler("demo_errors")

    try:
        raise TimeoutError("API timeout")
    except TimeoutError as e:
        should_retry = handler.handle("agent1", e, context={"endpoint": "/api/test"})
        print(f"Should retry: {should_retry}")

    print(f"Summary: {handler.summary()}\n")

    # Demo 4: Monitor
    print("Demo 4: Chain monitoring")
    print("-" * 50)

    monitor = ChainMonitor()
    status = monitor.get_status()
    print(f"Chain status: {status}")
