"""Вася — Планировщик публикаций. python vasya.py

CHAIN_ID TRACKING:
─────────────────
Vasya отслеживает очередь публикаций по chain_id. Каждая цепочка планирования (расписание
на неделю, месяц, реакция на комментарий) имеет уникальный chain_id. Это позволяет:
  • быстро найти все посты, связанные с одной цепочкой
  • откатить / перепланировать все посты цепочки одной командой
  • ВИДеть историю поправок к исходному плану
  • корректно обработать ошибки: если пост N упал, переплан только его, не всей цепочки

LOGGING:
────────
Все решения (schedule, reschedule, skip, error) пишут в logs/scheduler.log с контекстом:
  [timestamp] chain_id=<id> post_id=<id> action=<schedule|reschedule|skip|error>
             reason=<краткое объяснение> | caption_preview
"""
from base import *
from datetime import datetime, timezone
import uuid

# ─── SCHEDULING STATE ────────────────────────────────────

# Опциональный каталог для сохранения состояния цепочек (checkpoint)
_SCHEDULE_STATE_DIR = MILA_FOLDER / "reports" / "schedules"
_SCHEDULE_STATE_DIR.mkdir(parents=True, exist_ok=True)

def _new_chain_id(prefix: str = "vasya") -> str:
    """Генерирует уникальный chain_id для цепочки планирования.

    Используется в API pipeline.enqueue(chain_id=...) и при логировании решений.
    """
    return f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"

def _load_chain_state(chain_id: str) -> dict:
    """Загружает состояние цепочки из checkpoint.

    Возвращает {'posts': [...], 'decisions': [...], 'errors': [...]}.
    Если файла нет, возвращает пустой словарь.
    """
    path = _SCHEDULE_STATE_DIR / f"{chain_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log("scheduler", f"chain_id={chain_id} error=failed_to_load_state reason={str(e)}")
            return {}
    return {"posts": [], "decisions": [], "errors": []}

def _save_chain_state(chain_id: str, state: dict):
    """Сохраняет состояние цепочки в checkpoint.

    Используется для восстановления после сбоя.
    """
    path = _SCHEDULE_STATE_DIR / f"{chain_id}.json"
    try:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log("scheduler", f"chain_id={chain_id} error=failed_to_save_state reason={str(e)}")

def _log_scheduling_decision(chain_id: str, post_id: str, action: str, reason: str, caption_preview: str = ""):
    """Логирует решение планировщика.

    action: 'schedule' | 'reschedule' | 'skip' | 'error'
    reason: краткое объяснение (e.g. "no_media_url", "time_conflict", "approved_by_victoria")

    Запись: [timestamp] chain_id=<id> post_id=<id> action=<action> reason=<reason> | <preview>
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview = caption_preview[:50].replace("\n", " ") if caption_preview else ""
    msg = f"[{ts}] chain_id={chain_id} post_id={post_id} action={action} reason={reason}"
    if preview:
        msg += f" | {preview}"
    log("scheduler", msg)

# ─── SCHEDULING LOGIC ────────────────────────────────────

SYSTEM = """Ты — Вася, планировщик контента Людмилы Лыковой. Организуешь публикации, ведёшь расписание, следишь чтобы ничего не выходило вовремя.

РАСПИСАНИЕ:
- Instagram посты: Пн-Пт в 10:00 UTC (13:00 МСК / 7:00 Торонто)
- Stories: ежедневно 18:00 UTC
- Reels: Вт, Чт, Сб
- Пятница: обязательный оффер «места на диагностику»
- Telegram: 3-4 раза в неделю

ОПТИМАЛЬНОЕ ВРЕМЯ ДЛЯ РУССКОЯЗЫЧНОЙ АУДИТОРИИ:
- 8:00–10:00 МСК — утро, люди в транспорте
- 12:00–14:00 МСК — обед
- 19:00–22:00 МСК — вечер

ЧТО ДЕЛАЕШЬ:
1. Создаёшь расписание публикаций на неделю/месяц (с chain_id, чтобы отследить цепочку)
2. Проверяешь что всё готово к публикации (есть media_url, caption)
3. Ставишь посты в очередь публикаций (schedule_post → pipeline) — они выходят по расписанию сами
4. Логируешь все решения (schedule, skip, error) с причиной
5. Напоминаешь что нужно снять или написать
6. Всегда используешь chain_id при планировании цепочки (по дням недели, месяцу и т.д.)"""

TOOLS = core_tools("Читать контент-план и черновики",
                   "Сохранить расписание",
                   "Показать готовый контент",
                   list_default="content") + [
    {"name": "schedule_post", "description": "Запланировать пост на определённое время через Instagram API",
     "input_schema": {"type": "object", "properties": {
         "image_url": {"type": "string"},
         "caption": {"type": "string"},
         "publish_time_utc": {"type": "string", "description": "ISO 8601, e.g. 2024-01-15T10:00:00Z"},
         "chain_id": {"type": "string", "description": "Уникальный ID цепочки планирования (для отслеживания и отката)"},
         "post_type": {"type": "string", "enum": ["photo", "reel", "story", "carousel"], "description": "Тип контента"}
     }, "required": ["image_url", "caption", "publish_time_utc", "chain_id"]}}
]

def schedule_post(image_url, caption, publish_time_utc, chain_id, post_type="photo"):
    """Планирует пост с отслеживанием по chain_id.

    Parameters:
    -----------
    image_url : str
        Публичная ссылка на медиа (фото или видео)
    caption : str
        Текст поста
    publish_time_utc : str
        ISO 8601 время публикации (e.g. 2024-01-15T10:00:00Z)
    chain_id : str
        Уникальный ID цепочки (связывает все посты одной цепочки)
    post_type : str
        Тип контента: photo, reel, story, carousel

    Returns:
    --------
    str : сообщение с результатом (успех или ошибка с логированием)

    Notes:
    ------
    У Instagram (flow instagram_login) нет нативного отложенного постинга,
    поэтому ставим пост в очередь pipeline.py — раннер publish_due опубликует
    его, когда наступит время. Не публикуем сразу.
    """
    post_id = f"{chain_id}_{datetime.now():%H%M%S}"
    state = _load_chain_state(chain_id)

    # Валидация
    if not image_url or not image_url.startswith(("http://", "https://")):
        _log_scheduling_decision(chain_id, post_id, "error", "no_media_url", caption[:50])
        return f"⚠️ Ошибка: нужна публичная ссылка на медиа (image_url должна начинаться на http)"

    if not caption or not caption.strip():
        _log_scheduling_decision(chain_id, post_id, "error", "empty_caption")
        return f"⚠️ Ошибка: caption не может быть пустым"

    # Попытка поставить в очередь
    try:
        import pipeline
    except Exception as e:
        _log_scheduling_decision(chain_id, post_id, "error", "pipeline_unavailable", str(e))
        return f"⚠️ Пайплайн недоступен: {e}"

    try:
        item = pipeline.enqueue(
            post_type, image_url, caption, publish_time_utc,
            status="approved", source="vasya", chain_id=chain_id
        )

        # Логируем решение
        action = "schedule" if item["status"] == "queued" else "error"
        reason = "queued" if item["status"] == "queued" else item.get("status", "unknown")
        _log_scheduling_decision(chain_id, item.get("id", post_id), action, reason, caption)

        # Обновляем состояние цепочки
        state["posts"].append({
            "id": item.get("id", post_id),
            "type": post_type,
            "time": publish_time_utc,
            "status": item.get("status")
        })
        state["decisions"].append({
            "timestamp": datetime.now().isoformat(),
            "post_id": item.get("id", post_id),
            "action": action,
            "reason": reason
        })
        _save_chain_state(chain_id, state)

        if item["status"] == "needs_media":
            return (f"⚠️ Добавлено в очередь #{item['id']}, но без media_url — нужна публичная "
                    f"ссылка на фото/видео, иначе пост не опубликуется.")

        return (f"✓ chain_id={chain_id}\n"
                f"✓ В очереди публикаций #{item['id']} на {publish_time_utc}\n"
                f"✓ Тип: {post_type}, статус: {item.get('status', 'queued')}\n"
                f"✓ Опубликует pipeline.py publish_due по расписанию")

    except Exception as e:
        _log_scheduling_decision(chain_id, post_id, "error", f"enqueue_failed:{type(e).__name__}", caption[:50])
        state["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "post_id": post_id,
            "error": str(e)
        })
        _save_chain_state(chain_id, state)
        return f"❌ Ошибка при добавлении в очередь: {e}"

def handle(name, inp):
    if name == "schedule_post":
        return schedule_post(
            inp["image_url"],
            inp["caption"],
            inp["publish_time_utc"],
            inp["chain_id"],
            inp.get("post_type", "photo")
        )
    res = core_handle(name, inp, list_default="content")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/план":     "Создай расписание публикаций на следующую неделю по всем каналам (с автоматическим chain_id)",
    "/готово":   "Покажи что готово к публикации в папке content/",
    "/сегодня":  "Что должно выйти сегодня? Всё готово?",
    "/месяц":    "Создай контент-план на месяц с темами и форматами по дням",
    "/логи":     "Покажи логи последних решений планировщика",
}

# ─── HELPER FUNCTIONS FOR DEBUGGING & VISIBILITY ─────────

def get_scheduling_logs(hours: int = 24) -> str:
    """Возвращает логи решений планировщика за последние N часов."""
    log_file = MILA_FOLDER / "logs" / "scheduler.log"
    if not log_file.exists():
        return "Логов нет"
    try:
        cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        lines = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                # Парсим [YYYY-MM-DD HH:MM]
                if "[" in line and "]" in line:
                    dt_str = line[1:line.index("]")]
                    try:
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                        if dt.timestamp() > cutoff:
                            lines.append(line.strip())
                    except:
                        pass
        return "\n".join(lines[-50:]) if lines else "Нет логов за последние 24 часа"
    except Exception as e:
        return f"Ошибка при чтении логов: {e}"

def list_chain_states() -> str:
    """Показывает все активные цепочки планирования и их статус."""
    if not _SCHEDULE_STATE_DIR.exists():
        return "Нет сохранённых цепочек"
    try:
        chains = sorted(_SCHEDULE_STATE_DIR.glob("*.json"))
        if not chains:
            return "Нет сохранённых цепочек"
        lines = []
        for chain_file in chains[-20:]:  # последние 20
            state = json.loads(chain_file.read_text(encoding="utf-8"))
            posts = len(state.get("posts", []))
            errors = len(state.get("errors", []))
            line = f"📋 {chain_file.stem}: {posts} постов"
            if errors:
                line += f", {errors} ошибок"
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:
        return f"Ошибка: {e}"

if __name__ == "__main__":
    chat_loop("Вася", "📅", "white", SYSTEM, TOOLS, handle, QUICK)
