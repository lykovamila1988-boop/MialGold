# -*- coding: utf-8 -*-
"""
MILA OFFICE — веб-версия (чат с агентами в браузере).

Запуск:
    cd "E:\\MILA GOLD\\mila-office"
    python webapp.py
Откроется http://127.0.0.1:5000 — по агенту на вкладку, как в макете.

Бэкенд переиспользует тех же 8 агентов (base.run_agent + их SYSTEM/TOOLS/handle).
История диалога хранится на сервере по агенту (локальное приложение, один пользователь).
"""
import sys
# Принудительно UTF-8 для консоли Windows — до любого вывода/логирования
# (иначе русский и ✓/эмодзи в логах и stdout превращаются в кракозябры).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

import importlib
import logging
import os
import secrets
import threading
import uuid
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify, redirect, session, Response, abort

import base

# ─── Логирование ─────────────────────────────────────────
# Полный traceback пишем в файл, клиенту отдаём безопасное сообщение.
_LOG_FILE = base.MILA_FOLDER / "logs" / "webapp.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("mila.webapp")

# ─── Реестр агентов ──────────────────────────────────────
# Марина (office/agent.py) — со своим run_agent(msg, history).
marina = importlib.import_module("agent")

_mods = {
    "victoria": importlib.import_module("victoria"),
    "alina":    importlib.import_module("alina"),
    "dima":     importlib.import_module("dima"),
    "tyoma":    importlib.import_module("tyoma"),
    "olya":     importlib.import_module("olya"),
    "vasya":    importlib.import_module("vasya"),
    "lera":     importlib.import_module("lera"),
    "manager":  importlib.import_module("manager"),
    "producer": importlib.import_module("producer"),
}

_client = base.get_client()


def _office_responder(mod, key):
    # compose_system подмешивает улучшения Стаса (prompt_overrides/<key>.md) к SYSTEM.
    def respond(msg, history):
        return base.run_agent(_client, base.compose_system(key, mod.SYSTEM),
                              mod.TOOLS, mod.handle, msg, history, agent_key=key)
    return respond


def _marina_responder():
    # Марина со своим run_tool, но через общий runner — чтобы тоже получать улучшения.
    def respond(msg, history):
        return base.run_agent(_client, base.compose_system("marina", marina.SYSTEM_PROMPT),
                              marina.TOOLS, marina.run_tool, msg, history, agent_key="marina")
    return respond


def _chips(mod):
    """Берёт быстрые команды агента → [{label, prompt}] (без /помощь, /выход)."""
    quick = getattr(mod, "QUICK", None) or getattr(mod, "QUICK_COMMANDS", {}) or {}
    out = []
    for k, v in quick.items():
        if k in ("/помощь", "/выход"):
            continue
        out.append({"label": k.lstrip("/").capitalize(), "prompt": v})
    return out[:6]


AGENTS = {
    "marina": {
        "name": "Марина", "role": "Маркетолог", "emoji": "📣", "color": "#C4614A",
        "intro": "Привет, Людмила! 👋 Я Марина — твой маркетолог по личному бренду.\n\n"
                 "Я знаю твою нишу, продукты и цели. Готова помочь с контентом, "
                 "стратегией роста и монетизацией.\n\nС чего начнём? Выбери быстрое "
                 "действие внизу — или напиши свой вопрос.",
        "responder": _marina_responder(), "chips": _chips(marina),
    },
    "victoria": {
        "name": "Виктория", "role": "Редактор", "emoji": "✍️", "color": "#4A7A5E",
        "intro": "Я Виктория, редактор. Пришли текст поста — проверю голос, "
                 "пунктуацию, хук и CTA, дам оценку и финальную версию.",
        "responder": _office_responder(_mods["victoria"], "victoria"), "chips": _chips(_mods["victoria"]),
    },
    "alina": {
        "name": "Алина", "role": "Клиенты", "emoji": "👩", "color": "#2B7A8B",
        "intro": "Я Алина, менеджер клиентов. Помогу разобрать анкеты, определить "
                 "паттерн, подготовить тебя к сессии и вести истории клиенток.",
        "responder": _office_responder(_mods["alina"], "alina"), "chips": _chips(_mods["alina"]),
    },
    "dima": {
        "name": "Дима", "role": "Финансы", "emoji": "💰", "color": "#2C5F3A",
        "intro": "Я Дима, финансы. Посчитаю доход, сравню с целями, построю прогноз. "
                 "Для продаж с Gumroad нужен GUMROAD_ACCESS_TOKEN в .env.",
        "responder": _office_responder(_mods["dima"], "dima"), "chips": _chips(_mods["dima"]),
    },
    "tyoma": {
        "name": "Тёма", "role": "Telegram", "emoji": "💬", "color": "#2B5278",
        "intro": "Я Тёма, Telegram-менеджер. Напишу посты для канала и welcome-цепочку. "
                 "Для публикации нужен TELEGRAM_BOT_TOKEN в .env.",
        "responder": _office_responder(_mods["tyoma"], "tyoma"), "chips": _chips(_mods["tyoma"]),
    },
    "olya": {
        "name": "Оля", "role": "Тренды", "emoji": "🔍", "color": "#6B3FA0",
        "intro": "Я Оля, тренды. Найду вирусные темы, разберу конкурентов и дам "
                 "конкретные хуки для Reels.",
        "responder": _office_responder(_mods["olya"], "olya"), "chips": _chips(_mods["olya"]),
    },
    "vasya": {
        "name": "Вася", "role": "Планировщик", "emoji": "📅", "color": "#8B4513",
        "intro": "Я Вася, планировщик. Составлю расписание публикаций на неделю/месяц "
                 "и напомню, что нужно снять.",
        "responder": _office_responder(_mods["vasya"], "vasya"), "chips": _chips(_mods["vasya"]),
    },
    "lera": {
        "name": "Лера", "role": "Продажи", "emoji": "🎯", "color": "#A84F3C",
        "intro": "Я Лера, продажи. Напишу продающие тексты, разберу воронку и придумаю "
                 "акции для практикума.",
        "responder": _office_responder(_mods["lera"], "lera"), "chips": _chips(_mods["lera"]),
    },
    "manager": {
        "name": "Стас", "role": "Офис-менеджер", "emoji": "🗂️", "color": "#5C6B7A",
        "intro": "Я Стас, офис-менеджер и бизнес-стратег. Делаю ревью работы агентов, считаю "
                 "метрики офиса, веду задачи — и мыслю воронкой, юнит-экономикой и ставками "
                 "роста. Дам приоритеты, KPI и измеримый план.\n\nНачни с быстрого действия "
                 "внизу — «Обзор за 24ч» или «Стратегия».",
        "responder": _office_responder(_mods["manager"], "manager"), "chips": _chips(_mods["manager"]),
    },
    "producer": {
        "name": "Кирилл", "role": "Продюсер", "emoji": "🎬", "color": "#C8962C",
        "intro": "Я Кирилл, продюсер эксперта. Отвечаю за бизнес самой Людмилы: продуктовую "
                 "линейку, запуски, позиционирование и рост дохода — не «пост на завтра», а "
                 "«как вырасти за квартал».\n\nНачни с быстрого действия — «Линейка» или «Запуск».",
        "responder": _office_responder(_mods["producer"], "producer"), "chips": _chips(_mods["producer"]),
    },
}

# Состояние чата хранится по браузерной сессии, чтобы вкладки/пользователи
# не читали и не сбрасывали историю друг друга.
_histories = {}
_locks = {k: threading.Lock() for k in AGENTS}  # свой замок на агента → разные агенты параллельны
_jobs_lock = threading.Lock()

# Фоновые задачи: агент может думать десятки секунд. Не держим HTTP-запрос
# открытым — кладём вызов в пул, фронтенд опрашивает /api/result.
_pool = ThreadPoolExecutor(max_workers=4)
_jobs = OrderedDict()    # job_id -> {"status": ...}; ограничен по размеру, читается один раз
MAX_JOBS = 200           # бэкстоп против утечки незабранных задач
MAX_HISTORY_MSGS = 40    # ~20 последних реплик user/assistant на агента (защита памяти/токенов)

app = Flask(__name__)
# Нужен для session (CSRF-state в OAuth). Локальное single-user приложение —
# эфемерного ключа на процесс достаточно; можно зафиксировать через FLASK_SECRET_KEY.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(16)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("MILA_HTTPS", "").lower() in ("1", "true", "yes"),
)


def _session_id():
    sid = session.get("sid")
    if not sid:
        sid = secrets.token_urlsafe(24)
        session["sid"] = sid
    return sid


def _csrf_token():
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def _same_origin_request():
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return True
    host_url = request.host_url.rstrip("/")
    return origin.startswith(host_url)


@app.before_request
def _protect_post_routes():
    if request.method != "POST":
        return
    if not _same_origin_request():
        abort(403)
    if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), _csrf_token()):
        abort(403)


def _session_histories(sid):
    return _histories.setdefault(sid, {k: [] for k in AGENTS})


def _trim(history):
    """Обрезает историю до последних MAX_HISTORY_MSGS сообщений.

    base.run_agent кладёт в history только пары user/assistant (tool-блоки живут
    в локальном messages), поэтому срез по границе сохраняет порядок и не рвёт пары.
    """
    return history[-MAX_HISTORY_MSGS:] if len(history) > MAX_HISTORY_MSGS else history


def _set_job(job_id, value):
    """Кладёт результат задачи и держит размер _jobs под MAX_JOBS (FIFO-вытеснение)."""
    with _jobs_lock:
        _jobs[job_id] = value
        _jobs.move_to_end(job_id)
        while len(_jobs) > MAX_JOBS:
            _jobs.popitem(last=False)


def _run_job(job_id, sid, key, msg):
    """Выполняется в фоновом потоке: вызывает агента, обновляет историю и job."""
    try:
        with _locks[key]:  # сериализуем вызовы одного агента; разные агенты идут параллельно
            histories = _session_histories(sid)
            reply, new_hist = AGENTS[key]["responder"](msg, histories[key])
            histories[key] = _trim(new_hist)
        _set_job(job_id, {"status": "done", "sid": sid, "reply": reply})
    except Exception:
        logger.exception("Ошибка агента %s (job %s)", key, job_id)
        _set_job(job_id, {"status": "done", "sid": sid, "error": "Внутренняя ошибка — см. логи (logs/webapp.log)"})


@app.get("/api/meta")
def meta():
    _session_id()
    return jsonify({
        "csrf": _csrf_token(),
        "agents": [
            {"key": k, "name": a["name"], "role": a["role"], "emoji": a["emoji"],
             "color": a["color"], "intro": a["intro"], "chips": a["chips"]}
            for k, a in AGENTS.items()
        ]
    })


@app.post("/api/chat")
def chat():
    sid = _session_id()
    data = request.get_json(force=True)
    key = data.get("agent")
    msg = (data.get("message") or "").strip()
    if key not in AGENTS:
        return jsonify({"error": "Неизвестный агент"}), 400
    if not msg:
        return jsonify({"error": "Пустое сообщение"}), 400
    # Не блокируем запрос на время раздумий агента — ставим задачу в пул.
    job_id = uuid.uuid4().hex
    _set_job(job_id, {"status": "pending", "sid": sid})
    _pool.submit(_run_job, job_id, sid, key, msg)
    return jsonify({"job": job_id}), 202


@app.get("/api/result")
def result():
    sid = _session_id()
    job_id = request.args.get("job", "")
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None and job.get("sid") != sid:
            job = None
        if job is not None and job.get("status") != "pending":
            _jobs.pop(job_id, None)  # результат забран — освобождаем память (читается один раз)
    if job is None:
        return jsonify({"error": "Задача не найдена"}), 404
    if job["status"] == "pending":
        return jsonify({"status": "pending"})
    # Готово: либо reply, либо error — фронтенд рендерит как раньше.
    return jsonify({k: v for k, v in job.items() if k != "status"})


@app.post("/api/reset")
def reset():
    sid = _session_id()
    key = (request.get_json(force=True) or {}).get("agent")
    histories = _session_histories(sid)
    if key in histories:
        with _locks[key]:  # не сбрасываем историю, пока агент думает
            histories[key] = []
    return jsonify({"ok": True})


# ─── Настройки и подключения (статус + Instagram OAuth) ──
# Instagram API использует OAuth (в отличие от Anthropic Messages API — там только
# ключ). Здесь — реальный flow «Instagram API with Instagram Login»:
# authorize → callback → обмен кода на short-lived → обмен на long-lived → запись в .env.
IG_OAUTH_AUTHORIZE = "https://www.instagram.com/oauth/authorize"
IG_OAUTH_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
IG_OAUTH_LONGLIVED = "https://graph.instagram.com/access_token"
IG_OAUTH_SCOPES = ("instagram_business_basic,instagram_business_manage_comments,"
                   "instagram_business_manage_messages,instagram_business_content_publish,"
                   "instagram_business_manage_insights")
# Meta требует HTTPS-redirect, точно зарегистрированный в кабинете приложения
# (плоский http и 127.0.0.1 отклоняются — отсюда «Invalid redirect_uri»).
# При MILA_HTTPS=1 приложение поднимается по https и redirect — https://localhost.
_HTTPS = os.getenv("MILA_HTTPS", "").lower() in ("1", "true", "yes")
IG_REDIRECT_URI = os.getenv("IG_OAUTH_REDIRECT_URI") or (
    "https://localhost:5000/auth/instagram/callback" if _HTTPS
    else "http://127.0.0.1:5000/auth/instagram/callback")


def _ig_app_creds():
    return (os.getenv("IG_APP_ID") or os.getenv("META_APP_ID"),
            os.getenv("IG_APP_SECRET") or os.getenv("META_APP_SECRET"))


def _integration_status():
    """Статусы подключений без раскрытия секретов — только флаги/режимы."""
    cid, _ = _ig_app_creds()
    return {
        "claude": {"configured": bool(base.ANTHROPIC_KEY or base.ANTHROPIC_AUTH_TOKEN),
                   "mode": "auth_token (Bearer)" if base.ANTHROPIC_AUTH_TOKEN else "api_key (x-api-key)",
                   "oauth": False,
                   "note": "У Messages API нет публичного OAuth — авторизация по ключу."},
        "gemini": {"configured": bool(base.GEMINI_KEY),
                   "model": base.GEMINI_MODEL,
                   "provider": base.LLM_PROVIDER,
                   "heavy_lifting": base.LLM_PROVIDER in ("gemini", "google"),
                   "anthropic_agents": sorted(base.ANTHROPIC_AGENT_KEYS)},
        "instagram": {"configured": bool(base.INSTAGRAM_TOKEN), "flow": base.IG_FLOW,
                      "node": base.IG_NODE or "", "oauth": bool(cid),
                      "redirect_uri": IG_REDIRECT_URI},
        "telegram": {"configured": bool(base.TELEGRAM_TOKEN), "oauth": False},
        "gumroad": {"configured": bool(base.GUMROAD_TOKEN), "oauth": False},
    }


def _update_env(updates):
    """In-place обновление ключей в tools/.env, сохраняя остальные строки."""
    env_path = base.MILA_FOLDER / "tools" / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    for key, val in updates.items():
        if not val:
            continue
        for i, ln in enumerate(lines):
            if ln.strip().startswith(f"{key}="):
                lines[i] = f"{key}={val}"
                break
        else:
            lines.append(f"{key}={val}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _oauth_done(title, msg):
    return Response(
        f"<!doctype html><meta charset=utf-8><body style='font-family:Georgia,serif;"
        f"max-width:560px;margin:60px auto;color:#1E140F'>"
        f"<h2 style='color:#C4614A'>{title}</h2><p>{msg}</p>"
        f"<p><a href='/settings'>← Настройки</a></p></body>", mimetype="text/html")


@app.get("/api/settings")
def api_settings():
    _session_id()
    status = _integration_status()
    status["csrf"] = _csrf_token()
    return jsonify(status)


@app.get("/settings")
def settings_page():
    return Response(SETTINGS_HTML, mimetype="text/html")


@app.get("/auth/instagram/login")
def ig_login():
    cid, csec = _ig_app_creds()
    if not cid or not csec:
        return ("Instagram OAuth не настроен: задай IG_APP_ID и IG_APP_SECRET "
                "(или META_APP_ID/META_APP_SECRET) в tools/.env и зарегистрируй redirect URI "
                f"({IG_REDIRECT_URI}) в кабинете Meta."), 400
    state = secrets.token_urlsafe(16)
    session["ig_state"] = state
    params = {"client_id": cid, "redirect_uri": IG_REDIRECT_URI, "response_type": "code",
              "scope": IG_OAUTH_SCOPES, "state": state}
    return redirect(IG_OAUTH_AUTHORIZE + "?" + urlencode(params))


@app.get("/auth/instagram/callback")
def ig_callback():
    if request.args.get("error"):
        return f"OAuth ошибка: {request.args.get('error_description') or request.args.get('error')}", 400
    code = request.args.get("code")
    if not code or request.args.get("state") != session.pop("ig_state", None):
        return "Неверный ответ OAuth (нет code или несовпадение state).", 400
    cid, csec = _ig_app_creds()
    try:
        r = requests.post(IG_OAUTH_TOKEN_URL, data={
            "client_id": cid, "client_secret": csec, "grant_type": "authorization_code",
            "redirect_uri": IG_REDIRECT_URI, "code": code}, timeout=15)
        r.raise_for_status()
        short = r.json()
        token, user_id = short.get("access_token"), str(short.get("user_id") or "")
        # short-lived → long-lived (~60 дней)
        rl = requests.get(IG_OAUTH_LONGLIVED, params={
            "grant_type": "ig_exchange_token", "client_secret": csec, "access_token": token}, timeout=15)
        long_token = rl.json().get("access_token", token) if rl.ok else token
        _update_env({"IG_API_FLOW": "instagram_login",
                     "IG_ACCESS_TOKEN": long_token, "IG_USER_ID": user_id})
        logger.info("Instagram OAuth: токен сохранён (user_id=%s)", user_id)
        return _oauth_done("Instagram подключён ✓",
                           "Долгоживущий токен сохранён в tools/.env. Перезапусти приложение, "
                           "чтобы агенты подхватили новый токен и scope комментариев.")
    except Exception:
        logger.exception("Instagram OAuth token exchange failed")
        return "Обмен кода на токен не удался — подробности в logs/webapp.log.", 500


@app.post("/api/settings/instagram-token")
def ig_save_token():
    """Ручное подключение Instagram: проверяем вставленный токен через
    graph.instagram.com/me (без redirect URI!) и сохраняем в tools/.env.
    Надёжный путь на localhost, когда Meta отклоняет redirect_uri."""
    data = request.get_json(force=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "Пустой токен"}), 400
    try:
        r = requests.get("https://graph.instagram.com/v21.0/me",
                         params={"fields": "user_id,username", "access_token": token}, timeout=10)
        info = r.json()
        if "error" in info:
            return jsonify({"ok": False, "error": info["error"].get("message", "невалидный токен")}), 400
        user_id = str(info.get("user_id") or info.get("id") or (data.get("user_id") or ""))
        _update_env({"IG_API_FLOW": "instagram_login",
                     "IG_ACCESS_TOKEN": token, "IG_USER_ID": user_id})
        logger.info("IG token сохранён вручную (user=%s)", info.get("username"))
        return jsonify({"ok": True, "username": info.get("username"), "user_id": user_id})
    except Exception:
        logger.exception("manual IG token save failed")
        return jsonify({"ok": False, "error": "Не удалось проверить/сохранить токен — см. логи"}), 500


@app.get("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


# ─── Фронтенд (один файл, без внешних зависимостей/CDN) ───
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MILA OFFICE</title>
<style>
  :root{
    --t:#C4614A; --n:#1E140F; --c:#FAF6F1; --m:#F2EAE2;
    --u:#7A5E54; --b:#E0D0C8; --w:#fff;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--c);color:var(--n);height:100vh;display:flex;overflow:hidden}
  #side{width:84px;background:var(--n);display:flex;flex-direction:column;align-items:center;padding:14px 0;gap:8px;flex-shrink:0;overflow-y:auto}
  #side .logo{color:var(--t);font-size:10px;letter-spacing:2px;margin-bottom:8px;text-align:center;line-height:1.3}
  .apill{width:54px;height:54px;border-radius:16px;border:2px solid transparent;background:rgba(255,255,255,.06);display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;transition:.15s;color:#cbb}
  .apill:hover{background:rgba(255,255,255,.12)}
  .apill.active{background:rgba(255,255,255,.10)}
  .apill .em{font-size:20px;line-height:1}
  .apill .nm{font-size:9px;margin-top:3px;color:#cbb}
  #main{flex:1;display:flex;flex-direction:column;min-width:0}
  header{background:var(--n);padding:16px 22px;display:flex;align-items:center;gap:14px}
  header .av{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;color:#fff;flex-shrink:0}
  header .ttl{flex:1;min-width:0}
  header .ttl .nm{font-size:19px;font-weight:bold;color:#fff}
  header .ttl .sub{font-size:12px;color:#9a8278;margin-top:2px}
  header .toggle{background:rgba(196,97,74,.18);color:var(--t);border:1px solid var(--t);border-radius:8px;padding:8px 14px;font-size:12px;cursor:pointer;font-family:inherit}
  .chips{display:flex;gap:10px;flex-wrap:wrap;padding:14px 22px;background:var(--m);border-bottom:1px solid var(--b)}
  .chip{background:var(--w);border:1px solid var(--b);border-radius:20px;padding:9px 18px;font-size:13px;cursor:pointer;font-family:inherit;color:var(--n);transition:.15s}
  .chip:hover{border-color:var(--t);color:var(--t)}
  #chat{flex:1;overflow-y:auto;padding:24px 22px;display:flex;flex-direction:column;gap:16px}
  .row{display:flex;gap:12px;align-items:flex-start;max-width:78%}
  .row.me{align-self:flex-end;flex-direction:row-reverse}
  .row .av{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;color:#fff;flex-shrink:0}
  .bubble{background:var(--w);border:1px solid var(--b);border-radius:16px;padding:14px 18px;font-size:15px;line-height:1.6;white-space:pre-wrap;word-wrap:break-word}
  .row.me .bubble{background:var(--t);color:#fff;border-color:var(--t)}
  .bubble b{font-weight:bold}.bubble i{font-style:italic}
  .bubble code{background:rgba(0,0,0,.06);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:13px}
  .row.me .bubble code{background:rgba(255,255,255,.2)}
  .typing{font-size:13px;color:var(--u);font-style:italic;padding:0 22px 8px}
  footer{border-top:1px solid var(--b);background:var(--c);padding:16px 22px}
  .inbar{display:flex;gap:12px;align-items:flex-end;max-width:1000px;margin:0 auto}
  #inp{flex:1;border:1px solid var(--b);border-radius:22px;padding:13px 20px;font-size:15px;font-family:inherit;resize:none;max-height:160px;outline:none;background:var(--w)}
  #inp:focus{border-color:var(--t)}
  #send{width:46px;height:46px;border-radius:50%;border:none;background:var(--t);color:#fff;font-size:18px;cursor:pointer;flex-shrink:0}
  #send:disabled{opacity:.4;cursor:default}
  .hint{text-align:center;font-size:11px;color:var(--u);margin-top:8px}
</style>
</head>
<body>
  <div id="side"><div class="logo">MILA<br>OFFICE</div></div>
  <div id="main">
    <header>
      <div class="av" id="hav">M</div>
      <div class="ttl"><div class="nm" id="hname">…</div><div class="sub" id="hsub">@liudmyla.lykova · всегда онлайн</div></div>
      <button class="toggle" id="resetBtn">Очистить чат</button>
    </header>
    <div class="chips" id="chips"></div>
    <div id="chat"></div>
    <div class="typing" id="typing" style="display:none"></div>
    <footer>
      <div class="inbar">
        <textarea id="inp" rows="1" placeholder="Напиши сообщение…"></textarea>
        <button id="send" title="Отправить">➤</button>
      </div>
      <div class="hint">Enter — отправить · Shift+Enter — новая строка</div>
    </footer>
  </div>
<script>
let AGENTS=[], cur=null, CSRF='';

function postJSON(url, payload){
  return fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},
    body:JSON.stringify(payload||{})});
}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function md(s){
  s=esc(s);
  s=s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/(^|\n)\s*[-•]\s+/g,'$1• ');
  return s;
}
function agent(){return AGENTS.find(a=>a.key===cur);}

function addMsg(text, me){
  const chat=document.getElementById('chat');
  const a=agent();
  const row=document.createElement('div'); row.className='row'+(me?' me':'');
  const av=document.createElement('div'); av.className='av';
  av.style.background=me?'#7A5E54':a.color; av.textContent=me?'Я':a.emoji;
  const b=document.createElement('div'); b.className='bubble'; b.innerHTML=md(text);
  row.appendChild(av); row.appendChild(b); chat.appendChild(row);
  chat.scrollTop=chat.scrollHeight;
}

function renderAgent(){
  const a=agent();
  document.getElementById('hname').textContent=a.name+' — '+a.role;
  const hav=document.getElementById('hav'); hav.textContent=a.emoji; hav.style.background=a.color;
  document.getElementById('inp').placeholder='Спроси '+a.name+'…';
  const ch=document.getElementById('chips'); ch.innerHTML='';
  a.chips.forEach(c=>{
    const el=document.createElement('button'); el.className='chip'; el.textContent=c.label;
    el.onclick=()=>{ document.getElementById('inp').value=c.prompt; send(); };
    ch.appendChild(el);
  });
  document.querySelectorAll('.apill').forEach(p=>p.classList.toggle('active',p.dataset.k===cur));
  document.getElementById('chat').innerHTML='';
  addMsg(a.intro,false);
}

function switchAgent(k){ cur=k; renderAgent(); }

async function send(){
  const inp=document.getElementById('inp'); const text=inp.value.trim();
  if(!text) return;
  inp.value=''; inp.style.height='auto';
  addMsg(text,true);
  const t=document.getElementById('typing'); t.textContent=agent().name+' печатает…'; t.style.display='block';
  document.getElementById('send').disabled=true;
  try{
    const r=await postJSON('/api/chat',{agent:cur,message:text});
    const j=await r.json();
    if(j.error){ addMsg('⚠️ Ошибка: '+j.error,false); }
    else {
      // Агент думает в фоне — опрашиваем результат, пока не готов.
      const sleep=ms=>new Promise(r=>setTimeout(r,ms));
      let d=null;
      while(true){
        await sleep(1000);
        const rr=await fetch('/api/result?job='+encodeURIComponent(j.job));
        d=await rr.json();
        if(d.status!=='pending') break;
      }
      if(d.error) addMsg('⚠️ Ошибка: '+d.error,false);
      else addMsg(d.reply,false);
    }
  }catch(e){ addMsg('⚠️ Сеть недоступна: '+e,false); }
  t.style.display='none'; document.getElementById('send').disabled=false; inp.focus();
}

async function resetChat(){
  await postJSON('/api/reset',{agent:cur});
  renderAgent();
}

window.onload=async()=>{
  const d=await (await fetch('/api/meta')).json();
  AGENTS=d.agents;
  CSRF=d.csrf;
  const side=document.getElementById('side');
  AGENTS.forEach(a=>{
    const p=document.createElement('div'); p.className='apill'; p.dataset.k=a.key;
    p.innerHTML='<div class="em">'+a.emoji+'</div><div class="nm">'+a.name+'</div>';
    p.onclick=()=>switchAgent(a.key); side.appendChild(p);
  });
  const sp=document.createElement('div'); sp.className='apill'; sp.title='Настройки и подключения';
  sp.innerHTML='<div class="em">⚙</div><div class="nm">Настройки</div>';
  sp.onclick=()=>window.open('/settings','_blank'); side.appendChild(sp);
  const inp=document.getElementById('inp');
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} });
  inp.addEventListener('input',()=>{ inp.style.height='auto'; inp.style.height=Math.min(inp.scrollHeight,160)+'px'; });
  document.getElementById('send').onclick=send;
  document.getElementById('resetBtn').onclick=resetChat;
  switchAgent(AGENTS[0].key);
};
</script>
</body>
</html>"""


SETTINGS_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>MILA OFFICE · Настройки</title>
<style>
  body{margin:0;font-family:Georgia,'Times New Roman',serif;background:#FAF6F1;color:#1E140F}
  .wrap{max-width:720px;margin:0 auto;padding:28px 20px}
  h1{color:#C4614A;font-size:24px;margin:0 0 4px}
  .sub{color:#7A5E54;font-size:13px;margin-bottom:22px}
  .card{background:#fff;border:1px solid #E0D0C8;border-radius:14px;padding:18px 20px;margin-bottom:14px}
  .card h3{margin:0 0 6px;font-size:17px}
  .badge{display:inline-block;font-size:12px;padding:3px 10px;border-radius:20px;margin-left:8px;vertical-align:middle}
  .ok{background:#E3F0E6;color:#2C5F3A}.no{background:#F6E1DC;color:#A8412C}
  .meta{font-size:13px;color:#7A5E54;line-height:1.6;margin:6px 0 0}
  .btn{display:inline-block;margin-top:12px;background:#C4614A;color:#fff;border:none;border-radius:8px;
       padding:10px 18px;font-size:14px;font-family:inherit;cursor:pointer;text-decoration:none}
  .btn.dim{background:#B7A89F;cursor:default}
  code{background:rgba(0,0,0,.06);padding:1px 5px;border-radius:4px;font-family:monospace;font-size:12px}
  a.back{color:#7A5E54;font-size:13px}
</style></head><body><div class="wrap">
  <p><a class="back" href="/">← В чат</a></p>
  <h1>Настройки и подключения</h1>
  <div class="sub">Статус интеграций. Секреты не отображаются.</div>
  <div id="cards">Загрузка…</div>
<script>
let CSRF='';
function badge(ok){return '<span class="badge '+(ok?'ok':'no')+'">'+(ok?'подключено':'не настроено')+'</span>';}
async function saveToken(){
  const tok=document.getElementById('igtok').value.trim();
  const msg=document.getElementById('igmsg');
  if(!tok){ msg.textContent='Вставь токен'; return; }
  msg.textContent='Проверяю…';
  try{
    const r=await fetch('/api/settings/instagram-token',{method:'POST',
      headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},body:JSON.stringify({token:tok})});
    const d=await r.json();
    if(d.ok){ msg.innerHTML='✓ Сохранено: @'+(d.username||'?')+'. Перезапусти приложение, чтобы агенты подхватили токен.'; }
    else { msg.textContent='⚠️ '+(d.error||'ошибка'); }
  }catch(e){ msg.textContent='⚠️ сеть: '+e; }
}
async function load(){
  const s = await (await fetch('/api/settings')).json();
  CSRF=s.csrf;
  const el = document.getElementById('cards'); el.innerHTML='';
  // Claude
  el.innerHTML += '<div class="card"><h3>Claude (Anthropic)'+badge(s.claude.configured)+'</h3>'
    + '<p class="meta">Режим: <code>'+s.claude.mode+'</code><br>'+s.claude.note+'</p></div>';
  // Gemini
  el.innerHTML += '<div class="card"><h3>Gemini'+badge(s.gemini.configured)+'</h3>'
    + '<p class="meta">Provider: <code>'+s.gemini.provider+'</code> / model: <code>'+s.gemini.model+'</code><br>'
    + 'Heavy work: <code>'+(s.gemini.heavy_lifting?'Gemini':'Claude')+'</code> / Claude agents: <code>'
    + (s.gemini.anthropic_agents||[]).join(', ')+'</code></p></div>';
  // Instagram + OAuth
  const ig = s.instagram;
  let igc = '<div class="card"><h3>Instagram'+badge(ig.configured)+'</h3>'
    + '<p class="meta">Flow: <code>'+ig.flow+'</code> · node: <code>'+(ig.node||'—')+'</code><br>'
    + 'Redirect URI: <code>'+ig.redirect_uri+'</code> — зарегистрируй его в кабинете Meta '
    + '(часто нужен HTTPS; localhost-http может быть отклонён).</p>';
  if(ig.oauth){ igc += '<a class="btn" href="/auth/instagram/login">🔗 Подключить через OAuth</a>'; }
  else { igc += '<span class="btn dim">OAuth недоступен</span>'
    + '<p class="meta">Задай <code>IG_APP_ID</code> и <code>IG_APP_SECRET</code> в tools/.env.</p>'; }
  igc += '<hr style="border:none;border-top:1px solid #E0D0C8;margin:16px 0">'
    + '<p class="meta"><b>Или вставь токен вручную</b> — надёжно на localhost (без redirect URI). '
    + 'Сгенерируй в кабинете Meta токен с правом <code>instagram_business_manage_comments</code> и вставь сюда:</p>'
    + '<input id="igtok" placeholder="IG access token" '
    + 'style="width:100%;padding:9px 12px;border:1px solid #E0D0C8;border-radius:8px;'
    + 'font-family:monospace;font-size:12px;margin-bottom:8px">'
    + '<button class="btn" onclick="saveToken()">Проверить и сохранить</button> '
    + '<span id="igmsg" class="meta"></span>';
  igc += '</div>'; el.innerHTML += igc;
  // Telegram / Gumroad
  el.innerHTML += '<div class="card"><h3>Telegram'+badge(s.telegram.configured)+'</h3>'
    + '<p class="meta">Токен бота в <code>TELEGRAM_BOT_TOKEN</code> / <code>TELEGRAM_API</code>. OAuth не применяется.</p></div>';
  el.innerHTML += '<div class="card"><h3>Gumroad'+badge(s.gumroad.configured)+'</h3>'
    + '<p class="meta">Токен в <code>GUMROAD_ACCESS_TOKEN</code>. OAuth не применяется.</p></div>';
}
load();
</script></div></body></html>"""


def _open_browser():
    import time
    time.sleep(1.3)
    scheme = "https" if _HTTPS else "http"
    try:
        webbrowser.open(f"{scheme}://localhost:5000")
    except Exception:
        pass


if __name__ == "__main__":
    scheme = "https" if _HTTPS else "http"
    logger.info("MILA OFFICE web -> %s://localhost:5000  (Ctrl+C to stop)", scheme)
    if _HTTPS:
        logger.info("HTTPS включён (self-signed). Браузер один раз предупредит о сертификате.")
    logger.info("Логи: %s", _LOG_FILE)
    threading.Thread(target=_open_browser, daemon=True).start()
    # debug=False: traceback идёт в лог-файл, не в браузер. threaded=True —
    # чтобы /api/result опрашивался, пока фоновая задача ещё считается.
    # ssl_context='adhoc' (нужен пакет cryptography) — самоподписанный сертификат
    # для localhost: позволяет валидный https-redirect для Instagram OAuth.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True,
            ssl_context="adhoc" if _HTTPS else None)
