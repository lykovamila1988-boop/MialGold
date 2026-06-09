"""
_common.py — общие функции для скриптов MILA GOLD.
Shared helpers: load credentials, call the Graph API, save reports.
"""
import os
import sys
import json
import time
import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Не установлен 'requests'. Запустите: pip install requests python-dotenv")

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("Не установлен 'python-dotenv'. Запустите: pip install requests python-dotenv")

# Папка, где лежит этот файл (tools/)
TOOLS_DIR = Path(__file__).resolve().parent
ENV_PATH = TOOLS_DIR / ".env"
REPORTS_DIR = TOOLS_DIR.parent / "reports"
OFFICE_DIR = TOOLS_DIR.parent / "mila-office"
if str(OFFICE_DIR) not in sys.path:
    sys.path.insert(0, str(OFFICE_DIR))
try:
    import memory as office_memory
except Exception:
    office_memory = None

def _int_env(name: str, default: int) -> int:
    """Читает целочисленную env-переменную, не роняя импорт на мусорном значении.
    _common.py импортируется всеми скриптами (и mila-office/base.py как graph_api),
    поэтому кривой IG_RATE_LIMIT_PER_HOUR не должен ломать весь тулинг — берём
    default и пишем предупреждение в stderr."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        print(f"[config] {name}={raw!r} — не целое число, использую {default}.", file=sys.stderr)
        return default


IG_RATE_LIMIT_PER_HOUR = _int_env("IG_RATE_LIMIT_PER_HOUR", 200)
THREADS_RATE_LIMIT_PER_HOUR = _int_env("THREADS_RATE_LIMIT_PER_HOUR", 200)

# Слова-триггеры заявок (лид в комментариях/ответах). Раньше дублировались
# в get_analytics.py и get_threads.py — теперь единый источник.
TRIGGER_WORDS = ["хочу", "want", "цена", "сколько", "заказ"]


# ─── ОШИБКИ ──────────────────────────────────────────────
# Раньше функции звали sys.exit() прямо из библиотеки. Это ломало переиспользование
# (агенты не могли импортировать модуль — sys.exit убивал процесс, а SystemExit не
# ловится через `except Exception`). Теперь библиотека БРОСАЕТ исключения, а CLI
# превращает их в аккуратный sys.exit через run_cli().
class ConfigError(Exception):
    """Проблема конфигурации (.env): отсутствует файл или обязательный ключ."""


class GraphError(Exception):
    """Ошибка сетевого вызова или ответа Graph/Threads API."""


def _rate_limit_key(cfg) -> tuple[str, int]:
    base = (cfg.get("base") or "").lower()
    if "threads" in base:
        return "threads_api", THREADS_RATE_LIMIT_PER_HOUR
    return "instagram_api", IG_RATE_LIMIT_PER_HOUR


def check_rate_limit(cfg, cost=1):
    """Shared local limiter before Graph/Threads calls."""
    if office_memory is None:
        return {"ok": True, "api": "memory_unavailable"}
    api, limit = _rate_limit_key(cfg)
    res = office_memory.shared_rate_limit(api, limit, cost=cost)
    if not res.get("ok"):
        retry = res.get("retry_after", 0)
        raise GraphError(
            f"Rate limit {api}: {res.get('used')}/{res.get('limit')} requests in the last hour. "
            f"Retry after ~{retry}s."
        )
    return res


# ─── HTTP-СЕССИЯ С РЕТРАЯМИ ───────────────────────────────
# Одна Session на процесс → переиспользование TCP/TLS-соединений (раньше каждый
# вызов открывал новое). Ретраи с экспоненциальной паузой на временные ошибки.
def _build_session():
    s = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry = Retry(
            total=3, backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
    except Exception:
        pass  # без urllib3 Retry просто работаем без авто-ретраев
    return s


_session = _build_session()


def run_cli(main_callable):
    """Запускает CLI-обёртку: ловит наши ошибки и превращает их в чистый exit.

    Сохраняет прежний UX скриптов (сообщение + код возврата 1) при том, что
    сама библиотека теперь бросает исключения, а не зовёт sys.exit.
    """
    try:
        main_callable()
    except (ConfigError, GraphError) as e:
        sys.exit(str(e))


def load_config():
    """
    Загружает .env для Instagram и проверяет обязательные поля.

    Поддерживает ДВА способа подключения (IG_API_FLOW):
      • instagram_login — новый «Instagram API with Instagram Login».
        Хост graph.instagram.com, узел "me", Facebook-страница НЕ нужна,
        IG_USER_ID необязателен (берётся "me").
      • facebook (по умолчанию) — «Instagram Graph API» через Facebook-страницу.
        Хост graph.facebook.com, узел = IG_USER_ID (обязателен).

    В cfg['node'] лежит префикс пути для запросов media/insights/publish,
    чтобы скрипты не зависели от способа подключения.
    """
    if not ENV_PATH.exists():
        raise ConfigError(
            f"Файл не найден: {ENV_PATH}\n"
            "Скопируйте .env.example в .env и впишите свои данные."
        )
    load_dotenv(ENV_PATH)
    flow = (os.getenv("IG_API_FLOW", "facebook").strip().lower() or "facebook")
    cfg = {
        "flow": flow,
        "token": os.getenv("IG_ACCESS_TOKEN", "").strip(),
        "ig_user_id": os.getenv("IG_USER_ID", "").strip(),
        "fb_page_id": os.getenv("FB_PAGE_ID", "").strip(),
        "app_id": os.getenv("META_APP_ID", "").strip(),
        "app_secret": os.getenv("META_APP_SECRET", "").strip(),
        "version": os.getenv("GRAPH_API_VERSION", "v21.0").strip(),
    }

    if flow == "instagram_login":
        cfg["base"] = "https://graph.instagram.com"
        # При Instagram Login токена достаточно — узел "me", если ID не задан.
        cfg["node"] = cfg["ig_user_id"] or "me"
        if not cfg["token"]:
            raise ConfigError("В .env не заполнено: IG_ACCESS_TOKEN")
    else:
        cfg["base"] = "https://graph.facebook.com"
        cfg["node"] = cfg["ig_user_id"]
        missing = [k for k in ("token", "ig_user_id") if not cfg[k]]
        if missing:
            names = {"token": "IG_ACCESS_TOKEN", "ig_user_id": "IG_USER_ID"}
            raise ConfigError("В .env не заполнено: " + ", ".join(names[m] for m in missing))
    return cfg


def load_threads_config():
    """
    Загружает .env для Threads. Threads API — ОТДЕЛЬНЫЙ от Instagram:
    другой хост (graph.threads.net) и своё приложение/токен.
    Возвращает cfg, совместимый с graph_get / graph_post (отличается база).
    """
    if not ENV_PATH.exists():
        raise ConfigError(
            f"Файл не найден: {ENV_PATH}\n"
            "Скопируйте .env.example в .env и впишите свои данные."
        )
    load_dotenv(ENV_PATH)
    cfg = {
        "token": os.getenv("THREADS_ACCESS_TOKEN", "").strip(),
        "user_id": os.getenv("THREADS_USER_ID", "").strip(),
        "app_id": os.getenv("THREADS_APP_ID", "").strip(),
        "app_secret": os.getenv("THREADS_APP_SECRET", "").strip(),
        "version": os.getenv("THREADS_API_VERSION", "v1.0").strip(),
        "base": "https://graph.threads.net",
    }
    missing = [k for k in ("token", "user_id") if not cfg[k]]
    if missing:
        names = {"token": "THREADS_ACCESS_TOKEN", "user_id": "THREADS_USER_ID"}
        raise ConfigError("В .env не заполнено (Threads): " + ", ".join(names[m] for m in missing))
    return cfg


def api_base(cfg):
    # IG/Facebook → graph.facebook.com ; Threads → graph.threads.net.
    # База берётся из cfg['base'] (её ставят load_config / load_threads_config).
    return f"{cfg.get('base', 'https://graph.facebook.com')}/{cfg['version']}"


def graph_get(cfg, path, params=None):
    """GET-запрос к Graph API. Возвращает JSON или завершает работу с ошибкой."""
    check_rate_limit(cfg)
    params = dict(params or {})
    params.setdefault("access_token", cfg["token"])
    url = f"{api_base(cfg)}/{path.lstrip('/')}"
    try:
        r = _session.get(url, params=params, timeout=30)
    except requests.RequestException as e:
        raise GraphError(f"Сетевая ошибка: {e}")
    data = r.json() if r.content else {}
    if r.status_code != 200 or "error" in data:
        err = data.get("error", {})
        msg = err.get("message", r.text)
        raise GraphError(f"Ошибка Graph API ({r.status_code}): {msg}")
    return data


def graph_get_all(cfg, path, params=None, max_items=None):
    """GET с автоматической постраничной загрузкой (pagination)."""
    items = []
    data = graph_get(cfg, path, params)
    while True:
        items.extend(data.get("data", []))
        if max_items and len(items) >= max_items:
            return items[:max_items]
        next_url = data.get("paging", {}).get("next")
        if not next_url:
            return items
        try:
            check_rate_limit(cfg)
            r = _session.get(next_url, timeout=30)
            data = r.json()
        except requests.RequestException as e:
            print(f"[!] Пагинация прервана: {e}", file=sys.stderr)
            return items


def graph_post(cfg, path, data=None):
    """POST-запрос к Graph API."""
    check_rate_limit(cfg)
    payload = dict(data or {})
    payload.setdefault("access_token", cfg["token"])
    url = f"{api_base(cfg)}/{path.lstrip('/')}"
    try:
        r = _session.post(url, data=payload, timeout=60)
    except requests.RequestException as e:
        raise GraphError(f"Сетевая ошибка: {e}")
    out = r.json() if r.content else {}
    if r.status_code != 200 or "error" in out:
        err = out.get("error", {})
        raise GraphError(f"Ошибка Graph API ({r.status_code}): {err.get('message', r.text)}")
    return out


def wait_until_ready(cfg, container_id, *, status_field="status_code",
                     fail_codes=("ERROR",), fields=None, timeout=300,
                     interval=5, on_tick=None):
    """Ждёт, пока медиа-контейнер обработается (статус FINISHED).

    Единый поллинг для двухфазной публикации Instagram (status_code) и Threads
    (status). Раньше этот цикл был скопирован 3-4 раза. Возвращает финальный
    объект статуса; бросает GraphError при FAIL-коде или таймауте.
    """
    fields = fields or status_field
    waited = 0
    while waited < timeout:
        st = graph_get(cfg, container_id, params={"fields": fields})
        code = st.get(status_field)
        if code == "FINISHED":
            return st
        if code in fail_codes:
            detail = st.get("error_message") or st.get("status") or code
            raise GraphError(f"Обработка контейнера не удалась ({code}): {detail}")
        if on_tick:
            on_tick(code)
        time.sleep(interval)
        waited += interval
    raise GraphError("Контейнер не обработался за отведённое время.")


def save_report(name, payload):
    """Сохраняет данные в reports/ как JSON. Возвращает путь.

    Дедупликация: если за сегодня уже есть отчёт этого типа с идентичными данными,
    новый файл не создаётся (возвращается существующий). Иначе повторные запуски за
    день плодили дубли — особенно пустые comments_*.json при недоступных комментариях.
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    for existing in REPORTS_DIR.glob(f"{name}_{today}_*.json"):
        try:
            if existing.read_text(encoding="utf-8") == body:
                return existing
        except OSError:
            continue
    # секунды в имени → разные данные в одну минуту не перезатирают друг друга.
    # Если и секунда совпала (а данные иные — иначе сработал бы дедуп выше),
    # добавляем суффикс, чтобы ничего не перезаписать.
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = REPORTS_DIR / f"{name}_{stamp}.json"
    n = 2
    while path.exists():
        path = REPORTS_DIR / f"{name}_{stamp}_{n}.json"
        n += 1
    path.write_text(body, encoding="utf-8")
    return path


def get_consultations(days=30):
    """Получить завершённые консультации из Calendly API.

    Требует в .env:
    - CALENDLY_ACCESS_TOKEN: токен доступа Calendly
    - CALENDLY_EVENT_ID: ID типа события (консультации)
    - CALENDLY_PRICE: цена консультации ($120 по умолчанию)

    Возвращает список:
    [
        {
            "event_uuid": "...",
            "start_time": "2026-06-01T10:00:00Z",
            "end_time": "2026-06-01T11:00:00Z",
            "status": "completed",
            "invitees": [{"name": "...", "email": "..."}],
            "price": 120
        }
    ]
    """
    load_dotenv(ENV_PATH)
    calendly_token = os.getenv("CALENDLY_ACCESS_TOKEN", "").strip()
    calendly_event_id = os.getenv("CALENDLY_EVENT_ID", "").strip()
    calendly_price = float(os.getenv("CALENDLY_PRICE", "120"))

    if not calendly_token:
        print("[!] CALENDLY_ACCESS_TOKEN не установлен в .env", file=sys.stderr)
        return []

    if not calendly_event_id:
        print("[!] CALENDLY_EVENT_ID не установлен в .env", file=sys.stderr)
        return []

    try:
        # Calendly API: https://developer.calendly.com/docs/api/v2/scheduled_events
        headers = {"Authorization": f"Bearer {calendly_token}"}

        # Получаем все события за последние N дней
        start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
        params = {
            "user": f"https://api.calendly.com/users/me",  # Получим ID юзера сначала
            "status": "active",  # Только завершённые (обновим после получения юзера)
            "min_start_time": f"{start_date}Z",
        }

        # Сначала получаем ID пользователя
        r = _session.get("https://api.calendly.com/users/me",
                        headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"[!] Calendly error: {r.status_code} - {r.text}", file=sys.stderr)
            return []

        user_id = r.json()["resource"]["uri"]

        # Затем получаем события этого юзера
        params["user"] = user_id
        r = _session.get("https://api.calendly.com/scheduled_events",
                        headers=headers, params=params, timeout=30)

        if r.status_code != 200:
            print(f"[!] Calendly error: {r.status_code} - {r.text}", file=sys.stderr)
            return []

        events = r.json().get("collection", [])
        consultations = []

        for event in events:
            # Фильтруем только события нужного типа (консультации)
            if calendly_event_id not in event.get("event_type", ""):
                continue

            # Только завершённые события
            if event.get("status") != "active":
                continue

            consultation = {
                "event_uuid": event.get("uuid"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
                "status": "completed",
                "invitees": event.get("invitees", []),
                "price": calendly_price,
                "duration_minutes": event.get("duration_minutes", 60),
            }
            consultations.append(consultation)

        return consultations

    except Exception as e:
        print(f"[!] Ошибка при получении консультаций из Calendly: {e}", file=sys.stderr)
        return []


# ─── SUPABASE DATABASE ACCESS ──────────────────────────────────
# Высокоуровневые функции для доступа к таблицам Supabase
# Требует SUPABASE_SERVICE_ROLE_KEY в .env для обхода RLS

def _get_supa():
    """Загрузить модуль supa с обработкой ошибок."""
    try:
        import supa
        if not supa.available():
            raise Exception("Supabase не настроен (нет SUPABASE_URL или ключа)")
        return supa
    except ImportError:
        raise Exception("Модуль supa не найден в tools/")


def get_ig_posts(days=30, limit=100):
    """Получить публикации Instagram из Supabase (ig_posts таблица).

    Возвращает список:
    [
        {
            "media_id": "...",
            "post_date": "2026-06-08",
            "media_type": "IMAGE",
            "theme": "attachment",
            "reach": 1234,
            "likes": 45,
            "comments": 8,
            "caption": "...",
            "permalink": "..."
        }
    ]
    """
    try:
        supa = _get_supa()
        cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).date().isoformat()
        rows = supa.select(
            "ig_posts",
            columns="media_id,post_date,media_type,theme,reach,likes,comments,caption,permalink",
            filters={"post_date": f"gte.{cutoff_date}"},
            order="post_date.desc",
            limit=limit
        )
        return rows
    except Exception as e:
        print(f"[!] Ошибка при получении Instagram постов: {e}", file=sys.stderr)
        return []


def get_telegram_leads(status=None, days=30, limit=100):
    """Получить Telegram лидов из Supabase (telegram_leads таблица).

    status: None (все), 'new', 'warm', 'hot', 'converted', 'inactive'

    Возвращает список:
    [
        {
            "tg_user_id": "...",
            "tg_username": "...",
            "tg_name": "...",
            "status": "new",
            "wrote_want": true,
            "messages_count": 5,
            "last_message": "...",
            "created_at": "2026-06-08T10:30:00Z"
        }
    ]
    """
    try:
        supa = _get_supa()
        cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        filters = {"created_at": f"gte.{cutoff_date}"}
        if status:
            filters["status"] = f"eq.{status}"

        rows = supa.select(
            "telegram_leads",
            columns="tg_user_id,tg_username,tg_name,status,wrote_want,messages_count,last_message,created_at",
            filters=filters,
            order="created_at.desc",
            limit=limit
        )
        return rows
    except Exception as e:
        print(f"[!] Ошибка при получении Telegram лидов: {e}", file=sys.stderr)
        return []


def get_purchases(days=30, limit=100):
    """Получить покупки из Supabase (purchases таблица).

    Возвращает список:
    [
        {
            "id": "...",
            "user_id": "...",
            "product_id": "...",
            "amount_cad": 37.00,
            "currency": "CAD",
            "payment_method": "gumroad",
            "status": "completed",
            "created_at": "2026-06-08T10:30:00Z"
        }
    ]
    """
    try:
        supa = _get_supa()
        cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        rows = supa.select(
            "purchases",
            columns="id,user_id,product_id,amount_cad,currency,payment_method,status,created_at",
            filters={
                "created_at": f"gte.{cutoff_date}",
                "status": "eq.completed"
            },
            order="created_at.desc",
            limit=limit
        )
        return rows
    except Exception as e:
        print(f"[!] Ошибка при получении покупок: {e}", file=sys.stderr)
        return []


def get_consultations_from_db(days=30, limit=100):
    """Получить консультации из Supabase (consultations таблица).

    Возвращает список:
    [
        {
            "id": "...",
            "user_id": "...",
            "type": "single",
            "status": "completed",
            "scheduled_at": "2026-06-08T10:00:00Z",
            "completed_at": "2026-06-08T11:00:00Z",
            "duration_min": 60,
            "platform": "zoom"
        }
    ]
    """
    try:
        supa = _get_supa()
        cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()

        rows = supa.select(
            "consultations",
            columns="id,user_id,type,status,scheduled_at,completed_at,duration_min,platform",
            filters={
                "completed_at": f"gte.{cutoff_date}",
                "status": "eq.completed"
            },
            order="completed_at.desc",
            limit=limit
        )
        return rows
    except Exception as e:
        print(f"[!] Ошибка при получении консультаций: {e}", file=sys.stderr)
        return []


def get_supabase_status():
    """Проверить статус подключения к Supabase."""
    try:
        supa = _get_supa()
        return supa.status()
    except Exception as e:
        return {"error": str(e), "can_write": False}
