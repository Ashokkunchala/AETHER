"""Future-only objective checkpoint activity. Not study time or skill assessment."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ATTEMPT_SCHEMA = '''
CREATE TABLE IF NOT EXISTS mentor_checkpoint_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id TEXT NOT NULL,
    choice INTEGER NOT NULL,
    correct INTEGER NOT NULL CHECK(correct IN (0,1)),
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS mentor_checkpoint_attempts_time
ON mentor_checkpoint_attempts(recorded_at, id);
'''
MAX_ROWS = 10000


def record_attempt(db, lesson_id: str, choice: int, correct: bool) -> None:
    # Caller owns the same transaction as the existing latest-result upsert.
    recorded_at = datetime.now(UTC).isoformat(timespec='microseconds')
    db.execute('INSERT INTO mentor_checkpoint_attempts(lesson_id,choice,correct,recorded_at) VALUES(?,?,?,?)',
               (lesson_id, choice, int(correct), recorded_at))


def _day(value: str) -> date:
    if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
        raise ValueError('Use an explicit YYYY-MM-DD date.')
    return date.fromisoformat(value)


def daily_report(store, start_date: str, end_date: str, timezone: str) -> dict[str, Any]:
    start, end = _day(start_date), _day(end_date)
    span = (end - start).days + 1
    if not 1 <= span <= 366 or end == date.max:
        raise ValueError('Choose an inclusive range of 1-366 days before 9999-12-31.')
    if not isinstance(timezone, str) or not timezone or len(timezone) > 100:
        raise ValueError('Choose an explicit IANA timezone such as Asia/Kolkata.')
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError('Unknown IANA timezone.') from exc
    try:
        lower = datetime.combine(start, time.min, tz).astimezone(UTC).isoformat(timespec='microseconds')
        upper = datetime.combine(end + timedelta(days=1), time.min, tz).astimezone(UTC).isoformat(timespec='microseconds')
    except (OverflowError, ValueError) as exc:
        raise ValueError('Date range cannot be represented in this timezone.') from exc
    with store.connect() as db:
        rows = db.execute('''SELECT lesson_id,correct,recorded_at FROM mentor_checkpoint_attempts
            WHERE recorded_at >= ? AND recorded_at < ? ORDER BY recorded_at,id LIMIT ?''',
                          (lower, upper, MAX_ROWS + 1)).fetchall()
    partial = len(rows) > MAX_ROWS
    days: dict[str, dict[str, Any]] = {(start + timedelta(days=i)).isoformat(): {
        'date': (start + timedelta(days=i)).isoformat(), 'attempts': 0,
        'correct_choices': 0, 'incorrect_choices': 0, 'topics': set(),
    } for i in range(span)}
    invalid = 0
    from aether.mentor import LESSONS
    for lesson_id, correct, stamp in rows[:MAX_ROWS]:
        try:
            observed = datetime.fromisoformat(stamp)
            if observed.tzinfo is None or lesson_id not in LESSONS or correct not in (0, 1):
                raise ValueError('Invalid stored attempt.')
            local_day = observed.astimezone(tz).date().isoformat()
            if local_day not in days:
                raise ValueError('Attempt outside local range.')
            group = days[local_day]
            group['attempts'] += 1
            group['correct_choices' if correct else 'incorrect_choices'] += 1
            group['topics'].add(lesson_id)
        except (ValueError, TypeError, OverflowError):
            invalid += 1
    items = [{**row, 'topics': sorted(row['topics'])} for row in days.values()]
    return {'start_date': start.isoformat(), 'end_date': end.isoformat(), 'timezone': timezone,
            'utc_start_inclusive': lower, 'utc_end_exclusive': upper,
            'days': items, 'attempts': sum(row['attempts'] for row in items),
            'correct_choices': sum(row['correct_choices'] for row in items),
            'incorrect_choices': sum(row['incorrect_choices'] for row in items),
            'active_checkpoint_days': sum(row['attempts'] > 0 for row in items),
            'partial': partial, 'scan_limit': MAX_ROWS, 'invalid_rows_skipped': invalid,
            'scope': 'New objective-checkpoint attempts recorded by this version only. No backfill from existing latest-result rows.',
            'notice': ('A zero day means no captured checkpoint attempts, not no learning. '
                       'Repeated attempts count separately. Correct choices are not mastery, course completion or attendance. '
                       'No study duration, interview/project activity, external calendar or notification is included. '
                       'When partial=true, only the earliest scanned attempts in the range contribute; totals/days are incomplete.')}
