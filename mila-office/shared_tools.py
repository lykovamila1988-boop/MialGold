# -*- coding: utf-8 -*-
"""
Shared tools для агентов — единственный источник правды для общих инструментов.

Используется: Lera, Dima, Tyoma, Marina, Producer и др.
"""
import json
import os
import requests
from base import GUMROAD_TOKEN, TELEGRAM_TOKEN, log


def gumroad_sales(limit=10):
    """Получить список продаж из Gumroad (общая функция для Lera, Dima)."""
    if not GUMROAD_TOKEN:
        return "⚠️ Нет GUMROAD_ACCESS_TOKEN в .env"
    try:
        r = requests.get("https://api.gumroad.com/v2/sales",
                        params={"access_token": GUMROAD_TOKEN}, timeout=10)
        sales = r.json().get("sales", [])
        return json.dumps(sales[:limit], indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Gumroad недоступен: {e}"


def telegram_send(chat_id, text, confirm=True):
    """Отправить сообщение в Telegram (общая функция для Tyoma)."""
    if not TELEGRAM_TOKEN:
        return "⚠️ Нет TELEGRAM_BOT_TOKEN в .env"
    if confirm:
        return f"📋 ЧЕРНОВИК (не опубликовано):\n\n{text}\n\nЧтобы опубликовать — скажи 'подтверди публикацию'"
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        data = r.json()
        if data.get("ok"):
            log("telegram", f"Sent to {chat_id}: {text[:50]}")
            return f"✓ Опубликовано! Message ID: {data['result']['message_id']}"
        return f"Ошибка: {data.get('description')}"
    except Exception as e:
        return f"Ошибка: {e}"


def telegram_get_updates():
    """Получить новые сообщения в Telegram бот (для Tyoma)."""
    if not TELEGRAM_TOKEN:
        return "⚠️ Нет TELEGRAM_BOT_TOKEN в .env"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"limit": 20}, timeout=10)
        updates = r.json().get("result", [])
        messages = []
        for u in updates:
            msg = u.get("message", {})
            if msg.get("text"):
                messages.append({
                    "from": msg.get("from", {}).get("first_name"),
                    "username": msg.get("from", {}).get("username"),
                    "text": msg.get("text"),
                    "time": msg.get("date")
                })
        return json.dumps(messages, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


def telegram_channel_stats(chat_id):
    """Получить статистику Telegram канала (для Tyoma)."""
    if not TELEGRAM_TOKEN:
        return "⚠️ Нет TELEGRAM_BOT_TOKEN"
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMemberCount",
            params={"chat_id": chat_id}, timeout=10)
        data = r.json()
        if data.get("ok"):
            return json.dumps({
                "chat_id": chat_id,
                "member_count": data.get("result", 0)
            }, ensure_ascii=False, indent=2)
        return f"Ошибка: {data.get('description')}"
    except Exception as e:
        return f"Ошибка: {e}"


def calc_ltv_and_mrr():
    """Рассчитать LTV (lifetime value) и MRR (monthly recurring revenue) из Gumroad + Calendly консультаций.
    LTV = средний доход на одного клиента. MRR = среднемесячный доход.

    Источники дохода:
    1. Gumroad: практикум ($37)
    2. Calendly: консультации ($120)
    """
    try:
        from pathlib import Path
        import sys

        # Импортируем get_consultations из tools/_common
        tools_dir = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD")) / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))

        # Получаем данные продаж и консультаций
        sales_response = gumroad_sales(limit=100)
        if isinstance(sales_response, str) and sales_response.startswith("⚠️"):
            sales_data = []
        else:
            try:
                sales_data = json.loads(sales_response)
                if isinstance(sales_data, str):
                    sales_data = json.loads(sales_data)
                if not isinstance(sales_data, list):
                    sales_data = sales_data.get("sales", []) if isinstance(sales_data, dict) else []
            except:
                sales_data = []

        # Получаем консультации из Calendly
        try:
            from _common import get_consultations
            consultations = get_consultations(days=30)
        except:
            consultations = []

        # Объединяем обе потоки дохода
        all_transactions = []

        # Добавляем Gumroad продажи
        for sale in sales_data:
            all_transactions.append({
                "email": sale.get("purchaser_email", ""),
                "amount": float(sale.get("price", 0)) / 100,
                "date": sale.get("purchased_at", ""),
                "type": "praktikum"
            })

        # Добавляем Calendly консультации
        for consultation in consultations:
            if consultation.get("invitees"):
                email = consultation["invitees"][0].get("email", "") if consultation["invitees"] else ""
                all_transactions.append({
                    "email": email,
                    "amount": consultation.get("price", 0),
                    "date": consultation.get("start_time", ""),
                    "type": "consultation"
                })

        if not all_transactions:
            return json.dumps({
                "status": "no_data",
                "message": "Нет данных о продажах и консультациях",
                "ltv": 0,
                "mrr": 0,
                "sources": {"praktikum": 0, "consultations": 0}
            }, ensure_ascii=False, indent=2)

        # Анализируем всех клиентов
        total_revenue = sum(t["amount"] for t in all_transactions)
        unique_customers = len(set(t["email"] for t in all_transactions if t["email"]))
        transaction_dates = [t["date"] for t in all_transactions if t["date"]]

        # LTV: средний доход на одного клиента
        ltv = round(total_revenue / max(unique_customers, 1), 2)

        # MRR: прогноз среднемесячного дохода
        mrr = round(total_revenue / max(len(transaction_dates) / 30, 1), 2) if transaction_dates else ltv

        # Повторные покупки (консультации за одним клиентом)
        customer_transactions = {}
        for trans in all_transactions:
            email = trans.get("email", "")
            if email:
                customer_transactions[email] = customer_transactions.get(email, 0) + 1

        repeat_customers = len([c for c in customer_transactions.values() if c > 1])
        repeat_rate = round((repeat_customers / max(unique_customers, 1)) * 100, 1) if unique_customers > 0 else 0

        # Разбивка по источникам
        praktikum_revenue = sum(t["amount"] for t in all_transactions if t["type"] == "praktikum")
        consultation_revenue = sum(t["amount"] for t in all_transactions if t["type"] == "consultation")

        return json.dumps({
            "status": "ok",
            "period": "last 30 days + 100 sales",
            "revenue_sources": {
                "praktikum ($37)": f"${round(praktikum_revenue, 2)}",
                "consultations ($120)": f"${round(consultation_revenue, 2)}"
            },
            "metrics": {
                "ltv": f"${ltv}",
                "mrr": f"${mrr}",
                "total_revenue": f"${round(total_revenue, 2)}",
                "unique_customers": unique_customers,
                "repeat_customers": repeat_customers,
                "repeat_rate": f"{repeat_rate}%",
                "total_transactions": len(all_transactions),
                "avg_transaction_value": f"${round(total_revenue / len(all_transactions), 2)}"
            }
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Ошибка расчёта LTV: {e}"


def find_clients_by_pattern(pattern):
    """Найти клиентов с заданным паттерном из intake-форм (для Alina).
    Паттерны: 'Спасатель', 'Угодница', 'Избегание'"""
    from pathlib import Path

    mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
    intake_dir = mila_folder / "MILA-BUSINESS" / "03-clients" / "intake-forms"

    clients = []
    try:
        if not intake_dir.exists():
            return json.dumps({"status": "no_data", "message": f"Папка {intake_dir} не найдена"}, ensure_ascii=False)

        for file in intake_dir.glob("*.txt"):
            try:
                content = file.read_text(encoding="utf-8")
                # Ищем паттерн в содержимом файла
                if pattern.lower() in content.lower():
                    clients.append({
                        "name": file.stem,
                        "file": str(file),
                        "preview": content[:200] + "..." if len(content) > 200 else content
                    })
            except Exception:
                pass

        return json.dumps({
            "status": "ok",
            "pattern": pattern,
            "found": len(clients),
            "clients": clients
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Ошибка поиска клиентов: {e}"


def get_client_list():
    """Получить список всех клиентов из intake-форм (для Alina)."""
    from pathlib import Path

    mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
    intake_dir = mila_folder / "MILA-BUSINESS" / "03-clients" / "intake-forms"

    clients = []
    try:
        if not intake_dir.exists():
            return json.dumps({"status": "no_data", "total": 0}, ensure_ascii=False)

        for file in intake_dir.glob("*.txt"):
            clients.append({
                "name": file.stem,
                "file": str(file),
                "size": file.stat().st_size
            })

        return json.dumps({
            "status": "ok",
            "total": len(clients),
            "clients": sorted(clients, key=lambda x: x["name"])
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Ошибка получения списка клиентов: {e}"


def get_weekly_analytics(days=7):
    """Получить еженедельную аналитику охвата, лайков, комментариев (для всех агентов).

    Возвращает суммарные метрики за период:
    - total_reach: сумма охвата всех постов
    - total_engagement: сумма лайков + комментариев
    - avg_reach_per_post: средний охват на пост
    - total_posts: количество постов за период
    """
    from pathlib import Path
    import sys

    mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
    tools_dir = mila_folder / "tools"

    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    try:
        import weekly_stats
        from _common import load_config

        cfg = load_config()
        stats = weekly_stats.get_weekly_stats(cfg, days=days)

        return json.dumps({
            "status": "ok",
            "period": f"последние {days} дней",
            "summary": stats["summary"],
            "posts_count": len(stats["posts"]),
            "start_date": stats["start_date"],
            "end_date": stats["end_date"]
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Ошибка получения аналитики: {e}"


# ─── SUPABASE ДАННЫЕ ──────────────────────────────────────────
# Доступ к таблицам базы данных для агентов

def get_ig_posts_data(days=30):
    """Получить Instagram посты из Supabase для аналитики."""
    try:
        from _common import get_ig_posts
        posts = get_ig_posts(days=days)
        return json.dumps({
            "status": "ok" if posts else "empty",
            "count": len(posts),
            "posts": posts[:20]  # первые 20 для агента
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


def get_telegram_leads_data(status=None, days=7):
    """Получить Telegram лидов из Supabase."""
    try:
        from _common import get_telegram_leads
        leads = get_telegram_leads(status=status, days=days)
        return json.dumps({
            "status": "ok" if leads else "empty",
            "count": len(leads),
            "by_status": {},
            "leads": leads[:20]
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


def get_purchases_data(days=30):
    """Получить покупки из Supabase."""
    try:
        from _common import get_purchases
        purchases = get_purchases(days=days)
        total = sum(p.get("amount_cad", 0) for p in purchases)
        return json.dumps({
            "status": "ok" if purchases else "empty",
            "count": len(purchases),
            "total_cad": round(total, 2),
            "purchases": purchases[:20]
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


def get_consultations_data(days=30):
    """Получить консультации из Supabase."""
    try:
        from _common import get_consultations_from_db
        consultations = get_consultations_from_db(days=days)
        return json.dumps({
            "status": "ok" if consultations else "empty",
            "count": len(consultations),
            "consultations": consultations[:20]
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


def check_supabase_access():
    """Проверить статус доступа к Supabase."""
    try:
        from _common import get_supabase_status
        status = get_supabase_status()
        return json.dumps(status, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Ошибка: {e}"


def measure_sales_funnel(days=30):
    """Измерить воронку продаж: коррелирование постов с продажами (для Lera).
    Читает отчёты аналитики и Gumroad, вычисляет CTR и конверсию."""
    from pathlib import Path

    mila_folder = Path(os.getenv("MILA_FOLDER", r"E:\MILA GOLD"))
    reports_dir = mila_folder / "reports"

    funnel = {
        "period_days": days,
        "summary": {},
        "posts": [],
        "conversion_rate": None,
        "ctr": None
    }

    try:
        # Читаем последний отчёт о постах
        posts_files = sorted(reports_dir.glob("posts_*.json"))
        if posts_files:
            with open(posts_files[-1], encoding="utf-8") as f:
                posts_data = json.load(f)
                if isinstance(posts_data, dict):
                    posts_data = posts_data.get("posts", [])

                total_reach = 0
                total_clicks = 0

                for post in posts_data[:15]:  # последние 15 постов
                    post_info = {
                        "id": post.get("id"),
                        "type": post.get("type"),  # photo, carousel, reel
                        "reach": post.get("reach", 0),
                        "likes": post.get("likes", 0),
                        "comments": post.get("comments", 0),
                        "saves": post.get("saves", 0),
                        "clicks": post.get("link_clicks", 0),
                        "caption": (post.get("caption", "")[:60] + "...") if len(post.get("caption", "")) > 60 else post.get("caption", "")
                    }

                    if post_info["reach"] > 0:
                        post_info["engagement_rate"] = round(
                            ((post_info["likes"] + post_info["comments"] + post_info["saves"]) / post_info["reach"]) * 100, 2
                        )
                        post_info["ctr"] = round((post_info["clicks"] / post_info["reach"]) * 100, 2) if post_info["reach"] > 0 else 0

                    funnel["posts"].append(post_info)
                    total_reach += post_info["reach"]
                    total_clicks += post_info["clicks"]

        # Читаем продажи из Gumroad
        sales_data = json.loads(gumroad_sales(limit=100))
        if isinstance(sales_data, str):
            sales_list = []
        else:
            sales_list = json.loads(sales_data) if isinstance(sales_data, str) else sales_data

        funnel["summary"] = {
            "period": f"последние {days} дней",
            "total_posts": len(funnel["posts"]),
            "total_reach": sum(p["reach"] for p in funnel["posts"]),
            "total_clicks": sum(p["clicks"] for p in funnel["posts"]),
            "total_sales": len(sales_list),
            "avg_reach_per_post": round(sum(p["reach"] for p in funnel["posts"]) / max(len(funnel["posts"]), 1), 0),
            "avg_engagement_rate": round(
                sum(p.get("engagement_rate", 0) for p in funnel["posts"]) / max(len(funnel["posts"]), 1), 2
            ),
            "avg_ctr": round(
                sum(p.get("ctr", 0) for p in funnel["posts"]) / max(len(funnel["posts"]), 1), 2
            )
        }

        if total_reach > 0 and len(sales_list) > 0:
            funnel["conversion_rate"] = round((len(sales_list) / (total_reach / 100)) * 100, 3)

        return json.dumps(funnel, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Ошибка измерения воронки: {e}"
