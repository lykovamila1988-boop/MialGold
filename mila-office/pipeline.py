# -*- coding: utf-8 -*-
"""
pipeline.py — диспетчер цепочек агентов (Паттерн 1 «n8n как дирижёр»).

n8n (или человек) вызывает: python pipeline.py <chain> [--notify]
Скрипт прогоняет ЦЕПОЧКУ агентов неинтерактивно (без chat_loop), передавая
результат каждого следующему, и пишет ход в общую память (memory.py).
В конце опционально шлёт сигнал в n8n-webhook (Паттерн 2 «агенты → n8n»).

АВТОМАТИЧЕСКИЕ ОТЧЁТЫ (n8n workflow):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
n8n workflow "Fetch Instagram Reports" (каждые 24h или по расписанию):
  1. POST http://localhost:5000/api/fetch-analytics (type=posts)
  2. Сохранить reports/posts_YYYY-MM-DD_HHMMSS.json
  3. Использует tools/get_analytics.py (Instagram Graph API)

Результаты используют:
  • Rita:  read reports/posts_*.json → analyze_audience()
  • Olya:  get_weekly_analytics() → read reports/
  • Dima:  measure_sales_funnel() → correlate с Gumroad

Подробно: см. mila-office/N8N_INSTAGRAM_REPORTS.md

Цепочки:
  new_client      Алина → Лера         (по context.json: новая клиентка)
  content_week    Оля → Марина → Виктория → Вася
  monday_brief    Стас → Марина
  weekly_report   Дима → Марина → Стас

Примеры:
  python pipeline.py new_client --notify
  python pipeline.py content_week
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import re
import json
import argparse
import importlib
import threading
from pathlib import Path

import time
import base
import memory
import policies
try:
    import supa
except Exception:
    supa = None

# Опциональный сигнал в n8n: POST на webhook по завершении цепочки.
try:
    import requests
except Exception:
    requests = None

N8N_DONE_WEBHOOK = os.getenv("N8N_DONE_WEBHOOK", "")  # напр. http://localhost:5678/webhook/office-done
TELEGRAM_CHAT_ID = (
    os.getenv("TELEGRAM_ADMIN_CHAT_ID")
    or os.getenv("TELEGRAM_ALERT_CHAT_ID")
    or os.getenv("TELEGRAM_CHAT_ID")
    or ""
).strip()

# Checkpoint цепочек: прогресс по шагам, чтобы при падении на шаге N повторный
# запуск продолжил с N, а не с нуля (Разрыв «pipeline падает на середине»).
_STATE_DIR = base.MILA_FOLDER / "reports"


def _state_path(chain):
    return _STATE_DIR / f"pipeline_state_{chain}.json"


def run_agent_with_retry(client, system, tools, handle, msg, history, agent_key, max_retries=3, initial_delay=1):
    """Запустить агента с retry и exponential backoff."""
    retry_delay = initial_delay
    last_error = None
    for attempt in range(max_retries):
        try:
            return base.run_agent(client, system, tools, handle, msg, history, agent_key=agent_key)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"  Попытка {attempt + 1}/{max_retries} упала: {type(e).__name__}. Повтор через {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)  # exponential backoff, макс 60 сек
            else:
                print(f"  Все {max_retries} попыток исчерпаны.")
    raise last_error


def _load_state(chain):
    try:
        return json.loads(_state_path(chain).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def _save_state(chain, state):
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _state_path(chain).with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _state_path(chain))


def _clear_state(chain):
    try:
        _state_path(chain).unlink()
    except OSError:
        pass


# ─── Реестр агентов (ключ → как его запускать) ───────────
# Марина живёт в agent.py с SYSTEM_PROMPT/run_tool; остальные — единый интерфейс
# SYSTEM/TOOLS/handle. Оборачиваем оба варианта в одинаковый вызов.
def _load_agent(key: str):
    if key == "marina":
        m = importlib.import_module("agent")
        return {"key": key, "system": m.SYSTEM_PROMPT, "tools": m.TOOLS, "handle": m.run_tool}
    m = importlib.import_module(key if key != "manager" else "manager")
    return {"key": key, "system": m.SYSTEM, "tools": m.TOOLS, "handle": m.handle}


# модуль каждого агента по ключу (для не-Марины — имя файла совпадает с ключом)
AGENT_MODULE = {
    "marina": "agent", "victoria": "victoria", "alina": "alina", "dima": "dima",
    "tyoma": "tyoma", "olya": "olya", "vasya": "vasya", "lera": "lera",
    "manager": "manager", "producer": "producer", "rita": "rita",
}

# Цепочки: список (agent_key, шаблон-задача). {prev} = ответ предыдущего агента,
# {context} = JSON текущего контекста из памяти.
CHAINS = {
    "new_client": [
        ("alina", "Новая клиентка. Контекст: {context}\n"
                  "Разбери анкету/данные: определи паттерн (Спасатель/Угодница/Избегание), "
                  "подготовь к первой сессии (профиль, 5 вопросов, красные флаги). "
                  "В конце одной строкой передай рекомендацию агенту продаж (Лере): какой пакет предложить и почему."),
        ("lera", "Алина подготовила клиентку и дала тебе рекомендацию:\n{prev}\n\n"
                 "Напиши тёплый персональный follow-up для этой клиентки и предложи подходящий "
                 "пакет/следующий шаг по воронке. Без давления, в голосе Людмилы."),
    ],
    "content_week": [
        ("olya", "Найди 3 вирусные/работающие темы недели в нише психологии отношений. "
                 "Дай по каждой цепляющий хук. Контекст: {context}"),
        ("marina", "Оля предложила темы и хуки:\n{prev}\n\n"
                   "Составь контент-план на неделю (7 публикаций: форматы, темы, ключевые мысли, CTA). "
                   "Опирайся на то, что реально работало."),
        ("victoria", "Проверь этот контент-план перед публикацией:\n{prev}\n\n"
                     "Оцени голос Людмилы, хуки и CTA. Дай оценку 1-10 и финальную версию."),
        ("vasya", "Контент-план одобрен:\n{prev}\n\n"
                  "Составь расписание публикаций на неделю (день/время/формат) и список того, что нужно снять."),
    ],
    "monday_brief": [
        ("manager", "Сделай краткий обзор офиса за последние 24ч (office_review) и дай "
                    "топ-3 приоритета на неделю с KPI. Контекст: {context}"),
        ("marina", "Стас дал приоритеты недели:\n{prev}\n\n"
                   "Переведи их в конкретный план по контенту: что публиковать и зачем."),
    ],
    "weekly_report": [
        ("dima", "Посчитай доход за неделю и сравни с целью $5000. Контекст: {context}"),
        ("marina", "Финансовый итог недели:\n{prev}\n\n"
                   "Дай выводы по маркетингу: что сработало для продаж, что усилить."),
        ("manager", "Финансы и маркетинг за неделю:\n{prev}\n\n"
                    "Сделай ревью и сформулируй 2-3 улучшения процессов/промптов на следующую неделю "
                    "с измеримыми критериями."),
    ],
    # Конкурентная разведка (ежемесячно): Оля мониторит топ-аккаунты → извлекает
    # рыночные паттерны → Стас решает, что взять Марине (через improve_agent).
    "competitive_analysis": [
        ("olya", "Запусти monitor_competitors по списку competitors.json. По каждому аккаунту "
                 "извлеки ПОВТОРЯЮЩИЙСЯ паттерн (хук в первые 3 сек, структура, эмоц. триггер, тема, CTA). "
                 "Выдели 2-3 рыночных паттерна, которые повторяются у нескольких. Контекст: {context}"),
        ("manager", "Оля собрала конкурентную разведку и рыночные паттерны:\n{prev}\n\n"
                    "Реши, какой ОДИН паттерн стоит взять Марине (адаптировать под голос Людмилы, "
                    "не копировать). Если уверен на данных — примени через improve_agent к marina с "
                    "обоснованием и данными. Если данных мало — оформи как эксперимент (log_experiment)."),
    ],
    # Исследование под новый продукт: Оля даёт рыночный/трендовый контекст,
    # Рита анализирует СВЕЖУЮ аналитику (run_chain обновляет reports/ до старта)
    # и предлагает топ-3 темы воркбука. Дальше человек выбирает → new_product.
    "product_research": [
        ("olya", "Идёт исследование под новый цифровой продукт (воркбук) в нише "
                 "болезненных отношений/тревожной привязанности. Через web_search и "
                 "monitor_competitors найди, какие ТЕМЫ и боли сейчас резонируют на рынке "
                 "(тренды, что обсуждают, что у конкурентов залетает). Дай 5-7 болевых тем "
                 "с короткой формулировкой боли. Контекст: {context}"),
        ("rita", "Оля собрала рыночные боли и тренды:\n{prev}\n\n"
                 "Вызови analyze_audience (там СВЕЖАЯ аналитика аккаунта — топ-посты, "
                 "комментарии, профиль). Сопоставь рыночные боли Оли с реальными данными "
                 "аккаунта и предложи ТОП-3 темы для воркбука: по каждой — боль (на данных), "
                 "обещание результата, почему продастся (воронка $37→$120→пакеты), черновое "
                 "название. Где данных мало — помечай как гипотезу. В конце одной строкой — "
                 "какую тему рекомендуешь запустить первой и почему."),
    ],
    "new_product": [
        ("rita", "Идея продукта: {idea}\n\n"
                 "Собери структуру: главы, упражнения, поток, promise, ограничения голоса. "
                 "Сделай продукт конкретным и пригодным для PDF-воркбука."),
        ("marina", "Рита собрала структуру продукта:\n{prev}\n\n"
                   "Напиши полный текст продукта в голосе Людмилы. Это должен быть готовый текст для Gamma/PDF: "
                   "заголовки, вводная, главы, упражнения, инструкции, мягкий CTA в конце."),
        ("victoria", "Марина написала черновик продукта:\n{prev}\n\n"
                     "Сделай редактуру, убери воду, усили структуру, сохрани голос Людмилы. "
                     "Верни финальный текст целиком, готовый к одобрению Людмилой."),
    ],
}


def _refresh_analytics():
    """Обновляет reports/posts_*.json и comments_*.json свежими данными Instagram
    (через tools/get_analytics.py) ПЕРЕД product_research. Не фатально: если фетч
    упал (нет сети/токена) — продолжаем на последнем имеющемся отчёте."""
    import subprocess
    tools_dir = base.MILA_FOLDER / "tools"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for kind in ("posts", "comments"):
        try:
            r = subprocess.run([sys.executable, "get_analytics.py", kind],
                               cwd=str(tools_dir), env=env, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=120)
            ok = r.returncode == 0
            print(f"[refresh] get_analytics {kind}: {'ok' if ok else 'fail'}")
            if not ok:
                print(f"[refresh]   {(r.stderr or '')[-200:]}")
        except Exception as e:
            print(f"[refresh] get_analytics {kind} error: {e}")


def run_chain(name: str, notify: bool = False) -> dict:
    if name == "new_product":
        sys.exit("Для продукта укажи идею: python pipeline.py new_product \"воркбук красные флаги $27\"")
    if name not in CHAINS:
        sys.exit(f"Неизвестная цепочка: {name}. Доступны: {', '.join(CHAINS)}")

    owner = f"pipeline:{name}:pid:{os.getpid()}"
    lock = memory.acquire_lock(name, owner=owner, ttl_seconds=7200)
    if not lock.get("ok"):
        msg = f"Цепочка {name} уже выполняется ({lock.get('locked_by')})."
        print(f"[lock] {msg}")
        return {"chain": name, "ok": False, "status": "locked", "message": msg}

    try:
        client = base.get_client()
        ctx = memory.read_context()
        ctx_json = json.dumps(ctx, ensure_ascii=False)

        # product_research опирается на СВЕЖУЮ аналитику: обновляем reports/ ДО
        # прогона агентов, чтобы Рита (analyze_audience читает свежий posts_*.json)
        # работала на сегодняшних данных, а не на старом отчёте.
        if name == "product_research":
            _refresh_analytics()

        steps = CHAINS[name]
        # Checkpoint: незавершённую цепочку ДЛЯ ТОГО ЖЕ контекста продолжаем с шага
        # падения, а не с нуля (Разрыв «pipeline падает на середине»). Прогресс
        # пишется в reports/pipeline_state_<name>.json после каждого шага.
        st = _load_state(name)
        if st and st.get("context_ts") == ctx.get("ts") and st.get("steps"):
            transcript = st["steps"]
            prev = transcript[-1]["reply"]
            resume_from = len(transcript)
            print(f"↻ Продолжаю «{name}» с шага {resume_from + 1} (чекпоинт): "
                  f"уже сделано {[s['agent'] for s in transcript]}")
        else:
            transcript, prev, resume_from = [], "", 0
            memory.log_event(f"pipeline:start:{name}", {"context_event": ctx.get("event")})

        for idx, (agent_key, template) in enumerate(steps):
            if idx < resume_from:
                continue  # шаг выполнен в прошлый запуск — переиспользуем результат
            if agent_key == "vasya":
                approval = memory.get_approval(f"{name}:victoria")
                if approval.get("status") in {"rejected", "changes_requested"}:
                    msg = f"Вася остановлен: approval={approval.get('status')} ({approval.get('comment','')})"
                    print(f"\n[approval] {msg}")
                    transcript.append({"agent": "pipeline", "reply": msg})
                    break

            spec = _load_agent(agent_key)
            task = template.format(prev=prev, context=ctx_json, idea="")
            system = base.compose_system(spec["key"], spec["system"])
            print(f"\n=== {agent_key} ({idx + 1}/{len(steps)}) ===")
            try:
                reply, _ = run_agent_with_retry(client, system, spec["tools"], spec["handle"],
                                                task, [], agent_key=spec["key"])
            except Exception as e:
                # Падение на шаге: сохраняем прогресс — повтор продолжит отсюда.
                _save_state(name, {"context_ts": ctx.get("ts"), "steps": transcript,
                                   "failed_at": agent_key})
                memory.log_event(f"pipeline:fail:{name}", {"step": agent_key, "idx": idx})
                print(f"\n✗ Шаг «{agent_key}» упал: {e}\n  Прогресс сохранён — повтор продолжит отсюда.")
                raise
            print(reply)
            transcript.append({"agent": agent_key, "reply": reply})
            _save_state(name, {"context_ts": ctx.get("ts"), "steps": transcript})  # чекпоинт

            if idx + 1 < len(steps):
                nxt = steps[idx + 1][0]
                memory.handoff(agent_key, nxt, {
                    "pipeline": name,
                    "task": f"{agent_key}_to_{nxt}",
                    "content": reply,
                    "context": ctx,
                    "priority": "high" if name in ("new_client", "content_week") else "normal",
                })

            if agent_key == "victoria":
                low = reply.lower()
                status = "rejected" if any(x in low for x in ("не одоб", "отклон", "rejected", "слабый хук")) else "approved"
                memory.set_approval(f"{name}:victoria", "victoria", status, reply[:500])
            prev = reply

        result = {"chain": name, "steps": transcript, "context": ctx}
        _clear_state(name)  # цепочка дошла до конца — чекпоинт больше не нужен
        memory.log_event(f"pipeline:done:{name}", {"steps": len(transcript)})

        if notify:
            _notify_n8n(name, result)
        return result
    finally:
        memory.release_lock(name, owner=owner)


def _product_slug(idea: str, title: str = "") -> str:
    source = title or idea or "digital_product"
    lowered = source.lower()
    if "красн" in lowered and "флаг" in lowered:
        return "workbook_red_flags"
    if "workbook" in lowered or "воркбук" in lowered:
        prefix = "workbook"
    else:
        prefix = "product"
    return f"{prefix}_{base._slugify(source, 'digital_product')}"[:80].strip("_")


def _price_from_idea(idea: str):
    m = re.search(r"[$€£]?\s*(\d+(?:[.,]\d{1,2})?)", idea or "")
    return float(m.group(1).replace(",", ".")) if m else None


def _save_product_files(slug: str, draft_text: str, meta: dict):
    products_dir = base.MILA_FOLDER / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    draft_path = products_dir / f"{slug}_draft.txt"
    meta_path = products_dir / f"{slug}_meta.json"
    draft_path.write_text(draft_text, encoding="utf-8")
    meta["draft_path"] = str(draft_path)
    meta["meta_path"] = str(meta_path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft_path, meta_path


def _record_digital_product(meta: dict):
    if supa is None or not supa.can_write():
        return {"ok": False, "reason": "Supabase service-role key is not configured"}
    row = {
        "title": meta.get("title") or meta.get("idea") or "Digital product",
        "price_cad": meta.get("price_cad"),
        "gamma_url": meta.get("gamma_url"),
        "pdf_url": meta.get("pdf_url"),
        "gumroad_url": meta.get("gumroad_url"),
        "lemon_url": meta.get("lemon_url"),
        "status": meta.get("status", "draft"),
    }
    try:
        inserted = supa.insert("digital_products", row)
        return {"ok": True, "rows": inserted}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


def run_new_product(idea: str, approve_gamma: bool = False, notify: bool = False) -> dict:
    if not (idea or "").strip():
        sys.exit("Укажи идею: python pipeline.py new_product \"воркбук красные флаги $27\"")

    owner = f"pipeline:new_product:pid:{os.getpid()}"
    lock = memory.acquire_lock("new_product", owner=owner, ttl_seconds=7200)
    if not lock.get("ok"):
        msg = f"new_product уже выполняется ({lock.get('locked_by')})."
        print(f"[lock] {msg}")
        return {"chain": "new_product", "ok": False, "status": "locked", "message": msg}

    try:
        client = base.get_client()
        ctx = memory.read_context()
        ctx_json = json.dumps(ctx, ensure_ascii=False)
        memory.log_event("pipeline:start:new_product", {"idea": idea})

        prev = ""
        transcript = []
        existing_slug = _product_slug(idea)
        existing_draft = base.MILA_FOLDER / "products" / f"{existing_slug}_draft.txt"
        existing_meta = base.MILA_FOLDER / "products" / f"{existing_slug}_meta.json"

        if approve_gamma and existing_draft.exists():
            final_text = existing_draft.read_text(encoding="utf-8")
            title = (final_text.splitlines()[0] if final_text.splitlines() else idea).strip("# ").strip()
            slug = existing_slug
            try:
                meta = json.loads(existing_meta.read_text(encoding="utf-8"))
            except (FileNotFoundError, ValueError):
                meta = {"idea": idea, "title": title, "slug": slug, "price_cad": _price_from_idea(idea)}
            print(f"\n[product] Использую одобренный черновик: {existing_draft}")
        else:
            final_text = ""
            title = ""
            slug = ""
            meta = {}

        if not final_text:
            steps = CHAINS["new_product"]
            for idx, (agent_key, template) in enumerate(steps):
                spec = _load_agent(agent_key)
                task = template.format(prev=prev, context=ctx_json, idea=idea)
                system = base.compose_system(spec["key"], spec["system"])
                print(f"\n=== {agent_key} ===")
                reply, _ = run_agent_with_retry(client, system, spec["tools"], spec["handle"],
                                                task, [], agent_key=spec["key"])
                print(reply)
                transcript.append({"agent": agent_key, "reply": reply})
                if idx + 1 < len(steps):
                    memory.handoff(agent_key, steps[idx + 1][0], {
                        "pipeline": "new_product",
                        "task": f"{agent_key}_to_{steps[idx + 1][0]}",
                        "content": reply,
                        "context": {"idea": idea},
                        "priority": "high",
                    })
                prev = reply

            final_text = prev
            title = (final_text.splitlines()[0] if final_text.splitlines() else idea).strip("# ").strip()
            slug = _product_slug(idea, title)
            meta = {
                "idea": idea,
                "title": title,
                "slug": slug,
                "price_cad": _price_from_idea(idea),
                "status": "awaiting_approval",
                "steps": len(transcript),
            }

        draft_path, meta_path = _save_product_files(slug, final_text, meta)
        result = {"chain": "new_product", "steps": transcript, "context": ctx,
                  "draft_path": str(draft_path), "meta_path": str(meta_path),
                  "status": meta.get("status")}

        if not approve_gamma:
            print(f"\n[product] СТОП: текст ждёт одобрения Людмилы: {draft_path}")
            print("[product] После одобрения: python pipeline.py new_product \"...\" --approve-gamma")
            memory.set_approval(f"new_product:{slug}", "victoria", "pending", "Ждёт одобрения Людмилы")
            memory.log_event("pipeline:approval_required:new_product", {"slug": slug, "draft": str(draft_path)})
            if notify:
                _notify_n8n("new_product", result)
            return result

        approval_id = f"new_product:{slug}"
        approval = memory.get_approval(approval_id)
        if approval.get("status") != "approved":
            msg = (
                f"new_product stopped: {approval_id} approval is "
                f"{approval.get('status')}. Run: python pipeline.py approve {approval_id}"
            )
            print(f"\n[approval] {msg}")
            result.update({"status": "awaiting_approval", "approval": approval, "message": msg})
            memory.log_event("pipeline:approval_blocked:new_product", {
                "slug": slug,
                "approval_status": approval.get("status"),
            })
            if notify:
                _notify_n8n("new_product", result)
            return result

        gamma = base.create_gamma_document(title=title, content=final_text, format="document", export="pdf")
        pdf_path = base.MILA_FOLDER / "products" / f"{slug}_v1.pdf"
        generated_path = Path(gamma["local_path"])
        if generated_path.resolve() != pdf_path.resolve():
            generated_path.replace(pdf_path)
        meta.update({
            "status": "pdf_created",
            "gamma_url": gamma.get("gamma_url"),
            "pdf_url": gamma.get("pdf_url") or gamma.get("export_url"),
            "local_path": str(pdf_path),
            "generation_id": gamma.get("generation_id"),
        })
        db_result = _record_digital_product(meta)
        meta["supabase"] = db_result
        _save_product_files(slug, final_text, meta)

        prev = final_text
        for agent_key, task in [
            ("lera", "Для продукта ниже напиши sales page текст для Gumroad/Lemon Squeezy: оффер, bullets, кому подходит, CTA, цена.\n\n{prev}"),
            ("manager", "Продукт создан в Gamma. Meta: {meta}\n\nСформируй следующие шаги загрузки на Gumroad/Lemon Squeezy и проверь риски."),
            ("marina", "Продукт создан. Подготовь лонч-контент: 3 поста, 5 stories, 2 Reels hooks.\n\nПродукт:\n{prev}"),
        ]:
            spec = _load_agent(agent_key)
            msg = task.format(prev=prev, meta=json.dumps(meta, ensure_ascii=False))
            system = base.compose_system(spec["key"], spec["system"])
            print(f"\n=== {agent_key} ===")
            reply, _ = run_agent_with_retry(client, system, spec["tools"], spec["handle"],
                                            msg, [], agent_key=spec["key"])
            print(reply)
            transcript.append({"agent": agent_key, "reply": reply})
            prev = reply

        result.update({"steps": transcript, "status": "pdf_created", "pdf_path": str(pdf_path), "gamma": gamma})
        memory.set_approval(f"new_product:{slug}", "pipeline", "approved", "PDF created")
        memory.log_event("pipeline:done:new_product", {"slug": slug, "pdf": str(pdf_path)})
        if notify:
            _notify_n8n("new_product", result)
        return result
    finally:
        memory.release_lock("new_product", owner=owner)


def _notify_n8n(chain: str, result: dict):
    """Паттерн 2: сигналим n8n, что цепочка завершена. n8n решит, что дальше
    (уведомить Людмилу, запустить следующий шаг)."""
    summary = " | ".join(f"{s['agent']}: {s['reply'][:80]}" for s in result["steps"])
    if not N8N_DONE_WEBHOOK or requests is None:
        print(f"\n[notify] N8N_DONE_WEBHOOK не задан — шлю fallback в Telegram.")
        _notify_telegram(chain, summary, reason="N8N_DONE_WEBHOOK is not set")
        return
    try:
        r = requests.post(N8N_DONE_WEBHOOK, json={
            "chain": chain, "summary": summary, "steps": len(result["steps"]),
        }, timeout=15)
        print(f"\n[notify] n8n webhook -> {r.status_code}")
        if r.status_code >= 400:
            _notify_telegram(chain, summary, reason=f"n8n webhook returned {r.status_code}")
    except Exception as e:
        print(f"\n[notify] не удалось сообщить n8n: {e}")
        _notify_telegram(chain, summary, reason=f"n8n webhook failed: {e}")


def _notify_telegram(chain: str, summary: str, reason: str = ""):
    """Fallback: if n8n is not configured/reachable, Ludmila still gets the completion signal."""
    token = (base.TELEGRAM_TOKEN or "").strip()
    if not token or not TELEGRAM_CHAT_ID or requests is None:
        print("[notify] Telegram fallback недоступен: нет TELEGRAM token/chat.")
        memory.log_event("notify:fallback_failed", {
            "chain": chain, "reason": reason, "missing": "telegram_config",
        })
        return
    text = (
        f"✅ MILA Office: {chain}\n"
        f"Fallback уведомление: {reason or 'n8n недоступен'}\n\n"
        f"{summary}"
    )[:4000]
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=20,
        )
        try:
            ok = bool(r.json().get("ok"))
        except ValueError:
            ok = r.ok
        print(f"[notify] telegram fallback -> {r.status_code}")
        memory.log_event("notify:telegram_fallback", {
            "chain": chain, "reason": reason, "ok": ok, "status": r.status_code,
        })
    except Exception as e:
        print(f"[notify] Telegram fallback не сработал: {e}")
        memory.log_event("notify:fallback_failed", {
            "chain": chain, "reason": reason, "error": str(e)[:200],
        })


def _artifact_from_result(pipeline: str, status: str, result: dict | None) -> dict:
    result = result or {}
    steps = result.get("steps") or []
    files = []
    urls = []

    for key in ("pdf_path", "draft_path", "local_path"):
        if result.get(key):
            files.append(str(result[key]))
    gamma = result.get("gamma") or {}
    if isinstance(gamma, dict):
        for key in ("local_path",):
            if gamma.get(key):
                files.append(str(gamma[key]))
        for key in ("gamma_url", "pdf_url", "export_url"):
            if gamma.get(key):
                urls.append(str(gamma[key]))

    summary = result.get("message") or ""
    if not summary and steps:
        tail = steps[-1] or {}
        summary = f"{tail.get('agent', pipeline)}: {(tail.get('reply') or '')[:220]}"
    if not summary:
        summary = f"{pipeline}: {status}"

    next_actions = []
    if status == "awaiting_approval":
        next_actions.append("Review and approve in dashboard/operator before continuing.")
    if status == "failed":
        next_actions.append("Check task result and retry from /operator when ready.")

    return {
        "summary": summary[:600],
        "files": sorted(set(files)),
        "urls": sorted(set(urls)),
        "next_actions": next_actions,
    }


def _notify_task_status(pipeline: str, status: str, artifact: dict,
                        task_id: str = "", reason: str = ""):
    policy = policies.get_policy(pipeline)
    if status not in set(policy.get("notify_on_status") or []):
        return
    summary = artifact.get("summary") or f"{pipeline}: {status}"
    extra = ""
    if artifact.get("files"):
        extra += "\nFiles: " + ", ".join(artifact["files"][:3])
    if artifact.get("urls"):
        extra += "\nURLs: " + ", ".join(artifact["urls"][:3])
    task_part = f"task {task_id}: " if task_id else ""
    _notify_telegram(
        pipeline,
        f"{task_part}{status}\n{summary}{extra}",
        reason=reason or f"policy notify_on_status:{status}",
    )


def _notify_recovered_tasks(tasks: list):
    for task in tasks:
        artifact = {
            "summary": (
                f"Recovered stale task {task.get('id')} "
                f"({task.get('pipeline')}) to {task.get('status')}."
            ),
            "files": [],
            "urls": [],
            "next_actions": ["Worker will pick it up again if it is pending."],
        }
        _notify_telegram(
            task.get("pipeline") or "operator",
            artifact["summary"],
            reason="task:recovered",
        )


def run_worker(notify: bool = False) -> dict:
    """Run exactly one queued task by priority."""
    recovered = memory.recover_stale_tasks()
    if recovered:
        _notify_recovered_tasks(recovered)
    worker_id = memory.default_worker_id()
    task = memory.dequeue_task("pipeline", worker_id=worker_id)
    if not task:
        print("[queue] Нет pending задач.")
        return {"ok": True, "status": "empty"}
    pipeline = task.get("pipeline")
    data = task.get("data") or {}
    attempts = int(task.get("attempts", 1) or 1)
    stop_heartbeat = threading.Event()

    def _heartbeat_loop():
        while not stop_heartbeat.wait(60):
            memory.heartbeat_task(task["id"], worker_id=worker_id)

    threading.Thread(target=_heartbeat_loop, daemon=True).start()
    try:
        if pipeline == "new_product":
            result = run_new_product(
                data.get("idea") or data.get("title") or "",
                approve_gamma=bool(data.get("approve_gamma")),
                notify=notify or bool(data.get("notify")),
            )
        else:
            result = run_chain(pipeline, notify=notify or bool(data.get("notify")))
        status = policies.status_from_result(result)
        artifact = _artifact_from_result(pipeline, status, result)
        task_result = {
            "pipeline": pipeline,
            "result_status": status,
            "raw_status": result.get("status"),
            "artifact": artifact,
        }
        if policies.should_retry(pipeline, status, attempts):
            delay = policies.retry_delay_seconds(pipeline, attempts, status, result)
            memory.reschedule_task(task["id"], delay, reason=status, result=task_result)
            return {"ok": True, "status": "retry_scheduled", "task_id": task["id"],
                    "pipeline": pipeline, "retry_after": delay, "result": result}
        memory.complete_task(task["id"], status, task_result)
        _notify_task_status(pipeline, status, artifact, task_id=task["id"])
        return result
    except Exception as e:
        artifact = _artifact_from_result(pipeline, "failed", {"message": str(e)[:500]})
        task_result = {"pipeline": pipeline, "error": str(e)[:500], "artifact": artifact}
        if policies.should_retry(pipeline, "failed", attempts):
            delay = policies.retry_delay_seconds(pipeline, attempts, "failed", task_result)
            memory.reschedule_task(task["id"], delay, reason="failed", result=task_result)
        else:
            memory.complete_task(task["id"], "failed", task_result)
            _notify_task_status(pipeline, "failed", artifact, task_id=task["id"])
        raise
    finally:
        stop_heartbeat.set()


def _enqueue_pipeline(chain: str, args) -> dict:
    data = {"notify": bool(args.notify)}
    if chain == "new_product":
        data.update({
            "idea": args.idea or "",
            "approve_gamma": bool(args.approve_gamma),
        })
    if args.data_json:
        try:
            extra = json.loads(args.data_json)
        except ValueError as e:
            sys.exit(f"--data-json is not valid JSON: {e}")
        if not isinstance(extra, dict):
            sys.exit("--data-json must be a JSON object")
        data.update(extra)
    dedupe_key = args.dedupe_key or data.get("dedupe_key") or policies.default_dedupe_key(chain, data)
    priority = args.priority if args.priority is not None else policies.default_priority(chain)
    task = memory.enqueue_task(chain, priority=priority, data=data, dedupe_key=dedupe_key)
    print(json.dumps({"ok": True, "queued": True, "task": task}, ensure_ascii=False, indent=2))
    return task


def main():
    p = argparse.ArgumentParser(description="Диспетчер цепочек агентов MILA Office")
    p.add_argument("chain", nargs="?", choices=list(CHAINS) + ["worker", "enqueue", "status", "approve", "queue", "task", "retry", "cancel", "unblock"], help="какую цепочку запустить")
    p.add_argument("idea", nargs="?", help="идея продукта для new_product")
    p.add_argument("--priority", type=int, default=None, help="для enqueue: приоритет задачи, меньше = раньше")
    p.add_argument("--notify", action="store_true", help="сигналить n8n по завершении")
    p.add_argument("--direct", action="store_true", help="explicit override: run immediately, bypassing queue")
    p.add_argument("--data-json", default="", help="extra JSON object for queued task data")
    p.add_argument("--dedupe-key", default="", help="idempotency key for queued task")
    p.add_argument("--approval-status", choices=["approved", "rejected", "changes_requested", "pending"],
                   default="approved", help="for approve: approval status")
    p.add_argument("--comment", default="", help="for approve: approval comment")
    p.add_argument("--reset-attempts", action="store_true", help="for retry: reset attempts counter")
    p.add_argument("--approve-gamma", action="store_true",
                   help="для new_product: после текста сразу создать Gamma/PDF (только после одобрения Людмилы)")
    p.add_argument("--list", action="store_true", help="показать цепочки и выйти")
    args = p.parse_args()
    if args.list or not args.chain:
        for k, steps in CHAINS.items():
            print(f"{k}: " + " -> ".join(s[0] for s in steps))
        return
    if args.chain == "status":
        print(json.dumps(memory.office_status(), ensure_ascii=False, indent=2))
        return
    if args.chain == "queue":
        print(json.dumps(memory.list_tasks(), ensure_ascii=False, indent=2))
        return
    if args.chain == "task":
        if not args.idea:
            sys.exit("Укажи task_id: python pipeline.py task t12")
        print(json.dumps(memory.get_task(args.idea), ensure_ascii=False, indent=2))
        return
    if args.chain == "retry":
        if not args.idea:
            sys.exit("Укажи task_id: python pipeline.py retry t12")
        print(json.dumps(memory.retry_task(args.idea, reset_attempts=args.reset_attempts), ensure_ascii=False, indent=2))
        return
    if args.chain == "cancel":
        if not args.idea:
            sys.exit("Укажи task_id: python pipeline.py cancel t12")
        print(json.dumps(memory.cancel_task(args.idea, reason=args.comment), ensure_ascii=False, indent=2))
        return
    if args.chain == "unblock":
        if not args.idea:
            sys.exit("Укажи task_id: python pipeline.py unblock t12")
        print(json.dumps(memory.unblock_task(args.idea), ensure_ascii=False, indent=2))
        return
    if args.chain == "approve":
        if not args.idea:
            sys.exit("Укажи item_id: python pipeline.py approve new_product:workbook_red_flags")
        rec = memory.set_approval(args.idea, "liudmyla", args.approval_status, args.comment)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return
    if args.chain == "new_product":
        if args.direct and not policies.can_run_direct("new_product"):
            sys.exit("Direct run is disabled by policy for new_product. Use queue/worker.")
        if not args.direct:
            _enqueue_pipeline("new_product", args)
            return
        run_new_product(args.idea or "", approve_gamma=args.approve_gamma, notify=args.notify)
        return
    if args.chain == "enqueue":
        if not args.idea:
            sys.exit("Укажи pipeline: python pipeline.py enqueue content_week --priority 2")
        _enqueue_pipeline(args.idea, args)
        return
    if args.chain == "worker":
        run_worker(notify=args.notify)
        return
    if not args.direct:
        _enqueue_pipeline(args.chain, args)
        return
    if not policies.can_run_direct(args.chain):
        sys.exit(f"Direct run is disabled by policy for {args.chain}. Use queue/worker.")
    run_chain(args.chain, notify=args.notify)


if __name__ == "__main__":
    main()
