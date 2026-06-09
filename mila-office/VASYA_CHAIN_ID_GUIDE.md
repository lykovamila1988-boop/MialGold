# Vasya Chain ID Tracking & Scheduling Decisions

## Overview

Vasya now tracks all scheduling operations using **chain_id** — a unique identifier that links all posts scheduled as part of a single planning workflow (e.g., "weekly schedule", "monthly plan", "reaction to a comment thread").

### Benefits

- **Traceability**: Instantly find all posts from a single planning decision
- **Rollback**: Cancel/reschedule all posts in a chain with one command
- **Debugging**: See the full history of scheduling decisions and errors
- **Error recovery**: If post N fails, only replan that post, not the entire chain

---

## How It Works

### 1. Chain ID Generation

Every scheduling workflow gets a unique `chain_id` automatically:

```python
from vasya import _new_chain_id

chain_id = _new_chain_id()
# Returns: "vasya_20260608_143052_a7f9c3b2"
```

Or Vasya can generate one in the Claude prompt:

```
When creating a schedule for the week, use:
chain_id = vasya_20260608_weekly_posts_abc123
```

### 2. Scheduling with Chain ID

Pass `chain_id` to every `schedule_post` call:

```json
{
  "image_url": "https://example.com/photo.jpg",
  "caption": "Привет! Это рассказ о...",
  "publish_time_utc": "2026-06-09T10:00:00Z",
  "chain_id": "vasya_20260608_weekly_posts_abc123",
  "post_type": "photo"
}
```

### 3. Decision Logging

Every scheduling decision is logged with context:

```
[2026-06-08 14:30] chain_id=vasya_20260608_weekly_posts_abc123 post_id=vasya_20260608_weekly_posts_abc123_143052 action=schedule reason=queued | Привет! Это рассказ о выборе в отношениях
[2026-06-08 14:31] chain_id=vasya_20260608_weekly_posts_abc123 post_id=vasya_20260608_weekly_posts_abc123_143101 action=schedule reason=queued | Второй пост серии
[2026-06-08 14:32] chain_id=vasya_20260608_weekly_posts_abc123 post_id=vasya_20260608_weekly_posts_abc123_143110 action=error reason=no_media_url | Третий пост (видео)
```

**Log fields:**
- `chain_id` — the planning workflow ID
- `post_id` — individual post identifier
- `action` — one of: `schedule`, `reschedule`, `skip`, `error`
- `reason` — why (e.g., `queued`, `no_media_url`, `time_conflict`, `approved_by_victoria`)
- `caption_preview` — first 50 characters of the post text

---

## Scheduling Decision Examples

### Scenario 1: Weekly Schedule (Monday)

Vasya creates a plan for Mon–Fri:

```
User: /план (create weekly schedule)

Claude/Vasya:
1. Generate chain_id = "vasya_20260609_weekly_posts_monday_f3a2c1"
2. For each day Mon-Fri:
   - Call schedule_post(..., chain_id="vasya_20260609_weekly_posts_monday_f3a2c1")
   - Log: "[timestamp] chain_id=vasya_... post_id=vasya_... action=schedule reason=queued"
3. Save state to: reports/schedules/vasya_20260609_weekly_posts_monday_f3a2c1.json
4. Show summary:
   ✓ chain_id=vasya_20260609_weekly_posts_monday_f3a2c1
   ✓ 5 posts queued (Mon-Fri)
   ✓ State saved for recovery
```

**Saved state structure:**
```json
{
  "posts": [
    {
      "id": "vasya_20260609_weekly_posts_monday_f3a2c1_100000",
      "type": "photo",
      "time": "2026-06-09T10:00:00Z",
      "status": "queued"
    },
    {
      "id": "vasya_20260609_weekly_posts_monday_f3a2c1_100001",
      "type": "reel",
      "time": "2026-06-10T10:00:00Z",
      "status": "queued"
    }
  ],
  "decisions": [
    {
      "timestamp": "2026-06-08T14:30:00",
      "post_id": "vasya_20260609_weekly_posts_monday_f3a2c1_100000",
      "action": "schedule",
      "reason": "queued"
    }
  ],
  "errors": []
}
```

### Scenario 2: Partial Failure (Media URL Missing)

If one post in the chain lacks a media URL:

```
schedule_post(
  image_url="",  # EMPTY!
  caption="Pост без фото",
  publish_time_utc="2026-06-12T10:00:00Z",
  chain_id="vasya_20260609_weekly_posts_monday_f3a2c1"
)

Result:
[2026-06-08 14:35] chain_id=vasya_20260609_weekly_posts_monday_f3a2c1 post_id=vasya_20260609_weekly_posts_monday_f3a2c1_143500 action=error reason=no_media_url | Пост без фото

State updated:
{
  "errors": [
    {
      "timestamp": "2026-06-08T14:35:00",
      "post_id": "vasya_20260609_weekly_posts_monday_f3a2c1_143500",
      "error": "Ошибка: нужна публичная ссылка на медиа (image_url должна начинаться на http)"
    }
  ]
}
```

### Scenario 3: Reschedule a Chain

Later, if Vasya needs to reschedule all posts in a chain (e.g., move everything 1 hour earlier):

```
User: "Перепланируй всё на час раньше"

Claude/Vasya:
1. Load state: chain_state = _load_chain_state("vasya_20260609_weekly_posts_monday_f3a2c1")
2. For each post in chain_state["posts"]:
   - Adjust time by -1 hour
   - Call schedule_post(..., chain_id=<same>, publish_time_utc=<new_time>)
   - Log: "[timestamp] chain_id=vasya_... action=reschedule reason=moved_earlier"
3. Save updated state
4. Show: "✓ chain_id=vasya_... 5 posts rescheduled"
```

---

## Using Chain ID for Decisions

### Example Prompt for Vasya

When the user asks "Create a weekly schedule":

```
You are Vasya, scheduling posts. When a user asks for a SCHEDULE (weekly, monthly, 
by theme, etc.), follow this workflow:

1. Generate a unique chain_id with _new_chain_id():
   chain_id = f"vasya_{datetime.now():%Y%m%d}_weekly_posts_{uuid.uuid4().hex[:8]}"
   
2. For each post to schedule:
   - Validate: image_url (must be public http/https), caption (non-empty)
   - Call schedule_post(image_url, caption, time, chain_id=<above>, post_type=...)
   - Do NOT ignore errors; if one post fails, continue and log it
   
3. After all posts are submitted:
   - Show summary: "✓ chain_id=vasya_... N posts scheduled, M errors"
   - Never recommend publishing immediately; always use schedule_post
   
4. Log all decisions:
   - Success → log(action="schedule", reason="queued")
   - Error → log(action="error", reason=<specific>)
```

---

## Debugging: Viewing Logs & States

### View Scheduling Logs (Last 24 Hours)

```python
from vasya import get_scheduling_logs

logs = get_scheduling_logs(hours=24)
print(logs)
```

Output:
```
[2026-06-08 14:30:12] chain_id=vasya_20260608_weekly_posts_abc123 post_id=vasya_20260608_weekly_posts_abc123_143012 action=schedule reason=queued | Привет! Это рассказ о выборе
[2026-06-08 14:30:45] chain_id=vasya_20260608_weekly_posts_abc123 post_id=vasya_20260608_weekly_posts_abc123_143045 action=schedule reason=queued | Второй пост серии
[2026-06-08 14:31:10] chain_id=vasya_20260608_weekly_posts_abc123 post_id=vasya_20260608_weekly_posts_abc123_143110 action=error reason=no_media_url | Третий пост (видео)
```

### List Active Chains

```python
from vasya import list_chain_states

states = list_chain_states()
print(states)
```

Output:
```
📋 vasya_20260608_143000_a7f9c3b2: 5 posts
📋 vasya_20260608_weekly_posts_abc123: 2 posts, 1 error
📋 vasya_20260607_monthly_plan_xyz789: 10 posts
```

### Load Full State for a Chain

```python
from vasya import _load_chain_state
import json

state = _load_chain_state("vasya_20260608_weekly_posts_abc123")
print(json.dumps(state, indent=2))
```

---

## Integration Points

### 1. Pipeline Integration

The `pipeline.enqueue()` function now accepts `chain_id`:

```python
item = pipeline.enqueue(
    post_type="photo",
    image_url="https://...",
    caption="...",
    publish_time_utc="2026-06-09T10:00:00Z",
    status="approved",
    source="vasya",
    chain_id="vasya_20260608_weekly_posts_abc123"  # NEW
)
```

### 2. Recovery After Failures

If Vasya crashes mid-schedule:

```python
# Reload the chain and retry only failed posts
chain_id = "vasya_20260608_weekly_posts_abc123"
state = _load_chain_state(chain_id)

failed_posts = [p for p in state.get("posts", []) if p["status"] != "queued"]
for post in failed_posts:
    # Resubmit failed post with new timestamp
    schedule_post(post["image_url"], post["caption"], post["time"], chain_id)
```

### 3. Reporting & Analytics

Query all scheduling decisions for metrics:

```python
# Count posts by chain
from pathlib import Path
import json

schedule_dir = Path("E:/MILA GOLD/reports/schedules")
for chain_file in schedule_dir.glob("*.json"):
    state = json.loads(chain_file.read_text())
    success = len([p for p in state["posts"] if p["status"] == "queued"])
    errors = len(state["errors"])
    print(f"{chain_file.stem}: {success} success, {errors} errors")
```

---

## API Reference

### `_new_chain_id(prefix: str = "vasya") -> str`

Generates a unique chain ID.

```python
id1 = _new_chain_id()  # "vasya_20260608_143052_a7f9c3b2"
id2 = _new_chain_id("content")  # "content_20260608_143100_xyz789"
```

### `_load_chain_state(chain_id: str) -> dict`

Loads saved state for a chain (or empty dict if not found).

```python
state = _load_chain_state("vasya_20260608_weekly_posts_abc123")
# {'posts': [...], 'decisions': [...], 'errors': [...]}
```

### `_save_chain_state(chain_id: str, state: dict)`

Saves state after modifying it (called automatically by `schedule_post`).

```python
_save_chain_state("vasya_20260608_weekly_posts_abc123", state)
```

### `_log_scheduling_decision(chain_id, post_id, action, reason, caption_preview="")`

Logs a scheduling decision (called automatically by `schedule_post`).

```python
_log_scheduling_decision(
    "vasya_20260608_weekly_posts_abc123",
    "vasya_20260608_weekly_posts_abc123_143012",
    action="schedule",
    reason="queued",
    caption_preview="Привет! Это рассказ о выборе"
)
```

### `schedule_post(image_url, caption, publish_time_utc, chain_id, post_type="photo") -> str`

Schedules a post and updates chain state.

**Parameters:**
- `image_url` (str) – public HTTP(S) URL to media
- `caption` (str) – post text (non-empty)
- `publish_time_utc` (str) – ISO 8601 timestamp
- `chain_id` (str) – workflow identifier
- `post_type` (str) – "photo", "reel", "story", or "carousel" (default: "photo")

**Returns:** status message (starts with ✓ on success, ⚠️ or ❌ on error)

**Side effects:**
- Enqueues post to `pipeline.py`
- Logs decision to `logs/scheduler.log`
- Saves chain state to `reports/schedules/<chain_id>.json`

---

## Example: Weekly Schedule Workflow

```
User: /план (create weekly schedule)

Vasya:
1. Read 02-content/content-plan.md to find this week's themes
2. Generate chain_id = "vasya_20260609_weekly_schedule_f3a2c1"
3. For Mon-Fri:
   - Load draft from 02-content/posts/draft_*
   - Extract image_url, caption
   - Call schedule_post(..., chain_id=vasya_20260609_weekly_schedule_f3a2c1)
   - Log success or error
4. Show summary:
   ✓ chain_id=vasya_20260609_weekly_schedule_f3a2c1
   ✓ 5 posts queued
   ✓ 0 errors
   ✓ State saved to reports/schedules/
5. Suggest next: "Check back Friday for the Friday offer post"
```

---

## FAQ

**Q: Do I need to pass chain_id every time?**
A: Yes, but Vasya will do it automatically. When creating a new schedule workflow, he generates one; when updating an existing one, he uses the same ID.

**Q: What if I want to cancel all posts in a chain?**
A: Load the state with `_load_chain_state()`, then call a cancel function (to be implemented) for each post_id. The chain state will track which posts were cancelled.

**Q: Can two chains have overlapping times?**
A: Yes, but `pipeline.py` should detect and warn about conflicts. Chain IDs help identify which planning workflow caused the conflict.

**Q: Where are the logs stored?**
A: `E:\MILA GOLD\logs\scheduler.log` (appended, never truncated)

**Q: Where are the chain states?**
A: `E:\MILA GOLD\reports\schedules\<chain_id>.json` (one JSON file per chain)

