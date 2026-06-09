# -*- coding: utf-8 -*-
"""Flask маршруты для MILA OFFICE веб-приложения."""
import logging
from flask import request, jsonify, abort

import job_queue
import security
import message_handler

logger = logging.getLogger("mila.routes")

def register_routes(app):
    """Зарегистрировать все маршруты Flask приложения."""

    @app.get("/api/health")
    def health():
        """Проверка что сервер жив."""
        return jsonify({"status": "ok", "message": "MILA OFFICE is running"})

    @app.get("/api/meta")
    def meta():
        """Метаинформация о приложении: список агентов и их команд."""
        from agent_manager import list_agents, get_quick_commands
        try:
            agents = []
            for agent_key in list_agents():
                commands = get_quick_commands(agent_key)
                agents.append({
                    "key": agent_key,
                    "commands": list(commands.keys()) if commands else []
                })
            return jsonify({
                "version": "2.0",
                "agents": agents,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error in /api/meta: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.post("/api/chat")
    def chat():
        """Отправить сообщение агенту (создать задание).

        Может содержать контекст:
        - from_agent: от какого агента (если из цепочки)
        - to_agent: кому адресовано (если переделегировано)
        - chain_id: ID цепочки обработки
        """
        try:
            data = request.get_json(force=True) or {}
            agent_key = data.get("agent", "").strip()
            msg_text = data.get("message", "").strip()
            from_agent = data.get("from_agent", "").strip() or "user"  # Дефолт: от пользователя
            to_agent = data.get("to_agent", "").strip() or None
            chain_id = data.get("chain_id", "").strip() or None

            if not security.validate_agent_key(agent_key):
                abort(400)
            if not msg_text:
                abort(400)

            # Генерируем ID задания
            import secrets
            job_id = secrets.token_hex(8)

            # Создаём задание с контекстом
            job = job_queue.create_job(job_id, "session_id", agent_key)

            # Сохраняем контекст запроса
            job["from_agent"] = from_agent  # От кого пришел
            job["to_agent"] = to_agent or None  # Кому возвращать
            job["chain_id"] = chain_id  # ID цепочки

            logger.info(f"Created job {job_id} for agent {agent_key} from {from_agent}")
            return jsonify({
                "job": job_id,
                "ok": True,
                "agent": agent_key,
                "from_agent": from_agent,
                "chain_id": chain_id,
            })

        except Exception as e:
            logger.error(f"Error in /api/chat: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @app.get("/api/result")
    def result():
        """Получить результат задания с контекстом цепочки.

        Возвращает:
        - reply: ответ агента
        - verdict: статус (ready_next, done, etc)
        - next_agent: кому передать (если нужно)
        - from_agent: от кого был запрос
        - to_agent: кому адресовано (для деделегирования)
        - chain_id: ID цепочки
        """
        try:
            job_id = request.args.get("job", "").strip()

            if not security.validate_job_id(job_id):
                abort(404)

            job = job_queue.get_job(job_id)
            if job is None:
                return jsonify({"error": "Job not found"}), 404

            if job.get("status") == "pending":
                return jsonify({"status": "pending"})

            # Обработка ответа через message_handler
            if job.get("reply") and job.get("agent_key"):
                from_agent = job.get("from_agent", "user")
                chain_id = job.get("chain_id")
                response = message_handler.process_agent_response(
                    job["reply"],
                    job["agent_key"],
                    from_agent=from_agent,
                    chain_id=chain_id
                )
                job["verdict"] = response["verdict"]
                if response["should_switch"] and response["next_agent"]:
                    job["next_agent"] = response["next_agent"]

            # Результат забран — удаляем из памяти
            result_data = {k: v for k, v in job.items() if k != "status"}

            # Добавляем контекст цепочки для следующего агента
            if job.get("next_agent"):
                result_data["chain_context"] = {
                    "current_agent": job.get("agent_key"),
                    "from_agent": job.get("from_agent", "user"),
                    "original_to_agent": job.get("to_agent"),
                    "chain_id": job.get("chain_id"),
                }

            job_queue.remove_job(job_id)

            logger.info(
                f"Result for job {job_id}: "
                f"agent={job.get('agent_key')}, "
                f"verdict={result_data.get('verdict')}, "
                f"next={result_data.get('next_agent')}"
            )

            return jsonify(result_data)

        except Exception as e:
            logger.error(f"Error in /api/result: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @app.get("/")
    def index():
        """Главная страница (веб-интерфейс)."""
        try:
            from ui_helpers import html_header, html_footer, render_agent_button
            from agent_manager import list_agents, get_agent_metadata

            agents_html = ""
            for agent_key in list_agents():
                meta = get_agent_metadata(agent_key)
                name = meta.get("name", agent_key)
                emoji = meta.get("emoji", "🤖")
                agents_html += render_agent_button(agent_key, name, emoji)

            html = html_header() + f'''
        <div class="agents">
            {agents_html}
        </div>
        <div class="chat">
            <div class="messages" id="messages"></div>
            <div class="input-area">
                <div class="input-group">
                    <textarea id="input" placeholder="Напишите сообщение..."></textarea>
                    <button onclick="sendMessage()">Отправить</button>
                </div>
            </div>
        </div>
        <script>
            const AGENTS = {{"marina": {{}}, "victoria": {{}}, "alina": {{}}}};
            let current_agent = "marina";

            function switchAgent(agent) {{
                current_agent = agent;
                console.log("Switched to: " + agent);
            }}

            async function sendMessage() {{
                const text = document.getElementById("input").value.trim();
                if (!text) return;
                document.getElementById("input").value = "";

                const r = await fetch("/api/chat", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{agent: current_agent, message: text}})
                }});
                const j = await r.json();
                if (j.job) {{
                    console.log("Job: " + j.job);
                    setTimeout(() => checkResult(j.job), 1000);
                }}
            }}

            async function checkResult(job_id) {{
                const r = await fetch("/api/result?job=" + job_id);
                const j = await r.json();
                if (j.status === "pending") {{
                    setTimeout(() => checkResult(job_id), 2000);
                }} else if (j.reply) {{
                    console.log("Reply: " + j.reply);
                    if (j.next_agent && j.next_agent !== current_agent) {{
                        console.log("Auto-switching to: " + j.next_agent);
                        switchAgent(j.next_agent);
                    }}
                }}
            }}

            document.getElementById("input").addEventListener("keypress", (e) => {{
                if (e.key === "Enter" && !e.shiftKey) {{
                    e.preventDefault();
                    sendMessage();
                }}
            }});
        </script>
        ''' + html_footer()

            return html

        except Exception as e:
            logger.error(f"Error in index: {e}", exc_info=True)
            return f"<h1>Error: {e}</h1>", 500

    logger.info("All routes registered")
