# Chain ID Implementation — Integration with Pipeline

This document describes the changes to Vasya and what needs to be updated in `pipeline.py` to fully support chain_id tracking.

## Changes to Vasya (COMPLETED)

### New Functions

1. **`_new_chain_id(prefix="vasya") → str`**
   - Generates unique chain ID: `vasya_20260608_143052_a7f9c3b2`
   - Called once per scheduling workflow, reused for all posts in that workflow

2. **`_load_chain_state(chain_id) → dict`**
   - Loads checkpoint: `{'posts': [...], 'decisions': [...], 'errors': [...]}`
   - Used to recover after failures or when rescheduling

3. **`_save_chain_state(chain_id, state) → None`**
   - Persists state to `reports/schedules/<chain_id>.json`
   - Called after each post is queued, on error, and at checkpoint

4. **`_log_scheduling_decision(chain_id, post_id, action, reason, caption_preview="")`**
   - Writes to `logs/scheduler.log`
   - Format: `[timestamp] chain_id=<id> post_id=<id> action=<action> reason=<reason> | caption`

5. **`schedule_post(..., chain_id, post_type="photo") → str`**
   - Now requires `chain_id` parameter (enforced in TOOLS schema)
   - Logs every decision (success, error, validation failure)
   - Saves/updates chain state on every call

### New Slash Commands

- **`/логи`** – View scheduling logs (last 24 hours)
- Helper functions: `get_scheduling_logs(hours=24)`, `list_chain_states()`

### System Prompt Update

Vasya's system prompt now includes:
- Instruction to generate chain_id for every schedule workflow
- Logging requirement (log all decisions with reason)
- Note about chain_id reuse when rescheduling

---

## Required Changes to pipeline.py

To fully leverage chain_id tracking, `pipeline.py` needs these updates:

### 1. Accept chain_id in `enqueue()` Function

```python
# Current signature (approx line 120–140)
def enqueue(post_type, image_url, caption, publish_time_utc, status="approved", source=""):
    # ...

# NEW signature:
def enqueue(post_type, image_url, caption, publish_time_utc, status="approved", source="", chain_id=""):
    item = {
        "id": <generate_uuid>,
        "type": post_type,
        "image_url": image_url,
        "caption": caption,
        "publish_time_utc": publish_time_utc,
        "status": status,
        "source": source,
        "chain_id": chain_id,  # NEW: track which workflow this post belongs to
        "created_at": datetime.now().isoformat()
    }
    # Save to queue (JSON file or DB)
    return item
```

### 2. Store chain_id in Queue Items

The queue (currently stored as JSON in `reports/publishing_queue_*.json` or similar) should include chain_id:

```json
{
  "id": "uuid-12345",
  "type": "photo",
  "image_url": "https://...",
  "caption": "...",
  "publish_time_utc": "2026-06-09T10:00:00Z",
  "status": "queued",
  "source": "vasya",
  "chain_id": "vasya_20260609_weekly_posts_abc123",
  "created_at": "2026-06-08T14:30:00Z"
}
```

### 3. Add Query Functions for Chain Operations

```python
def get_chain_posts(chain_id):
    """Return all posts in a chain."""
    queue = load_queue()
    return [item for item in queue if item.get("chain_id") == chain_id]

def update_chain_status(chain_id, new_status):
    """Bulk update all posts in a chain."""
    queue = load_queue()
    for item in queue:
        if item.get("chain_id") == chain_id:
            item["status"] = new_status
    save_queue(queue)

def cancel_chain(chain_id):
    """Cancel all posts in a chain."""
    queue = load_queue()
    queue = [item for item in queue if item.get("chain_id") != chain_id]
    save_queue(queue)

def reschedule_chain(chain_id, time_offset_minutes):
    """Move all posts in a chain by N minutes."""
    queue = load_queue()
    for item in queue:
        if item.get("chain_id") == chain_id:
            current_time = datetime.fromisoformat(item["publish_time_utc"])
            new_time = current_time + timedelta(minutes=time_offset_minutes)
            item["publish_time_utc"] = new_time.isoformat()
    save_queue(queue)
```

### 4. Log Chain Operations in Pipeline

When publishing a post:

```python
def publish_due():
    """Publish posts whose time has arrived."""
    for item in queue:
        if item["status"] == "queued" and is_time_due(item["publish_time_utc"]):
            try:
                graph_api.post_instagram(item["image_url"], item["caption"])
                item["status"] = "published"
                item["published_at"] = datetime.now().isoformat()
                
                # Log to pipeline-specific log
                log("pipeline", f"Published chain_id={item.get('chain_id')} post_id={item['id']}")
            except Exception as e:
                item["status"] = "failed"
                item["error"] = str(e)
                log("pipeline", f"Failed chain_id={item.get('chain_id')} post_id={item['id']} error={e}")
```

---

## Usage Flow (End-to-End)

### 1. User asks Vasya to create a schedule

```
User: /план (weekly schedule)
```

### 2. Vasya generates chain_id and calls schedule_post

```python
chain_id = _new_chain_id()  # "vasya_20260609_weekly_abc123"

for day, content in weekly_posts:
    schedule_post(
        image_url=content["url"],
        caption=content["text"],
        publish_time_utc=content["time"],
        chain_id=chain_id,  # Same for all posts in this workflow
        post_type="photo"
    )
    # Internally:
    # - Calls pipeline.enqueue(..., chain_id=chain_id)
    # - Logs decision to scheduler.log
    # - Updates chain state in reports/schedules/<chain_id>.json
```

### 3. Logs are created

```
logs/scheduler.log:
[2026-06-08 14:30:00] chain_id=vasya_20260609_weekly_abc123 post_id=uuid-001 action=schedule reason=queued | Post 1 caption
[2026-06-08 14:30:15] chain_id=vasya_20260609_weekly_abc123 post_id=uuid-002 action=schedule reason=queued | Post 2 caption
```

### 4. Chain state is saved

```
reports/schedules/vasya_20260609_weekly_abc123.json:
{
  "posts": [
    {"id": "uuid-001", "type": "photo", "time": "2026-06-09T10:00:00Z", "status": "queued"},
    {"id": "uuid-002", "type": "photo", "time": "2026-06-10T10:00:00Z", "status": "queued"}
  ],
  "decisions": [
    {"timestamp": "...", "post_id": "uuid-001", "action": "schedule", "reason": "queued"}
  ],
  "errors": []
}
```

### 5. Pipeline publishes posts on schedule

```python
# In pipeline.publish_due()
for item in queue:
    if item["status"] == "queued" and is_time_due(item["publish_time_utc"]):
        try:
            post_to_instagram(item["image_url"], item["caption"])
            log("pipeline", f"Published chain_id={item['chain_id']} post_id={item['id']}")
        except Exception as e:
            log("pipeline", f"Failed chain_id={item['chain_id']} post_id={item['id']}")
```

### 6. Vasya can reschedule the entire chain if needed

```
User: "Перепланируй всё на 30 минут раньше"

Vasya:
1. Load state: chain_state = _load_chain_state(chain_id)
2. For each post: reschedule_chain(chain_id, time_offset_minutes=-30)
3. Log all reschedules
```

---

## Backward Compatibility

- The `chain_id` parameter in `schedule_post` is required (enforced by TOOLS schema)
- Posts scheduled without chain_id will fail validation
- Existing queue items without chain_id should be treated as having `chain_id=""` (system posts)
- Old logs without chain_id are still valid (they just can't be grouped by workflow)

---

## Monitoring & Debugging

### View all scheduling decisions for a chain

```bash
grep "chain_id=vasya_20260609_weekly_abc123" logs/scheduler.log
```

### View pipeline operations for a chain

```bash
grep "chain_id=vasya_20260609_weekly_abc123" logs/pipeline.log
```

### Find chains with errors

```python
from pathlib import Path
import json

for state_file in Path("reports/schedules").glob("*.json"):
    state = json.loads(state_file.read_text())
    if state.get("errors"):
        print(f"{state_file.stem}: {len(state['errors'])} errors")
        for error in state["errors"]:
            print(f"  - {error['post_id']}: {error['error']}")
```

### Check queue status by chain

```python
chain_posts = get_chain_posts(chain_id="vasya_20260609_weekly_abc123")
print(f"Total: {len(chain_posts)}")
print(f"Queued: {len([p for p in chain_posts if p['status'] == 'queued'])}")
print(f"Published: {len([p for p in chain_posts if p['status'] == 'published'])}")
print(f"Failed: {len([p for p in chain_posts if p['status'] == 'failed'])}")
```

---

## Implementation Checklist

- [x] Update vasya.py with chain_id functions
- [x] Add chain_id parameter to schedule_post
- [x] Implement logging for all scheduling decisions
- [x] Implement checkpoint/state save for chains
- [ ] Update pipeline.py to accept chain_id in enqueue()
- [ ] Update pipeline.py queue schema to include chain_id
- [ ] Add query functions to pipeline.py (get_chain_posts, cancel_chain, etc.)
- [ ] Update pipeline.py logging to include chain_id
- [ ] Create Flask endpoint to cancel/reschedule chains via webapp
- [ ] Add monitoring dashboard to show chain status

