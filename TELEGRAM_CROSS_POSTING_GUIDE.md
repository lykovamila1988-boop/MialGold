# Telegram Cross-Posting Architecture: Tyoma + Chain ID

## Overview

Updated **Tyoma** (Telegram agent) now supports **cross-posting** from Instagram to Telegram using a unified `chain_id` system. This enables content synchronization while allowing Telegram-specific adaptations (links, buttons, shorter text).

---

## Key Concepts

### Chain ID (`chain_id`)
- **Unique identifier** for a content piece across platforms
- Format: `ig_12345678` (Instagram source) or `tg_87654321` (Telegram-only)
- Links a single piece of content to its Instagram version, Telegram version, etc.
- Stored in **metadata** of every message in the unified queue

### Unified Message Queue
All platforms share one queue (`memory.queue_message()`):
- **Instagram comments**: channel `"instagram_comments"`, metadata includes `chain_id`
- **Telegram messages**: channel `"telegram"`, metadata includes `chain_id`
- **Threads posts**: channel `"threads"`, metadata includes `chain_id`

This is how Marina (Instagram) and Tyoma (Telegram) communicate without knowing about each other directly.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT CREATION (Marina)                │
│  Reads: MILA-BUSINESS/02-content/posts/YYYY-MM-DD.md       │
│  Creates Instagram caption + generates chain_id              │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│        UNIFIED MESSAGE QUEUE (memory.queue_message)          │
│                                                              │
│  {                                                           │
│    "id": "msg_...",                                         │
│    "channel": "instagram_comments",  ← or "telegram"       │
│    "text": "Caption/text",                                  │
│    "status": "pending",                                     │
│    "metadata": {                                            │
│      "chain_id": "ig_12345678",      ← SYNC KEY            │
│      "source": "instagram",                                 │
│      "content_type": "insight"                              │
│    }                                                        │
│  }                                                          │
│                                                              │
└────────────┬─────────────────────────┬──────────────────────┘
             │                         │
             ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │ Vasya (Publisher)│      │ Tyoma (Telegram) │
    │ (P3: Publish)    │      │ (Adapt + Send)   │
    │                  │      │                  │
    │ Uses chain_id to │      │ Uses chain_id to │
    │ link to original │      │ find Instagram   │
    │ post for 48h     │      │ version for      │
    │ measurement loop │      │ context/links    │
    └──────────────────┘      └──────────────────┘
             │                         │
             ▼                         ▼
       Instagram Post          Telegram Message
```

---

## How to Use: Step-by-Step

### Step 1: Marina Creates a Post (Instagram)

Marina (socialmedia agent) creates a post in `MILA-BUSINESS/02-content/posts/`:

```markdown
# 2026-06-08 Паттерн Спасателя

Когда мы пытаемся спасти другого человека...
[full post content]

#тревога #отношения
```

When Marina puts this in the queue, she:
1. Creates a `chain_id` (e.g., `ig_a1b2c3d4`)
2. Calls `memory.queue_message("instagram_comments", text, metadata={"chain_id": "ig_a1b2c3d4", ...})`
3. Returns the chain_id to the workflow

### Step 2: Vasya Publishes to Instagram (P3)

Vasya's workflow:
1. Takes message from queue with `channel="instagram_comments"`
2. **Preserves the `chain_id`** in metadata
3. Publishes to Instagram
4. Records in `memory.record_published(media_id=..., theme="спасатель", extra={"chain_id": "ig_a1b2c3d4"})`

**Why?** So Tyoma can find it later and know it's already published.

### Step 3: Tyoma Adapts for Telegram

When Tyoma needs to create Telegram content:

#### Option A: Automatic Cross-Posting (Best)
Tyoma polls the queue for new Instagram posts:
```python
pending = memory.get_pending_messages(channel="instagram_comments", limit=50)
for msg in pending:
    chain_id = msg.get("metadata", {}).get("chain_id")
    if chain_id:
        # This is a cross-post candidate
        tyoma.adapt_for_telegram(chain_id)
```

#### Option B: Manual Cross-Post via Slash Command
```
/кросс ig_a1b2c3d4
```

Tyoma:
1. Calls `get_cross_post_context("ig_a1b2c3d4")`
2. Retrieves original Instagram text from queue
3. Adapts it for Telegram:
   - Shorter (one idea = one message)
   - Adds links: `https://календли.com/` or `https://gumroad.com/`
   - Emoji support (Instagram doesn't allow links, so Telegram gets richer text)
4. Calls `send_to_queue(telegram_text, chain_id="ig_a1b2c3d4", content_type="insight")`

#### Option C: Telegram-Only Content
No Instagram version? Tyoma creates independent post:
```python
send_to_queue(
    text="Сообщение только для Telegram",
    chain_id="",  # ← Empty: no Instagram link
    content_type="welcome"
)
```
Tyoma auto-generates `chain_id = "tg_87654321"` for tracking.

---

## API Reference

### `send_to_queue(text, channel_id="", chat_id="", chain_id="", content_type="")`

**Parameters:**
- `text` (str, required): Message text
- `channel_id` (str): Telegram channel ID (for channel posts)
- `chat_id` (str): Telegram user/chat ID (for DMs)
- `chain_id` (str): Link to Instagram version (leave empty for Telegram-only)
- `content_type` (str): Type of content — `"insight"`, `"case"`, `"practice"`, `"offer"`, `"diagnostic"`, `"welcome"`

**Returns:**
```json
{
  "status": "queued",
  "message": "✓ В очередь",
  "id": "msg_1717862400000",
  "chain_id": "ig_a1b2c3d4"
}
```

**Example: Cross-Post Instagram Insight to Telegram**
```python
send_to_queue(
    text="Когда мы пытаемся спасти партнёра...\n\n📌 Читай практикум: [ссылка]\n📞 Консультация: [ссылка]",
    channel_id="-1001234567890",  # Telegram channel ID
    chain_id="ig_a1b2c3d4",  # Link to Instagram version
    content_type="insight"
)
```

---

### `get_cross_post_context(chain_id)`

**Purpose:** Retrieve Instagram post content for Telegram adaptation.

**Returns:**
```json
{
  "ok": true,
  "found": true,
  "chain_id": "ig_a1b2c3d4",
  "original_text": "Когда мы пытаемся спасти...",
  "original_type": "insight",
  "source": "instagram",
  "note": "Адаптируй этот контент для Telegram: добавь ссылки..."
}
```

Or (if not in pending queue, already published):
```json
{
  "ok": true,
  "found": false,
  "chain_id": "ig_a1b2c3d4",
  "note": "Пост может быть уже опубликован. Скажи что публиковать в Telegram."
}
```

---

### `list_pending_telegram(limit=10)`

**Purpose:** Show what's waiting to be sent to Telegram.

**Returns:**
```json
{
  "status": "ok",
  "count": 3,
  "limit": 10,
  "items": [
    {
      "id": "msg_1717862400000",
      "text": "Когда мы пытаемся спасти...",
      "status": "pending",
      "type": "insight",
      "chain_id": "ig_a1b2c3d4",
      "created_at": "2026-06-08T10:00:00Z"
    }
  ]
}
```

---

## Telegram-Specific Adaptations

### Links & CTAs
**Instagram:** No links in captions (shadowban risk)
```
Диагностика → напиши ХОЧУ в комментарии
```

**Telegram:** Full links + buttons
```
Диагностика → https://календли.com/Lyudmila/diagnostic
```

### Text Length
**Instagram:** Shorter captions (algorithm favors)
```
Когда мы спасаем партнёра, мы теряем себя.
Это паттерн Спасателя.
```

**Telegram:** Can be longer, one thought per message
```
Когда мы спасаем партнёра, мы теряем себя.

Паттерн Спасателя = попытка контролировать поведение другого через помощь.

Результат: codependency, resentment, потеря границ.

Что делать?
1. Спросить себя: чей это вопрос? (Мой или его?)
2. Дать ему выбор
3. Отпустить ответственность

📌 Читай в практикуме раздел про Спасателя
💬 Напиши ХОЧУ если хочешь консультацию
```

### Emoji Usage
**Instagram:** Minimal (too many = looks spammy)
```
Паттерн Спасателя — помощь, которая контролирует
```

**Telegram:** Emoji-friendly
```
🚨 Паттерн Спасателя = попытка контролировать через помощь
💭 Последствия: codependency, resentment
✅ Решение: 3 шага
📌 Практикум
🎯 Консультация
```

---

## Integration with Vasya (Scheduler/Publisher)

Vasya's workflow must **preserve `chain_id`** in published registry:

```python
# In vasya.py or publisher workflow
memory.record_published(
    media_id="instagram_12345678",
    theme="спасатель",
    hook="Когда мы пытаемся спасти...",
    extra={
        "chain_id": "ig_a1b2c3d4",  # ADD THIS
        "source": "marina",
        "posted_to": ["instagram"],
    }
)
```

---

## Quick Slash Commands

| Command | Purpose |
|---------|---------|
| `/новые` | Check new bot messages |
| `/пост` | Prepare a post from `04-telegram/` |
| `/цепочка` | Queue the welcome sequence |
| `/создай` | Create 3 posts for the week |
| `/статус` | Show queue + channel stats |
| `/синхро` | Auto-sync new Instagram posts |
| `/кросс CHAIN_ID` | Manually adapt one post |
| `/очередь` | Show pending messages |

---

## Files Modified

- **`mila-office/tyoma.py`** — Updated with chain_id support
- **`mila-office/memory.py`** — No changes (already supports metadata)
- **`mila-office/shared_tools.py`** — No changes

## Key Changes in tyoma.py

1. **`send_to_queue()`** — Now accepts `chain_id` and `content_type`
2. **`get_cross_post_context()`** — New tool to retrieve Instagram post for adaptation
3. **`list_pending_telegram()`** — New tool to show queue status
4. **System prompt** — Updated to explain Telegram context, cross-posting strategy
5. **QUICK commands** — Added `/синхро`, `/кросс`, `/очередь` for cross-posting
