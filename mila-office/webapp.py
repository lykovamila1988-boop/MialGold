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
import json
import logging
import os
import re
import secrets
import threading
import uuid
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify, redirect, session, Response, abort

import base
import memory  # общая память офиса (профиль/фаза/события) — для дашборда

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
    "rita":     importlib.import_module("rita"),
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
    return out[:10]  # у Стаса 8 команд — лимит 6 их резал; держим запас


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
    "rita": {
        "name": "Рита", "role": "Продуктовый архитектор", "emoji": "📚", "color": "#9C5BA8",
        "intro": "Я Рита, архитектор цифровых продуктов. Превращаю идею в ясную структуру "
                 "(главы, упражнения, поток) — основу для PDF-воркбука, который напишет Марина "
                 "и отредактирует Виктория.\n\nНачни с «Воркбук» или опиши идею продукта.",
        "responder": _office_responder(_mods["rita"], "rita"), "chips": _chips(_mods["rita"]),
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
# Нужен для session (CSRF + OAuth-state). Ключ ДОЛЖЕН переживать перезапуск, иначе
# каждый рестарт инвалидирует session-cookie открытой вкладки → старый CSRF-токен не
# сходится с новым → POST /api/chat падает 403 (фронт ловит как «Сеть недоступна»).
# Берём из .env, иначе генерим один раз и кладём в .secret_key рядом с webapp.
def _persistent_secret():
    env = os.getenv("FLASK_SECRET_KEY")
    if env:
        return env
    f = Path(__file__).resolve().parent / ".secret_key"
    try:
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
        key = secrets.token_hex(32)
        f.write_text(key, encoding="utf-8")
        return key
    except OSError:
        return secrets.token_hex(32)  # фолбэк: хотя бы не падаем

app.secret_key = _persistent_secret()
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


# Короткое описание агента для тултипа (1-2 строки). Имена/роли — как в AGENTS.
_TAGLINES = {
    "marina":   "Контент, стратегия роста, аналитика Instagram.",
    "victoria": "Проверяет тексты перед публикацией: голос, хук, CTA.",
    "alina":    "Анкеты, подготовка к сессиям, CRM клиенток.",
    "dima":     "Доход, Gumroad, прогнозы и цели.",
    "tyoma":    "Telegram-канал, бот, welcome-цепочка.",
    "olya":     "Вирусные темы, тренды, конкуренты.",
    "vasya":    "Расписание публикаций и что нужно снять.",
    "lera":     "Воронка, офферы, конверсия в продажи.",
    "manager":  "Система, метрики офиса, самообучение.",
    "producer": "Продуктовая линейка, запуски, масштаб дохода.",
    "rita":     "Структура цифровых продуктов: воркбуки, гайды.",
}


@app.get("/api/meta")
def meta():
    _session_id()
    return jsonify({
        "csrf": _csrf_token(),
        "agents": [
            {"key": k, "name": a["name"], "role": a["role"], "emoji": a["emoji"],
             "color": a["color"], "intro": a["intro"], "chips": a["chips"],
             "tagline": _TAGLINES.get(k, "")}
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
    data = request.get_json(force=True) or {}
    histories = _session_histories(sid)
    if data.get("all"):
        # «Очистить сессию» — сбрасываем историю ВСЕХ агентов этой сессии.
        for k in list(histories.keys()):
            lock = _locks.get(k)
            if lock:
                with lock:  # не трогаем историю, пока агент думает
                    histories[k] = []
            else:
                histories[k] = []
        return jsonify({"ok": True, "cleared": "all"})
    key = data.get("agent")
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


def _probe(url, timeout=2.5):
    """Живой GET-пробник локального сервиса: up/down + код. Без секретов."""
    try:
        r = requests.get(url, timeout=timeout)
        return {"up": r.status_code < 500, "status": r.status_code}
    except Exception as e:
        return {"up": False, "error": type(e).__name__}


@app.get("/api/health")
def api_health():
    """Единая health-сводка: конфигурация LLM/каналов (флаги) + ЖИВЫЕ пробы
    локальных сервисов (n8n, bridge) + доступность Supabase. Безопасно —
    только статусы, без ключей."""
    cfg = _integration_status()
    n8n_url = os.getenv("N8N_BASE_URL", "http://127.0.0.1:5678").rstrip("/")
    bridge_port = os.getenv("N8N_BRIDGE_PORT", "5051")
    # Supabase: проверяем только наличие конфига (живой запрос требует supa+сети).
    try:
        import sys as _sys
        tdir = str(base.MILA_FOLDER / "tools")
        if tdir not in _sys.path:
            _sys.path.insert(0, tdir)
        import supa
        supa_state = {"configured": supa.available(), "can_write": supa.can_write()}
    except Exception:
        supa_state = {"configured": False, "can_write": False}

    health = {
        "gemini":   {"configured": cfg["gemini"]["configured"], "model": cfg["gemini"]["model"]},
        "claude":   {"configured": cfg["claude"]["configured"]},
        "telegram": {"configured": cfg["telegram"]["configured"]},
        "instagram": {"configured": cfg["instagram"]["configured"], "flow": cfg["instagram"]["flow"]},
        "supabase": supa_state,
        "n8n":      _probe(f"{n8n_url}/healthz"),
        "bridge":   _probe(f"http://127.0.0.1:{bridge_port}/health"),
    }
    # Сводный флаг: всё ли критичное поднято (LLM + хотя бы один канал).
    health["ok"] = bool(
        (health["gemini"]["configured"] or health["claude"]["configured"])
        and health["telegram"]["configured"]
    )
    return jsonify(health)


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


# ─── Дашборд Людмилы: «готовят → она одобряет» ───────────
# Собирает всё, что ждёт её решения, и даёт одну кнопку «Одобрить всё».
_POST_QUEUE = base.MILA_FOLDER / "MILA-BUSINESS" / "02-content" / "post_queue.json"
_OFFICE_ACTIONS = base.MILA_FOLDER / "reports" / "office_actions.json"
_OVERRIDES_DIR = base.MILA_FOLDER / "MILA-BUSINESS" / "05-analytics" / "prompt_overrides"


def _read_json_safe(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return default


def _pending_posts():
    """Посты в очереди, ждущие одобрения (не approved/published/needs_media)."""
    q = _read_json_safe(_POST_QUEUE, [])
    out = []
    for it in q:
        if it.get("status") in ("draft", "pending", "review", None):
            out.append({"id": it.get("id"), "when": it.get("when"),
                        "caption": (it.get("caption") or "")[:160],
                        "has_media": bool((it.get("media_url") or "").strip())})
    return out


def _open_actions():
    """Открытые задачи офиса от Стаса (office_actions.json)."""
    acts = _read_json_safe(_OFFICE_ACTIONS, [])
    return [{"id": a.get("id"), "title": a.get("title"), "assignee": a.get("assignee"),
             "priority": a.get("priority"), "due": a.get("due")}
            for a in acts if a.get("status") == "open"]


def _recent_events(limit=12):
    """Последние события из общей памяти (что агенты делали)."""
    f = base.MILA_FOLDER / "mila-office" / "memory" / "events.jsonl"
    try:
        lines = f.read_text(encoding="utf-8").splitlines()[-limit:]
    except (FileNotFoundError, OSError):
        return []
    out = []
    for ln in reversed(lines):
        try:
            e = json.loads(ln)
            out.append({"ts": e.get("ts", "")[:16].replace("T", " "),
                        "kind": e.get("kind", "")})
        except ValueError:
            continue
    return out


def _pending_improvements():
    """Активные улучшения Стаса (overrides) — что он предлагает агентам."""
    out = []
    if _OVERRIDES_DIR.exists():
        for f in sorted(_OVERRIDES_DIR.glob("*.md")):
            if f.name in ("README.md", "improvement_log.md"):
                continue
            txt = f.read_text(encoding="utf-8")
            topics = re.findall(r"^##\s+(.+?)\s+—", txt, re.MULTILINE)
            if topics:
                out.append({"agent": f.stem, "topics": topics})
    return out


@app.get("/api/dashboard")
def api_dashboard():
    _session_id()
    prof = {}
    try:
        prof = memory.read_profile().get("business", {})
    except Exception:
        pass
    return jsonify({
        "csrf": _csrf_token(),
        "pending_posts": _pending_posts(),
        "open_actions": _open_actions(),
        "improvements": _pending_improvements(),
        "events": _recent_events(),
        "profile": {"phase": (lambda: _safe_phase())(),
                    "followers": prof.get("ig_followers"),
                    "goal": prof.get("goal")},
    })


def _safe_phase():
    try:
        return memory.current_phase()
    except Exception:
        return "—"


@app.post("/api/approve-all")
def api_approve_all():
    """Главная кнопка: одобрить все черновики постов из очереди (status→approved).
    Безопасно: только посты, у которых есть медиа; публикует их потом publish_due
    по расписанию (не здесь). Улучшения Стаса и задачи — отдельными кнопками."""
    q = _read_json_safe(_POST_QUEUE, [])
    approved = 0
    for it in q:
        if it.get("status") in ("draft", "pending", "review", None):
            if (it.get("media_url") or "").strip():
                it["status"] = "approved"
                approved += 1
            else:
                it["status"] = "needs_media"
    if approved or q:
        try:
            Path(_POST_QUEUE).write_text(json.dumps(q, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        except OSError as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    try:
        memory.log_event("dashboard:approve_all", {"approved": approved})
    except Exception:
        pass
    return jsonify({"ok": True, "approved": approved})


@app.get("/dashboard")
def dashboard_page():
    return Response(DASHBOARD_HTML, mimetype="text/html")


@app.get("/operator")
def operator_page():
    return Response(OPERATOR_HTML, mimetype="text/html")


@app.get("/api/operator")
def api_operator():
    status = request.args.get("status") or None
    tasks = memory.list_tasks(status)
    approvals = memory.office_status().get("approvals", {})
    pending_approvals = {
        k: v for k, v in approvals.items()
        if v.get("status") in {"pending", "missing", "changes_requested"}
    }
    return jsonify({
        "ok": True,
        "csrf": _csrf_token(),
        "tasks": tasks,
        "status": memory.office_status(limit=30),
        "events": memory.recent_events(30),
        "pending_approvals": pending_approvals,
    })


@app.post("/api/operator/task/<task_id>/<action>")
def api_operator_task(task_id: str, action: str):
    body = request.get_json(silent=True) or {}
    if action == "retry":
        rec = memory.retry_task(task_id, reset_attempts=bool(body.get("reset_attempts")))
    elif action == "cancel":
        rec = memory.cancel_task(task_id, reason=body.get("reason", "operator"))
    elif action == "unblock":
        rec = memory.unblock_task(task_id)
    else:
        return jsonify({"ok": False, "error": f"unknown action: {action}"}), 400
    return jsonify({"ok": bool(rec.get("id")), "task": rec}), (200 if rec.get("id") else 400)


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
  /* Тултип агента — position:fixed (через JS), чтобы не обрезался overflow сайдбара.
     Появляется справа от кнопки при hover с задержкой 300ms. */
  .atip{position:fixed;z-index:30;width:220px;max-width:220px;
        background:#1E140F;border:1px solid #c08;border-radius:10px;padding:12px 14px;
        box-shadow:0 4px 16px rgba(0,0,0,.3);pointer-events:none;
        opacity:0;transform:translateX(-4px);transition:opacity .12s,transform .12s}
  .atip.show{opacity:1;transform:translateX(0)}
  .atip .h{font-size:12px;font-weight:bold;margin-bottom:6px}
  .atip .d{font-size:11px;color:#c0a898;line-height:1.5;margin-bottom:8px}
  .atip .cmds{display:flex;flex-wrap:wrap;gap:5px}
  .atip .cmd{font-size:10px;padding:2px 7px;border-radius:10px;color:#e6d7cc}
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
      <button class="toggle" id="resetSessBtn" title="Очистить переписку со всеми агентами">Очистить сессию</button>
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

async function postJSON(url, payload){
  const body=JSON.stringify(payload||{});
  let r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},body});
  // 403 = протухший CSRF (напр. сервер перезапускали). Обновляем токен и пробуем ещё раз.
  if(r.status===403){
    try{ const m=await (await fetch('/api/meta')).json(); CSRF=m.csrf; }catch(e){}
    r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},body});
  }
  return r;
}

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
// #RRGGBB + alpha → rgba(...) для полупрозрачного фона пилюль-команд в тултипе.
function hexA(hex,a){const h=(hex||'#888').replace('#','');
  const r=parseInt(h.substr(0,2),16),g=parseInt(h.substr(2,2),16),b=parseInt(h.substr(4,2),16);
  return 'rgba('+r+','+g+','+b+','+a+')';}
function md(s){
  s=esc(s);
  s=s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/(^|\n)\s*[-•]\s+/g,'$1• ');
  return s;
}
function agent(){return AGENTS.find(a=>a.key===cur);}

// UI-переписка по агенту: {agentKey: [{text, me}, ...]}. Бэкенд хранит свою
// историю (для контекста модели), а это — то, что видно на экране. Переключение
// агентов больше НЕ стирает переписку: для каждого реплеим её из этого стора.
const TRANSCRIPTS = {};

// Рисует один пузырь в DOM (без записи в стор).
function drawMsg(text, me){
  const chat=document.getElementById('chat');
  const a=agent();
  const row=document.createElement('div'); row.className='row'+(me?' me':'');
  const av=document.createElement('div'); av.className='av';
  av.style.background=me?'#7A5E54':a.color; av.textContent=me?'Я':a.emoji;
  const b=document.createElement('div'); b.className='bubble'; b.innerHTML=md(text);
  row.appendChild(av); row.appendChild(b); chat.appendChild(row);
  chat.scrollTop=chat.scrollHeight;
}

// Добавляет сообщение и в стор текущего агента, и на экран.
function addMsg(text, me){
  (TRANSCRIPTS[cur] = TRANSCRIPTS[cur] || []).push({text, me});
  drawMsg(text, me);
}

function renderAgent(){
  const a=agent();
  document.getElementById('hname').textContent=a.name+' — '+a.role;
  const hav=document.getElementById('hav'); hav.textContent=a.emoji; hav.style.background=a.color;
  document.getElementById('inp').placeholder='Спроси '+a.name+'…';
  const ch=document.getElementById('chips'); ch.innerHTML='';
  a.chips.forEach(c=>{
    const el=document.createElement('button'); el.className='chip'; el.textContent=c.label;
    el.title=c.prompt;  // подсказка при наведении — полный текст промпта
    el.onclick=()=>{ document.getElementById('inp').value=c.prompt; send(); };
    ch.appendChild(el);
  });
  document.querySelectorAll('.apill').forEach(p=>p.classList.toggle('active',p.dataset.k===cur));
  const chat=document.getElementById('chat'); chat.innerHTML='';
  const hist=TRANSCRIPTS[cur];
  if(hist && hist.length){ hist.forEach(m=>drawMsg(m.text, m.me)); }   // реплей сохранённой переписки
  else { drawMsg(a.intro,false); }                                     // первый визит — только intro
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
    if(!r.ok){ addMsg('⚠️ Сервер вернул '+r.status+' (попробуй обновить страницу).',false);
      t.style.display='none'; document.getElementById('send').disabled=false; return; }
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
  // Чистит переписку ТОЛЬКО текущего агента (UI + бэкенд-история).
  await postJSON('/api/reset',{agent:cur});
  TRANSCRIPTS[cur]=[];
  renderAgent();
}

async function resetSession(){
  // Чистит переписку со ВСЕМИ агентами (UI + бэкенд-истории всех).
  if(!confirm('Очистить переписку со всеми агентами?')) return;
  await postJSON('/api/reset',{all:true});
  for(const k in TRANSCRIPTS) delete TRANSCRIPTS[k];
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
    p.onclick=()=>switchAgent(a.key);

    // Тултип: заголовок (emoji·имя·роль) + описание + до 3 быстрых команд.
    // Лежит в body (position:fixed) — иначе overflow сайдбара его обрежет.
    const tip=document.createElement('div'); tip.className='atip';
    tip.style.borderColor=a.color;
    const cmds=(a.chips||[]).slice(0,3).map(c=>
      '<span class="cmd" style="background:'+hexA(a.color,.15)+'">/'+
      esc((c.label||'').toLowerCase())+'</span>').join('');
    tip.innerHTML='<div class="h" style="color:'+a.color+'">'+a.emoji+' '+esc(a.name)+
      ' · '+esc(a.role)+'</div>'+
      '<div class="d">'+esc(a.tagline||'')+'</div>'+
      (cmds?'<div class="cmds">'+cmds+'</div>':'');
    document.body.appendChild(tip);

    let timer=null;
    p.addEventListener('mouseenter',()=>{
      timer=setTimeout(()=>{
        const r=p.getBoundingClientRect();
        tip.style.left=(r.right+8)+'px';
        // не вылезать за низ окна
        tip.style.top=Math.min(r.top, window.innerHeight-tip.offsetHeight-8)+'px';
        tip.classList.add('show');
      },300);
    });
    p.addEventListener('mouseleave',()=>{ clearTimeout(timer); tip.classList.remove('show'); });

    side.appendChild(p);
  });
  const sp=document.createElement('div'); sp.className='apill'; sp.title='Настройки и подключения';
  sp.innerHTML='<div class="em">⚙</div><div class="nm">Настройки</div>';
  sp.onclick=()=>window.open('/settings','_blank'); side.appendChild(sp);
  const op=document.createElement('div'); op.className='apill'; op.title='Operator queue';
  op.innerHTML='<div class="em">Q</div><div class="nm">Queue</div>';
  op.onclick=()=>window.open('/operator','_blank'); side.appendChild(op);
  const inp=document.getElementById('inp');
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} });
  inp.addEventListener('input',()=>{ inp.style.height='auto'; inp.style.height=Math.min(inp.scrollHeight,160)+'px'; });
  document.getElementById('send').onclick=send;
  document.getElementById('resetBtn').onclick=resetChat;
  document.getElementById('resetSessBtn').onclick=resetSession;
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


# ─── Дашборд Людмилы (одна страница, кнопка «Одобрить всё») ──
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MILA — Дашборд</title>
<style>
  :root{--t:#C4614A;--n:#1E140F;--c:#FAF6F1;--m:#F2EAE2;--u:#7A5E54;--b:#E0D0C8;--w:#fff;--g:#4a7a5e;}
  *{box-sizing:border-box}
  body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--c);color:var(--n)}
  header{background:var(--n);padding:20px 28px}
  header .t{font-size:11px;color:var(--t);letter-spacing:3px}
  header .h{font-size:24px;color:var(--w);margin-top:4px}
  header .s{font-size:12px;color:#9a8278;margin-top:4px}
  .wrap{max-width:920px;margin:0 auto;padding:22px 20px 60px}
  .hero{background:var(--w);border:2px solid var(--t);border-radius:16px;padding:20px;margin-bottom:20px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
  .hero .sum{flex:1;min-width:220px;font-size:14px;color:var(--u);line-height:1.5}
  .hero .sum b{color:var(--n)}
  .approve{background:var(--t);color:#fff;border:none;border-radius:12px;padding:16px 30px;font-size:17px;font-family:inherit;cursor:pointer;font-weight:bold}
  .approve:hover{filter:brightness(1.08)}
  .approve:disabled{opacity:.5;cursor:default}
  .card{background:var(--w);border:1px solid var(--b);border-radius:14px;padding:18px 20px;margin-bottom:16px}
  .card h2{font-size:15px;margin:0 0 12px;color:var(--n)}
  .card h2 .n{color:var(--t);font-size:13px;margin-left:6px}
  .row{padding:9px 0;border-bottom:1px solid var(--m);font-size:13px;color:var(--n);line-height:1.5}
  .row:last-child{border:0}
  .row .meta{color:var(--u);font-size:11px}
  .empty{color:var(--u);font-size:13px;font-style:italic}
  .pill{display:inline-block;font-size:10px;padding:1px 8px;border-radius:8px;background:var(--m);color:var(--u);margin-right:6px}
  .pill.p1{background:#f6dcd6;color:#a23a28}
  .topbar{display:flex;gap:14px;margin-bottom:18px}
  .topbar a{font-size:12px;color:var(--t);text-decoration:none}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:640px){.grid{grid-template-columns:1fr}}
  #toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--g);color:#fff;padding:12px 22px;border-radius:10px;font-size:14px;display:none}
</style></head>
<body>
<header>
  <div class="t">УТРЕННИЙ ОБЗОР · MILA OFFICE</div>
  <div class="h">Дашборд Людмилы</div>
  <div class="s" id="sub">@liudmyla.lykova</div>
</header>
<div class="wrap">
  <div class="topbar"><a href="/">← к агентам</a><a href="/settings">настройки</a></div>

  <div class="hero">
    <div class="sum" id="summary">Загружаю…</div>
    <button class="approve" id="approveAll" disabled>Одобрить всё</button>
  </div>

  <div class="grid">
    <div class="card"><h2>📸 Посты на одобрение <span class="n" id="cPosts"></span></h2><div id="posts"></div></div>
    <div class="card"><h2>✅ Задачи офиса <span class="n" id="cActions"></span></h2><div id="actions"></div></div>
  </div>
  <div class="grid">
    <div class="card"><h2>⚙️ Улучшения от Стаса <span class="n" id="cImpr"></span></h2><div id="impr"></div></div>
    <div class="card"><h2>🕑 Что было ночью <span class="n" id="cEv"></span></h2><div id="events"></div></div>
  </div>
</div>
<div id="toast"></div>
<script>
let CSRF="";
function esc(s){return (s||"").replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',3500);}

async function load(){
  const d=await (await fetch('/api/dashboard')).json();
  CSRF=d.csrf;
  const ph=d.profile||{};
  document.getElementById('sub').textContent='@liudmyla.lykova · фаза: '+(ph.phase||'—')+(ph.followers?(' · '+ph.followers+' подписчиков'):'');
  const np=d.pending_posts.length, na=d.open_actions.length, ni=d.improvements.length;
  document.getElementById('summary').innerHTML=
    'Доброе утро! На одобрении: <b>'+np+'</b> пост(ов), <b>'+na+'</b> задач(и), <b>'+ni+'</b> улучшений агентов. '
    +(np?'Жми «Одобрить всё» — одобренные посты опубликуются по расписанию.':'Новых постов на одобрение нет.');
  const btn=document.getElementById('approveAll'); btn.disabled = np===0;

  // posts
  document.getElementById('cPosts').textContent=np||'';
  document.getElementById('posts').innerHTML = np ? d.pending_posts.map(p=>
    '<div class="row">'+esc(p.caption||'(без текста)')
    +'<div class="meta">'+(p.when?('⏰ '+esc(p.when)+' · '):'')+(p.has_media?'медиа ✓':'⚠️ нет медиа')+'</div></div>'
  ).join('') : '<div class="empty">Пусто</div>';

  // actions
  document.getElementById('cActions').textContent=na||'';
  document.getElementById('actions').innerHTML = na ? d.open_actions.map(a=>
    '<div class="row"><span class="pill '+((a.priority||'').toLowerCase()==='p1'?'p1':'')+'">'+esc(a.priority||'P?')+'</span>'
    +esc(a.title||'')+'<div class="meta">'+esc(a.assignee||'')+(a.due?(' · до '+esc(a.due)):'')+'</div></div>'
  ).join('') : '<div class="empty">Открытых задач нет</div>';

  // improvements
  document.getElementById('cImpr').textContent=ni||'';
  document.getElementById('impr').innerHTML = ni ? d.improvements.map(i=>
    '<div class="row"><b>'+esc(i.agent)+'</b><div class="meta">темы: '+i.topics.map(esc).join(', ')+'</div></div>'
  ).join('') : '<div class="empty">Активных улучшений нет</div>';

  // events
  document.getElementById('cEv').textContent=d.events.length||'';
  document.getElementById('events').innerHTML = d.events.length ? d.events.map(e=>
    '<div class="row">'+esc(e.kind)+'<div class="meta">'+esc(e.ts)+'</div></div>'
  ).join('') : '<div class="empty">Событий нет</div>';
}

document.getElementById('approveAll').onclick=async()=>{
  const btn=document.getElementById('approveAll'); btn.disabled=true;
  try{
    const r=await fetch('/api/approve-all',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},body:'{}'});
    const d=await r.json();
    if(d.ok){ toast('Одобрено постов: '+d.approved+'. Опубликуются по расписанию.'); load(); }
    else { toast('Ошибка: '+(d.error||'?')); btn.disabled=false; }
  }catch(e){ toast('Сеть недоступна'); btn.disabled=false; }
};
load();
</script></body></html>"""


OPERATOR_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MILA OFFICE · Operator</title>
<style>
  :root{--t:#C4614A;--n:#1E140F;--c:#FAF6F1;--m:#F2EAE2;--u:#7A5E54;--b:#E0D0C8;--w:#fff;--g:#4A7A5E;--r:#A8412C}
  *{box-sizing:border-box}
  body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--c);color:var(--n)}
  header{background:var(--n);padding:18px 24px;color:#fff}
  header .k{font-size:11px;color:var(--t);letter-spacing:2px}
  header .h{font-size:24px;margin-top:4px}
  .wrap{max-width:1120px;margin:0 auto;padding:20px}
  .top{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
  .top a,.top button{font-family:inherit;font-size:13px;color:var(--t);background:transparent;border:1px solid var(--b);border-radius:8px;padding:8px 12px;text-decoration:none;cursor:pointer}
  .tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
  .tab{background:#fff;border:1px solid var(--b);border-radius:8px;padding:8px 12px;font-family:inherit;cursor:pointer;color:var(--n)}
  .tab.on{border-color:var(--t);color:var(--t)}
  .grid{display:grid;grid-template-columns:2fr 1fr;gap:16px}
  .card{background:#fff;border:1px solid var(--b);border-radius:8px;padding:16px}
  h2{font-size:16px;margin:0 0 12px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;color:var(--u);font-weight:normal;border-bottom:1px solid var(--b);padding:7px}
  td{border-bottom:1px solid var(--m);padding:8px;vertical-align:top}
  .pill{display:inline-block;border-radius:6px;padding:2px 7px;background:var(--m);font-size:11px;color:var(--u)}
  .pending{color:#8B6B10}.running{color:#2B5278}.failed{color:var(--r)}.done{color:var(--g)}.cancelled{color:#777}.awaiting_approval{color:#8B4513}
  .actions{display:flex;gap:6px;flex-wrap:wrap}
  .actions button{border:1px solid var(--b);background:#fff;border-radius:7px;padding:5px 8px;font-size:12px;font-family:inherit;cursor:pointer}
  .actions button:hover{border-color:var(--t);color:var(--t)}
  .muted{color:var(--u);font-size:12px}
  .event{border-bottom:1px solid var(--m);padding:8px 0;font-size:13px}
  .event:last-child{border:0}
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--g);color:#fff;border-radius:8px;padding:10px 16px;display:none}
  @media(max-width:760px){.grid{grid-template-columns:1fr} th:nth-child(4),td:nth-child(4){display:none}}
</style></head><body>
<header><div class="k">MILA OFFICE · OPERATOR</div><div class="h">Queue Control</div></header>
<div class="wrap">
  <div class="top"><a href="/">Agents</a><a href="/dashboard">Dashboard</a><a href="/settings">Settings</a><button onclick="load()">Refresh</button></div>
  <div class="tabs" id="tabs"></div>
  <div class="grid">
    <div class="card"><h2>Tasks</h2><div id="tasks"></div></div>
    <div>
      <div class="card"><h2>Pending Approvals</h2><div id="approvals"></div></div>
      <div class="card"><h2>Recent Events</h2><div id="events"></div></div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
let CSRF='', FILTER='';
const statuses=['','pending','running','awaiting_approval','failed','done','cancelled'];
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function toast(s){const t=document.getElementById('toast');t.textContent=s;t.style.display='block';setTimeout(()=>t.style.display='none',2200);}
function tabName(s){return s||'all';}
function renderTabs(){
  document.getElementById('tabs').innerHTML=statuses.map(s=>'<button class="tab '+(s===FILTER?'on':'')+'" onclick="FILTER=\''+s+'\';load()">'+tabName(s)+'</button>').join('');
}
async function act(id, action){
  const body=action==='retry'?{reset_attempts:false}:action==='cancel'?{reason:'operator'}:{};
  const r=await fetch('/api/operator/task/'+encodeURIComponent(id)+'/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},body:JSON.stringify(body)});
  const d=await r.json();
  toast(d.ok ? action+' '+id : (d.error||'error'));
  load();
}
function actions(t){
  if(t.status==='running') return '';
  return '<div class="actions"><button onclick="act(\''+esc(t.id)+'\',\'retry\')">retry</button><button onclick="act(\''+esc(t.id)+'\',\'unblock\')">unblock</button><button onclick="act(\''+esc(t.id)+'\',\'cancel\')">cancel</button></div>';
}
async function load(){
  renderTabs();
  const url='/api/operator'+(FILTER?'?status='+encodeURIComponent(FILTER):'');
  const d=await (await fetch(url)).json();
  CSRF=d.csrf;
  const tasks=d.tasks||[];
  document.getElementById('tasks').innerHTML=tasks.length?'<table><thead><tr><th>ID</th><th>Pipeline</th><th>Status</th><th>Dedupe</th><th>Next</th><th></th></tr></thead><tbody>'+tasks.map(t=>
    '<tr><td>'+esc(t.id)+'<div class="muted">try '+esc(t.attempts||0)+'</div></td><td>'+esc(t.pipeline)+'</td><td><span class="'+esc(t.status)+'">'+esc(t.status)+'</span></td><td><span class="pill">'+esc(t.dedupe_key||'—')+'</span></td><td>'+esc(t.next_run_at||'')+'</td><td>'+actions(t)+'</td></tr>'
  ).join('')+'</tbody></table>':'<div class="muted">No tasks</div>';
  const approvals=d.pending_approvals||{};
  const ak=Object.keys(approvals);
  document.getElementById('approvals').innerHTML=ak.length?ak.map(k=>'<div class="event"><b>'+esc(k)+'</b><div class="muted">'+esc(approvals[k].status)+' · '+esc(approvals[k].comment||'')+'</div></div>').join(''):'<div class="muted">No pending approvals</div>';
  const ev=d.events||[];
  document.getElementById('events').innerHTML=ev.length?ev.map(e=>'<div class="event">'+esc(e.kind)+'<div class="muted">'+esc(e.ts)+' · '+esc(JSON.stringify(e.payload||{}))+'</div></div>').join(''):'<div class="muted">No events</div>';
}
load();
</script></body></html>"""


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
