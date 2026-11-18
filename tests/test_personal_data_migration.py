"""Concurrent backend connections must upgrade old databases atomically."""
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import personal_data


def legacy_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE memories(id INTEGER PRIMARY KEY, text TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'general', created_at TEXT NOT NULL);
        CREATE TABLE reminders(id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_at TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE plans(id INTEGER PRIMARY KEY, title TEXT NOT NULL, steps_json TEXT NOT NULL, due_at TEXT, status TEXT NOT NULL DEFAULT 'planned', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT INTO memories VALUES(1,'Keep this memory','general','old');
        INSERT INTO plans VALUES(1,'Keep this plan','[]','2027-01-01T00:00:00Z','planned','old','old');
        """)


@pytest.mark.parametrize('old_database', [False, True])
def test_concurrent_first_connect_upgrades_once(monkeypatch, tmp_path, old_database):
    path = tmp_path / 'concurrent.sqlite3'
    if old_database:
        legacy_db(path)
    monkeypatch.setenv('AETHER_DB_PATH', str(path))
    original = sqlite3.connect
    class SlowInspection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            cursor = super().execute(sql, parameters)
            if sql == 'PRAGMA table_info(memories)':
                # Widen the old check/ALTER race. BEGIN IMMEDIATE must keep
                # another connection from taking the same stale schema view.
                time.sleep(.02)
            return cursor
    monkeypatch.setattr(personal_data.sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=SlowInspection))
    start = threading.Barrier(8)
    def connect(_):
        start.wait(timeout=3)
        db = personal_data._connect()
        try:
            assert not db.in_transaction
            return {row[1] for row in db.execute('PRAGMA table_info(memories)')}
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        columns = list(pool.map(connect, range(8)))
    assert all('expires_at' in item for item in columns)
    with original(path) as db:
        assert 'recurrence' in {r[1] for r in db.execute('PRAGMA table_info(reminders)')}
        assert 'reminder_id' in {r[1] for r in db.execute('PRAGMA table_info(plans)')}
        if old_database:
            assert db.execute('SELECT text FROM memories').fetchone()[0] == 'Keep this memory'
            assert db.execute('SELECT count(*) FROM reminders').fetchone()[0] == 1
            assert db.execute('SELECT reminder_id FROM plans WHERE id=1').fetchone()[0] is not None


def test_upgrade_error_rolls_back_and_releases_lock(monkeypatch, tmp_path):
    path = tmp_path / 'rollback.sqlite3'
    legacy_db(path)
    monkeypatch.setenv('AETHER_DB_PATH', str(path))
    original = sqlite3.connect
    class FailOnce(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith('ALTER TABLE reminders'):
                raise sqlite3.OperationalError('injected upgrade failure')
            return super().execute(sql, parameters)
    with monkeypatch.context() as patch:
        patch.setattr(personal_data.sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=FailOnce))
        with pytest.raises(sqlite3.OperationalError, match='injected'):
            personal_data._connect()
    with original(path) as db:
        assert 'expires_at' not in {r[1] for r in db.execute('PRAGMA table_info(memories)')}
    db = personal_data._connect()
    db.close()


@pytest.mark.parametrize('code', [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_BUSY | (2 << 8)])
def test_wal_lock_contention_retries_then_succeeds(monkeypatch, tmp_path, code):
    monkeypatch.setenv('AETHER_DB_PATH', str(tmp_path / 'busy.sqlite3'))
    original = sqlite3.connect
    attempts = []
    class BusySetup(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == 'PRAGMA journal_mode=WAL':
                attempts.append(sql)
                if len(attempts) < 3:
                    error = sqlite3.OperationalError('injected lock contention')
                    error.sqlite_errorcode = code
                    raise error
            return super().execute(sql, parameters)
    monkeypatch.setattr(personal_data.sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=BusySetup))
    monkeypatch.setattr(personal_data.time, 'sleep', lambda _:None)
    db = personal_data._connect()
    assert len(attempts) == 3
    assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    db.close()


@pytest.mark.parametrize('failure', ['timeout', 'not_busy', 'schema'])
def test_initial_setup_error_closes_connection_and_stops(monkeypatch, tmp_path, failure):
    monkeypatch.setenv('AETHER_DB_PATH', str(tmp_path / 'fail.sqlite3'))
    original = sqlite3.connect
    closed, attempts = [], []
    class FailedSetup(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == 'PRAGMA journal_mode=WAL' and failure != 'schema':
                attempts.append(sql)
                error = sqlite3.OperationalError('injected setup failure')
                error.sqlite_errorcode = sqlite3.SQLITE_BUSY if failure == 'timeout' else sqlite3.SQLITE_READONLY
                raise error
            return super().execute(sql, parameters)
        def executescript(self, sql):
            if failure == 'schema':
                raise sqlite3.OperationalError('injected schema setup failure')
            return super().executescript(sql)
        def close(self):
            closed.append(True)
            return super().close()
    monkeypatch.setattr(personal_data.sqlite3, 'connect', lambda *a, **kw: original(*a, **kw, factory=FailedSetup))
    ticks = iter([0, 11])
    monkeypatch.setattr(personal_data.time, 'monotonic', lambda:next(ticks))
    with pytest.raises(sqlite3.OperationalError, match='injected'):
        personal_data._connect()
    assert closed == [True]
    assert len(attempts) == (0 if failure == 'schema' else 1)
