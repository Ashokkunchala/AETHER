"""Credential-bound provider approval checks. No provider calls or bearer storage."""
from __future__ import annotations

import hashlib
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import Header, HTTPException

from app.core.ws_sessions import SessionIdentity
from aether.security import SecurityStore


def identity(authorization: str | None = Header(default=None)) -> SessionIdentity:
    return SessionIdentity.authenticate(authorization)


def migrate(db):
    """Additive, serialized upgrades; legacy unbound rows stay non-executable."""
    db.execute('BEGIN IMMEDIATE')
    for table, columns in {
        'approval_requests': {'requester_kind': 'TEXT', 'requester_hash': 'TEXT',
                              'requester_device': 'TEXT', 'expires_at': 'TEXT',
                              'account_binding': 'TEXT'},
        'integration_secrets': {'approval_generation': "TEXT NOT NULL DEFAULT ''"},
    }.items():
        present = {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')}
        for column, kind in columns.items():
            if column not in present:
                db.execute('ALTER TABLE ' + table + ' ADD COLUMN ' + column + ' ' + kind)
    db.commit()


def account(db, provider, settings):
    if provider == 'whatsapp':
        value = settings.whatsapp_phone_number_id + ':' + settings.whatsapp_access_token
    else:
        row = db.execute("SELECT approval_generation FROM integration_secrets WHERE provider='google'").fetchone()
        value = 'google:' + row[0] if row else 'google:disconnected'
    return hashlib.sha256(value.encode()).hexdigest()


def guard(actor):
    if not actor.is_active():
        raise HTTPException(401, 'Approval credential was revoked or rotated.')
    try:
        stopped = SecurityStore().stopped()
    except Exception as exc:
        raise HTTPException(503, 'Approval safety checks are unavailable.') from exc
    if stopped:
        raise HTTPException(409, 'Emergency stop is active.')


def check(db, row, actor, settings):
    guard(actor)
    if (not row or row['requester_hash'] != actor.credential_hash
            or row['requester_kind'] != actor.kind
            or row['requester_device'] != actor.device_id):
        raise HTTPException(404, 'Bound approval not found. Recreate legacy requests.')
    try:
        expiry = datetime.fromisoformat(row['expires_at'] or '')
        active = expiry.tzinfo is not None and expiry > datetime.now(UTC)
    except (TypeError, ValueError):
        active = False
    if not active:
        raise HTTPException(409, 'Approval expired. Create and review a new request.')
    if row['account_binding'] != account(db, row['provider'], settings):
        raise HTTPException(409, 'Provider connection changed. Create and review a new request.')


execution_check: ContextVar = ContextVar('aether_provider_execution_check', default=None)


def before_network_write():
    check_now = execution_check.get()
    if check_now is not None:
        check_now()
