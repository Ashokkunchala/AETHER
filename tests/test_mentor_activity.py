import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from jarvis.mentor import MentorStore


@pytest.fixture
def store(tmp_path):
    return MentorStore(tmp_path / 'mentor.db')


def insert(store, stamp, topic='infrastructure', correct=1):
    with store.connect() as db:
        db.execute('INSERT INTO mentor_checkpoint_attempts(lesson_id,choice,correct,recorded_at) VALUES(?,?,?,?)', (topic, 0, correct, stamp))


def test_utc_midnight_maps_to_requested_local_day(store):
    insert(store, '2026-11-15T18:29:59.999999+00:00')
    insert(store, '2026-11-15T18:30:00.000000+00:00', correct=0)
    insert(store, '2026-11-16T18:29:59.999999+00:00')
    insert(store, '2026-11-16T18:30:00.000000+00:00')
    result = store.daily_activity('2026-11-16', '2026-11-16', 'Asia/Kolkata')
    assert result['attempts'] == 2
    assert result['correct_choices'] == result['incorrect_choices'] == 1
    assert result['active_checkpoint_days'] == 1
    assert result['days'][0]['topics'] == ['infrastructure']
    assert result['utc_start_inclusive'] == '2026-11-15T18:30:00.000000+00:00'


@pytest.mark.parametrize('day,hours', [('2026-03-08', 23), ('2026-11-01', 25)])
def test_dst_local_day_is_not_assumed_to_be_24_hours(store, day, hours):
    result = store.daily_activity(day, day, 'America/New_York')
    lower = datetime.fromisoformat(result['utc_start_inclusive'])
    upper = datetime.fromisoformat(result['utc_end_exclusive'])
    assert (upper - lower).total_seconds() == hours * 3600
    insert(store, lower.isoformat(timespec='microseconds'))
    assert store.daily_activity(day, day, 'America/New_York')['attempts'] == 1


def test_no_backfill_or_fake_study_time(store):
    with store.connect() as db:
        db.execute('INSERT INTO mentor_answers VALUES(?,?,?,?,?)', ('linux', 1, 1, 8, '2026-11-01 12:00:00'))
    result = store.daily_activity('2026-11-01', '2026-11-02', 'UTC')
    assert result['attempts'] == 0 and len(result['days']) == 2
    assert 'not no learning' in result['notice']
    assert 'No backfill' in result['scope']
    assert 'study_minutes' not in result
    assert store.progress()['answers'][0]['attempts'] == 8


def test_submit_appends_while_latest_result_remains_compatible(store):
    store.submit('infrastructure', 1)
    store.submit('infrastructure', 0)
    with store.connect() as db:
        rows = db.execute('SELECT lesson_id,choice,correct,recorded_at FROM mentor_checkpoint_attempts ORDER BY id').fetchall()
    assert [r[:3] for r in rows] == [('infrastructure', 1, 0), ('infrastructure', 0, 1)]
    day = datetime.fromisoformat(rows[0][3]).date().isoformat()
    result = MentorStore(store.path).daily_activity(day, day, 'UTC')
    assert result['attempts'] == 2 and result['active_checkpoint_days'] == 1
    assert store.progress()['answers'][0]['attempts'] == 2
    assert store.progress()['passed_checkpoints'] == 1


def test_ledger_failure_rolls_back_latest_result(store, monkeypatch):
    import jarvis.mentor as mentor
    store.submit('linux', 1)
    before = store.progress()
    def fail(*args):
        raise sqlite3.OperationalError('injected ledger failure')
    monkeypatch.setattr(mentor, 'record_attempt', fail)
    with pytest.raises(sqlite3.OperationalError):
        store.submit('linux', 0)
    assert store.progress() == before
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM mentor_checkpoint_attempts').fetchone()[0] == 1


def test_parallel_submissions_keep_both_counters_consistent(store):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: MentorStore(store.path).submit('linux', 1), range(8)))
    assert store.progress()['answers'][0]['attempts'] == 8
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM mentor_checkpoint_attempts').fetchone()[0] == 8


@pytest.mark.parametrize('choice', [True, -1, 3, '1'])
def test_invalid_choice_writes_nothing(store, choice):
    with pytest.raises(ValueError):
        store.submit('linux', choice)
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM mentor_checkpoint_attempts').fetchone()[0] == 0


@pytest.mark.parametrize('start,end,tz', [
    ('2026-1-01', '2026-01-02', 'UTC'), ('2026-02-30', '2026-03-01', 'UTC'),
    ('2026-11-02', '2026-11-01', 'UTC'), ('2026-01-01', '2027-01-02', 'UTC'),
    ('9999-12-31', '9999-12-31', 'UTC'), ('2026-11-01', '2026-11-01', ''),
    ('2026-11-01', '2026-11-01', 'No/Such_Zone'), ('2026-11-01', '2026-11-01', None),
    (None, '2026-11-01', 'UTC'),
])
def test_range_and_timezone_validation(store, start, end, tz):
    with pytest.raises(ValueError):
        store.daily_activity(start, end, tz)


def test_limit_and_invalid_rows_are_explicit(store, monkeypatch):
    from jarvis import mentor_activity
    monkeypatch.setattr(mentor_activity, 'MAX_ROWS', 2)
    insert(store, '2026-11-01T00:00:00.000000+00:00')
    insert(store, '2026-11-01T01:00:00.000000+00:00', topic='unknown')
    insert(store, '2026-11-01T02:00:00.000000+00:00')
    result = store.daily_activity('2026-11-01', '2026-11-01', 'UTC')
    assert result['partial'] and result['scan_limit'] == 2
    assert result['attempts'] == 1 and result['invalid_rows_skipped'] == 1


def test_additive_schema_does_not_replace_existing_records(tmp_path):
    path = tmp_path / 'mentor.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE unrelated_private_data(value TEXT)')
        db.execute("INSERT INTO unrelated_private_data VALUES('keep')")
    store = MentorStore(path)
    MentorStore(path)
    with store.connect() as db:
        assert db.execute('SELECT * FROM unrelated_private_data').fetchall() == [('keep',)]
    assert store.daily_activity('2024-02-29', '2024-02-29', 'UTC')['attempts'] == 0


def test_report_safe_after_stop_and_attempts_do_not_bypass_stop(store, tmp_path, monkeypatch):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_MENTOR_DB', store.path)
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'security.db'))
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    assert not asyncio.run(registry.execute('mentor_submit', {'lesson_id': 'linux', 'choice': 1})).ok
    result = asyncio.run(registry.execute('mentor_daily_activity', {'start_date': '2026-11-01', 'end_date': '2026-11-01', 'timezone': 'UTC'}))
    assert result.ok and result.data['data']['attempts'] == 0
