# -*- coding: utf-8 -*-
"""Генерация HTML, CSS, JS для пользовательского интерфейса."""
import logging

logger = logging.getLogger("mila.ui_helpers")

def html_header(title: str = "MILA Office") -> str:
    """Генерировать HTML header с CSS."""
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f5f5; color: #333; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                   margin-bottom: 20px; }}
        .agents {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }}
        .agent-btn {{ padding: 10px 16px; border: 2px solid #ddd; background: white; cursor: pointer;
                      border-radius: 6px; font-weight: 500; transition: all 0.2s; }}
        .agent-btn:hover {{ border-color: #999; }}
        .agent-btn.active {{ border-color: #4CAF50; background: #f1f8f4; }}
        .chat {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                 min-height: 400px; display: flex; flex-direction: column; }}
        .messages {{ flex: 1; overflow-y: auto; padding: 20px; }}
        .message {{ margin-bottom: 15px; display: flex; gap: 12px; }}
        .message.user {{ flex-direction: row-reverse; }}
        .message.assistant .avatar {{ background: #e8f5e9; }}
        .avatar {{ width: 40px; height: 40px; border-radius: 50%; display: flex;
                   align-items: center; justify-content: center; font-weight: bold;
                   font-size: 20px; flex-shrink: 0; }}
        .bubble {{ max-width: 70%; padding: 12px 16px; border-radius: 12px;
                   word-wrap: break-word; }}
        .message.assistant .bubble {{ background: #f0f0f0; }}
        .message.user .bubble {{ background: #4CAF50; color: white; }}
        .input-area {{ padding: 20px; border-top: 1px solid #eee; }}
        .input-group {{ display: flex; gap: 10px; }}
        textarea {{ flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 6px;
                    font-family: inherit; resize: vertical; min-height: 60px; }}
        button {{ padding: 12px 24px; background: #4CAF50; color: white; border: none;
                  border-radius: 6px; cursor: pointer; font-weight: 500; }}
        button:hover {{ background: #45a049; }}
        button:disabled {{ background: #ccc; cursor: not-allowed; }}
        .typing {{ color: #999; font-style: italic; padding: 10px 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏢 MILA OFFICE</h1>
            <p>Агенты для автоматизации контента</p>
        </div>
'''

def html_footer() -> str:
    """Генерировать HTML footer."""
    return '''
    </div>
</body>
</html>
'''

def render_agent_button(agent_key: str, agent_name: str, emoji: str, is_active: bool = False) -> str:
    """Рендерить кнопку агента."""
    active_class = "active" if is_active else ""
    return f'<button class="agent-btn {active_class}" onclick="switchAgent(\'{agent_key}\')">{emoji} {agent_name}</button>'

def render_message(role: str, content: str, emoji: str = "", bg_color: str = "") -> str:
    """Рендерить одно сообщение."""
    role_class = "user" if role == "user" else "assistant"
    return f'''
    <div class="message {role_class}">
        <div class="avatar" style="background: {bg_color}">{emoji}</div>
        <div class="bubble">{content}</div>
    </div>
    '''

def render_typing_indicator(agent_name: str) -> str:
    """Рендерить индикатор "печатает"."""
    return f'<div class="typing">{agent_name} печатает…</div>'

def render_error_message(error: str) -> str:
    """Рендерить сообщение об ошибке."""
    return f'<div style="padding: 20px; color: #d32f2f; background: #ffebee; border-radius: 6px;">⚠️ Ошибка: {error}</div>'

def render_success_message(message: str) -> str:
    """Рендерить сообщение об успехе."""
    return f'<div style="padding: 20px; color: #388e3c; background: #e8f5e9; border-radius: 6px;">✅ {message}</div>'

def get_agent_color(agent_key: str) -> str:
    """Получить цвет для агента."""
    colors = {
        "marina": "#e8d4f8",
        "victoria": "#d4f8d4",
        "alina": "#d4f8f8",
        "dima": "#f8f8d4",
        "tyoma": "#d4e8f8",
        "olya": "#f8d4f8",
        "vasya": "#f8d4c8",
        "lera": "#f8d4d4",
        "rita": "#d4f8c8",
        "manager": "#e8e8e8",
        "producer": "#f8e8d4",
    }
    return colors.get(agent_key, "#f0f0f0")

def get_agent_emoji(agent_key: str) -> str:
    """Получить emoji для агента."""
    emojis = {
        "marina": "💼",
        "victoria": "✍️",
        "alina": "📋",
        "dima": "💰",
        "tyoma": "💬",
        "olya": "🔍",
        "vasya": "📅",
        "lera": "🎯",
        "rita": "🎨",
        "manager": "👔",
        "producer": "🎬",
    }
    return emojis.get(agent_key, "🤖")

def escape_html(text: str) -> str:
    """Экранировать HTML спецсимволы."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))
