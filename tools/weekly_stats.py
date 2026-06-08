#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_stats.py — Еженедельная аналитика охвата, лайков, комментариев.

Использование:
    python weekly_stats.py                      # последняя неделя (7 дней)
    python weekly_stats.py --days 14            # последние 2 недели
    python weekly_stats.py --days 30            # последний месяц
    python weekly_stats.py --export excel       # экспорт в Excel
"""
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from _common import load_config, graph_get_all, save_report, run_cli

TOOLS_DIR = Path(__file__).parent
REPORTS_DIR = TOOLS_DIR.parent / "reports"


def get_weekly_stats(cfg, days=7):
    """Получить аналитику за последние N дней.

    Returns:
        dict: {
            "period": "last 7 days",
            "start_date": "2026-06-01",
            "end_date": "2026-06-08",
            "posts": [
                {
                    "id": "123...",
                    "date": "2026-06-05",
                    "type": "IMAGE|VIDEO|CAROUSEL_ALBUM",
                    "caption": "...",
                    "reach": 1234,
                    "likes": 45,
                    "comments": 12,
                    "engagement": 57
                }
            ],
            "summary": {
                "total_posts": 5,
                "total_reach": 6789,
                "total_engagement": 234,
                "avg_reach_per_post": 1357,
                "avg_likes_per_post": 9,
                "avg_comments_per_post": 2.4,
                "top_post_reach": 2100,
                "top_post_engagement": 78
            }
        }
    """
    # Вычисляем период
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Получаем все посты
    fields = (
        "id,caption,media_type,media_product_type,permalink,timestamp,"
        "like_count,comments_count,thumbnail_url,media_url"
    )
    media = graph_get_all(
        cfg, f"{cfg['node']}/media",
        params={"fields": fields, "limit": 25},
        max_items=100  # Получаем достаточно много для анализа
    )

    posts = []
    for m in media:
        # Проверяем дату
        timestamp_str = m.get("timestamp", "")
        if not timestamp_str:
            continue

        post_date = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if post_date < start_date or post_date > end_date:
            continue

        # Пытаемся получить reach через insights
        reach = None
        try:
            ins = graph_get_all(
                cfg, f"{m['id']}/insights",
                params={"metric": "reach"},
                max_items=1
            )
            if ins and isinstance(ins, list) and ins[0].get("values"):
                reach = ins[0]["values"][0].get("value")
        except Exception:
            pass

        likes = m.get("like_count", 0)
        comments = m.get("comments_count", 0)
        engagement = likes + comments

        post = {
            "id": m.get("id"),
            "date": timestamp_str[:10],
            "timestamp": timestamp_str,
            "type": m.get("media_product_type") or m.get("media_type"),
            "caption": (m.get("caption") or "")[:100],
            "reach": reach,
            "likes": likes,
            "comments": comments,
            "engagement": engagement,
        }
        posts.append(post)

    # Сортируем по дате (новые первыми)
    posts.sort(key=lambda x: x["timestamp"], reverse=True)

    # Вычисляем суммарные метрики
    total_reach = sum(p["reach"] or 0 for p in posts)
    total_likes = sum(p["likes"] or 0 for p in posts)
    total_comments = sum(p["comments"] or 0 for p in posts)
    total_engagement = total_likes + total_comments

    total_posts = len(posts)
    avg_reach = round(total_reach / max(total_posts, 1))
    avg_likes = round(total_likes / max(total_posts, 1), 1)
    avg_comments = round(total_comments / max(total_posts, 1), 1)

    top_reach = max((p["reach"] or 0 for p in posts), default=0)
    top_engagement = max((p["engagement"] or 0 for p in posts), default=0)

    result = {
        "period": f"last {days} days",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "posts": posts,
        "summary": {
            "total_posts": total_posts,
            "total_reach": total_reach,
            "total_engagement": total_engagement,
            "avg_reach_per_post": avg_reach,
            "avg_likes_per_post": avg_likes,
            "avg_comments_per_post": avg_comments,
            "top_post_reach": top_reach,
            "top_post_engagement": top_engagement,
        }
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Еженедельная аналитика Instagram охвата и вовлечённости"
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Количество дней для анализа (по умолчанию 7)"
    )
    parser.add_argument(
        "--export", choices=["json", "excel", "csv"], default="json",
        help="Формат экспорта (по умолчанию json)"
    )
    args = parser.parse_args()

    try:
        cfg = load_config()
        print(f"[INFO] Получаю аналитику за последние {args.days} дней...")

        stats = get_weekly_stats(cfg, days=args.days)

        # Печатаем результат
        print("\n" + "=" * 60)
        print(f"АНАЛИТИКА: {stats['start_date']} до {stats['end_date']}")
        print("=" * 60)

        summary = stats["summary"]
        print(f"\nВсего постов: {summary['total_posts']}")
        print(f"Всего охвата: {summary['total_reach']:,}")
        print(f"Всего вовлечённости: {summary['total_engagement']}")
        print(f"\nСредний охват на пост: {summary['avg_reach_per_post']:,}")
        print(f"Средние лайки на пост: {summary['avg_likes_per_post']}")
        print(f"Средние комментарии на пост: {summary['avg_comments_per_post']}")
        print(f"\nЛучший охват: {summary['top_post_reach']:,}")
        print(f"Лучшая вовлечённость: {summary['top_post_engagement']}")

        print(f"\n\n{len(stats['posts'])} ПОСЛЕДНИХ ПОСТОВ:")
        print("-" * 60)
        for p in stats["posts"][:10]:  # Показываем только первые 10
            print(f"\n{p['date']} | {p['type']}")
            print(f"  Охват: {p['reach'] or 'N/A'} | Лайки: {p['likes']} | Комм: {p['comments']}")
            if p['caption']:
                print(f"  {p['caption']}")

        # Сохраняем в JSON
        report_file = save_report(stats, prefix="weekly_stats")
        print(f"\n✓ Отчёт сохранён: {report_file}")

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_cli(main)
