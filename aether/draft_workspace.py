"""Local-only drafts for posts, applications, messages and reports.

AETHER can prepare words - a LinkedIn post, a job-application answer, a
message, a report - and keep them here for review. Drafts never leave the
machine: nothing in this module sends, submits, posts or publishes, and no
other module is allowed to treat a stored draft as approval. Submission is
always the user's own action after they read the words.

Resume-grounding rule for application material: callers must ground claims in
the user's real, supplied resume (the job-evidence reviewer exists for that);
this store refuses nothing by content because it never publishes - the
no-invented-facts rule is enforced at preparation time, not here.
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

_KINDS = ('linkedin_post', 'job_application', 'message', 'report', 'other')
_MAX_DRAFTS = 100
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _db_path() -> Path:
    return Path(os.environ.get('AETHER_DRAFTS_DB') or Path.home() / '.aether' / 'drafts.db')


class DraftStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or _db_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                'CREATE TABLE IF NOT EXISTS drafts ('
                'id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, '
                "status TEXT NOT NULL DEFAULT 'draft', created REAL NOT NULL, updated REAL NOT NULL)")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _clean(self, value, name, limit):
        if not isinstance(value, str) or not value.strip() or len(value) > limit or _CONTROL.search(value):
            raise ValueError(f'{name} must be non-empty text of at most {limit} characters.')
        return value

    def create(self, kind: str, title: str, body: str):
        if kind not in _KINDS:
            raise ValueError(f'Kind must be one of {list(_KINDS)}.')
        title = self._clean(title, 'title', 200)
        body = self._clean(body, 'body', 20000)
        now = time.time()
        with self.connect() as db:
            count = db.execute('SELECT count(*) AS n FROM drafts').fetchone()['n']
            if count >= _MAX_DRAFTS:
                raise ValueError(f'At most {_MAX_DRAFTS} stored drafts; delete old ones first.')
            cur = db.execute('INSERT INTO drafts(kind,title,body,created,updated) VALUES (?,?,?,?,?)', (kind, title, body, now, now))
            draft_id = cur.lastrowid
        return {'id': draft_id, 'kind': kind, 'title': title, 'status': 'draft',
                'notice': 'Stored locally only. Nothing is sent, submitted, posted or published - submission is always your own action after you read the words.'}

    def list(self, status: str | None = None):
        with self.connect() as db:
            if status is None:
                rows = db.execute('SELECT id,kind,title,status,created,updated FROM drafts ORDER BY id DESC LIMIT 100').fetchall()
            else:
                if status not in ('draft', 'reviewed'):
                    raise ValueError("Status filter must be 'draft' or 'reviewed'.")
                rows = db.execute('SELECT id,kind,title,status,created,updated FROM drafts WHERE status=? ORDER BY id DESC LIMIT 100', (status,)).fetchall()
        return [dict(row) for row in rows]

    def get(self, draft_id: int):
        if type(draft_id) is not int or draft_id < 1:
            raise ValueError('Choose an integer draft ID from draft_list.')
        with self.connect() as db:
            row = db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
        if row is None:
            raise ValueError('No draft with that ID.')
        return dict(row)

    def update(self, draft_id: int, body: str):
        body = self._clean(body, 'body', 20000)
        with self.connect() as db:
            row = db.execute('SELECT status FROM drafts WHERE id=?', (draft_id,)).fetchone() if type(draft_id) is int and draft_id >= 1 else None
            if row is None:
                raise ValueError('No draft with that ID.')
            if row['status'] != 'draft':
                raise ValueError('Only unreviewed drafts can be edited; create a new draft instead.')
            db.execute('UPDATE drafts SET body=?, updated=? WHERE id=?', (body, time.time(), draft_id))
        return {'id': draft_id, 'updated': True}

    def mark_reviewed(self, draft_id: int):
        if type(draft_id) is not int or draft_id < 1:
            raise ValueError('Choose an integer draft ID from draft_list.')
        with self.connect() as db:
            changed = db.execute("UPDATE drafts SET status='reviewed', updated=? WHERE id=?", (time.time(), draft_id)).rowcount
        if not changed:
            raise ValueError('No draft with that ID.')
        return {'id': draft_id, 'status': 'reviewed',
                'notice': "Reviewed is a reading marker, not an approval to send. Nothing is submitted anywhere; sending stays your own action."}

    def delete(self, draft_id: int):
        if type(draft_id) is not int or draft_id < 1:
            raise ValueError('Choose an integer draft ID from draft_list.')
        with self.connect() as db:
            changed = db.execute('DELETE FROM drafts WHERE id=?', (draft_id,)).rowcount
        if not changed:
            raise ValueError('No draft with that ID.')
        return {'deleted': draft_id}


def register_draft_workspace(registry):
    from aether.tools.registry import Risk, Tool
    def handler_for(method):
        def handler(**kwargs):
            return {'success': True, 'data': getattr(DraftStore(), method)(**kwargs)}
        return handler
    never_sent = ' Drafts stay local: never sent, submitted, posted or published.'
    definitions = [
        ('draft_create', 'Store a prepared draft (LinkedIn post, job application answer, message, report).' + never_sent, 'create', Risk.LOW,
         {'kind': {'type': 'string', 'enum': list(_KINDS)}, 'title': {'type': 'string'}, 'body': {'type': 'string'}}, ['kind', 'title', 'body']),
        ('draft_list', 'List stored drafts (ID, kind, title, status) without bodies.', 'list', Risk.SAFE, {'status': {'type': 'string'}}, []),
        ('draft_get', 'Read one stored draft in full by integer ID.', 'get', Risk.SAFE, {'draft_id': {'type': 'integer'}}, ['draft_id']),
        ('draft_update', 'Replace the body of an unreviewed draft by integer ID.' + never_sent, 'update', Risk.LOW, {'draft_id': {'type': 'integer'}, 'body': {'type': 'string'}}, ['draft_id', 'body']),
        ('draft_mark_reviewed', 'Mark a draft read by integer ID. A reading marker, never an approval to send.', 'mark_reviewed', Risk.LOW, {'draft_id': {'type': 'integer'}}, ['draft_id']),
        ('draft_delete', 'Delete a stored local draft by integer ID.', 'delete', Risk.LOW, {'draft_id': {'type': 'integer'}}, ['draft_id']),
    ]
    for name, description, method, risk, properties, required in definitions:
        registry.register(Tool(name=name, description=description, parameters={'type': 'object', 'properties': properties, 'required': required}, handler=handler_for(method), risk=risk, category='research'))
