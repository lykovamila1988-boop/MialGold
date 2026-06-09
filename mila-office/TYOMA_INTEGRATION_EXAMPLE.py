"""
TYOMA INTEGRATION EXAMPLE: How to use chain_id for cross-posting

This shows how Marina (Instagram agent) and Tyoma (Telegram agent) coordinate
using the unified message queue and chain_id synchronization.

See: TELEGRAM_CROSS_POSTING_GUIDE.md for full architecture
"""

import memory
import uuid
from datetime import datetime


# ─── SCENARIO 1: Marina Creates Instagram Post ───────────────────────────────
def marina_create_post_with_chainid():
    """
    Marina (Instagram agent) creates a post and assigns chain_id.
    This happens in the P1 (content creation) phase.
    """

    # Generate unique chain_id for this content piece
    post_title = "Паттерн Спасателя"
    timestamp = datetime.now().isoformat()[:10].replace("-", "")  # e.g., "20260608"
    chain_id = f"ig_{timestamp}_{str(uuid.uuid4())[:6]}"  # e.g., "ig_20260608_a1b2c3"

    instagram_caption = """Когда мы спасаем партнёра, мы теряем себя.

Паттерн Спасателя = помощь, которая контролирует.

Что происходит:
💔 Codependency (привязанность через помощь)
🔴 Обида и resentment (партнёр не ценит "жертвы")
🚫 Потеря своих границ

Как выйти?
1. Спроси себя: это мой вопрос или его?
2. Дай ему выбор (не спасай, предложи)
3. Отпусти ответственность

Дальше — в практикуме (раздел про Спасателя)."""

    # Put in the unified queue with chain_id
    msg_result = memory.queue_message(
        channel="instagram_comments",
        text=instagram_caption,
        confirm=False,
        metadata={
            "chain_id": chain_id,
            "source": "marina",
            "content_type": "insight",
            "post_title": post_title,
            "platform": "instagram",
            "created_at": timestamp,
        }
    )

    print(f"✓ Marina created Instagram post")
    print(f"  Chain ID: {chain_id}")
    print(f"  Title: {post_title}")
    print(f"  Queue status: {msg_result.get('status')}")

    return chain_id


# ─── SCENARIO 2: Vasya Publishes to Instagram (P3) ──────────────────────────
def vasya_publish_to_instagram(chain_id):
    """
    Vasya (Publisher/Scheduler) takes message from queue and publishes to Instagram.
    IMPORTANT: Preserves chain_id in metadata so Tyoma can find it later.
    """

    # In real workflow, Vasya would:
    # 1. Check approval status (Victoria already reviewed in P2)
    # 2. Call Instagram API to publish
    # 3. Get back media_id
    # 4. Record in published registry with chain_id

    media_id = "123456789_987654321"  # From Instagram API response

    # Record the published post with chain_id for 48h measurement loop
    memory.record_published(
        media_id=media_id,
        theme="спасатель",  # For analytics
        hook="Когда мы спасаем партнёра...",
        extra={
            "chain_id": chain_id,  # ← THIS IS KEY: Links to Instagram version
            "source": "marina",
            "posted_to": ["instagram"],
            "message_id": None,  # Not yet on Telegram
        }
    )

    print(f"✓ Vasya published to Instagram")
    print(f"  Media ID: {media_id}")
    print(f"  Preserved chain_id: {chain_id}")

    return media_id


# ─── SCENARIO 3: Tyoma Adapts for Telegram ──────────────────────────────────
def tyoma_adapt_for_telegram(chain_id):
    """
    Tyoma (Telegram agent) finds the Instagram post and adapts it for Telegram.

    Key differences:
    - Longer text (one idea per message is OK in Telegram)
    - Full links & CTAs (Instagram bans links)
    - More emoji (helps scanning)
    - Channels/buttons instead of comments
    """

    # Step 1: Get context from Instagram version
    context = get_cross_post_context(chain_id)
    if not context.get("found"):
        print("⚠️ Instagram post not found. Skipping.")
        return None

    original_text = context.get("original_text", "")

    # Step 2: Adapt for Telegram (different voice, add links)
    telegram_text = f"""🚨 Когда мы спасаем партнёра, мы теряем себя.

Паттерн Спасателя = попытка контролировать поведение другого через помощь.

Что происходит:
💔 Codependency — привязанность через "нужность"
🔴 Обида и resentment — партнёр не ценит наши жертвы
🚫 Потеря границ — его проблемы становятся моими

Почему так получается?
Когда мы молоды, нас награждают за помощь:
✓ "Какая ты добрая!"
✓ "Спасибо, что помогла"
✓ "Только ты понимаешь"

Но во взрослых отношениях этот паттерн становится ядом.

Как выйти?
1️⃣ Спросить себя: это МОЙ вопрос или ЕГО?
   (Часто мы решаем чужие проблемы вместо своих)

2️⃣ Дать ему выбор (не спасай!)
   Вместо: "Я знаю как тебе помочь"
   Говори: "Вот варианты. Что ты выбираешь?"

3️⃣ Отпустить ответственность
   Ты не можешь спасти никого. Только он может спасти себя.

📌 Читай в практикуме раздел "Паттерны" → "Спасатель"
💬 Вопросы? Напиши ХОЧУ → я отвечу в личное сообщение
🎯 Консультация с психологом: https://calendly.com/lyudmila/diagnostic

#отношения #паттерны #психология"""

    # Step 3: Put in Telegram queue with same chain_id
    result = memory.queue_message(
        channel="telegram",
        text=telegram_text,
        confirm=False,
        metadata={
            "chain_id": chain_id,  # ← Same chain_id as Instagram!
            "source": "tyoma",
            "adapted_from_instagram": True,
            "content_type": "insight",
            "platform": "telegram",
            "created_at": datetime.now().isoformat(),
        }
    )

    print(f"✓ Tyoma adapted for Telegram")
    print(f"  Chain ID: {chain_id}")
    print(f"  Status: {result.get('status')}")
    print(f"  Telegram-specific features:")
    print(f"    - Full Calendly link (Instagram bans links)")
    print(f"    - More emoji (helps scanning)")
    print(f"    - Longer text (one idea per message)")
    print(f"    - Direct ХОЧУ response (DM instead of comments)")

    return result


def get_cross_post_context(chain_id):
    """
    Find the Instagram post in queue by chain_id.
    This is what tyoma.get_cross_post_context() does.
    """
    pending = memory.get_pending_messages(channel="instagram_comments", limit=100)
    for msg in pending:
        if msg.get("metadata", {}).get("chain_id") == chain_id:
            return {
                "ok": True,
                "found": True,
                "chain_id": chain_id,
                "original_text": msg.get("text", "")[:500],
                "original_type": msg.get("metadata", {}).get("content_type"),
                "source": "instagram",
            }
    return {"ok": True, "found": False, "chain_id": chain_id}


# ─── SCENARIO 4: Analytics - Compare Performance ──────────────────────────────
def compare_cross_post_performance(chain_id):
    """
    After 48 hours, measure which version (Instagram vs Telegram) performed better.
    Both share the same chain_id, so we can correlate metrics.
    """

    print(f"\n📊 Comparing cross-post performance for {chain_id}:")
    print()
    print("INSTAGRAM:")
    print("  Reach: 1,240 | Likes: 87 | Comments: 12")
    print("  Engagement rate: 7.9%")
    print("  Type: Reel (algorithm favors video)")
    print()
    print("TELEGRAM:")
    print("  Views: 245 | Reactions: 34")
    print("  Clicks to Calendly: 8")
    print("  'ХОЧУ' responses: 3")
    print("  Type: Text + link (direct CTA)")
    print()
    print("ANALYSIS:")
    print("  ✓ Instagram reaches more (algorithm boost)")
    print("  ✓ Telegram has higher CTA conversion (direct links, ХОЧУ)")
    print("  → Strategy: Keep both! Instagram for awareness, Telegram for conversion")


# ─── SCENARIO 5: Telegram-Only Content (No Instagram) ──────────────────────
def tyoma_create_telegram_only_post():
    """
    Sometimes Tyoma publishes content that never goes to Instagram.
    Example: Welcome sequence for new Telegram subscribers, fast responses, etc.

    Still uses chain_id, but it's generated locally (tg_ prefix).
    """

    # Generate chain_id for Telegram-only content
    chain_id = f"tg_{str(uuid.uuid4())[:8]}"

    welcome_msg = """Привет! Я — Людмила, психолог, работаю с женщинами в трудных отношениях.

Здесь в канале я делюсь инсайтами про три паттерна выбора партнёра:
🚨 Спасатель — помогаю и контролирую
😔 Угодница — угождаю и теряю себя
🏃 Избегание — убегаю от близости

Каждый паттерн — способ справиться с тревогой в отношениях.

Постов: понедельник, среда, пятница (10:00 UTC)
Пятница: специальное предложение на диагностику

👉 Напиши ХОЧУ если готова к консультации"""

    result = memory.queue_message(
        channel="telegram",
        text=welcome_msg,
        confirm=False,
        metadata={
            "chain_id": chain_id,  # Telegram-only chain_id
            "source": "tyoma",
            "content_type": "welcome",
            "platform": "telegram",
            "instagram_version": None,  # No Instagram equivalent
        }
    )

    print(f"✓ Tyoma created Telegram-only welcome message")
    print(f"  Chain ID: {chain_id} (tg_ prefix = Telegram-only)")
    print(f"  Status: {result.get('status')}")

    return chain_id


# ─── MAIN: Run Examples ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("TYOMA CROSS-POSTING INTEGRATION EXAMPLE")
    print("=" * 70)
    print()

    # Example 1: Marina creates with chain_id
    chain_id = marina_create_post_with_chainid()
    print()

    # Example 2: Vasya publishes and preserves chain_id
    media_id = vasya_publish_to_instagram(chain_id)
    print()

    # Example 3: Tyoma adapts for Telegram
    tyoma_adapt_for_telegram(chain_id)
    print()

    # Example 4: Analytics
    compare_cross_post_performance(chain_id)
    print()

    # Example 5: Telegram-only
    tg_chain_id = tyoma_create_telegram_only_post()
    print()

    print("=" * 70)
    print("HOW IT WORKS:")
    print("=" * 70)
    print("""
1. Marina creates Instagram post → assigns chain_id → puts in queue

2. Vasya publishes to Instagram → preserves chain_id → records in registry

3. Tyoma finds Instagram version by chain_id → adapts for Telegram → puts in queue

4. Both versions share metadata: same chain_id, different content

5. Analytics: Compare Instagram metrics vs Telegram conversion in 48h

Result: One idea, two platforms, two voices, one sync system.
""")

    print("See TELEGRAM_CROSS_POSTING_GUIDE.md for full documentation.")
