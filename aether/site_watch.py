"""Opt-in, polite, read-only website change watching.

The user registers exact public URLs. A manual or scheduled check fetches each
due page once with the same SSRF-guarded, size-capped GET as the web tools and
records whether the fetched bytes changed since the last check. That is all:
no forms, no logins, no rendering, no following links, no mutations.

Politeness rules:
- Minimum interval between checks of one URL is 15 minutes; the default is one
  hour. The store refuses shorter intervals.
- At most 20 watched URLs, each checked at most once per interval.
- A failed fetch is recorded once and the URL is next due after its interval;
  there are no retries inside a check.

Change detection is a SHA-256 over the bounded fetched bytes. Dynamic pages
(ads, timestamps, rotating banners) can report "changed" without any
meaningful difference; a change event is a cue to look, never a summary of
what changed.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from pathlib import Path

_MIN_INTERVAL = 900
_MAX_INTERVAL = 86400
_MAX_WATCHES = 20
_LABEL = re.compile(r'[^\x20-\x7e]')


def _db_path() -> Path:
    return Path(os.environ.get('AETHER_SITEWATCH_DB') or Path.home() / '.aether' / 'site_watch.db')


class SiteWatchStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or _db_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS site_watches (
                    id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, label TEXT NOT NULL DEFAULT '',
                    interval_seconds INTEGER NOT NULL DEFAULT 3600, enabled INTEGER NOT NULL DEFAULT 0,
                    last_checked REAL, last_hash TEXT, consecutive_errors INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS site_watch_events (
                    id INTEGER PRIMARY KEY, watch_id INTEGER NOT NULL, created REAL NOT NULL,
                    outcome TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
                );
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add(self, url: str, label: str | None = None, interval_seconds: int = 3600, enabled: bool = False):
        from aether.tools.net.web_tools import _validate_public_url
        clean = _validate_public_url(url)
        if type(interval_seconds) is not int or not _MIN_INTERVAL <= interval_seconds <= _MAX_INTERVAL:
            raise ValueError(f'Interval must be whole seconds from {_MIN_INTERVAL} (15 minutes) to {_MAX_INTERVAL} (a day). The hourly default is deliberate: more frequent polling is impolite to the site.')
        if type(enabled) is not bool:
            raise ValueError('enabled must be a boolean.')
        if label is not None and (not isinstance(label, str) or len(label) > 120):
            raise ValueError('Label must be a short string.')
        clean_label = _LABEL.sub('', label or '')[:120]
        with self.connect() as db:
            count = db.execute('SELECT count(*) AS n FROM site_watches').fetchone()['n']
            existing = db.execute('SELECT id FROM site_watches WHERE url=?', (clean,)).fetchone()
            if existing is None and count >= _MAX_WATCHES:
                raise ValueError(f'At most {_MAX_WATCHES} watched URLs.')
            db.execute(
                'INSERT INTO site_watches(url,label,interval_seconds,enabled,created) VALUES (?,?,?,?,?) '
                'ON CONFLICT(url) DO UPDATE SET label=excluded.label,interval_seconds=excluded.interval_seconds,enabled=excluded.enabled',
                (clean, clean_label, interval_seconds, int(enabled), time.time()))
        return {'url': clean, 'label': clean_label, 'interval_seconds': interval_seconds, 'enabled': enabled,
                'notice': 'Read-only change watching: one guarded GET per interval, never more often than every 15 minutes. A change event means the fetched bytes differ, which includes ads and timestamps - it is a cue to look, not a summary of what changed.'}

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM site_watches ORDER BY id')]

    def remove(self, watch_id: int):
        if type(watch_id) is not int or watch_id < 1:
            raise ValueError('Choose an integer watch ID from site_watch_list.')
        with self.connect() as db:
            changed = db.execute('DELETE FROM site_watches WHERE id=?', (watch_id,)).rowcount
            db.execute('DELETE FROM site_watch_events WHERE watch_id=?', (watch_id,))
        if not changed:
            raise ValueError('No watch with that ID.')
        return {'removed': watch_id}

    def set_enabled(self, watch_id: int, enabled: bool):
        if type(watch_id) is not int or watch_id < 1 or type(enabled) is not bool:
            raise ValueError('Integer watch ID and boolean enabled required.')
        with self.connect() as db:
            changed = db.execute('UPDATE site_watches SET enabled=? WHERE id=?', (int(enabled), watch_id)).rowcount
        if not changed:
            raise ValueError('No watch with that ID.')
        return {'watch_id': watch_id, 'enabled': enabled}

    def check(self, watch_id: int | None = None, now: float | None = None, fetch=None):
        """Check due enabled watches once each. Returns one result per checked watch."""
        from aether.tools.net import web_tools
        now = time.time() if now is None else now
        fetch = fetch or web_tools._fetch
        results = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if watch_id is not None:
                if type(watch_id) is not int or watch_id < 1:
                    raise ValueError('watch_id must be a positive integer.')
                rows = db.execute('SELECT * FROM site_watches WHERE id=? AND enabled=1', (watch_id,)).fetchall()
            else:
                rows = db.execute('SELECT * FROM site_watches WHERE enabled=1').fetchall()
            for row in rows:
                if row['last_checked'] is not None and now - row['last_checked'] < row['interval_seconds']:
                    continue  # Not due yet; the interval bound is the politeness rule.
                outcome, note, new_hash = 'error', '', None
                try:
                    content, _ctype = fetch(row['url'])
                    new_hash = hashlib.sha256(content).hexdigest()
                    if row['last_hash'] is None:
                        outcome, note = 'baseline', 'First check recorded; future checks compare against this snapshot.'
                    elif new_hash != row['last_hash']:
                        outcome, note = 'changed', 'Fetched bytes differ from the last snapshot. This includes dynamic content such as ads and timestamps - open the page to see what actually changed.'
                    else:
                        outcome = 'unchanged'
                except Exception as exc:  # network failure is data, recorded once
                    note = f'Fetch failed: {type(exc).__name__}. Next try after the interval.'
                db.execute(
                    'UPDATE site_watches SET last_checked=?, last_hash=COALESCE(?, last_hash), consecutive_errors=? WHERE id=?',
                    (now, new_hash, 0 if outcome != 'error' else row['consecutive_errors'] + 1, row['id']))
                db.execute('INSERT INTO site_watch_events(watch_id,created,outcome,note) VALUES (?,?,?,?)', (row['id'], now, outcome, note))
                results.append({'watch_id': row['id'], 'url': row['url'], 'outcome': outcome, 'note': note})
            db.execute('DELETE FROM site_watch_events WHERE id NOT IN (SELECT id FROM site_watch_events ORDER BY id DESC LIMIT 500)')
        return results

    def events(self, watch_id: int | None = None):
        with self.connect() as db:
            if watch_id is None:
                rows = db.execute('SELECT * FROM site_watch_events ORDER BY id DESC LIMIT 100').fetchall()
            else:
                rows = db.execute('SELECT * FROM site_watch_events WHERE watch_id=? ORDER BY id DESC LIMIT 100', (watch_id,)).fetchall()
        return [dict(row) for row in rows]


def register_site_watch(registry):
    from aether.tools.registry import Risk, Tool
    def handler_for(method):
        def handler(**kwargs):
            return {'success': True, 'data': getattr(SiteWatchStore(), method)(**kwargs)}
        return handler
    definitions = [
        ('site_watch_add', 'Register or update one exact public URL for polite read-only change watching. Disabled unless enabled=true; default interval one hour, minimum 15 minutes. One guarded GET per interval, never a summary of what changed.', 'add', Risk.LOW,
         {'url': {'type': 'string'}, 'label': {'type': 'string'}, 'interval_seconds': {'type': 'integer'}, 'enabled': {'type': 'boolean'}}, ['url']),
        ('site_watch_list', 'List registered website watches with interval, enabled state and last-check status.', 'list', Risk.SAFE, {}, []),
        ('site_watch_remove', 'Stop watching a URL and drop its change history, by integer watch ID.', 'remove', Risk.LOW, {'watch_id': {'type': 'integer'}}, ['watch_id']),
        ('site_watch_enable', 'Turn a registered watch on or off by integer watch ID.', 'set_enabled', Risk.LOW, {'watch_id': {'type': 'integer'}, 'enabled': {'type': 'boolean'}}, ['watch_id', 'enabled']),
        ('site_watch_check', 'Check due enabled watches once each now (or one by ID). Skips watches not yet due; never retries inside a check.', 'check', Risk.LOW, {'watch_id': {'type': 'integer'}}, []),
        ('site_watch_events', 'Read the bounded local change-event inbox for watched sites, newest first.', 'events', Risk.SAFE, {'watch_id': {'type': 'integer'}}, []),
    ]
    for name, description, method, risk, properties, required in definitions:
        registry.register(Tool(name=name, description=description, parameters={'type': 'object', 'properties': properties, 'required': required}, handler=handler_for(method), risk=risk, category='research'))
