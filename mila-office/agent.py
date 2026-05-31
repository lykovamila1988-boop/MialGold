r"""
MILA Agent — Локальный маркетинг-агент для @liudmyla.lykova
Работает с папкой E:\MILA GOLD и Instagram API

Запуск: python agent.py
"""

import json
from datetime import datetime
import anthropic
from rich.markdown import Markdown
from rich.prompt import Prompt

# Общая инфраструктура (env, пути, ключи, safe-path, allowlist, граф-клиент) — в base.
import base

# ─── SETUP ───────────────────────────────────────────────
# Конфиг (.env, пути, ключи, Instagram-резолв) уже загружен в base при импорте —
# не дублируем. Берём готовые значения оттуда.
console = base.console
MILA_FOLDER = base.MILA_FOLDER
ANTHROPIC_API_KEY = base.ANTHROPIC_KEY      # для баннера в main()
INSTAGRAM_TOKEN = base.INSTAGRAM_TOKEN      # для баннера в main()

# Единый источник аутентификации (ключ или ANTHROPIC_AUTH_TOKEN / gateway) — в base.
client = base.get_client()

# ─── SYSTEM PROMPT ───────────────────────────────────────
SYSTEM_PROMPT = """Ты — Марина, маркетолог и стратег личного бренда Людмилы Лыковой.

БРЕНД:
- @liudmyla.lykova, психолог, Канада
- Ниша: болезненные отношения, тревожная привязанность
- Методология «Точки выбора»: Ловушка знакомой боли → Синдром заслуживания → Точка выбора → Интеграция идентичности
- Продукты: практикум $37 CAD, консультации $120, пакеты $420/$750

ТВОЙ СТИЛЬ:
- Конкретные, практические действия
- Всегда с примерами — хуки, тексты, заголовки
- Думаешь цифрами: охваты, конверсии, доход
- Говоришь прямо если что-то не будет работать

ИНСТРУМЕНТЫ:
У тебя есть доступ к файлам в папке MILA GOLD и Instagram API.
Используй инструменты проактивно — не жди когда попросят.
При запросе контента — сразу пиши финальный текст, не шаблоны.
"""

# ─── TOOLS DEFINITION ────────────────────────────────────
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the MILA GOLD folder. Use to read content plans, analytics, post drafts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from MILA GOLD folder, e.g. 'content/posts/post_mon.txt'"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the MILA GOLD folder. Use to save posts, scripts, reports.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from MILA GOLD folder"},
                "content": {"type": "string", "description": "Content to write"},
                "mode": {"type": "string", "enum": ["write", "append"], "description": "Write mode", "default": "write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and folders in a directory within MILA GOLD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path, empty string for root", "default": ""}
            }
        }
    },
    {
        "name": "instagram_get_analytics",
        "description": "Get Instagram account analytics: follower count, reach, impressions, top posts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["day", "week", "month"], "default": "week"}
            }
        }
    },
    {
        "name": "instagram_get_posts",
        "description": "Get recent Instagram posts with performance metrics (likes, comments, reach, saves).",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "description": "Number of posts to retrieve"}
            }
        }
    },
    {
        "name": "instagram_get_comments",
        "description": "Get recent comments from Instagram posts. Use to find 'ХОЧУ' comments and questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "posts_limit": {"type": "integer", "default": 5, "description": "How many recent posts to check"}
            }
        }
    },
    {
        "name": "instagram_publish_post",
        "description": "Publish a photo post to Instagram. Requires a public image URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Public URL of the image"},
                "caption": {"type": "string", "description": "Post caption text"}
            },
            "required": ["image_url", "caption"]
        }
    },
    {
        "name": "instagram_get_dms",
        "description": "Get Instagram Direct Messages. Requires Instagram Messaging API permissions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the MILA GOLD folder. Use for Python scripts in tools/ folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run, e.g. 'python tools/get_analytics.py posts'"}
            },
            "required": ["command"]
        }
    }
]

# ─── TOOL IMPLEMENTATIONS ────────────────────────────────

def tool_read_file(path: str) -> str:
    try:
        full_path = base._safe_path(path)
    except ValueError as e:
        return f"Ошибка: {e}"
    try:
        return full_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Файл не найден: {full_path}"
    except Exception as e:
        return f"Ошибка чтения: {e}"

def tool_write_file(path: str, content: str, mode: str = "write") -> str:
    try:
        full_path = base._safe_path(path)
    except ValueError as e:
        return f"Ошибка: {e}"
    full_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        flag = "w" if mode == "write" else "a"
        with open(full_path, flag, encoding="utf-8") as f:
            f.write(content)
        return f"✓ Сохранено: {full_path} ({len(content)} символов)"
    except Exception as e:
        return f"Ошибка записи: {e}"

def tool_list_files(path: str = "") -> str:
    try:
        full_path = base._safe_path(path)
    except ValueError as e:
        return f"Ошибка: {e}"
    try:
        items = []
        for item in sorted(full_path.iterdir()):
            icon = "📁" if item.is_dir() else "📄"
            size = f" ({item.stat().st_size:,} bytes)" if item.is_file() else ""
            items.append(f"{icon} {item.name}{size}")
        return "\n".join(items) if items else "Папка пустая"
    except FileNotFoundError:
        return f"Папка не найдена: {full_path}"
    except Exception as e:
        return f"Ошибка: {e}"

def _ig_cfg():
    """cfg для общего Graph-клиента или None, если Instagram не настроен."""
    if base.graph_api is None:
        return None
    try:
        return base.graph_api.load_config()
    except base.graph_api.ConfigError:
        return None

_IG_NOT_SET = "⚠️ Instagram API не настроен. Проверь tools/.env: IG_ACCESS_TOKEN и IG_USER_ID"

def tool_instagram_get_analytics(period: str = "week") -> str:
    cfg = _ig_cfg()
    if not cfg:
        return _IG_NOT_SET
    try:
        # В Instagram Login узел профиля отдаёт счётчики напрямую (старый
        # набор insights-метрик API отклоняет).
        if cfg["flow"] == "instagram_login":
            data = base.graph_api.graph_get(cfg, cfg["node"], params={
                "fields": "username,followers_count,media_count,biography"})
            return json.dumps(data, ensure_ascii=False, indent=2)
        data = base.graph_api.graph_get(cfg, f"{cfg['node']}/insights", params={
            "metric": "impressions,reach,profile_views,follower_count", "period": period})
        result = {}
        for item in data.get("data", []):
            result[item["name"]] = item["values"][-1]["value"] if item.get("values") else 0
        return json.dumps(result, ensure_ascii=False, indent=2)
    except base.graph_api.GraphError as e:
        return f"API ошибка: {e}"

def tool_instagram_get_posts(limit: int = 10) -> str:
    cfg = _ig_cfg()
    if not cfg:
        return _IG_NOT_SET
    try:
        data = base.graph_api.graph_get(cfg, f"{cfg['node']}/media", params={
            "fields": "id,caption,media_type,timestamp,like_count,comments_count,media_url",
            "limit": limit})
        posts = []
        for post in data.get("data", []):
            posts.append({
                "id": post.get("id"),
                "type": post.get("media_type"),
                "date": post.get("timestamp", "")[:10],
                "likes": post.get("like_count", 0),
                "comments": post.get("comments_count", 0),
                "caption_preview": (post.get("caption") or "")[:80] + "..."
            })
        return json.dumps(posts, ensure_ascii=False, indent=2)
    except base.graph_api.GraphError as e:
        return f"API ошибка: {e}"

def tool_instagram_get_comments(posts_limit: int = 5) -> str:
    cfg = _ig_cfg()
    if not cfg:
        return _IG_NOT_SET
    try:
        media = base.graph_api.graph_get(cfg, f"{cfg['node']}/media", params={
            "fields": "id,timestamp,caption,comments_count", "limit": posts_limit})
        all_comments = []
        for post in media.get("data", []):
            cr = base.graph_api.graph_get(cfg, f"{post['id']}/comments", params={
                "fields": "id,text,username,timestamp"})
            for c in cr.get("data", []):
                all_comments.append({
                    "username": c.get("username"),
                    "text": c.get("text"),
                    "time": c.get("timestamp", "")[:10],
                    "post_caption": (post.get("caption") or "")[:50]
                })
        # comments_count > 0, но получили 0 — это не «особенность Reels» (пустыми
        # приходят и FEED-посты), а нехватка доступа токена к чтению комментариев.
        if not all_comments:
            expected = sum(p.get("comments_count") or 0 for p in media.get("data", []))
            if expected:
                return (f"API вернул 0 комментариев, хотя у постов их {expected} "
                        f"(comments_count). Это не ограничение Reels — пустыми приходят и "
                        f"обычные посты. Токену не хватает разрешения на чтение комментариев: "
                        f"нужен scope instagram_business_manage_comments + advanced access "
                        f"(App Review). Перевыпусти токен с этим разрешением.")
        return json.dumps(all_comments, ensure_ascii=False, indent=2)
    except base.graph_api.GraphError as e:
        return f"API ошибка: {e}"

def tool_instagram_publish_post(image_url: str, caption: str) -> str:
    cfg = _ig_cfg()
    if not cfg:
        return _IG_NOT_SET
    try:
        # Двухфазная публикация фото: контейнер → media_publish. Фото-контейнер
        # готов сразу (как в tools/post_content.py photo) — слепой sleep не нужен.
        container = base.graph_api.graph_post(cfg, f"{cfg['node']}/media", {
            "image_url": image_url, "caption": caption})
        container_id = container["id"]
        result = base.graph_api.graph_post(cfg, f"{cfg['node']}/media_publish", {
            "creation_id": container_id})
        # Лог публикаций
        log_path = MILA_FOLDER / "logs" / "published.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | POST | {result.get('id')} | {caption[:50]}\n")
        return f"✓ Опубликовано! Post ID: {result.get('id')}"
    except base.graph_api.GraphError as e:
        return f"Ошибка публикации: {e}"

def tool_instagram_get_dms(limit: int = 10) -> str:
    cfg = _ig_cfg()
    if not cfg:
        return _IG_NOT_SET
    try:
        data = base.graph_api.graph_get(cfg, f"{cfg['node']}/conversations", params={
            "fields": "id,participants,updated_time,messages{message,from,created_time}",
            "platform": "instagram", "limit": limit})
        return json.dumps(data.get("data", []), ensure_ascii=False, indent=2)
    except base.graph_api.GraphError as e:
        return f"API ошибка (нужен Instagram Professional API): {e}"

def tool_run_command(command: str) -> str:
    # Делегируем в base.run_command: только allowlist (python tools/<script>.py …),
    # без shell=True. Раньше здесь выполнялась произвольная shell-строка.
    return base.run_command(command)

# ─── TOOL DISPATCHER ─────────────────────────────────────

def run_tool(name: str, inputs: dict) -> str:
    handlers = {
        "read_file":                  lambda: tool_read_file(inputs["path"]),
        "write_file":                 lambda: tool_write_file(inputs["path"], inputs["content"], inputs.get("mode","write")),
        "list_files":                 lambda: tool_list_files(inputs.get("path","")),
        "instagram_get_analytics":    lambda: tool_instagram_get_analytics(inputs.get("period","week")),
        "instagram_get_posts":        lambda: tool_instagram_get_posts(inputs.get("limit",10)),
        "instagram_get_comments":     lambda: tool_instagram_get_comments(inputs.get("posts_limit",5)),
        "instagram_publish_post":     lambda: tool_instagram_publish_post(inputs["image_url"], inputs["caption"]),
        "instagram_get_dms":          lambda: tool_instagram_get_dms(inputs.get("limit",10)),
        "run_command":                lambda: tool_run_command(inputs["command"]),
    }
    handler = handlers.get(name)
    if not handler:
        return f"Неизвестный инструмент: {name}"
    return handler()

# ─── AGENT LOOP ──────────────────────────────────────────

def run_agent(user_message: str, history: list):
    """Делегирует в общий base.run_agent — единый tool-use цикл для всех агентов
    (модель/лимит токенов берутся из base, печать tool-вызовов — тоже там)."""
    return base.run_agent(client, SYSTEM_PROMPT, TOOLS, run_tool, user_message, history)

# ─── CLI INTERFACE ───────────────────────────────────────

WELCOME = """
╔══════════════════════════════════════════════════╗
║         MILA AGENT  ·  @liudmyla.lykova          ║
║         Маркетолог Марина  —  локальный режим    ║
╚══════════════════════════════════════════════════╝
"""

QUICK_COMMANDS = {
    "/аналитика":   "Проверь аналитику Instagram за эту неделю и скажи что работает",
    "/комменты":    "Прочитай последние комментарии в Instagram и напиши черновики ответов на каждый",
    "/контент":     "Создай 5 постов для Instagram на эту неделю и сохрани их в папку content/posts/",
    "/reels":       "Придумай 3 идеи для Reels которые вирусятся прямо сейчас в нише психологии отношений",
    "/файлы":       "Покажи что сейчас есть в папке MILA GOLD",
    "/dm":          "Прочитай Direct Messages и подготовь ответы",
    "/помощь":      "Покажи список всех команд",
    "/выход":       "Завершить работу",
}

def main():
    console.print(WELCOME, style="bold")
    console.print(f"📁 Рабочая папка: [bold]{MILA_FOLDER}[/bold]")
    console.print(f"🔑 API: {'✓ настроен' if ANTHROPIC_API_KEY else '✗ нет ANTHROPIC_API_KEY в .env'}")
    console.print(f"📱 Instagram: {'✓ подключён' if INSTAGRAM_TOKEN else '⚠ нет токена'}")
    console.print()
    console.print("[dim]Быстрые команды: /аналитика · /комменты · /контент · /reels · /файлы · /помощь[/dim]")
    console.print("[dim]Или просто напиши что нужно на русском языке[/dim]")
    console.print()

    history = []

    while True:
        try:
            user_input = Prompt.ask("\n[bold terra]Ты[/bold terra]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]До свидания![/dim]")
            break

        if not user_input:
            continue

        if user_input == "/выход":
            console.print("[dim]До свидания![/dim]")
            break

        if user_input == "/помощь":
            for cmd, desc in QUICK_COMMANDS.items():
                console.print(f"  [bold]{cmd}[/bold] — {desc}")
            continue

        # Expand quick commands
        message = QUICK_COMMANDS.get(user_input, user_input)

        console.print("\n[bold]Марина:[/bold]", end=" ")
        try:
            reply, history = run_agent(message, history)
            console.print(Markdown(reply))
        except anthropic.APIError as e:
            console.print(f"[red]API ошибка: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Ошибка: {e}[/red]")

if __name__ == "__main__":
    main()
