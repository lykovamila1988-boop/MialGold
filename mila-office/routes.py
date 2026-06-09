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
        """Отправить сообщение агенту (создать задание)."""
        try:
            data = request.get_json(force=True) or {}
            agent_key = data.get("agent", "").strip()
            msg_text = data.get("message", "").strip()

            if not security.validate_agent_key(agent_key):
                abort(400)
            if not msg_text:
                abort(400)

            # Генерируем ID задания
            import secrets
            job_id = secrets.token_hex(8)

            # Создаём задание
            job_queue.create_job(job_id, "session_id", agent_key)

            logger.info(f"Created job {job_id} for agent {agent_key}")
            return jsonify({"job": job_id, "ok": True})

        except Exception as e:
            logger.error(f"Error in /api/chat: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @app.get("/api/result")
    def result():
        """Получить результат задания."""
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
                response = message_handler.process_agent_response(
                    job["reply"],
                    job["agent_key"]
                )
                job["verdict"] = response["verdict"]
                if response["should_switch"] and response["next_agent"]:
                    job["next_agent"] = response["next_agent"]

            # Результат забран — удаляем из памяти
            result_data = {k: v for k, v in job.items() if k != "status"}
            job_queue.remove_job(job_id)

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
