"""Стас — Офис-менеджер. python manager.py

Операционный агент: ревью работы других агентов, метрики офиса и задачи
(action items). Действует проактивно — сначала собирает данные инструментами,
потом даёт приоритеты и измеримый план.

Задачи пишутся в локальный JSON (reports/office_actions.json). Позже сюда же
можно подключить Supabase — достаточно заменить _read_actions/_write_actions.
"""
import re
from datetime import datetime, timedelta
from base import *

# Клиент Supabase (БД проекта mila-platform). tools/ уже в sys.path (добавляет base).
try:
    import supa
except Exception:
    supa = None

SYSTEM = """Ты — Стас, Chief of Staff Людмилы Лыковой и движок самоулучшения офиса
(self-improving system). Команда агентов: Марина — маркетинг, Виктория — редактура,
Алина — клиенты, Дима — финансы, Тёма — Telegram, Оля — тренды, Вася — планирование,
Лера — продажи, Кирилл — продюсер. Ты не просто следишь — ты ЭВОЛЮЦИОНИРУЕШЬ офис.

ЦИКЛ САМОУЛУЧШЕНИЯ (твоя главная работа):
собрать данные → найти узкое место → предложить улучшение (на данных) → применить →
залогировать → через неделю измерить результат → повторить.
- Данные: db_query (БД Supabase: products/purchases/consultations/telegram_leads/kpi_snapshots/
  content/ig_posts) + measure_metrics + office_review + read_agent_prompt + отчёты reports/
  (digest_week_*, kpi_week_*, posts_*, comments_*, account_*). БД — первичный источник по
  продажам/лидам/консультациям. ВАЖНО: сейчас в .env только publishable-ключ → запись в БД
  запрещена RLS, а часть таблиц читается пусто (db_status покажет). Если db_query вернул 0 строк
  по продажам/лидам — это, скорее всего, RLS, а не «нет данных»: скажи, что нужен
  SUPABASE_SERVICE_ROLE_KEY, и не выдумывай цифры.
- Узкое место ищи по воронке: где теряются деньги/лиды ПРЯМО СЕЙЧАС, с конкретными цифрами.
- Улучшение агента применяй инструментом improve_agent: он делает бэкап исходника в
  backups/agents/, дописывает инструкцию в prompt_overrides/<агент>.md (код агента НЕ меняется)
  и пишет запись в improvement_log.md. Изменение применяется со следующего сообщения агента
  (overrides читаются на каждом ответе — перезапуск не нужен).
- Эксперименты (один A/B тест = одна переменная на неделю) логируй через log_experiment.
- /прогресс — improvement_history: что меняли и что получили.

ПРАВИЛА БЕЗОПАСНОСТИ (строго):
- Никогда не меняй агента без объяснения ПОЧЕМУ и НА КАКИХ ДАННЫХ. improve_agent требует
  rationale и data — без них откажись.
- Меняешь только промпты агентов (через overrides) — не их код, не base/webapp/tools, не себя.
- Перед изменением — бэкап (делается автоматически). Любое изменение обратимо: revert_agent.
- Одно улучшение за раз, потом измерь эффект. Не ломай то, что работает.

Также ревьюишь приложение (app_review) и мыслишь как бизнес-стратег: связываешь метрики
с деньгами и ростом, а не только с задачами.

БИЗНЕС-МОДЕЛЬ (опора для расчётов — не выдумывай другие цифры):
- Ниша: женщины 25–45, болезненные отношения / тревожная привязанность; русскоязычная аудитория.
- Воронка: Reels (охват) → подписка → Telegram → практикум $37 → бесплатная диагностика 20 мин
  → консультация $120 → пакеты $420 (4 сессии) / $750 (8 сессий).
- Дифференциатор: метод «Точки выбора» + личная история Людмилы (эмиграция, свой путь).

СТРАТЕГИЧЕСКОЕ МЫШЛЕНИЕ:
- Думай юнит-экономикой по воронке: охват → подписчики → лиды (ХОЧУ/комменты/DM) → продажи →
  доход и LTV. Где узкое горлышко и где рычаг с наибольшим ROI?
- Разделяй три рычага: рост (привлечение), конверсия (воронка), удержание/допродажи (LTV, пакеты).
- Предлагай 2–3 стратегические ставки: гипотеза → ожидаемый эффект в цифрах → как проверим →
  стоимость/риск. Дешёвые быстрые эксперименты помечай отдельно.
- Бери факты из инструментов и отчётов (measure_metrics, digest_week_*, kpi_week_*, аналитика по
  Gumroad у Димы/Леры). Не знаешь цифру — скажи, какой отчёт нужен, не выдумывай.
- Операционные задачи (процессы, quick wins) и стратегические ставки (рост, экономика) — разные
  вещи: на стратегические вопросы отвечай гипотезами, эффектом и метриками, а не списком галочек.

ТОН: деловой, коротко, конкретно. Приоритеты и quick wins, без воды.

ФОРМАТ ОТВЕТА (всегда соблюдай):
1. Резюме в 1–2 предложениях.
2. 3 приоритетных шага — P1/P2/P3, у каждого исполнитель и срок.
3. 2 измеримых KPI.
4. Короткий измеримый план: что и к какому сроку сделать.

ПРАВИЛА:
- Работай от данных: сначала собери факты инструментами (office_review / measure_metrics /
  list_reports), потом делай выводы. НЕ выдумывай цифры — бери их из инструментов.
- К каждому действию давай измеримый критерий приёмки (как поймём, что сделано).
- Quick wins (выполнимо за ≤72 ч) помечай как P1.
- Никогда не меняй продакшн-данные автоматически без явного подтверждения. create_action
  только фиксирует задачу в списке — это безопасно. Любые публикации/рассылки — только после
  явного «подтверждаю» и силами профильного агента, не твоими.
- Предложения по улучшению ПРИЛОЖЕНИЯ давай только по данным app_review (не выдумывай файлы и
  цифры). Баги и проблемы безопасности — всегда P1. Сам код не правишь — оформляешь задачу
  через create_action с измеримым критерием.

ИНСТРУМЕНТЫ:
- office_review(agent, since) — ревью логов/отчётов за период (agent='all' или имя; since='24h','7d'…).
- measure_metrics(period) — метрики офиса за период (24h/week/month).
- list_reports(limit) — последние отчёты из reports/.
- app_review(scope) — техобзор кода приложения (модули, маркеры долга/рисков): основа для
  предложений по улучшению. scope='all' или 'mila-office'/'tools'/'mila-agent'.
- create_action(title, assignee, due_in_days, priority) — записать задачу в список офиса.
- read_file/write_file/list_files — файлы рабочей папки."""

# ─── Хранилище задач и пути ──────────────────────────────
ACTIONS_PATH = MILA_FOLDER / "reports" / "office_actions.json"
LOGS_DIR = MILA_FOLDER / "logs"
REPORTS_DIR = MILA_FOLDER / "reports"
_LOG_TS = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(.*)$")


def _parse_since(s):
    """'24h' / '7d' / 'week' / 'month' → datetime-порог. Дефолт — 24 часа назад."""
    s = (s or "").strip().lower()
    named = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=30)}
    if s in named:
        return datetime.now() - named[s]
    m = re.fullmatch(r"(\d+)\s*([hd])", s)
    if m:
        n = int(m.group(1))
        return datetime.now() - (timedelta(hours=n) if m.group(2) == "h" else timedelta(days=n))
    return datetime.now() - timedelta(hours=24)


def _safe_dt(s):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _read_actions():
    try:
        return json.loads(ACTIONS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


def _write_actions(actions):
    ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIONS_PATH.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")


def _count_items(p):
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for k in ("comments", "posts", "leads", "data"):
            if isinstance(data.get(k), list):
                return len(data[k])
        return len(data)
    return None


def _recent_reports(limit=10, cutoff=None):
    out = []
    if not REPORTS_DIR.exists():
        return out
    files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files:
        if p.name == "office_actions.json":
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        if cutoff and mtime < cutoff:
            continue
        out.append({"name": p.name, "time": mtime.strftime("%Y-%m-%d %H:%M"),
                    "items": _count_items(p)})
        if len(out) >= limit:
            break
    return out


# ─── ИНСТРУМЕНТЫ ─────────────────────────────────────────
def office_review(agent="all", since="24h"):
    """Сводка логов + свежих отчётов + открытых задач за период. agent — фокус-подсказка."""
    cutoff = _parse_since(since)
    logs, flags = {}, []
    if LOGS_DIR.exists():
        for f in sorted(LOGS_DIR.glob("*.log")):
            entries = []
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = _LOG_TS.match(line)
                low = line.lower()
                if m:
                    ts = _safe_dt(m.group(1))
                    if ts and ts >= cutoff:
                        entries.append({"time": m.group(1), "message": m.group(2)})
                elif "traceback" in low or "error" in low or "ошибка" in low:
                    entries.append({"time": None, "message": line.strip()[:200]})
            if entries:
                logs[f.stem] = entries[-50:]
                errs = sum(1 for e in entries
                           if any(w in e["message"].lower() for w in ("error", "ошибка", "traceback")))
                if errs:
                    flags.append(f"{f.stem}.log: {errs} строк(и) с ошибками")
    open_tasks = [a for a in _read_actions() if a.get("status") == "open"]
    return json.dumps({
        "agent": agent, "since": since, "cutoff": cutoff.strftime("%Y-%m-%d %H:%M"),
        "logs": logs, "recent_reports": _recent_reports(10, cutoff),
        "flags": flags, "open_tasks": open_tasks,
    }, ensure_ascii=False, indent=2)


def measure_metrics(period="week"):
    """Базовые метрики офиса за период."""
    cutoff = _parse_since(period)
    reports = _recent_reports(1000, cutoff)
    actions = _read_actions()
    now = datetime.now()
    open_tasks = [a for a in actions if a.get("status") == "open"]
    overdue = [a for a in open_tasks
               if (_safe_dt(a.get("due")) and _safe_dt(a["due"]) < now)]
    ttc = []
    for a in actions:
        if a.get("status") == "done":
            c, d = _safe_dt(a.get("created")), _safe_dt(a.get("closed"))
            if c and d:
                ttc.append((d - c).total_seconds() / 3600)
    metrics = {
        "period": period,
        "reports_count": len(reports),
        "posts_reports_in_period": sum(1 for r in reports if r["name"].startswith("posts_")),
        "open_tasks": len(open_tasks),
        "overdue_tasks": len(overdue),
        "avg_time_to_close_hours": round(sum(ttc) / len(ttc), 1) if ttc else None,
    }
    return json.dumps(metrics, ensure_ascii=False, indent=2)


def list_reports(limit=10):
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 10
    return json.dumps(_recent_reports(limit), ensure_ascii=False, indent=2)


_APP_DIRS = ("mila-office", "tools", "mila-agent")
# Маркер долга в каноничной форме — слово с двоеточием или скобкой сразу после.
# Так не ловим само определение/описание маркеров (где после слова идёт | или запятая).
_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b\s*[:(]")


def app_review(scope="all"):
    """Технический обзор кода приложения: инвентарь модулей + маркеры долга/рисков.
    Читает только *.py (никогда .env и секреты) — даёт Стасу факты для предложений."""
    dirs = _APP_DIRS if scope in ("all", "", None) else (scope,)
    modules, todos, shell_true, bare_except, dyn_exec = [], [], [], [], []
    total_lines, test_files = 0, 0
    for d in dirs:
        base_dir = MILA_FOLDER / d
        if not base_dir.exists():
            continue
        for p in sorted(base_dir.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(MILA_FOLDER).as_posix()
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            modules.append({"path": rel, "lines": len(lines)})
            total_lines += len(lines)
            if p.name.startswith("test_") or p.name.endswith("_test.py") or "tests" in p.parts:
                test_files += 1
            for i, ln in enumerate(lines, 1):
                # TODO-маркеры живут в комментариях — сканируем всю строку.
                if _MARKER_RE.search(ln):
                    todos.append({"file": rel, "line": i, "text": ln.strip()[:120]})
                # Риски кода проверяем по коду без комментария, чтобы не ловить
                # упоминания в комментах/докстрингах (например «раньше был shell=True»).
                code = ln.split("#", 1)[0]
                # Только реальный вызов с shell=True, не упоминания/описания.
                if re.search(r"(subprocess|\.run\(|\.Popen\()[^#]*shell\s*=\s*True", code):
                    shell_true.append({"file": rel, "line": i})
                if re.match(r"\s*except\s*:\s*$", code):
                    bare_except.append({"file": rel, "line": i})
                if re.search(r"\b(eval|exec)\s*\(", code):
                    dyn_exec.append({"file": rel, "line": i, "text": ln.strip()[:120]})
    # ошибки в логе webapp за 24ч — сигнал текущих проблем приложения
    log_errors = 0
    wl = MILA_FOLDER / "logs" / "webapp.log"
    if wl.exists():
        for ln in wl.read_text(encoding="utf-8", errors="replace").splitlines():
            if " ERROR " in ln:
                log_errors += 1
    cap = lambda xs: xs[:30]
    return json.dumps({
        "scope": scope,
        "totals": {"files": len(modules), "lines": total_lines, "test_files": test_files},
        "biggest_modules": sorted(modules, key=lambda m: m["lines"], reverse=True)[:15],
        "markers": {
            "todo_fixme": cap(todos),
            "shell_true": cap(shell_true),
            "bare_except": cap(bare_except),
            "eval_exec": cap(dyn_exec),
        },
        "webapp_log_errors": log_errors,
    }, ensure_ascii=False, indent=2)


def create_action(title, assignee="", due_in_days=3, priority="P2"):
    """Фиксирует задачу (action item) в локальном списке офиса. Ничего не публикует."""
    actions = _read_actions()
    try:
        days = int(due_in_days)
    except (ValueError, TypeError):
        days = 3
    created = datetime.now()
    task = {
        "id": max([a.get("id", 0) for a in actions], default=0) + 1,
        "title": title,
        "assignee": assignee or "—",
        "priority": (priority or "P2").upper(),
        "status": "open",
        "created": created.strftime("%Y-%m-%d %H:%M"),
        "due": (created + timedelta(days=days)).strftime("%Y-%m-%d %H:%M"),
    }
    actions.append(task)
    _write_actions(actions)
    log("office", f"Action #{task['id']} [{task['priority']}] {title} -> {task['assignee']} (due {task['due']})")
    return json.dumps({"created": task}, ensure_ascii=False, indent=2)


# ─── ДВИЖОК САМОУЛУЧШЕНИЯ ─────────────────────────────────
# Стас читает и улучшает промпты агентов БЕЗ правки их кода: улучшение пишется в
# prompt_overrides/<агент>.md (подмешивается к SYSTEM на лету в base.compose_system).
# Перед каждым улучшением — бэкап исходника и запись в improvement_log.md.
_AGENT_FILES = {
    "marina": "agent.py", "victoria": "victoria.py", "alina": "alina.py",
    "dima": "dima.py", "tyoma": "tyoma.py", "olya": "olya.py",
    "vasya": "vasya.py", "lera": "lera.py", "producer": "producer.py",
    "rita": "rita.py",
}  # себя (manager) Стас не правит автоматически
_OFFICE_DIR = MILA_FOLDER / "mila-office"
_BACKUP_DIR = MILA_FOLDER / "backups" / "agents"
# Версионирование overrides: снимок файла prompt_overrides/<agent>.md ПЕРЕД каждым
# изменением → откат на N шагов (#8). Снимки тут, по агенту, с меткой времени.
_OVERRIDE_HISTORY = MILA_FOLDER / "MILA-BUSINESS" / "05-analytics" / "prompt_overrides" / ".history"
IMPROVEMENT_LOG = MILA_FOLDER / "MILA-BUSINESS" / "05-analytics" / "improvement_log.md"
_SYSTEM_RE = re.compile(r"SYSTEM(?:_PROMPT)?\s*=\s*(\"\"\"|''')(.*?)\1", re.S)


def _snapshot_overrides(agent, ts):
    """Сохраняет текущее состояние prompt_overrides/<agent>.md (или пустого) в
    .history/<agent>/<ts>.md — чтобы можно было откатиться на N шагов назад."""
    ofile = PROMPT_OVERRIDES_DIR / f"{agent}.md"
    snap_dir = _OVERRIDE_HISTORY / agent
    snap_dir.mkdir(parents=True, exist_ok=True)
    content = ofile.read_text(encoding="utf-8") if ofile.exists() else ""
    (snap_dir / f"{ts}.md").write_text(content, encoding="utf-8")


def _override_snapshots(agent):
    """Список снимков агента, новейшие — в конце (по имени = времени)."""
    snap_dir = _OVERRIDE_HISTORY / agent
    if not snap_dir.exists():
        return []
    return sorted(snap_dir.glob("*.md"))


def _log_improvement(line):
    IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(IMPROVEMENT_LOG, "a", encoding="utf-8") as f:
        f.write(f"- [{datetime.now():%Y-%m-%d %H:%M}] {line}\n")


def read_agent_prompt(agent):
    """Возвращает текущий SYSTEM агента + активные улучшения (overrides)."""
    agent = (agent or "").strip().lower()
    if agent not in _AGENT_FILES:
        return f"Неизвестный агент: {agent}. Доступны: {', '.join(_AGENT_FILES)}"
    try:
        text = (_OFFICE_DIR / _AGENT_FILES[agent]).read_text(encoding="utf-8")
    except OSError as e:
        return f"Ошибка чтения: {e}"
    m = _SYSTEM_RE.search(text)
    return json.dumps({
        "agent": agent,
        "system": (m.group(2).strip()[:4000] if m else "(SYSTEM не найден)"),
        "active_override": agent_overrides(agent)[:2000],
    }, ensure_ascii=False, indent=2)


# Максимум активных выводов в overrides одного агента. Старше — вытесняются
# (полная история остаётся в improvement_log.md). Защита от распухания промпта.
_MAX_ACTIVE_OVERRIDES = 7
# Секция override: "## <topic> — <ts>" … до следующей "## " или конца файла.
_OVERRIDE_SECTION_RE = re.compile(
    r"^##\s+(?P<topic>.+?)\s+—\s+(?P<ts>[\d_\-:]+)\s*$(?P<body>.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _parse_overrides(text):
    """Разбирает overrides-файл на список секций [{topic, ts, raw}]. Текст до
    первой '## ' (преамбула) сохраняется отдельно."""
    sections, preamble_end = [], None
    for m in _OVERRIDE_SECTION_RE.finditer(text):
        if preamble_end is None:
            preamble_end = m.start()
        sections.append({"topic": m.group("topic").strip(),
                         "ts": m.group("ts").strip(),
                         "raw": m.group(0).rstrip()})
    preamble = text[:preamble_end] if preamble_end is not None else (text if not sections else "")
    return preamble.rstrip(), sections


def improve_agent(agent, addition, rationale="", data="", topic=""):
    """Применяет улучшение промпта агента через overrides со СТРАТЕГИЕЙ ВЫТЕСНЕНИЯ:
    вывод по той же теме (topic) заменяет старый, активных ≤ _MAX_ACTIVE_OVERRIDES;
    вытесненное уходит в improvement_log.md. Требует rationale + data.

    topic — короткий тег темы (напр. «хуки», «тема-отношения»). Если пуст — берём
    из первых слов addition, чтобы повторные выводы по одной теме не накапливались."""
    agent = (agent or "").strip().lower()
    if agent not in _AGENT_FILES:
        return f"Неизвестный агент: {agent}. Доступны: {', '.join(_AGENT_FILES)}"
    if not (addition or "").strip():
        return "Нужен текст улучшения (addition)."
    if not (rationale or "").strip() or not (data or "").strip():
        return ("⛔ Правило безопасности: не меняю агента без обоснования и данных. "
                "Передай rationale (почему) и data (на каких цифрах/наблюдениях основано).")
    topic = (topic or " ".join(addition.strip().split()[:4])).strip().lower()
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # 1) бэкап исходника агента (как было)
    src = _OFFICE_DIR / _AGENT_FILES[agent]
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if src.exists():
        (_BACKUP_DIR / f"{_AGENT_FILES[agent]}.{ts}.bak").write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8")

    # 2) читаем текущие overrides, парсим на секции
    PROMPT_OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    ofile = PROMPT_OVERRIDES_DIR / f"{agent}.md"
    text = ofile.read_text(encoding="utf-8") if ofile.exists() else ""
    # снимок ДО изменения — для отката на N шагов (revert_agent steps=N)
    _snapshot_overrides(agent, ts)
    preamble, sections = _parse_overrides(text)

    # 3) вытеснение: убрать прежнюю секцию с тем же topic
    evicted = [s for s in sections if s["topic"] == topic]
    sections = [s for s in sections if s["topic"] != topic]
    for s in evicted:
        _log_improvement(f"EVICT {agent}/{topic}: вытеснен прежний вывод ({s['ts']})")

    # 4) новая секция
    new_section = (f"## {topic} — {ts}\n{addition.strip()}\n"
                   f"_Основание: {rationale.strip()} · Данные: {data.strip()}_")
    sections.append({"topic": topic, "ts": ts, "raw": new_section})

    # 5) кап по количеству: старейшие сверх лимита вытесняем в лог
    if len(sections) > _MAX_ACTIVE_OVERRIDES:
        sections.sort(key=lambda s: s["ts"])  # старые первыми
        overflow = sections[:len(sections) - _MAX_ACTIVE_OVERRIDES]
        sections = sections[len(overflow):]
        for s in overflow:
            _log_improvement(f"EVICT {agent}/{s['topic']}: вытеснен по лимиту ({s['ts']})")

    # 6) пересобрать файл (преамбула + активные секции, новейшие снизу)
    sections.sort(key=lambda s: s["ts"])
    head = (preamble + "\n\n") if preamble.strip() else ""
    ofile.write_text(head + "\n\n".join(s["raw"] for s in sections) + "\n", encoding="utf-8")

    _log_improvement(f"IMPROVE {agent}/{topic}: {addition.strip()[:80]} | почему: "
                     f"{rationale.strip()[:60]} | данные: {data.strip()[:60]}")
    return (f"✓ Улучшение «{agent}» по теме «{topic}» применено (вытеснение по теме; "
            f"активных выводов: {len(sections)}/{_MAX_ACTIVE_OVERRIDES}; исходник в backups/agents/ {ts}).\n"
            f"Применяется со следующего сообщения. Откат: revert_agent('{agent}').")


def revert_agent(agent, steps=0):
    """Откат улучшений агента.

    steps=0 (по умолчанию) — убрать ВСЕ улучшения (вернуть исходный промпт).
    steps=N>0 — откатить на N изменений назад: восстановить override-файл из
    снимка, сделанного перед N-м с конца улучшением. Так, если Стас сделал
    5 плохих апдейтов подряд, revert_agent(agent, steps=3) вернёт состояние
    до последних трёх."""
    agent = (agent or "").strip().lower()
    if agent not in _AGENT_FILES:
        return f"Неизвестный агент: {agent}. Доступны: {', '.join(_AGENT_FILES)}"
    ofile = PROMPT_OVERRIDES_DIR / f"{agent}.md"
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    try:
        steps = int(steps)
    except (ValueError, TypeError):
        steps = 0

    if steps <= 0:
        # полный откат — снести overrides
        if not ofile.exists():
            return f"У «{agent}» нет активных улучшений."
        _snapshot_overrides(agent, ts)  # снимок текущего перед сносом (можно вернуть)
        (PROMPT_OVERRIDES_DIR / f"{agent}.md.{ts}.removed").write_text(
            ofile.read_text(encoding="utf-8"), encoding="utf-8")
        ofile.unlink()
        _log_improvement(f"REVERT {agent}: все улучшения убраны (копия сохранена)")
        return f"✓ Откат «{agent}»: все улучшения убраны. Действует со следующего сообщения."

    # откат на N шагов: каждый improve делал снимок ДО себя, поэтому снимок с
    # индексом -steps = состояние до последних N улучшений.
    snaps = _override_snapshots(agent)
    if len(snaps) < steps:
        return (f"У «{agent}» только {len(snaps)} снимков — нельзя откатить на {steps}. "
                f"Доступно шагов: {len(snaps)} (или revert_agent('{agent}') — полный откат).")
    target = snaps[-steps]
    _snapshot_overrides(agent, ts)  # снимок текущего (чтобы откат тоже был обратим)
    restored = target.read_text(encoding="utf-8")
    if restored.strip():
        ofile.write_text(restored, encoding="utf-8")
    elif ofile.exists():
        ofile.unlink()  # снимок был пустой → состояние «без улучшений»
    _log_improvement(f"REVERT {agent}: откат на {steps} шаг(ов) к снимку {target.stem}")
    return (f"✓ Откат «{agent}» на {steps} шаг(ов): восстановлено состояние "
            f"{target.stem}. Действует со следующего сообщения.")


def log_experiment(hypothesis, variable="", metric=""):
    """Логирует один A/B-эксперимент недели (одна переменная)."""
    if not (hypothesis or "").strip():
        return "Нужна гипотеза эксперимента."
    _log_improvement(f"EXPERIMENT: {hypothesis.strip()[:100]} | переменная: "
                     f"{(variable or '—').strip()[:60]} | метрика: {(metric or '—').strip()[:60]}")
    return (f"✓ Эксперимент залогирован. Меняем ОДНУ переменную: {variable or '—'}. "
            f"Через неделю измерь «{metric or '—'}» и сравни в /прогресс.")


def improvement_history(limit=30):
    """История изменений офиса из improvement_log.md."""
    try:
        lines = IMPROVEMENT_LOG.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return "История пуста — улучшений ещё не было."
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 30
    tail = [ln for ln in lines if ln.strip()][-limit:]
    return "\n".join(tail) or "История пуста."


_DB_TABLES = ("products", "digital_products", "purchases", "consultations", "telegram_leads",
              "kpi_snapshots", "content", "ig_posts", "users")


def db_query(table, columns="*", limit=20):
    """Читает таблицу БД (Supabase). Чтение под RLS: без service-role ключа
    продакшн-таблицы (purchases/leads/…) могут вернуть пусто — это не «нет данных»,
    а политика доступа. Запись недоступна, пока в .env нет SUPABASE_SERVICE_ROLE_KEY."""
    if supa is None or not supa.available():
        return "БД (Supabase) не настроена: нет SUPABASE_URL/ключа в tools/.env."
    table = (table or "").strip()
    if table not in _DB_TABLES:
        return f"Неизвестная таблица: {table}. Доступны: {', '.join(_DB_TABLES)}"
    try:
        rows = supa.select(table, columns=columns or "*", limit=int(limit or 20))
    except supa.SupabaseError as e:
        return f"Ошибка БД: {e}"
    note = ""
    if not rows and not supa.can_write():
        note = ("\n(0 строк. Возможно, RLS скрывает данные от publishable-ключа — "
                "добавь SUPABASE_SERVICE_ROLE_KEY для полного чтения.)")
    return json.dumps({"table": table, "count": len(rows), "rows": rows},
                      ensure_ascii=False, indent=2, default=str) + note


def db_status():
    """Статус подключения к БД (есть ли запись)."""
    if supa is None:
        return "Клиент supa недоступен."
    return json.dumps(supa.status(), ensure_ascii=False, indent=2)


TOOLS = core_tools("Прочитать лог/отчёт/файл рабочей папки",
                   "Сохранить отчёт-ревью или заметку",
                   "Показать файлы (логи/отчёты)",
                   list_default="reports") + [
    {"name": "office_review",
     "description": "Ревью логов и свежих отчётов за период. agent='all' или имя агента; since='24h','7d','week'.",
     "input_schema": {"type": "object", "properties": {
         "agent": {"type": "string", "default": "all"},
         "since": {"type": "string", "default": "24h"}}}},
    {"name": "measure_metrics",
     "description": "Метрики офиса за период: отчёты, открытые/просроченные задачи, среднее время закрытия.",
     "input_schema": {"type": "object", "properties": {
         "period": {"type": "string", "default": "week"}}}},
    {"name": "list_reports",
     "description": "Последние отчёты из reports/ с числом записей.",
     "input_schema": {"type": "object", "properties": {
         "limit": {"type": "integer", "default": 10}}}},
    {"name": "app_review",
     "description": "Техобзор кода приложения: модули, размеры, маркеры долга/рисков (TODO, shell=True, bare except, eval/exec), ошибки в логе. scope='all' или 'mila-office'/'tools'/'mila-agent'.",
     "input_schema": {"type": "object", "properties": {
         "scope": {"type": "string", "default": "all"}}}},
    {"name": "create_action",
     "description": "Записать задачу (action item) в список офиса. Только фиксация, без публикаций.",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"},
         "assignee": {"type": "string"},
         "due_in_days": {"type": "integer", "default": 3},
         "priority": {"type": "string", "enum": ["P1", "P2", "P3"], "default": "P2"}},
         "required": ["title"]}},
    {"name": "read_agent_prompt",
     "description": "Прочитать текущий SYSTEM-промпт агента + активные улучшения. agent: marina/victoria/alina/dima/tyoma/olya/vasya/lera/producer/rita.",
     "input_schema": {"type": "object", "properties": {"agent": {"type": "string"}}, "required": ["agent"]}},
    {"name": "improve_agent",
     "description": "Применить улучшение промпта агента (через overrides; бэкап + лог автоматом). "
                    "ТРЕБУЕТ rationale и data. Вывод по той же теме (topic) ВЫТЕСНЯЕТ старый — "
                    "промпт не распухает. Применяется со следующего сообщения агента.",
     "input_schema": {"type": "object", "properties": {
         "agent": {"type": "string"},
         "addition": {"type": "string", "description": "Что дописать в промпт агента"},
         "rationale": {"type": "string", "description": "Почему — гипотеза/логика"},
         "data": {"type": "string", "description": "На каких цифрах/наблюдениях основано"},
         "topic": {"type": "string", "description": "Короткий тег темы (напр. «хуки», «тема-отношения»). Новый вывод по той же теме заменит старый."}},
         "required": ["agent", "addition", "rationale", "data"]}},
    {"name": "revert_agent",
     "description": "Откат улучшений агента. steps=0 — убрать ВСЕ (исходный промпт); steps=N — "
                    "откатить на N изменений назад (если сделано N плохих апдейтов подряд).",
     "input_schema": {"type": "object", "properties": {
         "agent": {"type": "string"},
         "steps": {"type": "integer", "default": 0, "description": "0 = полный откат; N = на N шагов назад"}},
         "required": ["agent"]}},
    {"name": "log_experiment",
     "description": "Залогировать один A/B-эксперимент недели (одна переменная).",
     "input_schema": {"type": "object", "properties": {
         "hypothesis": {"type": "string"}, "variable": {"type": "string"}, "metric": {"type": "string"}},
         "required": ["hypothesis"]}},
    {"name": "improvement_history",
     "description": "История изменений офиса (improvement_log.md): что меняли и что получили.",
     "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 30}}}},
    {"name": "db_query",
     "description": "Прочитать таблицу БД Supabase: products/purchases/consultations/telegram_leads/kpi_snapshots/content/ig_posts/users. Чтение под RLS (без service-role ключа продакшн-таблицы могут вернуть пусто).",
     "input_schema": {"type": "object", "properties": {
         "table": {"type": "string"}, "columns": {"type": "string", "default": "*"},
         "limit": {"type": "integer", "default": 20}}, "required": ["table"]}},
    {"name": "db_status",
     "description": "Статус подключения к БД Supabase (читаем/пишем; нужен ли service-role ключ).",
     "input_schema": {"type": "object", "properties": {}}},
]


def handle(name, inp):
    if name == "office_review":
        return office_review(inp.get("agent", "all"), inp.get("since", "24h"))
    if name == "measure_metrics":
        return measure_metrics(inp.get("period", "week"))
    if name == "list_reports":
        return list_reports(inp.get("limit", 10))
    if name == "app_review":
        return app_review(inp.get("scope", "all"))
    if name == "create_action":
        # title формально required, но модель может его не передать — не падаем
        # с KeyError (это уходило в лог как ERROR), а просим уточнить.
        title = (inp.get("title") or "").strip()
        if not title:
            return "Не могу создать задачу: нужно непустое поле title (краткое описание)."
        return create_action(title, inp.get("assignee", ""),
                             inp.get("due_in_days", 3), inp.get("priority", "P2"))
    if name == "read_agent_prompt":
        return read_agent_prompt(inp.get("agent", ""))
    if name == "improve_agent":
        return improve_agent(inp.get("agent", ""), inp.get("addition", ""),
                             inp.get("rationale", ""), inp.get("data", ""),
                             inp.get("topic", ""))
    if name == "revert_agent":
        return revert_agent(inp.get("agent", ""), inp.get("steps", 0))
    if name == "log_experiment":
        return log_experiment(inp.get("hypothesis", ""), inp.get("variable", ""), inp.get("metric", ""))
    if name == "improvement_history":
        return improvement_history(inp.get("limit", 30))
    if name == "db_query":
        return db_query(inp.get("table", ""), inp.get("columns", "*"), inp.get("limit", 20))
    if name == "db_status":
        return db_status()
    res = core_handle(name, inp, list_default="reports")
    return res if res is not None else f"Неизвестный инструмент: {name}"


QUICK = {
    "/отчёт":      "Полный цикл самоулучшения: собери данные (measure_metrics + последние отчёты reports/), найди узкие места воронки и дай список улучшений с приоритетами и данными",
    "/узкое":      "Найди ОДНО главное узкое место, где офис теряет деньги/лиды прямо сейчас — с конкретными цифрами и тем, какого отчёта не хватает, если данных нет",
    "/улучши":     "Прочитай промпты агентов (read_agent_prompt), найди слабое место по данным и предложи конкретный апгрейд; примени топ-1 через improve_agent с обоснованием и данными",
    "/эксперимент": "Спроектируй один A/B-тест на неделю (одна переменная): гипотеза, что меняем, метрика — и залогируй через log_experiment",
    "/прогресс":   "Покажи историю изменений офиса (improvement_history): что меняли, зачем и что получили",
    "/стратегия":  "Как бизнес-стратег: разбери воронку и юнит-экономику по последним отчётам, найди узкое горлышко и дай топ-3 ставки роста — гипотеза, эффект в цифрах, метрика, риск",
    "/автоматизировать": "Предложи, что автоматизировать (скрипт/шаблон), с критериями успеха и оценкой времени",
    "/улучшения":  "Сделай app_review и предложи топ-3 технических улучшения приложения с приоритетами",
}

if __name__ == "__main__":
    chat_loop("Стас", "🗂️", "bright_blue", SYSTEM, TOOLS, handle, QUICK)
