"""Friend-mode companion endpoints: a deterministic, read-only daily greeting.

The warm, playful conversation itself lives in the personality system
(``app/personality.py`` + ``aether/personality_modes.py``) and the live voice
interface. This module adds the one piece that is a backend concern: when the
user opens AETHER, greet them for the time of day and summarize what is on
their plate today from local records only. No AI provider call, no external
service, nothing is written, sent or scheduled.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException

from app.personal_data import _connect, memory_enabled, require_device_token
from app.personal_reports import today_plan

router = APIRouter(prefix="/api", tags=["companion"])

GREETINGS = {
    "morning": "Good morning",
    "afternoon": "Good afternoon",
    "evening": "Good evening",
    "night": "Up late",
}


def daypart_for(hour: int) -> str:
    """Map a local hour (0-23) to a greeting daypart."""
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _reminder_counts(now_utc: datetime, end_utc: datetime) -> dict[str, int]:
    """Open reminders split into overdue vs due today. Tolerates a missing table."""
    with _connect() as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reminders'"
        ).fetchone()
        if not exists:
            return {"overdue": 0, "due_today": 0}
        rows = db.execute(
            "SELECT due_at FROM reminders WHERE completed=0"
        ).fetchall()
    overdue = due_today = 0
    for row in rows:
        try:
            due = datetime.fromisoformat(str(row["due_at"]))
        except ValueError:
            continue
        if due.tzinfo is None:
            continue
        due = due.astimezone(UTC)
        if due <= now_utc:
            overdue += 1
        elif due < end_utc:
            due_today += 1
    return {"overdue": overdue, "due_today": due_today}


@router.get("/companion/greeting", dependencies=[Depends(require_device_token)])
def companion_greeting(timezone: str = "Asia/Kolkata"):
    """Time-of-day greeting plus a read-only snapshot of today's local records."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Use a valid IANA timezone, such as Asia/Kolkata.") from None
    now_local = datetime.now(zone)
    now_utc = now_local.astimezone(UTC)
    day = now_local.date()
    end_utc = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)

    plan = today_plan(timezone)
    reminders = _reminder_counts(now_utc, end_utc)
    top = [str(task.get("title", ""))[:120] for task in plan["top_priorities"][:3]]
    daypart = daypart_for(now_local.hour)
    return {
        "greeting": GREETINGS[daypart],
        "daypart": daypart,
        "local_time": now_local.isoformat(timespec="minutes"),
        "date": day.isoformat(),
        "timezone": timezone,
        "memory_enabled": memory_enabled(),
        "top_priorities": top,
        "counts": {
            "tasks_overdue": plan["counts"]["overdue"],
            "tasks_due_today": plan["counts"]["due_today"],
            "tasks_upcoming": plan["counts"]["upcoming"],
            "calendar_drafts": plan["calendar_draft_count"],
            "reminders_overdue": reminders["overdue"],
            "reminders_due_today": reminders["due_today"],
        },
        "notice": (
            "Read-only greeting built from local life records. Nothing was changed, sent or scheduled. "
            "Calendar drafts are unconfirmed drafts, not booked events. Warm conversation, jokes, "
            "stories and motivation come from chat with a personality mode such as friend, funny, "
            "calm or motivational."
        ),
    }
