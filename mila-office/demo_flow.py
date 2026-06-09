#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Demo: Pipeline Marina - Victoria - Tyoma (bez vyzova realnyh agentov)

Pokazyvaet kak rabotaet avtomatizacija sozdanija i publikacii kontenta.
"""

import json
import sys
import os
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Demo посты которые Marina "создала" бы
DEMO_POSTS = [
    {
        "type": "инсайт",
        "title": "Паттерн Спасателя",
        "text": "Паттерн Спасателя — это когда ты спешишь помочь, даже если не просили.\n✓ Спешишь на помощь подруге\n✓ Берёшь на себя проблемы парня\n✓ Ищешь подтверждение через благодарность\nЭто не про добро — это про потребность быть нужной.",
        "cta": "Узнай больше в консультации"
    },
    {
        "type": "кейс",
        "title": "История Наташи",
        "text": "Наташа всегда спешила в отношения. Познакомится — уже выбирает кольца 💍\n\nДумала что это любовь. На самом деле — страх остаться одной.\n\nЧерез диагностику мы нашли паттерн: папа уходил по командировкам → мама переживала → Наташа решила быть хорошей чтоб папа не ушёл.\n\nРезультат: теперь Наташа выбирает партнёра осознанно.",
        "cta": "Запиши диагностику"
    },
    {
        "type": "практика",
        "title": "Упражнение: 5 минут на себя",
        "text": "Возьми 5 минут. Закрой глаза. Ответь одно:\n'Чего я хочу, если не думать про других?'\n\nНе 'что должна'\nНе 'что ожидают'\nПросто: что я хочу?\n\nЭто упражнение показывает как часто ты игнорируешь свои потребности.",
        "cta": None
    }
]


def demo_marina_creates():
    """Демо: Marina создаёт посты"""
    print("\n" + "="*80)
    print("[P1] Marina: creating posts")
    print("="*80)

    posts = []
    for i, post_data in enumerate(DEMO_POSTS, 1):
        post = {
            **post_data,
            'id': f"post_{i}_{int(datetime.now().timestamp())}",
            'status': 'draft',
            'created_at': datetime.now().isoformat(),
            'created_by': 'marina',
            'version': 1
        }
        posts.append(post)
        print(f"  {i}. [{post['type'].upper()}] {post['title']}")
        print(f"     ID: {post['id']}")

    print(f"\n[OK] Marina created {len(posts)} posts")
    return posts


def demo_victoria_reviews(posts):
    """Демо: Victoria редактирует"""
    print("\n" + "="*80)
    print("[P2] ✏️  Victoria: reviewing посты")
    print("="*80)

    reviewed = []
    for post in posts:
        # Victoria одобряет все (в реальности может попросить правки)
        post['status'] = 'approved'
        post['reviewed_by'] = 'victoria'
        post['reviewed_at'] = datetime.now().isoformat()
        post['feedback'] = "Отлично! Тон верный, структура понятна."

        reviewed.append(post)
        print(f"  ✓ {post['title']} → ОДОБРЕНО")

    approved_count = sum(1 for p in reviewed if p['status'] == 'approved')
    print(f"\n✅ Victoria approved {approved_count}/{len(reviewed)} posts")
    return reviewed


def demo_tyoma_publishes(posts):
    """Демо: Tyoma публикует в Telegram"""
    print("\n" + "="*80)
    print("[P3] 📱 Tyoma: публикую в Telegram")
    print("="*80)

    published = []
    for post in posts:
        if post['status'] != 'approved':
            continue

        post['status'] = 'published'
        post['published_by'] = 'tyoma'
        post['published_at'] = datetime.now().isoformat()
        post['telegram_message_id'] = f"msg_{len(published) + 100}"

        published.append(post)
        print(f"  ✓ [{post['type'].upper()}] {post['title']}")
        print(f"    → Message ID: {post['telegram_message_id']}")
        print(f"    → Канал: {'-1003005733230'}")

    print(f"\n✅ Tyoma published {len(published)} posts в Telegram канал")
    return published


def run_demo_pipeline():
    """Полный pipeline: Marina → Victoria → Tyoma"""

    print("\n\n")
    print("="*80)
    print("  DEMO: ПОЛНЫЙ PIPELINE СОЗДАНИЯ И ПУБЛИКАЦИИ CONTENTА".center(80))
    print("  Marina -> Victoria -> Tyoma".center(80))
    print("="*80)

    # Шаг 1: Marina создаёт
    posts = demo_marina_creates()

    # Шаг 2: Victoria редактирует
    posts = demo_victoria_reviews(posts)

    # Шаг 3: Tyoma публикует
    posts = demo_tyoma_publishes(posts)

    # Итоговая статистика
    print("\n" + "="*80)
    print("📊 SUMMARY STATS")
    print("="*80)

    stats = {
        "created": len([p for p in posts if p['created_by'] == 'marina']),
        "approved": len([p for p in posts if p['status'] == 'approved' or p['reviewed_by'] == 'victoria']),
        "published": len([p for p in posts if p['status'] == 'published']),
    }

    print(f"\n✓ Created by Marina:       {stats['created']} posts")
    print(f"✓ Approved by Victoria:    {stats['approved']} posts")
    print(f"✓ Published by Tyoma:   {stats['published']} posts в Telegram")
    print(f"\n✅ SUCCESS: {stats['published']}/{stats['created']} posts passed all pipeline!")

    print("\n" + "="*80)
    print("📝 PUBLISHED CONTENT")
    print("="*80)

    for post in posts:
        if post['status'] == 'published':
            print(f"\n[{post['type'].upper()}] {post['title']}")
            print("-" * 80)
            print(post['text'])
            if post.get('cta'):
                print(f"\nCTA: {post['cta']}")
            print()

    return {
        "status": "completed",
        "posts": posts,
        "stats": stats
    }


if __name__ == "__main__":
    result = run_demo_pipeline()

    # Сохранить результат
    output_file = "logs/demo_pipeline_result.json"
    os.makedirs("logs", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Result saved: {output_file}")
