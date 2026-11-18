"""Read-only reports over AETHER's existing local life-manager records.

No provider requests, external calendars, second database or schedule writes.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.personal_data import require_device_token

router = APIRouter(prefix="/reports", dependencies=[Depends(require_device_token)])
ROW_LIMIT = 10000


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Use a valid IANA timezone, such as Asia/Kolkata.") from None


def _date(value: str) -> date:
    try:
        result = date.fromisoformat(value)
        if result.isoformat() != value:
            raise ValueError
        return result
    except ValueError:
        raise HTTPException(422, "Dates must use YYYY-MM-DD.") from None


def _instant(value: str | None) -> datetime | None:
    try:
        result = datetime.fromisoformat(value or "")
        return result.astimezone(UTC) if result.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def today_plan(timezone: str = "Asia/Kolkata", plan_date: str | None = None) -> dict:
    """Deterministic priorities and local-day drafts, not an invented time-block plan."""
    from app.life_manager import _db

    zone = _zone(timezone)
    day = _date(plan_date) if plan_date else datetime.now(zone).date()
    try:
        start = datetime.combine(day, time.min, zone).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    except OverflowError:
        raise HTTPException(422, "Date is outside the supported planning range.") from None
    with _db() as db:
        tasks = db.execute("SELECT * FROM life_tasks WHERE status IN ('open','in_progress','postponed') ORDER BY priority,id LIMIT ?", (ROW_LIMIT + 1,)).fetchall()
        events = db.execute("SELECT * FROM life_events WHERE status='draft' ORDER BY id LIMIT ?", (ROW_LIMIT + 1,)).fetchall()
    partial = len(tasks) > ROW_LIMIT or len(events) > ROW_LIMIT
    groups: dict[str, list] = {name: [] for name in ("overdue", "due_today", "upcoming", "undated")}
    invalid = 0
    for row in tasks[:ROW_LIMIT]:
        task = dict(row)
        due = _instant(task['due_at'])
        if task['due_at'] and due is None:
            invalid += 1
            continue
        key = 'undated' if due is None else 'overdue' if due < start else 'due_today' if due < end else 'upcoming'
        task['due_local'] = due.astimezone(zone).isoformat() if due else None
        groups[key].append(task)
    for values in groups.values():
        values.sort(key=lambda row: (row['priority'], row['due_at'] or '9999', row['id']))
    drafts = []
    for row in events[:ROW_LIMIT]:
        event = dict(row)
        begins, ends = _instant(event['starts_at']), _instant(event['ends_at'])
        if begins is None or (event['ends_at'] and (ends is None or ends <= begins)):
            invalid += 1
            continue
        # Include cross-midnight drafts overlapping the selected local day.
        if begins < end and (ends > start if ends else begins >= start):
            event['starts_local'] = begins.astimezone(zone).isoformat()
            event['ends_local'] = ends.astimezone(zone).isoformat() if ends else None
            drafts.append(event)
    drafts.sort(key=lambda row: row['starts_at'])
    counts = {key: len(value) for key, value in groups.items()}
    priorities = (groups['overdue'] + groups['due_today'] + groups['undated'])[:5]
    return {'date': day.isoformat(), 'timezone': timezone,
            'day_start_utc': start.isoformat(), 'day_end_utc': end.isoformat(),
            'counts': counts, 'tasks': {key: value[:50] for key, value in groups.items()},
            'top_priorities': priorities, 'calendar_drafts': drafts[:50],
            'calendar_draft_count': len(drafts), 'partial_scan': partial,
            'invalid_records_skipped': invalid, 'saved': False,
            'source': 'life_manager.tasks_and_calendar_drafts',
            'notice': 'Local records only. Calendar drafts are unconfirmed, not booked events. No external calendar, reminders or CLI tasks included. Scans at most 10000 tasks and 10000 drafts; lists show at most 50 per group. No tasks or calendar entries changed.'}


def expense_report(start_date: str, end_date: str) -> dict:
    """Inclusive saved-date range; keep currencies separate, round only after summing."""
    from app.life_manager import _db

    start, end = _date(start_date), _date(end_date)
    if end < start or (end - start).days > 366:
        raise HTTPException(422, 'Use an ordered date range of at most 367 days.')
    with _db() as db:
        rows = db.execute('SELECT amount,currency,category,spent_on FROM life_expenses WHERE spent_on>=? AND spent_on<=? ORDER BY spent_on,id LIMIT ?', (start.isoformat(), end.isoformat(), ROW_LIMIT + 1)).fetchall()
    totals: dict[str, Decimal] = defaultdict(Decimal)
    categories: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    daily: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    invalid = 0
    for row in rows[:ROW_LIMIT]:
        try:
            amount = Decimal(str(row['amount']))
            _date(row['spent_on'])
            if not amount.is_finite() or amount <= 0 or amount > 100000000:
                raise ValueError
        except (InvalidOperation, ValueError, HTTPException):
            invalid += 1
            continue
        currency = row['currency']
        totals[currency] += amount
        categories[currency, row['category']] += amount
        daily[currency, row['spent_on']] += amount
        counts[currency] += 1
    def money(value):
        return format(value.quantize(Decimal('0.01')), 'f')
    return {'start_date': start.isoformat(), 'end_date': end.isoformat(),
            'totals': [{'currency': key, 'amount': money(value), 'count': counts[key]} for key, value in sorted(totals.items())],
            'by_category': [{'currency': key[0], 'category': key[1], 'amount': money(value)} for key, value in sorted(categories.items())],
            'by_day': [{'currency': key[0], 'spent_on': key[1], 'amount': money(value)} for key, value in sorted(daily.items())],
            'partial': len(rows) > ROW_LIMIT, 'invalid_records_skipped': invalid,
            'source': 'life_manager.expenses',
            'notice': 'Saved expenses only, not bank or CLI records. Dates are entered spending dates, not converted timestamps. Currencies are never combined. Scans at most 10000 rows; partial=true means totals are incomplete. Amounts are decimal strings based on saved values.'}


@router.get('/today')
def get_today_plan(timezone: str = 'Asia/Kolkata', plan_date: str | None = None):
    return today_plan(timezone, plan_date)


@router.get('/expenses')
def get_expense_report(start_date: str, end_date: str):
    return expense_report(start_date, end_date)


@router.get('/expenses.csv')
def download_expense_report(start_date: str, end_date: str):
    report = expense_report(start_date, end_date)
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['AETHER saved expense report', start_date, end_date])
    writer.writerow(['Partial', str(report['partial']), 'Invalid records skipped', report['invalid_records_skipped']])
    writer.writerow(['Grouping', 'Currency', 'Label', 'Amount'])
    # Prefix user-supplied labels so spreadsheet apps cannot evaluate formulas.
    def text(value):
        return "'" + str(value)
    for row in report['totals']:
        writer.writerow(['total', text(row['currency']), 'All categories', row['amount']])
    for row in report['by_category']:
        writer.writerow(['category', text(row['currency']), text(row['category']), row['amount']])
    for row in report['by_day']:
        writer.writerow(['day', text(row['currency']), row['spent_on'], row['amount']])
    writer.writerow([report['notice']])
    return Response(out.getvalue(), media_type='text/csv', headers={
        'Content-Disposition': f'attachment; filename="aether-expenses-{start_date}-{end_date}.csv"',
        'Cache-Control': 'no-store'})
