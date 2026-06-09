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

import os, json, subprocess, re, time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import anthropic
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

try:
    import system_prompt_builder
except ImportError:
    system_prompt_builder = None

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
GEMINI_KEY      = os.getenv("GEMINI_KEY") or os.getenv("GOOGLE_API_KEY")
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")  # ID Telegram канала для публикаций
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")  # Личный чат Людмилы для уведомлений
GUMROAD_TOKEN   = os.getenv("GUMROAD_ACCESS_TOKEN") or os.getenv("GUMROAD_TOKEN")
GAMMA_API_KEY   = os.getenv("GAMMA_API_KEY")
GAMMA_THEME_ID  = os.getenv("GAMMA_THEME_ID")

# Аутентификация Claude. У Messages API нет публичного OAuth-флоу — это либо ключ
# (x-api-key), либо bearer-токен для шлюза/прокси перед Anthropic. Если задан
# ANTHROPIC_AUTH_TOKEN — используем Bearer (через SDK auth_token=), иначе ключ.
ANTHROPIC_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN")
ANTHROPIC_BASE_URL   = os.getenv("ANTHROPIC_BASE_URL")  # напр. URL gateway/прокси

# Модель Claude — настраивается через MILA_MODEL. Дефолт сохраняет прежнее
# поведение; бамп до Opus 4.8 = поменять переменную окружения, без правок кода.
MODEL         = os.getenv("MILA_MODEL", "claude-opus-4-6")
GEMINI_MODEL  = os.getenv("MILA_GEMINI_MODEL", "gemini-2.5-flash")
MAX_TOKENS    = int(os.getenv("MILA_MAX_TOKENS", "4096"))
LLM_PROVIDER  = (os.getenv("MILA_LLM_PROVIDER") or "gemini").lower()
ANTHROPIC_AGENT_KEYS = {
    k.strip().lower()
    for k in os.getenv("MILA_ANTHROPIC_AGENTS", "manager,producer").split(",")
    if k.strip()
}

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
    if LLM_PROVIDER in ("gemini", "google") and not ANTHROPIC_AUTH_TOKEN and not ANTHROPIC_KEY:
        return None
    if ANTHROPIC_AUTH_TOKEN:
        return anthropic.Anthropic(auth_token=ANTHROPIC_AUTH_TOKEN, **kwargs)
    require_config("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=ANTHROPIC_KEY, **kwargs)

# ─── CONFIG VALIDATION ───────────────────────────────────
# Канонические имена → их значения (после разбора .env с учётом legacy-алиасов).
_CONFIG = {
    "ANTHROPIC_API_KEY":    ANTHROPIC_KEY,
    "GEMINI_KEY":           GEMINI_KEY,
    "TELEGRAM_BOT_TOKEN":   TELEGRAM_TOKEN,
    "TELEGRAM_CHANNEL_ID":  TELEGRAM_CHANNEL_ID,
    "TELEGRAM_ADMIN_CHAT_ID": TELEGRAM_ADMIN_CHAT_ID,
    "GUMROAD_ACCESS_TOKEN": GUMROAD_TOKEN,
    "GAMMA_API_KEY":       GAMMA_API_KEY,
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

# Потолок на чтение файла В КОНТЕКСТ модели. Без него read_file большого файла
# (напр. praktikum_редактура.html ~5 МБ ≈ 1.5 млн токенов) раздувает запрос —
# это и слив денег, и риск превысить лимит контекста. 40000 символов ≈ 10-13k
# токенов — достаточно для анализа, дальше модель попросит конкретный фрагмент.
_READ_MAX_CHARS = int(os.getenv("MILA_READ_MAX_CHARS", "40000"))

def read_file(path: str) -> str:
    try: p = _safe_path(path)
    except ValueError as e: return f"Ошибка: {e}"
    try:
        txt = p.read_text(encoding="utf-8")
    except FileNotFoundError: return f"Файл не найден: {p}"
    except Exception as e: return f"Ошибка: {e}"
    if len(txt) > _READ_MAX_CHARS:
        return (txt[:_READ_MAX_CHARS] +
                f"\n\n…[файл обрезан: показано {_READ_MAX_CHARS} из {len(txt)} символов. "
                f"Попроси конкретный раздел/фрагмент, если нужен остаток.]")
    return txt

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


def _slugify(value: str, fallback: str = "gamma_document") -> str:
    value = (value or "").strip().lower()
    translit = str.maketrans({
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    })
    value = value.translate(translit)
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value[:80] or fallback


class GammaError(RuntimeError):
    pass


def _gamma_headers() -> dict:
    require_config("GAMMA_API_KEY")
    return {
        "Content-Type": "application/json",
        "X-API-KEY": GAMMA_API_KEY,
    }


def create_gamma_document(
    title: str,
    content: str,
    format: str = "document",
    export: str = "pdf",
) -> dict:
    """Create a branded Gamma document/presentation and download the exported PDF.

    Gamma API is async: POST /generations returns generationId, then we poll
    GET /generations/{id} until status is completed or failed.
    """
    title = (title or "").strip()
    content = (content or "").strip()
    format = (format or "document").strip().lower()
    export = (export or "pdf").strip().lower()
    if not title:
        raise GammaError("title is required")
    if not content:
        raise GammaError("content is required")
    if format not in {"document", "presentation", "social", "webpage"}:
        raise GammaError("format must be document, presentation, social, or webpage")
    if export not in {"pdf", "pptx", "png"}:
        raise GammaError("export must be pdf, pptx, or png")

    payload = {
        "inputText": content,
        "textMode": "preserve",
        "format": format,
        "exportAs": export,
        "additionalInstructions": f"Title: {title}\nLanguage: ru",
    }
    if GAMMA_THEME_ID:
        payload["themeId"] = GAMMA_THEME_ID

    base_url = "https://public-api.gamma.app/v1.0"
    try:
        started = requests.post(
            f"{base_url}/generations",
            headers=_gamma_headers(),
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        raise GammaError(f"Gamma API request failed: {e}") from e
    if started.status_code not in (200, 201):
        raise GammaError(f"Gamma API {started.status_code}: {(started.text or '')[:500]}")
    generation_id = (started.json() or {}).get("generationId")
    if not generation_id:
        raise GammaError("Gamma did not return generationId")

    timeout_sec = int(os.getenv("GAMMA_TIMEOUT_SEC", "900"))
    poll_sec = int(os.getenv("GAMMA_POLL_SEC", "10"))
    deadline = time.time() + timeout_sec
    status_payload = {}
    while time.time() < deadline:
        try:
            polled = requests.get(
                f"{base_url}/generations/{generation_id}",
                headers=_gamma_headers(),
                timeout=30,
            )
        except requests.RequestException as e:
            raise GammaError(f"Gamma polling failed: {e}") from e
        if polled.status_code != 200:
            raise GammaError(f"Gamma polling {polled.status_code}: {(polled.text or '')[:500]}")
        status_payload = polled.json() or {}
        status = status_payload.get("status")
        if status == "completed":
            break
        if status == "failed":
            raise GammaError(f"Gamma generation failed: {json.dumps(status_payload, ensure_ascii=False)[:800]}")
        time.sleep(max(5, poll_sec))
    else:
        raise GammaError(f"Gamma generation timed out after {timeout_sec}s: {generation_id}")

    gamma_url = status_payload.get("gammaUrl")
    export_url = status_payload.get("exportUrl")
    if not export_url:
        raise GammaError("Gamma completed but did not return exportUrl")

    products_dir = MILA_FOLDER / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    suffix = "pdf" if export == "pdf" else export
    local_path = products_dir / f"{_slugify(title)}.{suffix}"
    try:
        download = requests.get(export_url, timeout=120)
    except requests.RequestException as e:
        raise GammaError(f"Gamma export download failed: {e}") from e
    if download.status_code != 200:
        raise GammaError(f"Gamma export download {download.status_code}: {(download.text or '')[:300]}")
    local_path.write_bytes(download.content)

    return {
        "generation_id": generation_id,
        "gamma_url": gamma_url,
        "pdf_url": export_url if export == "pdf" else "",
        "export_url": export_url,
        "local_path": str(local_path),
        "credits": status_payload.get("credits"),
    }

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


# Общий голос бренда (_brand_voice.md) — единый источник правды для ВСЕХ агентов,
# пишущих тексты бренда. Подмешивается им всем, каждый применяет свою часть:
# Марина — форматы, Рита — воркбуки, Виктория — редактура/чек-лист, Лера — продажи,
# Тёма — Telegram. Не-контентные агенты (финансы/CRM/планировщик/менеджер) его не получают.
CONTENT_VOICE_AGENTS = {"marina", "rita", "victoria", "lera", "tyoma"}
_BRAND_VOICE_FILE = PROMPT_OVERRIDES_DIR / "_brand_voice.md"


def brand_voice() -> str:
    try:
        return _BRAND_VOICE_FILE.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""

# memory.py не зависит от base (только stdlib) — импорт безопасен, цикла нет.
try:
    import memory as _memory
except Exception as _e:
    _memory = None  # без memory профиль/фаза просто не подмешиваются
    # Один раз сообщаем оператору, ПОЧЕМУ контекст офиса не подмешивается — иначе
    # «фаза/профиль исчезли» молча и непонятно, что чинить (сломан memory.py?).
    print(f"[base] memory.py недоступна ({type(_e).__name__}: {_e}) — "
          f"контекст офиса (фаза/профиль) не будет подмешан в промпты.", file=sys.stderr)

_phase_warned = False  # чтобы предупреждение о сбое чтения фазы печаталось 1 раз/процесс

# Что фаза означает для поведения. Общая часть видна всем агентам; для Стаса
# (manager) — отдельная инструкция, т.к. в фазе 0 он стратег запуска, а не аналитик.
_PHASE_NOTE = {
    "cold_start": "Данных почти нет — опирайся на экспертные defaults из профиля, "
                  "не выдумывай статистику и не ссылайся на «данные», которых нет.",
    "learning":   "Данные начали накапливаться (первые посты измерены) — выводы возможны, "
                  "но осторожные: помечай их как предварительные.",
    "analysis":   "Данных достаточно для выводов — опирайся на реальные метрики, а не на defaults.",
}
# Фазовый АКЦЕНТ для Стаса — НЕ ограничение его роли. Он всегда аналитик+стратег
# со всеми инструментами (measure_metrics, app_review, db_query, improve_agent…);
# фаза лишь подсказывает, на что делать упор и насколько уверенно говорить о данных.
_MANAGER_PHASE_NOTE = {
    "cold_start": "Сейчас фаза запуска: данных мало, поэтому ДОПОЛНИТЕЛЬНО к обычной работе "
                  "делай упор на построение воронки и первые сигналы. Анализ, метрики и "
                  "техобзор (measure_metrics/app_review/db_query) применяй как обычно — просто "
                  "честно помечай, где выводы предварительные из-за нехватки данных.",
    "learning":   "Появляются первые точки данных — анализируй как обычно, но выводы помечай "
                  "как предварительные и готовь почву для режима полного анализа.",
    "analysis":   "Данных достаточно: анализируй на полную — узкие места по реальным метрикам, "
                  "улучшения агентов на данных.",
}

def _phase_preamble(key: str) -> str:
    """Профиль офиса + текущая фаза → текст-преамбула к SYSTEM. Доходит до ВСЕХ
    агентов, потому что compose_system вызывается и из webapp, и из pipeline.
    Возвращает '' если memory недоступна."""
    if _memory is None:
        return ""
    try:
        phase = _memory.current_phase()
        profile = _memory.read_profile()
    except Exception as e:
        global _phase_warned
        if not _phase_warned:
            _phase_warned = True
            print(f"[base] не удалось прочитать фазу/профиль ({type(e).__name__}: {e}) — "
                  f"промпты идут без контекста офиса. Проверь memory/profile.json.",
                  file=sys.stderr)
        return ""
    biz = profile.get("business", {}) if isinstance(profile, dict) else {}
    lines = [
        f"# ─ Контекст офиса (фаза: {phase}) ─",
        _PHASE_NOTE.get(phase, ""),
    ]
    if key == "manager":
        lines.append(_MANAGER_PHASE_NOTE.get(phase, ""))
    # Краткие defaults — то, на что агент опирается, пока нет статистики.
    if biz:
        topics = ", ".join(biz.get("top_topics", []) or [])
        facts = [
            f"подписчиков ~{biz['ig_followers']}" if biz.get("ig_followers") else "",
            f"лучший формат: {biz['best_content_type']}" if biz.get("best_content_type") else "",
            f"лучшее время: {biz['best_posting_time']}" if biz.get("best_posting_time") else "",
            f"рабочие темы: {topics}" if topics else "",
        ]
        facts = [f for f in facts if f]
        if facts:
            lines.append("Defaults профиля — " + "; ".join(facts) + ".")
        if biz.get("note"):
            lines.append(biz["note"])
    # Позиционирование — чем Людмила отличается от рынка. Это читает КАЖДЫЙ агент
    # (особенно Марина при написании поста): держать голос и отстройку.
    pos = profile.get("positioning", {}) if isinstance(profile, dict) else {}
    if pos.get("summary"):
        lines.append("Отстройка от рынка: " + pos["summary"])
    return "\n".join(l for l in lines if l)

def compose_system(key: str, system: str, context: dict = None) -> str:
    """SYSTEM агента + контекст фазы офиса + контекст запроса + активные улучшения от Стаса.

    Args:
        key: ключ агента (marina, victoria, итд)
        system: базовый system prompt
        context: контекст запроса {from_agent, to_agent, chain_id} или None
    """
    out = system

    # Добавляем контекст запроса если есть
    if context and system_prompt_builder:
        context_section = system_prompt_builder._build_context_section(
            key, context,
            system_prompt_builder.get_agent_chain_info(key)
        )
        if context_section:
            out += "\n\n" + context_section

    preamble = _phase_preamble(key).strip()
    if preamble:
        out += "\n\n" + preamble
    if key in CONTENT_VOICE_AGENTS:
        voice = brand_voice().strip()
        if voice:
            out += "\n\n# ─ Голос бренда Людмилы (общий; применяй свою часть) ─\n" + voice
    extra = agent_overrides(key).strip()
    if extra:
        out += "\n\n# ─ Улучшения от Стаса (data-driven; см. improvement_log) ─\n" + extra
    # Подсказка о next actions в интерфейсе.
    out += "\n\n# ─ Механика переходов между агентами ─\n" \
           "Если в конце твоего ответа добавить [→ rita] (где rita — ключ агента), " \
           "интерфейс выделит это действие как рекомендуемое. " \
           "Пример: 'Вот структура... [→ victoria]' → пользователю предложится редактура у Виктории. " \
           "Это необязательно — next actions предложены интерфейсом по умолчанию, но ты можешь подсказать лучший следующий шаг.\n\n" \
           "# ─ Статус работы (VERDICT) ─\n" \
           "В конце своего ответа указывай VERDICT в одной из форм:\n" \
           "  [VERDICT: ready_next] — работа готова, пусть следующий агент продолжает\n" \
           "  [VERDICT: needs_revision] — нужны правки (вернись к предыдущему этапу)\n" \
           "  [VERDICT: done] — работа завершена, можно публиковать\n" \
           "Пример: 'Всё проверено и отредактировано. [VERDICT: ready_next] [→ rita]'\n" \
           "VERDICT обязателен для document workflow tracking и помогает системе понять что дальше.\n\n" \
           "# ─ Готовый документ для скачивания ─\n" \
           "Когда ты ВНОСИШЬ ПРАВКИ в текст/документ и выдаёшь его финальную версию, оберни " \
           "ПОЛНЫЙ исправленный текст (целиком, с уже применёнными правками — не diff, не пересказ) " \
           "в маркеры:\n" \
           "  [ДОКУМЕНТ]\n  …весь готовый текст…\n  [/ДОКУМЕНТ]\n" \
           "Свои комментарии (что и почему изменил, оценка) пиши ВНЕ этих маркеров. " \
           "Приложение вырежет блок [ДОКУМЕНТ] и предложит пользователю скачать чистый готовый " \
           "файл — без твоих пометок. Без маркеров скачается транскрипт обсуждения, а не документ. " \
           "Если правок не вносишь (только отзыв/совет) — маркеры не нужны."
    return out

# ─── AGENT RUNNER ────────────────────────────────────────
def _anthropic_configured() -> bool:
    return bool(ANTHROPIC_AUTH_TOKEN or ANTHROPIC_KEY)


def provider_for_agent(agent_key: str | None = None) -> str:
    key = (agent_key or "").lower()
    provider = (LLM_PROVIDER or "auto").lower()
    if provider in ("anthropic", "claude"):
        return "anthropic"
    if provider in ("gemini", "google"):
        if key in ANTHROPIC_AGENT_KEYS:
            return "anthropic"
        return "gemini"
    if key in ANTHROPIC_AGENT_KEYS and _anthropic_configured():
        return "anthropic"
    if GEMINI_KEY:
        return "gemini"
    return "anthropic"


def _strip_gemini_schema(value):
    if isinstance(value, dict):
        return {
            k: _strip_gemini_schema(v)
            for k, v in value.items()
            if k not in {"default", "$schema"}
        }
    if isinstance(value, list):
        return [_strip_gemini_schema(v) for v in value]
    return value


def _gemini_tools(tools: list) -> list:
    declarations = []
    for tool in tools or []:
        declarations.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": _strip_gemini_schema(
                tool.get("input_schema") or {"type": "object", "properties": {}}
            ),
        })
    return [{"function_declarations": declarations}] if declarations else []


def _gemini_contents(messages: list) -> list:
    contents = []
    for msg in messages:
        role = "model" if msg.get("role") == "assistant" else "user"
        content = msg.get("content", "")
        if isinstance(content, str):
            contents.append({"role": role, "parts": [{"text": content}]})
    return contents


def _parse_retry_after(value: str | None, fallback: float, cap: float = 30.0) -> float:
    """Retry-After по RFC 7231: либо целые секунды, либо HTTP-дата. Возвращает
    паузу в секундах, ограниченную [0, cap]; на мусоре/пустоте — fallback.
    Раньше брали только .isdigit() → пробелы и дата-формат игнорировались, и
    мы спали слишком мало, усугубляя rate-limit."""
    if not value:
        return fallback
    raw = value.strip()
    try:
        secs = float(raw)              # «120», « 120 »
    except ValueError:
        try:                            # HTTP-дата → дельта от текущего момента
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(raw)
            if dt is None:
                return fallback
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            secs = (dt - datetime.now(dt.tzinfo)).total_seconds()
        except (TypeError, ValueError):
            return fallback
    if secs <= 0:
        return fallback
    return min(secs, cap)


def _gemini_generate(contents: list, system: str, tools: list) -> dict:
    require_config("GEMINI_KEY")
    # gemini-2.5-flash по умолчанию тратит «динамический» бюджет на размышления
    # (наблюдалось ~1100 thinking-токенов/ответ) — это заметная часть задержки.
    # Для редактуры/структуры столько рассуждений не нужно: ограничиваем бюджет,
    # чтобы ответы были быстрее (цель < 5000 мс у Виктории/Риты). Настраивается
    # MILA_GEMINI_THINKING_BUDGET: 0 — выключить thinking, N>0 — лимит токенов,
    # -1 (или пусто) — вернуть дефолтное динамическое поведение модели.
    gen = {"maxOutputTokens": MAX_TOKENS}
    try:
        _tb = int(os.getenv("MILA_GEMINI_THINKING_BUDGET", "512"))
        if _tb >= 0:
            gen["thinkingConfig"] = {"thinkingBudget": _tb}
    except ValueError:
        pass
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": gen,
    }
    converted_tools = _gemini_tools(tools)
    if converted_tools:
        payload["tools"] = converted_tools
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    # Транзиентные сбои Google (503 Service Unavailable, 429 rate limit, 500) —
    # не падаем с первой попытки, а повторяем с экспоненциальной паузой.
    import time as _time
    last = None
    for attempt in range(4):
        try:
            resp = requests.post(url, params={"key": GEMINI_KEY}, json=payload, timeout=90)
        except requests.RequestException as e:
            last = e
            _time.sleep(1.5 * (attempt + 1))
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            last = resp
            if attempt < 3:
                # Respect Retry-After если есть (секунды ИЛИ HTTP-дата), иначе
                # backoff 1.5/3/4.5с. Капаем, чтобы битый заголовок не усыпил надолго.
                backoff = 1.5 * (attempt + 1)
                _time.sleep(_parse_retry_after(resp.headers.get("Retry-After"), backoff))
                continue
        # ВАЖНО: НЕ raise_for_status() — он кладёт полный URL (с ?key=…) в текст
        # исключения, а тот уходит в логи. Бросаем своё сообщение БЕЗ ключа.
        if resp.status_code != 200:
            raise RuntimeError(
                f"Gemini API {resp.status_code} ({GEMINI_MODEL}): "
                f"{(resp.text or '')[:300]}")
        return resp.json()
    # все попытки исчерпаны
    code = getattr(last, "status_code", "network")
    raise RuntimeError(
        f"Gemini API недоступен после 4 попыток (последний код: {code}, модель {GEMINI_MODEL}). "
        f"Обычно это временный сбой Google (503) — попробуй ещё раз через минуту.")


def _run_gemini_agent(system: str, tools: list, tool_handler, messages: list, history: list):
    contents = _gemini_contents(messages)
    while True:
        data = _gemini_generate(contents, system, tools)
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        texts = [p["text"] for p in parts if p.get("text")]
        calls = [p["functionCall"] for p in parts if p.get("functionCall")]

        if not calls:
            reply = "\n".join(texts)
            history.append({"role": "assistant", "content": reply})
            return reply, history

        if texts:
            console.print(f"[dim italic]{''.join(texts)}[/dim italic]")

        model_parts = []
        response_parts = []
        for call in calls:
            name = call.get("name", "")
            args = call.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            console.print(f"  [dim]tool {name}({list(args.keys())})[/dim]")
            result = tool_handler(name, args)
            model_parts.append({"functionCall": {"name": name, "args": args}})
            response_parts.append({
                "functionResponse": {
                    "name": name,
                    "response": {"result": "" if result is None else str(result)},
                }
            })
        contents.append({"role": "model", "parts": model_parts})
        contents.append({"role": "user", "parts": response_parts})


def _run_anthropic_agent(client, system: str, tools: list, tool_handler, messages: list, history: list):
    if client is None:
        client = get_client()

    # Prompt caching: system+tools — стабильный префикс, который шлётся заново на
    # КАЖДОМ витке tool-loop и в каждом сообщении чата. Помечаем его cache_control,
    # чтобы Anthropic кэшировал (повторное чтение ~в 10× дешевле). Порядок в API —
    # tools → system → messages, поэтому один маркер на system кэширует и tools.
    system_cached = [{"type": "text", "text": system,
                      "cache_control": {"type": "ephemeral"}}]

    while True:
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            system=system_cached, tools=tools, messages=messages
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
            console.print(f"  [dim]tool {c.name}({list(c.input.keys())})[/dim]")
            result = tool_handler(c.name, c.input)
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": result})
        messages.append({"role": "user", "content": results})


def run_agent(client, system: str, tools: list, tool_handler, user_message: str, history: list,
              agent_key: str | None = None, context: dict = None):
    """Запустить агента с поддержкой контекста запроса.

    Args:
        context: {from_agent, to_agent, chain_id} или None
    """
    # Извлекаем контекст из сообщения если есть теги
    if not context and system_prompt_builder:
        context = system_prompt_builder.extract_context_from_message(user_message)

    # Обновляем system prompt с контекстом
    enhanced_system = compose_system(agent_key or "default", system, context)

    # Логируем если контекст есть
    if context:
        from_agent = context.get("from_agent", "user")
        chain_id = context.get("chain_id", "")
        log("chain", f"agent={agent_key} from={from_agent} chain={chain_id}")

    history.append({"role": "user", "content": user_message})
    messages = history.copy()
    provider = provider_for_agent(agent_key)
    if provider == "gemini":
        return _run_gemini_agent(enhanced_system, tools, tool_handler, messages, history)
    # Claude-агенты (Стас, Кирилл): если Claude недоступен (нет кредитов, 429,
    # сеть) — НЕ падаем, а откатываемся на Gemini. Tool-loop пишет в локальный
    # messages, не в history, поэтому при сбое history чистая (только user-msg) —
    # можно безопасно перезапустить на Gemini со свежей копией.
    try:
        return _run_anthropic_agent(client, enhanced_system, tools, tool_handler, messages, history)
    except Exception as e:
        if not GEMINI_KEY:
            raise  # фолбэка нет — пробрасываем исходную ошибку Claude
        console.print(f"[yellow]Claude недоступен ({str(e)[:80]}) → фолбэк на Gemini[/yellow]")
        log("llm", f"fallback claude->gemini agent={agent_key}: {str(e)[:120]}")
        return _run_gemini_agent(enhanced_system, tools, tool_handler, history.copy(), history)

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
