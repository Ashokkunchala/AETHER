"""Read-only personal dashboard: one view of today's local assistant records.

Aggregates tasks, calendar drafts, reminders, notifications, expenses and
integration status from AETHER's local database. No provider calls, no writes,
no external calendar, email or messaging access. Sections whose table has not
been created yet report available=false instead of failing.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Query

from app.config import Settings
from app.personal_data import require_device_token
from app.personal_reports import _date, _zone, today_plan

router = APIRouter(prefix="/api/life", tags=["AETHER personal dashboard"])

REMINDER_SCAN_LIMIT = 10000
REMINDER_PREVIEW = 50
NOTIFICATION_SCAN_LIMIT = 10000
NOTIFICATION_PREVIEW = 5
EXPENSE_SCAN_LIMIT = 10000


def _instant(value: str | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value or "")
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _has_table(db, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _reminders(zone, start: datetime, end: datetime) -> dict:
    from app.life_manager import _db

    empty = {"overdue": [], "due_today": [], "upcoming": []}
    with _db() as db:
        if not _has_table(db, "reminders"):
            return {"available": False, "counts": {key: 0 for key in empty}, **empty,
                    "invalid_records_skipped": 0, "partial": False,
                    "notice": "No reminders store yet. Create a reminder first."}
        rows = db.execute(
            "SELECT id,title,due_at,recurrence FROM reminders WHERE completed=0 "
            "ORDER BY due_at,id LIMIT ?", (REMINDER_SCAN_LIMIT + 1,)).fetchall()
    groups: dict[str, list] = {key: [] for key in empty}
    invalid = 0
    for row in rows[:REMINDER_SCAN_LIMIT]:
        due = _instant(row["due_at"])
        if due is None:
            # Legacy rows without a timezone stay visible nowhere; count them.
            invalid += 1
            continue
        key = "overdue" if due < start else "due_today" if due < end else "upcoming"
        groups[key].append({"id": row["id"], "title": row["title"],
                            "recurrence": row["recurrence"],
                            "due_at": due.isoformat(),
                            "due_local": due.astimezone(zone).isoformat()})
    for values in groups.values():
        values.sort(key=lambda item: (item["due_at"], item["id"]))
    return {"available": True,
            "counts": {key: len(value) for key, value in groups.items()},
            "overdue": groups["overdue"][:REMINDER_PREVIEW],
            "due_today": groups["due_today"][:REMINDER_PREVIEW],
            "upcoming": groups["upcoming"][:REMINDER_PREVIEW],
            "invalid_records_skipped": invalid,
            "partial": len(rows) > REMINDER_SCAN_LIMIT}


def _notifications() -> dict:
    from app.life_manager import _db

    with _db() as db:
        if not _has_table(db, "aether_notifications"):
            return {"available": False, "unread": 0, "latest": [], "partial": False,
                    "notice": "No notifications store yet. Nothing has been delivered."}
        unread = db.execute(
            "SELECT COUNT(*) FROM aether_notifications WHERE read_at IS NULL").fetchone()[0]
        rows = db.execute(
            "SELECT * FROM aether_notifications ORDER BY id DESC LIMIT ?",
            (NOTIFICATION_SCAN_LIMIT + 1,)).fetchall()
    latest = [{"id": row["id"], "title": row["title"], "body": row["body"][:500],
               "channel": row["channel"], "due_at": row["due_at"],
               "created_at": row["created_at"], "read": row["read_at"] is not None}
              for row in rows[:NOTIFICATION_PREVIEW]]
    return {"available": True, "unread": unread, "latest": latest,
            "partial": len(rows) > NOTIFICATION_SCAN_LIMIT}


def _expenses(month: str) -> dict:
    from app.life_manager import _db

    with _db() as db:
        rows = db.execute(
            "SELECT amount,currency FROM life_expenses WHERE substr(spent_on,1,7)=? LIMIT ?",
            (month, EXPENSE_SCAN_LIMIT + 1)).fetchall()
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    invalid = 0
    for row in rows[:EXPENSE_SCAN_LIMIT]:
        try:
            amount = Decimal(str(row["amount"]))
            if not amount.is_finite() or amount <= 0 or amount > 100000000:
                raise ValueError
            if not re.fullmatch(r"[A-Z]{3}", row["currency"] or ""):
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            invalid += 1
            continue
        currency = row["currency"]
        totals[currency] = totals.get(currency, Decimal(0)) + amount
        counts[currency] = counts.get(currency, 0) + 1
    return {"month": month,
            "totals": [{"currency": currency,
                        "amount": format(totals[currency].quantize(Decimal("0.01")), "f"),
                        "count": counts[currency]} for currency in sorted(totals)],
            "invalid_records_skipped": invalid,
            "partial": len(rows) > EXPENSE_SCAN_LIMIT}


def _integrations() -> dict:
    from app.life_manager import _db

    # Fresh Settings, not the cached one: tests and restarts change env.
    settings = Settings()
    with _db() as db:
        connected = (_has_table(db, "integration_secrets")
                     and db.execute("SELECT 1 FROM integration_secrets WHERE provider='google'").fetchone() is not None)
    return {"google_connected": connected,
            "whatsapp_configured": bool(settings.whatsapp_access_token
                                        and settings.whatsapp_phone_number_id),
            "notice": "Configured or connected only; not a live delivery check."}


@router.get("/dashboard", dependencies=[Depends(require_device_token)])
def personal_dashboard(timezone: str = Query(default="Asia/Kolkata", min_length=1, max_length=80),
                       plan_date: str | None = None):
    """Today's priorities, tasks, reminders, alerts and month spending in one read."""
    zone = _zone(timezone)
    day = _date(plan_date) if plan_date else datetime.now(zone).date()
    try:
        start = datetime.combine(day, time.min, zone).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    except OverflowError:
        from fastapi import HTTPException

        raise HTTPException(422, "Date is outside the supported planning range.") from None
    plan = today_plan(timezone, day.isoformat())
    reminders = _reminders(zone, start, end)
    notifications = _notifications()
    expenses = _expenses(day.strftime("%Y-%m"))
    partial = (plan["partial_scan"] or reminders["partial"] or notifications["partial"]
               or expenses["partial"])
    invalid = (plan["invalid_records_skipped"] + reminders["invalid_records_skipped"]
               + expenses["invalid_records_skipped"])
    return {"date": day.isoformat(), "timezone": timezone,
            "generated_at": datetime.now(UTC).isoformat(),
            "top_priorities": plan["top_priorities"],
            "task_counts": plan["counts"],
            "tasks": plan["tasks"],
            "calendar_drafts": plan["calendar_drafts"],
            "reminders": reminders,
            "notifications": notifications,
            "expenses": expenses,
            "integrations": _integrations(),
            "partial": partial,
            "invalid_records_skipped": invalid,
            "saved": False,
            "notice": "Read-only view over AETHER's saved local records. Calendar drafts are "
                      "unconfirmed, not booked events. Reminders and notifications are local "
                      "records. Expense totals are saved entries per currency, never converted "
                      "or combined. Integration flags mean configured, not verified live. Lists "
                      "are previews with per-section limits; partial=true means a scan limit was "
                      "hit. Nothing was changed, sent, booked or paid."}
