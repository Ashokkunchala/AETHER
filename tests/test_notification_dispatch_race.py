"""Parallel reminder dispatch claims and enqueues each local notification once."""
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app import integrations, personal_data


@pytest.fixture
def database(monkeypatch, tmp_path):
    path = tmp_path / 'dispatch.sqlite3'
    monkeypatch.setenv('JARVIS_DB_PATH', str(path))
    monkeypatch.setattr(integrations.settings, 'jarvis_db_path', str(path))
    personal_data.create_reminder(personal_data.ReminderCreate(title='Due one', due_at=datetime.now(UTC) - timedelta(minutes=1)))
    personal_data.create_reminder(personal_data.ReminderCreate(title='Due two', due_at=datetime.now(UTC) + timedelta(minutes=5)))
    personal_data.create_reminder(personal_data.ReminderCreate(title='Future', due_at=datetime.now(UTC) + timedelta(days=1)))
    return path


@pytest.mark.parametrize('column_exists', [False, True])
def test_concurrent_dispatchers_enqueue_once(database, monkeypatch, column_exists):
    if column_exists:
        with sqlite3.connect(database) as db:
            db.execute('ALTER TABLE reminders ADD COLUMN notification_sent_at TEXT')
    original = sqlite3.connect
    class SlowClaim(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            cursor = super().execute(sql, parameters)
            if sql.startswith('SELECT id,title,due_at FROM reminders'):
                # Force overlapping stale reads without transaction serialization.
                time.sleep(.04)
            return cursor
    monkeypatch.setattr(personal_data.sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=SlowClaim))
    start = threading.Barrier(8)
    def dispatch(_):
        start.wait(timeout=3)
        return integrations.dispatch_due_reminders()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(dispatch, range(8)))
    assert sum(results) == 2
    with original(database) as db:
        assert db.execute('SELECT count(*) FROM aether_notifications').fetchone()[0] == 2
        assert db.execute('SELECT count(*) FROM reminders WHERE notification_sent_at IS NOT NULL').fetchone()[0] == 2
        assert db.execute("SELECT notification_sent_at FROM reminders WHERE title='Future'").fetchone()[0] is None
    assert integrations.dispatch_due_reminders() == 0


def test_enqueue_failure_rolls_back_claim_and_allows_retry(database, monkeypatch):
    original = sqlite3.connect
    class FailEnqueue(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith('INSERT INTO aether_notifications'):
                raise sqlite3.OperationalError('injected enqueue failure')
            return super().execute(sql, parameters)
    with monkeypatch.context() as patch:
        patch.setattr(personal_data.sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=FailEnqueue))
        with pytest.raises(sqlite3.OperationalError, match='injected'):
            integrations.dispatch_due_reminders()
    with original(database) as db:
        assert db.execute('SELECT count(*) FROM aether_notifications').fetchone()[0] == 0
    assert integrations.dispatch_due_reminders() == 2
    assert integrations.dispatch_due_reminders() == 0
