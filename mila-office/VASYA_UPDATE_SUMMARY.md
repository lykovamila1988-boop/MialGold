# Vasya Update Summary — Chain ID Tracking

## Overview

Vasya (the scheduling agent) has been updated with **chain_id tracking** — a system to uniquely identify, monitor, and manage scheduling workflows. Every scheduling operation now logs its decision with context, enabling full visibility and recovery from failures.

## What Changed

### Core Updates

1. **Chain ID Generation** — `_new_chain_id(prefix="vasya")`
   - Generates unique IDs: `vasya_20260608_143052_a7f9c3b2`
   - One ID per workflow (weekly schedule, monthly plan, response thread, etc.)

2. **State Management** — Checkpoint persistence
   - `_load_chain_state(chain_id)` — Load saved state (posts, decisions, errors)
   - `_save_chain_state(chain_id, state)` — Persist after each operation
   - Stored in: `reports/schedules/<chain_id>.json`

3. **Decision Logging** — All actions recorded
   - `_log_scheduling_decision(chain_id, post_id, action, reason, caption_preview)`
   - Actions: `schedule`, `reschedule`, `skip`, `error`
   - Logged to: `logs/scheduler.log`

4. **Updated `schedule_post()` API**
   - **NEW required parameter**: `chain_id` (string)
   - **NEW optional parameter**: `post_type` ("photo", "reel", "story", "carousel")
   - Automatically validates, logs, and saves state

5. **Helper Functions** for debugging
   - `get_scheduling_logs(hours=24)` — View recent decisions
   - `list_chain_states()` — Show active chains and status

## File Changes

### Modified Files

- **`vasya.py`** (↑180 lines)
  - Added chain tracking infrastructure
  - Updated `schedule_post()` with chain_id and logging
  - Added QUICK command `/логи` (view logs)
  - Updated system prompt to mention chain_id usage

### New Files

- **`VASYA_CHAIN_ID_GUIDE.md`** — Complete user guide
- **`CHAIN_ID_IMPLEMENTATION.md`** — Integration checklist for pipeline.py
- **`VASYA_USAGE_EXAMPLES.py`** — 6 practical code examples
- **`VASYA_UPDATE_SUMMARY.md`** — This file

## How It Works

### Workflow

```
User: /план (create weekly schedule)
    ↓
Vasya generates chain_id = "vasya_20260609_weekly_posts_abc123"
    ↓
For each day (Mon-Fri):
  1. Call schedule_post(..., chain_id=<above>)
  2. Log decision: "action=schedule reason=queued"
  3. Save state: posts[], decisions[], errors[]
    ↓
User can:
  • View logs: /логи
  • Reschedule: reload state, adjust times, requeue with same chain_id
  • Cancel: query by chain_id and remove from pipeline
  • Recover: load state, retry failed posts
```

### Example: Weekly Schedule

```python
chain_id = _new_chain_id()  # "vasya_20260609_weekly_f3a2c1"

for day, url, caption, time in weekly_posts:
    schedule_post(url, caption, time, chain_id)
    # Logs: [timestamp] chain_id=vasya_... action=schedule reason=queued | caption
    # Saves: {posts: [...], decisions: [...], errors: []}

# View results
state = _load_chain_state(chain_id)
print(f"Posts: {len(state['posts'])}, Errors: {len(state['errors'])}")
```

## Backward Compatibility

- `chain_id` is **required** in the new API (enforced by TOOLS schema)
- Old code that calls `schedule_post()` without `chain_id` will fail validation
- This is intentional: we want visibility on every scheduled post

## Integration with Pipeline

For full functionality, `pipeline.py` needs updates (see `CHAIN_ID_IMPLEMENTATION.md`):

1. Accept `chain_id` in `enqueue()` function
2. Store `chain_id` in queue items
3. Add query functions: `get_chain_posts()`, `cancel_chain()`, `reschedule_chain()`
4. Log chain_id in `publish_due()` operations

## Key Features

### 1. Traceability

Find all posts from a single planning workflow:

```bash
grep "chain_id=vasya_20260609_weekly_f3a2c1" logs/scheduler.log
```

### 2. Error Recovery

After a crash, retry only failed posts:

```python
state = _load_chain_state(chain_id)
for error in state['errors']:
    # Resubmit post that failed
```

### 3. Bulk Rescheduling

Move all posts in a chain by N hours:

```python
# Load state, adjust times, requeue with new chain_id
chain_id_new = _new_chain_id()
for post in state['posts']:
    new_time = adjust_time(post['time'], hours=-1)
    schedule_post(..., publish_time_utc=new_time, chain_id=chain_id_new)
```

### 4. Decision Logging

Understand why each post was scheduled/skipped:

```
[2026-06-08 14:30] chain_id=vasya_20260609_weekly post_id=uuid-001 
                   action=schedule reason=queued | Привет! Это рассказ о выборе

[2026-06-08 14:35] chain_id=vasya_20260609_weekly post_id=uuid-002 
                   action=error reason=no_media_url | Пост без фото
```

## Usage Examples

See `VASYA_USAGE_EXAMPLES.py` for code:

1. **Create weekly schedule** — 5 posts, 1 chain_id
2. **Handle errors** — Missing media URL, continues with others
3. **Reschedule chain** — Move all posts 1 hour earlier
4. **View logs** — Recent decisions, active chains
5. **Analyze state** — Detailed breakdown of chain status
6. **Decision tree** — Show how scheduling decisions are made

## System Prompt Update

Vasya's system prompt now includes:

> "Всегда используешь chain_id при планировании цепочки (по дням недели, месяцу и т.д.)"

He will:
- Generate a unique chain_id for each scheduling workflow
- Log all decisions with clear reasons
- Save state for recovery

## Logging Format

```
logs/scheduler.log format:
[YYYY-MM-DD HH:MM] chain_id=<id> post_id=<id> action=<action> reason=<reason> | <caption_preview>

Examples:
[2026-06-08 14:30:00] chain_id=vasya_20260609_weekly_f3a2c1 post_id=uuid-001 action=schedule reason=queued | Привет!
[2026-06-08 14:31:10] chain_id=vasya_20260609_weekly_f3a2c1 post_id=uuid-002 action=error reason=no_media_url | Пост без фото
[2026-06-08 15:00:00] chain_id=vasya_20260609_daily_x7y2z9 post_id=uuid-003 action=reschedule reason=moved_1h_earlier | Story для истории
```

## State File Format

```json
// reports/schedules/<chain_id>.json

{
  "posts": [
    {
      "id": "uuid-001",
      "type": "photo",
      "time": "2026-06-09T10:00:00Z",
      "status": "queued"
    }
  ],
  "decisions": [
    {
      "timestamp": "2026-06-08T14:30:00",
      "post_id": "uuid-001",
      "action": "schedule",
      "reason": "queued"
    }
  ],
  "errors": [
    {
      "timestamp": "2026-06-08T14:35:00",
      "post_id": "uuid-002",
      "error": "Ошибка: нужна публичная ссылка на медиа..."
    }
  ]
}
```

## Testing

To verify the implementation:

```bash
cd e:\MILA GOLD\mila-office

# Check syntax
python -m py_compile vasya.py

# Run examples
python VASYA_USAGE_EXAMPLES.py

# Check logs
cat ..\logs\scheduler.log

# Check states
ls ..\reports\schedules\
```

## Next Steps

1. **Update pipeline.py** to accept and use chain_id (see `CHAIN_ID_IMPLEMENTATION.md`)
2. **Add Flask endpoints** to webapp.py for canceling/rescheduling chains
3. **Monitor dashboard** to show chain status and decisions
4. **Integration tests** for full scheduling workflows
5. **Document Vasya's prompt** to reference chain_id usage

## API Quick Reference

| Function | Purpose | Returns |
|----------|---------|---------|
| `_new_chain_id(prefix)` | Generate chain ID | `str` (e.g., "vasya_20260608_143052_a7f9c3b2") |
| `_load_chain_state(chain_id)` | Load state | `dict` with posts/decisions/errors |
| `_save_chain_state(chain_id, state)` | Save state | `None` |
| `_log_scheduling_decision(...)` | Log decision | `None` (writes to scheduler.log) |
| `schedule_post(..., chain_id, post_type)` | Schedule post | `str` (status message) |
| `get_scheduling_logs(hours)` | View logs | `str` (formatted log lines) |
| `list_chain_states()` | Show chains | `str` (list of active chains) |

## Questions?

- **How do I use chain_id?** → See `VASYA_CHAIN_ID_GUIDE.md`
- **How do I integrate with pipeline?** → See `CHAIN_ID_IMPLEMENTATION.md`
- **Show me code examples** → See `VASYA_USAGE_EXAMPLES.py`
- **Where are logs/state?** → `logs/scheduler.log` and `reports/schedules/`

---

**Status**: Implementation complete ✓  
**Files modified**: 1 (vasya.py)  
**Files created**: 3 (guides, examples, summary)  
**Syntax check**: Passed ✓  
**Ready for integration**: Yes ✓
