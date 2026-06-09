"""
VASYA CHAIN_ID USAGE EXAMPLES

This file shows practical code examples for using Vasya's chain_id tracking
in various scheduling scenarios.
"""

from vasya import (
    schedule_post, _new_chain_id, _load_chain_state, _save_chain_state,
    _log_scheduling_decision, get_scheduling_logs, list_chain_states
)
from datetime import datetime, timedelta
import json

# =============================================================================
# EXAMPLE 1: Create a Weekly Schedule (Mon-Fri)
# =============================================================================

def example_weekly_schedule():
    """Schedule posts for each weekday with a single chain_id."""

    chain_id = _new_chain_id("weekly")  # "weekly_20260608_143052_a7f9c3b2"
    print(f"Creating weekly schedule with chain_id={chain_id}")

    posts = [
        {
            "day": "Monday",
            "image_url": "https://example.com/mon.jpg",
            "caption": "Понедельник: начало недели, время выбора",
            "time": "2026-06-09T10:00:00Z",
            "type": "photo"
        },
        {
            "day": "Tuesday",
            "image_url": "https://example.com/tue.mp4",
            "caption": "Вторник: рассказ о паттернах",
            "time": "2026-06-10T10:00:00Z",
            "type": "reel"
        },
        {
            "day": "Wednesday",
            "image_url": "https://example.com/wed.jpg",
            "caption": "Среда: середина недели, переоценка",
            "time": "2026-06-11T10:00:00Z",
            "type": "photo"
        },
        {
            "day": "Thursday",
            "image_url": "https://example.com/thu.mp4",
            "caption": "Четверг: готовимся к выходным",
            "time": "2026-06-12T10:00:00Z",
            "type": "reel"
        },
        {
            "day": "Friday",
            "image_url": "https://example.com/fri.jpg",
            "caption": "Пятница: СПЕЦПРЕДЛОЖЕНИЕ - диагностика",
            "time": "2026-06-13T10:00:00Z",
            "type": "photo"
        },
    ]

    results = []
    for post in posts:
        result = schedule_post(
            image_url=post["image_url"],
            caption=post["caption"],
            publish_time_utc=post["time"],
            chain_id=chain_id,  # Same chain_id for all
            post_type=post["type"]
        )
        results.append(result)
        print(f"  {post['day']}: {result[:40]}...")

    # Load and show final state
    state = _load_chain_state(chain_id)
    print(f"\nChain state saved:")
    print(f"  Total posts: {len(state['posts'])}")
    print(f"  Successful: {len([p for p in state['posts'] if p['status'] == 'queued'])}")
    print(f"  Errors: {len(state['errors'])}")

    return chain_id


# =============================================================================
# EXAMPLE 2: Handle Partial Failure (Missing Media URL)
# =============================================================================

def example_with_errors():
    """Demonstrate error handling when one post lacks a media URL."""

    chain_id = _new_chain_id("error_demo")
    print(f"\nScheduling with intentional error (chain_id={chain_id})")

    posts = [
        ("https://example.com/1.jpg", "Post 1: OK"),
        ("", "Post 2: Missing URL - will error"),
        ("https://example.com/3.jpg", "Post 3: OK after error"),
    ]

    base_time = datetime(2026, 6, 9, 10, 0, 0)

    for idx, (url, caption) in enumerate(posts):
        time = base_time + timedelta(days=idx)
        result = schedule_post(
            image_url=url,
            caption=caption,
            publish_time_utc=time.isoformat() + "Z",
            chain_id=chain_id,
            post_type="photo"
        )
        status = "✓ OK" if "✓" in result else "❌ ERROR"
        print(f"  Post {idx+1}: {status}")

    # Show state with errors
    state = _load_chain_state(chain_id)
    print(f"\nChain state:")
    print(f"  Posts: {len(state['posts'])}")
    print(f"  Errors: {len(state['errors'])}")
    if state['errors']:
        print(f"  Error details:")
        for error in state['errors']:
            print(f"    - {error['post_id']}: {error['error'][:60]}...")

    return chain_id


# =============================================================================
# EXAMPLE 3: Reschedule an Entire Chain
# =============================================================================

def example_reschedule_chain(original_chain_id):
    """Move all posts in a chain earlier by 1 hour."""

    print(f"\nRescheduling chain {original_chain_id} (-1 hour)")

    state = _load_chain_state(original_chain_id)

    if not state.get("posts"):
        print("  No posts found in chain")
        return

    # Generate new chain_id for the rescheduled workflow
    new_chain_id = _new_chain_id("rescheduled")

    for post in state['posts']:
        if post['status'] == 'queued':
            # Parse original time, subtract 1 hour
            original_time = datetime.fromisoformat(post['time'].replace('Z', '+00:00'))
            new_time = (original_time - timedelta(hours=1)).isoformat()

            # Resubmit with new time and new chain_id
            result = schedule_post(
                image_url=post.get('image_url', 'https://example.com/placeholder.jpg'),
                caption=f"[Rescheduled] {post.get('caption', 'Post')}",
                publish_time_utc=new_time,
                chain_id=new_chain_id,
                post_type=post.get('type', 'photo')
            )

            # Log the reschedule decision
            _log_scheduling_decision(
                new_chain_id,
                post['id'],
                action="reschedule",
                reason=f"moved_1h_earlier (was: {post['time']})",
                caption_preview=f"[Rescheduled] {post.get('caption', 'Post')[:40]}"
            )

    new_state = _load_chain_state(new_chain_id)
    print(f"  Created new chain: {new_chain_id}")
    print(f"  Rescheduled {len(new_state['posts'])} posts")

    return new_chain_id


# =============================================================================
# EXAMPLE 4: View Scheduling Logs
# =============================================================================

def example_view_logs():
    """Show recent scheduling decisions."""

    print("\n" + "="*60)
    print("SCHEDULING LOGS (last 24 hours)")
    print("="*60)

    logs = get_scheduling_logs(hours=24)
    print(logs)

    print("\n" + "="*60)
    print("ACTIVE CHAINS")
    print("="*60)

    chains = list_chain_states()
    print(chains)


# =============================================================================
# EXAMPLE 5: Analyze Chain State
# =============================================================================

def example_analyze_chain(chain_id):
    """Detailed analysis of a chain's state and decisions."""

    state = _load_chain_state(chain_id)

    print(f"\n" + "="*60)
    print(f"CHAIN ANALYSIS: {chain_id}")
    print("="*60)

    # Posts breakdown
    print("\nPosts:")
    print(f"  Total: {len(state.get('posts', []))}")
    print(f"  By status:")
    status_counts = {}
    for post in state.get('posts', []):
        s = post.get('status', 'unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
    for status, count in status_counts.items():
        print(f"    {status}: {count}")

    # Post timeline
    print("\n  Timeline:")
    for post in sorted(state.get('posts', []), key=lambda p: p.get('time', '')):
        t = post.get('time', '???')
        print(f"    {t} | {post.get('type', 'unknown'):6} | {post.get('status', 'unknown')}")

    # Decisions
    print("\nDecisions:")
    print(f"  Total: {len(state.get('decisions', []))}")
    by_action = {}
    for decision in state.get('decisions', []):
        action = decision.get('action', 'unknown')
        by_action[action] = by_action.get(action, 0) + 1
    for action, count in by_action.items():
        print(f"    {action}: {count}")

    # Errors
    print("\nErrors:")
    errors = state.get('errors', [])
    print(f"  Total: {len(errors)}")
    if errors:
        for error in errors[-5:]:  # last 5
            print(f"    {error['post_id']}: {error['error'][:50]}...")


# =============================================================================
# EXAMPLE 6: Decision-Based Scheduling
# =============================================================================

def example_decision_tree():
    """
    Show how Vasya uses chain_id to make scheduling decisions.
    """

    chain_id = _new_chain_id("decision_demo")
    print(f"\nDECISION-BASED SCHEDULING (chain_id={chain_id})")
    print("="*60)

    # Decision: Is content ready?
    content_ready = True
    if not content_ready:
        _log_scheduling_decision(
            chain_id, "post_1", "skip",
            reason="content_not_ready",
            caption_preview="Ждём одобрения Виктории"
        )
        print("✗ Content not ready, skipping schedule")
        return

    # Decision: Is media available?
    media_available = True
    if not media_available:
        _log_scheduling_decision(
            chain_id, "post_1", "skip",
            reason="no_media",
            caption_preview="Нужно снять видео"
        )
        print("✗ Media not available, skipping schedule")
        return

    # Decision: What type of content?
    content_type = "reel"  # based on content plan

    # Decision: What time?
    is_friday = datetime.now().weekday() == 4
    publish_time = "2026-06-13T14:00:00Z" if is_friday else "2026-06-09T10:00:00Z"

    reason = "friday_offer" if is_friday else "regular_schedule"

    _log_scheduling_decision(
        chain_id, "post_1", "schedule",
        reason=reason,
        caption_preview=f"Пост ({content_type}) в {publish_time}"
    )

    print(f"✓ Decision tree passed")
    print(f"  Content type: {content_type}")
    print(f"  Publish time: {publish_time}")
    print(f"  Reason: {reason}")


# =============================================================================
# MAIN: Run all examples
# =============================================================================

if __name__ == "__main__":
    print("\nVASYA CHAIN_ID EXAMPLES\n")

    # Run examples
    chain1 = example_weekly_schedule()
    chain2 = example_with_errors()
    chain3 = example_reschedule_chain(chain1)
    example_analyze_chain(chain1)
    example_decision_tree()
    example_view_logs()

    print("\n" + "="*60)
    print("Examples complete. Check logs/scheduler.log and reports/schedules/")
    print("="*60)
