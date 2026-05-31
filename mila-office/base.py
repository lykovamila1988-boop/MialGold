"""
base.py — Общие утилиты для всех агентов MILA Office
"""
import sys
# Принудительно UTF-8 для консоли Windows — до создания Console/любого вывода.
# Агенты запускаются и напрямую (python victoria.py), без обёртки office.py,
# поэтому фиксим кодировку здесь, иначе русский текст и ✓/эмодзи падают с
# UnicodeEncodeError на cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

import os, json, subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import anthropic
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

# ─── CONFIG ──────────────────────────────────────────────
MILA_FOLDER = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
env_file = MILA_FOLDER / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()
# tools/.env содержит рабочий Instagram-токен (IG_*). Подхватываем его тоже.
tools_env = MILA_FOLDER / "tools" / ".env"
if tools_env.exists():
    load_dotenv(tools_env)

# Имена ключей в .env исторически расходятся (tools/.env использует ANTHROPIC_KEY /
# TELEGRAM_API, шаблоны — ANTHROPIC_API_KEY / TELEGRAM_BOT_TOKEN). Принимаем оба, чтобы
# существующий .env работал без правок. Канонические имена — первые в каждой цепочке.
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_KEY")
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API")
GUMROAD_TOKEN   = os.getenv("GUMROAD_ACCESS_TOKEN") or os.getenv("GUMROAD_TOKEN")

# Аутентификация Claude. У Messages API нет публичного OAuth-флоу — это либо ключ
# (x-api-key), либо bearer-токен для шлюза/прокси перед Anthropic. Если задан
# ANTHROPIC_AUTH_TOKEN — используем Bearer (через SDK auth_token=), иначе ключ.
ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN")
ANTHROPIC_BASE_URL   = os.getenv("ANTHROPIC_BASE_URL")  # напр. URL gateway/прокси

# Модель Claude — настраивается через MILA_MODEL. Дефолт сохраняет прежнее
# поведение; бамп до Opus 4.8 = поменять переменную окружения, без правок кода.
MODEL      = os.getenv("MILA_MODEL", "claude-opus-4-6")
MAX_TOKENS = int(os.getenv("MILA_MAX_TOKENS", "2048"))

# Instagram: сначала рабочие IG_* (Instagram Login flow), потом старые INSTAGRAM_*.
INSTAGRAM_TOKEN = os.getenv("IG_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACC   = os.getenv("IG_USER_ID") or os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
IG_FLOW         = (os.getenv("IG_API_FLOW", "facebook") or "facebook").lower()
_GRAPH_VERSION  = os.getenv("GRAPH_API_VERSION", "v21.0")
if IG_FLOW == "instagram_login":
    GRAPH_URL = f"https://graph.instagram.com/{_GRAPH_VERSION}"
    IG_NODE   = INSTAGRAM_ACC or "me"
else:
    GRAPH_URL = f"https://graph.facebook.com/{_GRAPH_VERSION}"
    IG_NODE   = INSTAGRAM_ACC

# Общий Graph-клиент из tools/_common.py — единый источник HTTP-логики для
# Instagram/Threads. Агенты (Марина, Вася) больше не дублируют requests-вызовы,
# а ходят через retрай-сессию и общий разбор ошибок (graph_api.GraphError).
_TOOLS_DIR = MILA_FOLDER / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
try:
    import _common as graph_api
except Exception:
    graph_api = None  # tools/ недоступны — Instagram-инструменты вернут понятную ошибку

console = Console()

def get_client():
    """Клиент Anthropic. Два поддерживаемых способа аутентификации:

    • ANTHROPIC_AUTH_TOKEN → Authorization: Bearer (SDK auth_token=) — для шлюза/
      прокси перед Anthropic или заранее полученного bearer-токена;
    • иначе ANTHROPIC_API_KEY → x-api-key (обычный ключ из Console, по умолчанию).

    ANTHROPIC_BASE_URL (опц.) переопределяет базовый URL (например, для gateway).
    """
    kwargs = {}
    if ANTHROPIC_BASE_URL:
        kwargs["base_url"] = ANTHROPIC_BASE_URL
    if ANTHROPIC_AUTH_TOKEN:
        return anthropic.Anthropic(auth_token=ANTHROPIC_AUTH_TOKEN, **kwargs)
    require_config("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=ANTHROPIC_KEY, **kwargs)

# ─── CONFIG VALIDATION ───────────────────────────────────
# Канонические имена → их значения (после разбора .env с учётом legacy-алиасов).
_CONFIG = {
    "ANTHROPIC_API_KEY":    ANTHROPIC_KEY,
    "TELEGRAM_BOT_TOKEN":   TELEGRAM_TOKEN,
    "GUMROAD_ACCESS_TOKEN": GUMROAD_TOKEN,
    "IG_ACCESS_TOKEN":      INSTAGRAM_TOKEN,
    "IG_USER_ID":           INSTAGRAM_ACC,
}

def require_config(*keys):
    """Проверяет, что заданные ключи заполнены. Иначе — понятное сообщение и выход.

    Вызывай лениво (внутри обработчика инструмента или перед запуском агента),
    чтобы агенты, которым ключ не нужен, продолжали работать. Зеркалит подход
    tools/_common.py:load_config — fail early с ясной ошибкой вместо тихого None.
    """
    missing = [k for k in keys if not _CONFIG.get(k)]
    if missing:
        console.print(
            f"[red]В .env не заполнено: {', '.join(missing)}.[/red]\n"
            f"[dim]Заполни их в E:\\MILA GOLD\\.env или tools\\.env "
            f"(см. env.template). Принимаются и legacy-имена.[/dim]"
        )
        raise SystemExit(1)

# ─── SHARED TOOLS ────────────────────────────────────────
# Бизнес-папки физически лежат под MILA-BUSINESS/, но промпты и команды агентов
# исторически называют их коротко («04-telegram», «content»). Подставляем
# реальное расположение, чтобы и короткая, и полная форма пути работали.
_FOLDER_ALIASES = {
    "01-praktikum":  "MILA-BUSINESS/01-praktikum",
    "02-content":    "MILA-BUSINESS/02-content",
    "content":       "MILA-BUSINESS/02-content",
    "03-clients":    "MILA-BUSINESS/03-clients",
    "04-telegram":   "MILA-BUSINESS/04-telegram",
    "05-analytics":  "MILA-BUSINESS/05-analytics",
}

def _apply_alias(path: str) -> str:
    """Подменяет первый сегмент пути на реальный (см. _FOLDER_ALIASES).

    Пути, уже начинающиеся с MILA-BUSINESS/tools/reports/logs, не трогаем.
    """
    norm = (path or "").replace("\\", "/").lstrip("/")
    if not norm:
        return path
    head, _, rest = norm.partition("/")
    mapped = _FOLDER_ALIASES.get(head)
    if not mapped:
        return path
    return f"{mapped}/{rest}" if rest else mapped

def _safe_path(path: str) -> Path:
    """Резолвит path внутри MILA_FOLDER и не даёт выйти за её пределы.

    Защита от path traversal: модель может подставить путь из подхваченного
    извне текста (комментарий, caption), поэтому всё, что вне рабочей папки,
    отклоняем. Возвращает абсолютный Path; бросает ValueError при выходе наружу.
    """
    root = MILA_FOLDER.resolve()
    p = (root / (_apply_alias(path) or "")).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"Путь вне рабочей папки: {path}")
    return p

def read_file(path: str) -> str:
    try: p = _safe_path(path)
    except ValueError as e: return f"Ошибка: {e}"
    try: return p.read_text(encoding="utf-8")
    except FileNotFoundError: return f"Файл не найден: {p}"
    except Exception as e: return f"Ошибка: {e}"

def write_file(path: str, content: str, mode: str = "write") -> str:
    try: p = _safe_path(path)
    except ValueError as e: return f"Ошибка: {e}"
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(p, "w" if mode == "write" else "a", encoding="utf-8") as f:
            f.write(content)
        return f"✓ Сохранено: {p}"
    except Exception as e: return f"Ошибка: {e}"

def list_files(path: str = "") -> str:
    try: p = _safe_path(path)
    except ValueError as e: return f"Ошибка: {e}"
    try:
        items = [f"{'📁' if i.is_dir() else '📄'} {i.name}" for i in sorted(p.iterdir())]
        return "\n".join(items) or "Пусто"
    except Exception as e: return f"Ошибка: {e}"

# Команды, которые единственному агенту с run_command (Марина) реально нужны —
# запуск скриптов из tools/. Произвольный shell больше не выполняется.
_ALLOWED_COMMAND_PREFIXES = (
    ("python", "tools/"),
    ("python", "tools\\"),
    ("py", "tools/"),
    ("py", "tools\\"),
)

def run_command(cmd: str) -> str:
    """Запускает только разрешённые команды (python tools/<script>.py …).

    Раньше здесь выполнялась произвольная shell-строка — это давало модели
    полный доступ к оболочке. Теперь разбираем в argv, сверяем с allowlist и
    запускаем без оболочки.
    """
    import shlex
    try:
        argv = shlex.split(cmd, posix=False)
    except ValueError as e:
        return f"Ошибка разбора команды: {e}"
    if not argv:
        return "Пустая команда"
    interp = os.path.basename(argv[0]).lower().removesuffix(".exe")
    target = argv[1].replace("\\", "/").lower() if len(argv) > 1 else ""
    allowed = any(
        interp == pfx[0] and target.startswith(pfx[1].replace("\\", "/"))
        for pfx in _ALLOWED_COMMAND_PREFIXES
    )
    if not allowed:
        return ("⚠️ Команда не разрешена. Доступен только запуск скриптов: "
                "python tools/<script>.py …")
    # Форсируем UTF-8 у дочернего процесса (раньше это делал cmd /c set
    # PYTHONIOENCODING=utf-8), иначе русский вывод скриптов ломает декодирование.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run(argv, shell=False, capture_output=True,
                           encoding="utf-8", errors="replace",
                           timeout=60, cwd=str(MILA_FOLDER), env=env)
        return (r.stdout + r.stderr)[:3000] or "Готово"
    except Exception as e: return f"Ошибка: {e}"

def log(category: str, message: str):
    p = MILA_FOLDER / "logs" / f"{category}.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {message}\n")

# ─── РЕЕСТР БАЗОВЫХ ИНСТРУМЕНТОВ ──────────────────────────
# Раньше каждый из 8 агентов дублировал JSON-схемы read_file/write_file/list_files
# (~25 строк) и одинаковую ветку handle() (~10 строк). Теперь схемы собирает
# core_tools(), диспетчеризацию делает core_handle(). Описания и default-папку
# агент задаёт сам — текст, который видит модель, остаётся прежним.
def core_tools(read_desc, write_desc, list_desc, list_default=""):
    """Собирает схемы трёх базовых файловых инструментов с заданными описаниями."""
    return [
        {"name": "read_file", "description": read_desc,
         "input_schema": {"type": "object",
                          "properties": {"path": {"type": "string"}},
                          "required": ["path"]}},
        {"name": "write_file", "description": write_desc,
         "input_schema": {"type": "object",
                          "properties": {"path": {"type": "string"},
                                         "content": {"type": "string"}},
                          "required": ["path", "content"]}},
        {"name": "list_files", "description": list_desc,
         "input_schema": {"type": "object",
                          "properties": {"path": {"type": "string", "default": list_default}}}},
    ]

def core_handle(name, inp, list_default=""):
    """Выполняет базовый инструмент. Возвращает строку-результат или None, если
    инструмент не базовый (тогда агент обрабатывает его сам)."""
    if name == "read_file":  return read_file(inp["path"])
    if name == "write_file": return write_file(inp["path"], inp.get("content", ""))
    if name == "list_files": return list_files(inp.get("path", list_default))
    return None

# ─── СЛОЙ УЛУЧШЕНИЙ ПРОМПТОВ (self-improving office) ──────
# Стас (Chief of Staff) дописывает агентам data-driven инструкции НЕ трогая их
# исходный код: каждое улучшение — это текст в prompt_overrides/<key>.md, который
# подмешивается к SYSTEM агента на лету. Безопасно (код не портится) и обратимо.
PROMPT_OVERRIDES_DIR = MILA_FOLDER / "MILA-BUSINESS" / "05-analytics" / "prompt_overrides"

def agent_overrides(key: str) -> str:
    """Возвращает накопленные улучшения промпта для агента (или '')."""
    try:
        return (PROMPT_OVERRIDES_DIR / f"{key}.md").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""

def compose_system(key: str, system: str) -> str:
    """SYSTEM агента + активные улучшения от Стаса. Так офис эволюционирует без
    правки кода агентов."""
    extra = agent_overrides(key).strip()
    if extra:
        return system + ("\n\n# ─ Улучшения от Стаса (data-driven; см. improvement_log) ─\n" + extra)
    return system

# ─── AGENT RUNNER ────────────────────────────────────────
def run_agent(client, system: str, tools: list, tool_handler, user_message: str, history: list):
    history.append({"role": "user", "content": user_message})
    messages = history.copy()

    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            system=system, tools=tools, messages=messages
        )
        texts, calls = [], []
        for b in resp.content:
            if b.type == "text": texts.append(b.text)
            elif b.type == "tool_use": calls.append(b)

        if not calls:
            reply = "\n".join(texts)
            history.append({"role": "assistant", "content": reply})
            return reply, history

        if texts:
            console.print(f"[dim italic]{''.join(texts)}[/dim italic]")

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for c in calls:
            console.print(f"  [dim]🔧 {c.name}({list(c.input.keys())})[/dim]")
            result = tool_handler(c.name, c.input)
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": result})
        messages.append({"role": "user", "content": results})

def chat_loop(name: str, emoji: str, color: str, system: str, tools: list, tool_handler, quick_cmds: dict):
    client = get_client()
    console.print(f"\n[bold]{emoji} {name} готова к работе[/bold]")
    console.print(f"[dim]Команды: {' · '.join(quick_cmds.keys())} · /выход[/dim]\n")
    history = []
    while True:
        try: user = Prompt.ask(f"[bold]Ты[/bold]").strip()
        except (KeyboardInterrupt, EOFError): break
        if not user: continue
        if user == "/выход": break
        if user == "/помощь":
            for k, v in quick_cmds.items(): console.print(f"  [bold]{k}[/bold] — {v}")
            continue
        msg = quick_cmds.get(user, user)
        console.print(f"\n[bold {color}]{name}:[/bold {color}]", end=" ")
        try:
            reply, history = run_agent(client, system, tools, tool_handler, msg, history)
            console.print(Markdown(reply))
        except Exception as e:
            console.print(f"[red]Ошибка: {e}[/red]")
