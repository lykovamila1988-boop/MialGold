# -*- coding: utf-8 -*-
"""
CHAIN_DASHBOARD.py — Flask blueprint для мониторинга цепочек агентов.

Отслеживает:
  1. Активные цепочки (какой агент, откуда, статус, прошедшее время)
  2. История цепочек (завершённые цепи с общим временем выполнения)
  3. Timeline агентов (что сейчас делает каждый агент)
  4. Детали цепочки (полные логи для chain_id)
  5. Метрики производительности (среднее время по агентам, success rate)

Интеграция с webapp.py:
  1. В webapp.py после app = Flask(__name__) добавить:
     from chain_dashboard import chain_bp
     app.register_blueprint(chain_bp)

  2. Убедиться, что memory.py ведёт лог событий (EVENTS JSONL).

  3. Доступные маршруты:
     GET /chains/api/active          — список активных цепочек
     GET /chains/api/history         — история цепочек (с фильтром)
     GET /chains/api/timeline        — timeline агентов (кто что делает)
     GET /chains/api/details/<id>    — полные логи цепочки
     GET /chains/api/metrics         — метрики производительности
     GET /chains                     — веб-интерфейс дашборда

Структура данных:
  Цепочка отслеживается по трём событиям в memory.EVENTS (JSONL):
    - "chain:start"   — {chain_id, from_agent, agents: [список]}
    - "chain:step"    — {chain_id, agent, step_num, status: "running|done", elapsed_ms}
    - "chain:end"     — {chain_id, status: "ok|failed", total_ms}

  Pipeline может писать события через memory.log_event("chain:...", payload).
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import dict, list, tuple

from flask import Blueprint, jsonify, request, render_template_string

import base
import memory

logger = logging.getLogger("mila.chain_dashboard")

chain_bp = Blueprint(
    "chains",
    __name__,
    url_prefix="/chains",
    static_folder=None,
)


# ─── Чтение и парсинг логов ─────────────────────────────────────
def _read_chain_events() -> list:
    """Прочитать все события цепочек из memory.EVENTS (JSONL)."""
    try:
        lines = memory.EVENTS.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    events = []
    for line in lines:
        try:
            rec = json.loads(line)
            if rec.get("kind", "").startswith("chain:"):
                events.append(rec)
        except (ValueError, json.JSONDecodeError):
            continue
    return events


def _parse_iso(ts_str: str) -> datetime:
    """Распарсить ISO строку в datetime (UTC)."""
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _elapsed_ms(ts1: str, ts2: str) -> float:
    """Вычислить разницу между двумя ISO timestamps в миллисекундах."""
    try:
        dt1 = _parse_iso(ts1)
        dt2 = _parse_iso(ts2)
        delta = dt2 - dt1
        return delta.total_seconds() * 1000
    except Exception:
        return 0.0


def _format_ms(ms: float) -> str:
    """Отформатировать миллисекунды в читаемый вид."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        return f"{ms / 60000:.1f}m"


# ─── Построение моделей данных ──────────────────────────────────
def _build_active_chains() -> list:
    """
    Активные цепочки: событие chain:start без соответствующего chain:end.
    Возвращает: [{chain_id, from_agent, agents, status, elapsed_ms, start_ts}]
    """
    events = _read_chain_events()
    chain_starts = {}
    chain_ends = set()

    for evt in events:
        kind = evt.get("kind", "")
        pl = evt.get("payload", {})
        chain_id = pl.get("chain_id")

        if kind == "chain:start" and chain_id:
            chain_starts[chain_id] = {
                "start_ts": evt.get("ts"),
                "from_agent": pl.get("from_agent"),
                "agents": pl.get("agents", []),
                "description": pl.get("description", ""),
            }
        elif kind == "chain:end" and chain_id:
            chain_ends.add(chain_id)

    active = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for chain_id, info in chain_starts.items():
        if chain_id not in chain_ends:
            elapsed = _elapsed_ms(info["start_ts"], now_iso)
            active.append({
                "chain_id": chain_id,
                "from_agent": info["from_agent"] or "external",
                "agents": info["agents"],
                "status": "running",
                "elapsed_ms": elapsed,
                "elapsed_human": _format_ms(elapsed),
                "start_ts": info["start_ts"],
                "description": info["description"],
            })

    # Сортируем по времени старта (новые вверху)
    active.sort(key=lambda x: x["start_ts"], reverse=True)
    return active


def _build_chain_history(limit: int = 50) -> list:
    """
    История цепочек: все chain:end события с расходом времени.
    Возвращает: [{chain_id, from_agent, agents, status, total_ms, end_ts}]
    """
    events = _read_chain_events()
    chain_info = {}
    chain_ends = []

    for evt in events:
        kind = evt.get("kind", "")
        pl = evt.get("payload", {})
        chain_id = pl.get("chain_id")

        if kind == "chain:start" and chain_id:
            chain_info[chain_id] = {
                "from_agent": pl.get("from_agent", "external"),
                "agents": pl.get("agents", []),
                "start_ts": evt.get("ts"),
            }
        elif kind == "chain:end" and chain_id:
            start_info = chain_info.get(chain_id, {})
            total_ms = _elapsed_ms(
                start_info.get("start_ts", evt.get("ts")),
                evt.get("ts")
            )
            chain_ends.append({
                "chain_id": chain_id,
                "from_agent": start_info.get("from_agent", "external"),
                "agents": start_info.get("agents", []),
                "status": pl.get("status", "unknown"),
                "total_ms": total_ms,
                "total_human": _format_ms(total_ms),
                "end_ts": evt.get("ts"),
                "error": pl.get("error"),
            })

    # Сортируем по времени конца (новые вверху)
    chain_ends.sort(key=lambda x: x["end_ts"], reverse=True)
    return chain_ends[:limit]


def _build_agent_timeline() -> dict:
    """
    Timeline агентов: для каждого агента, что он сейчас делает (из активных цепочек).
    Возвращает: {agent_name: {"status": "running|idle", "chain_id": "...", "elapsed_ms": ...}}
    """
    active_chains = _build_active_chains()
    timeline = {}

    # Инициализируем всех известных агентов как idle
    all_agents = {
        "marina", "victoria", "alina", "dima", "tyoma", "olya", "vasya", "lera",
        "manager", "producer", "rita", "user", "n8n"
    }
    for agent in all_agents:
        timeline[agent] = {"status": "idle", "chain_id": None, "elapsed_ms": 0}

    # Заполняем информацию об активных цепочках
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for chain in active_chains:
        elapsed = _elapsed_ms(chain["start_ts"], now_iso)
        from_agent = chain["from_agent"]
        if from_agent not in timeline:
            timeline[from_agent] = {}
        timeline[from_agent].update({
            "status": "running",
            "chain_id": chain["chain_id"],
            "elapsed_ms": elapsed,
            "elapsed_human": _format_ms(elapsed),
        })

        # Все агенты в цепочке тоже рабочие
        for agent in chain["agents"]:
            if agent not in timeline:
                timeline[agent] = {}
            if timeline[agent].get("status") != "running":
                timeline[agent].update({
                    "status": "running",
                    "chain_id": chain["chain_id"],
                    "elapsed_ms": elapsed,
                    "elapsed_human": _format_ms(elapsed),
                })

    return timeline


def _build_chain_details(chain_id: str) -> dict:
    """
    Полные логи для конкретной цепочки: все события chain:step для этого chain_id.
    Возвращает: {chain_id, from_agent, agents, steps: [{agent, step_num, status, elapsed_ms, ts}], ...}
    """
    events = _read_chain_events()
    chain_info = {}
    steps = []

    for evt in events:
        kind = evt.get("kind", "")
        pl = evt.get("payload", {})
        ev_chain_id = pl.get("chain_id")

        if ev_chain_id != chain_id:
            continue

        if kind == "chain:start":
            chain_info.update({
                "from_agent": pl.get("from_agent"),
                "agents": pl.get("agents", []),
                "start_ts": evt.get("ts"),
                "description": pl.get("description", ""),
            })

        elif kind == "chain:step":
            steps.append({
                "agent": pl.get("agent"),
                "step_num": pl.get("step_num"),
                "status": pl.get("status"),
                "elapsed_ms": pl.get("elapsed_ms"),
                "elapsed_human": _format_ms(pl.get("elapsed_ms", 0)),
                "ts": evt.get("ts"),
                "input_summary": (pl.get("input_text") or "")[:200],
                "output_summary": (pl.get("output_text") or "")[:200],
            })

        elif kind == "chain:end":
            chain_info.update({
                "end_ts": evt.get("ts"),
                "status": pl.get("status"),
                "error": pl.get("error"),
            })

    # Вычисляем общее время
    start = chain_info.get("start_ts")
    end = chain_info.get("end_ts")
    total_ms = _elapsed_ms(start, end) if start and end else 0

    return {
        "chain_id": chain_id,
        "from_agent": chain_info.get("from_agent", "unknown"),
        "agents": chain_info.get("agents", []),
        "description": chain_info.get("description", ""),
        "status": chain_info.get("status", "running"),
        "error": chain_info.get("error"),
        "start_ts": start,
        "end_ts": end,
        "total_ms": total_ms,
        "total_human": _format_ms(total_ms),
        "steps": steps,
        "step_count": len(steps),
    }


def _build_performance_metrics() -> dict:
    """
    Метрики производительности: среднее время по агентам, success rate, max/min.
    Возвращает: {agent: {avg_ms, min_ms, max_ms, count, success_rate}, ...}
    """
    events = _read_chain_events()
    agent_stats = defaultdict(lambda: {
        "total_ms": 0,
        "min_ms": float("inf"),
        "max_ms": 0,
        "count": 0,
        "success": 0,
        "failed": 0,
    })

    for evt in events:
        kind = evt.get("kind", "")
        if kind != "chain:step":
            continue

        pl = evt.get("payload", {})
        agent = pl.get("agent")
        elapsed = pl.get("elapsed_ms", 0)
        status = pl.get("status", "")

        if agent:
            stats = agent_stats[agent]
            stats["total_ms"] += elapsed
            stats["min_ms"] = min(stats["min_ms"], elapsed)
            stats["max_ms"] = max(stats["max_ms"], elapsed)
            stats["count"] += 1

            if status == "done":
                stats["success"] += 1
            elif status == "failed":
                stats["failed"] += 1

    # Считаем средние и процент успехов
    metrics = {}
    for agent, stats in agent_stats.items():
        count = stats["count"]
        if count > 0:
            success_rate = (stats["success"] / (stats["success"] + stats["failed"])) * 100 if (stats["success"] + stats["failed"]) > 0 else 0
            metrics[agent] = {
                "avg_ms": stats["total_ms"] / count,
                "avg_human": _format_ms(stats["total_ms"] / count),
                "min_ms": stats["min_ms"] if stats["min_ms"] != float("inf") else 0,
                "min_human": _format_ms(stats["min_ms"]),
                "max_ms": stats["max_ms"],
                "max_human": _format_ms(stats["max_ms"]),
                "count": count,
                "success_rate": success_rate,
                "success": stats["success"],
                "failed": stats["failed"],
            }

    return metrics


# ─── API маршруты ───────────────────────────────────────────────
@chain_bp.route("/api/active", methods=["GET"])
def api_active_chains():
    """Список активных цепочек."""
    try:
        chains = _build_active_chains()
        return jsonify({"ok": True, "chains": chains, "count": len(chains)})
    except Exception as e:
        logger.exception("Error fetching active chains")
        return jsonify({"ok": False, "error": str(e)}), 500


@chain_bp.route("/api/history", methods=["GET"])
def api_chain_history():
    """История цепочек с фильтром."""
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        status_filter = request.args.get("status", "")  # фильтр по статусу (ok/failed)

        history = _build_chain_history(limit=limit)

        if status_filter:
            history = [c for c in history if c.get("status") == status_filter]

        return jsonify({"ok": True, "chains": history, "count": len(history)})
    except Exception as e:
        logger.exception("Error fetching chain history")
        return jsonify({"ok": False, "error": str(e)}), 500


@chain_bp.route("/api/timeline", methods=["GET"])
def api_agent_timeline():
    """Timeline: что делает каждый агент."""
    try:
        timeline = _build_agent_timeline()
        return jsonify({"ok": True, "agents": timeline})
    except Exception as e:
        logger.exception("Error fetching agent timeline")
        return jsonify({"ok": False, "error": str(e)}), 500


@chain_bp.route("/api/details/<chain_id>", methods=["GET"])
def api_chain_details(chain_id: str):
    """Полные логи цепочки."""
    try:
        chain_id = chain_id.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{1,100}$", chain_id):
            return jsonify({"ok": False, "error": "Invalid chain_id"}), 400

        details = _build_chain_details(chain_id)
        if not details.get("start_ts"):
            return jsonify({"ok": False, "error": "Chain not found"}), 404

        return jsonify({"ok": True, "chain": details})
    except Exception as e:
        logger.exception("Error fetching chain details")
        return jsonify({"ok": False, "error": str(e)}), 500


@chain_bp.route("/api/metrics", methods=["GET"])
def api_performance_metrics():
    """Метрики производительности по агентам."""
    try:
        metrics = _build_performance_metrics()

        # Общие метрики
        all_ms = [m["avg_ms"] for m in metrics.values()]
        all_success = sum(m["success"] for m in metrics.values())
        all_failed = sum(m["failed"] for m in metrics.values())
        overall_success_rate = (all_success / (all_success + all_failed) * 100) if (all_success + all_failed) > 0 else 0

        return jsonify({
            "ok": True,
            "agents": metrics,
            "overall": {
                "avg_ms": sum(all_ms) / len(all_ms) if all_ms else 0,
                "total_tasks": all_success + all_failed,
                "success_rate": overall_success_rate,
                "success": all_success,
                "failed": all_failed,
            }
        })
    except Exception as e:
        logger.exception("Error fetching performance metrics")
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── HTML дашборд ───────────────────────────────────────────────
_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MILA OFFICE — Мониторинг цепочек</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #f5f0ea 0%, #ebe6e0 100%);
            color: #2d1f1a;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-left: 4px solid #C4614A;
        }
        h1 {
            font-size: 28px;
            margin-bottom: 8px;
        }
        .subtitle {
            color: #7A5E54;
            font-size: 14px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .card h2 {
            font-size: 18px;
            margin-bottom: 16px;
            color: #1E140F;
            border-bottom: 2px solid #f0e8e0;
            padding-bottom: 12px;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f5f0ea;
        }
        .stat:last-child {
            border-bottom: none;
        }
        .stat-label {
            color: #7A5E54;
            font-size: 13px;
        }
        .stat-value {
            font-size: 20px;
            font-weight: bold;
            color: #C4614A;
        }
        .chain-item {
            background: #faf8f5;
            border-left: 3px solid #C4614A;
            padding: 12px;
            margin-bottom: 12px;
            border-radius: 6px;
        }
        .chain-id {
            font-family: "Monaco", "Courier New", monospace;
            font-size: 12px;
            color: #999;
            margin-bottom: 4px;
        }
        .chain-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .status-running {
            background: #e8f5e9;
            color: #2e7d32;
        }
        .status-ok {
            background: #c8e6c9;
            color: #1b5e20;
        }
        .status-failed {
            background: #ffcdd2;
            color: #c62828;
        }
        .agent-tag {
            display: inline-block;
            background: #e8dfd5;
            color: #5D4E47;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            margin-right: 6px;
            margin-bottom: 6px;
        }
        .elapsed {
            color: #7A5E54;
            font-size: 12px;
        }
        .timeline-agent {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: #faf8f5;
            border-radius: 6px;
            margin-bottom: 8px;
        }
        .agent-name {
            font-weight: bold;
            color: #2d1f1a;
            min-width: 100px;
        }
        .agent-status-idle {
            color: #aaa;
            font-size: 12px;
        }
        .agent-status-running {
            color: #2e7d32;
            font-size: 12px;
        }
        .refresh-btn {
            background: #C4614A;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            float: right;
        }
        .refresh-btn:hover {
            background: #A0483A;
        }
        .loading {
            color: #999;
            text-align: center;
            padding: 20px;
        }
        .metric-bar {
            background: linear-gradient(90deg, #C4614A 0%, #e8a89a 100%);
            height: 8px;
            border-radius: 4px;
            margin-top: 4px;
        }
        .success-rate {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #7A5E54;
            margin-top: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔗 Мониторинг цепочек агентов</h1>
            <p class="subtitle">Отслеживание выполнения и производительности</p>
            <button class="refresh-btn" onclick="location.reload()">Обновить</button>
        </header>

        <div class="grid">
            <!-- Активные цепочки -->
            <div class="card">
                <h2>Активные цепочки</h2>
                <div id="active-chains" class="loading">Загрузка…</div>
            </div>

            <!-- Timeline агентов -->
            <div class="card">
                <h2>Timeline агентов</h2>
                <div id="timeline" class="loading">Загрузка…</div>
            </div>

            <!-- Метрики -->
            <div class="card">
                <h2>Производительность</h2>
                <div id="metrics" class="loading">Загрузка…</div>
            </div>
        </div>

        <!-- История цепочек -->
        <div class="card">
            <h2>История цепочек (последние 20)</h2>
            <div id="history" class="loading">Загрузка…</div>
        </div>
    </div>

    <script>
        async function loadDashboard() {
            try {
                const [active, timeline, metrics, history] = await Promise.all([
                    fetch("/chains/api/active").then(r => r.json()),
                    fetch("/chains/api/timeline").then(r => r.json()),
                    fetch("/chains/api/metrics").then(r => r.json()),
                    fetch("/chains/api/history?limit=20").then(r => r.json()),
                ]);

                renderActive(active);
                renderTimeline(timeline);
                renderMetrics(metrics);
                renderHistory(history);
            } catch (e) {
                console.error("Error loading dashboard", e);
                document.getElementById("active-chains").innerHTML = "⚠️ Ошибка загрузки данных";
            }
        }

        function renderActive(data) {
            const el = document.getElementById("active-chains");
            if (!data.ok || data.count === 0) {
                el.innerHTML = "<p style='color: #999;'>Нет активных цепочек</p>";
                return;
            }
            let html = `<p style='color: #7A5E54; font-size: 13px; margin-bottom: 12px;'>${data.count} цепочек выполняется</p>`;
            for (const chain of data.chains) {
                html += `
                    <div class="chain-item">
                        <div class="chain-id">${chain.chain_id}</div>
                        <div>
                            <span class="chain-status status-running">Выполняется</span>
                            <span class="elapsed">${chain.elapsed_human}</span>
                        </div>
                        <div style='margin-top: 8px;'>
                            От: <strong>${chain.from_agent}</strong>
                        </div>
                        ${chain.agents.length > 0 ? `
                            <div style='margin-top: 8px;'>
                                Этапы:
                                ${chain.agents.map(a => `<span class="agent-tag">${a}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;
            }
            el.innerHTML = html;
        }

        function renderTimeline(data) {
            const el = document.getElementById("timeline");
            if (!data.ok) {
                el.innerHTML = "⚠️ Ошибка загрузки timeline";
                return;
            }
            let html = '';
            const agents = Object.entries(data.agents);
            for (const [agent, info] of agents) {
                const running = info.status === 'running';
                const statusClass = running ? 'agent-status-running' : 'agent-status-idle';
                const statusText = running ? `▶ Выполняется (${info.elapsed_human})` : '⚪ Ожидание';
                html += `
                    <div class="timeline-agent">
                        <div class="agent-name">${agent}</div>
                        <div class="${statusClass}">${statusText}</div>
                    </div>
                `;
            }
            el.innerHTML = html;
        }

        function renderMetrics(data) {
            const el = document.getElementById("metrics");
            if (!data.ok) {
                el.innerHTML = "⚠️ Ошибка загрузки метрик";
                return;
            }
            const o = data.overall;
            let html = `
                <div class="stat">
                    <span class="stat-label">Средн. время</span>
                    <span class="stat-value">${Math.round(o.avg_ms)}ms</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Задач выполнено</span>
                    <span class="stat-value">${o.total_tasks}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Успешных</span>
                    <span class="stat-value">${o.success}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Ошибок</span>
                    <span class="stat-value">${o.failed}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Успешность</span>
                    <span class="stat-value">${o.success_rate.toFixed(1)}%</span>
                </div>
            `;
            el.innerHTML = html;
        }

        function renderHistory(data) {
            const el = document.getElementById("history");
            if (!data.ok || data.count === 0) {
                el.innerHTML = "<p style='color: #999;'>История цепочек пуста</p>";
                return;
            }
            let html = '';
            for (const chain of data.chains) {
                const statusClass = chain.status === 'ok' ? 'status-ok' : 'status-failed';
                html += `
                    <div class="chain-item">
                        <div class="chain-id">${chain.chain_id}</div>
                        <div>
                            <span class="chain-status ${statusClass}">${chain.status === 'ok' ? 'Завершено' : 'Ошибка'}</span>
                            <span class="elapsed">${chain.total_human}</span>
                        </div>
                        ${chain.agents.length > 0 ? `
                            <div style='margin-top: 8px;'>
                                ${chain.agents.map(a => `<span class="agent-tag">${a}</span>`).join('')}
                            </div>
                        ` : ''}
                        ${chain.error ? `<div style='color: #c62828; font-size: 12px; margin-top: 8px;'>⚠️ ${chain.error}</div>` : ''}
                    </div>
                `;
            }
            el.innerHTML = html;
        }

        // Загружаем при открытии и обновляем каждые 5 сек
        loadDashboard();
        setInterval(loadDashboard, 5000);
    </script>
</body>
</html>
"""


@chain_bp.route("", methods=["GET"])
def dashboard_html():
    """Веб-интерфейс дашборда."""
    return render_template_string(_DASHBOARD_HTML)


# ─── Вспомогательные функции для логирования из pipeline.py ───────
def log_chain_start(chain_id: str, from_agent: str, agents: list, description: str = ""):
    """Начало выполнения цепочки. Вызывать из pipeline.py в начале."""
    memory.log_event("chain:start", {
        "chain_id": chain_id,
        "from_agent": from_agent,
        "agents": agents,
        "description": description,
    })


def log_chain_step(chain_id: str, agent: str, step_num: int, status: str, elapsed_ms: float,
                   input_text: str = "", output_text: str = ""):
    """Завершение шага в цепочке. Вызывать после каждого агента."""
    memory.log_event("chain:step", {
        "chain_id": chain_id,
        "agent": agent,
        "step_num": step_num,
        "status": status,  # "running" или "done" или "failed"
        "elapsed_ms": elapsed_ms,
        "input_text": input_text[:1000] if input_text else "",
        "output_text": output_text[:1000] if output_text else "",
    })


def log_chain_end(chain_id: str, status: str, total_ms: float, error: str = ""):
    """Конец цепочки. Вызывать после завершения всех агентов."""
    memory.log_event("chain:end", {
        "chain_id": chain_id,
        "status": status,  # "ok" или "failed"
        "total_ms": total_ms,
        "error": error,
    })
