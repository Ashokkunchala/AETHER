"""AETHER in-process WebSocket credentials. Never store bearer tokens or grant new rights."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Literal

from fastapi import HTTPException

from app.core.auth import get_db_connection, hash_token, token_auth
from app.core.config import Settings


@dataclass(frozen=True)
class SessionIdentity:
    kind: Literal['legacy', 'device']
    credential_hash: str = field(repr=False)
    device_id: str | None = None

    @classmethod
    def authenticate(cls, authorization: str | None) -> SessionIdentity:
        principal = token_auth.validate_token(authorization)
        supplied = (authorization or '').removeprefix('Bearer ').strip()
        return cls(principal['type'], hash_token(supplied), principal.get('device_id'))

    def is_active(self) -> bool:
        """Recheck rotation/revocation without retaining or logging the secret."""
        expected = Settings().jarvis_api_token
        if len(expected) < 32 or expected.startswith('replace_'):
            return False
        if self.kind == 'legacy':
            return secrets.compare_digest(self.credential_hash, hash_token(expected))
        with get_db_connection() as conn:
            return conn.execute(
                'SELECT 1 FROM devices WHERE device_id=? AND token_hash=? AND revoked_at IS NULL',
                (self.device_id, self.credential_hash),
            ).fetchone() is not None


class TicketStore:
    """Bounded one-use tickets bound to the issuing credential. Single worker only."""

    def __init__(self, ttl: float = 60, capacity: int = 1024):
        self.ttl, self.capacity = ttl, capacity
        self._tickets: dict[str, tuple[float, SessionIdentity]] = {}
        self._lock = Lock()

    @staticmethod
    def _digest(ticket: str) -> str:
        return hashlib.sha256(ticket.encode('utf-8')).hexdigest()

    def issue(self, identity: SessionIdentity) -> str:
        now = time.monotonic()
        with self._lock:
            self._tickets = {k: v for k, v in self._tickets.items() if v[0] > now}
            if len(self._tickets) >= self.capacity:
                raise HTTPException(503, 'WebSocket ticket capacity reached; retry shortly.')
            ticket = secrets.token_urlsafe(32)
            self._tickets[self._digest(ticket)] = (now + self.ttl, identity)
        return ticket

    def consume(self, ticket: str) -> SessionIdentity | None:
        if not ticket or len(ticket) > 256:
            return None
        with self._lock:
            record = self._tickets.pop(self._digest(ticket), None)
        if record is None or record[0] <= time.monotonic():
            return None
        identity = record[1]
        return identity if identity.is_active() else None
