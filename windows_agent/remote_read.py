"""Per-device read-only request/result path; execution only after laptop-local review."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import secrets
import sys
import time
import uuid

from windows_agent.local_approval import LocalApprovalStore

ACTION = "memory_snapshot"
REQUEST_TTL = 120
RESULT_TTL = 120


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Invalid opaque identifier.")
    return value


def _digest(token):
    if (
        not isinstance(token, str)
        or not 32 <= len(token) <= 256
        or not token.isascii()
        or any(ord(c) <= 32 or ord(c) == 127 for c in token)
    ):
        raise ValueError("Valid dedicated per-device token required.")
    return hashlib.sha256(token.encode()).hexdigest()


def memory_snapshot():
    if platform.system() != "Windows":
        raise ValueError("This read-only action requires the trusted Windows laptop.")
    import psutil

    memory = psutil.virtual_memory()
    total, available, percent = memory.total, memory.available, memory.percent
    if (
        type(total) is not int
        or type(available) is not int
        or not 0 < total <= 2**60
        or not 0 <= available <= total
    ):
        raise ValueError("Unsupported memory metrics.")
    if type(percent) not in (int, float) or not math.isfinite(percent) or not 0 <= percent <= 100:
        raise ValueError("Unsupported memory percentage.")
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_percent_reported": round(percent, 1),
    }


def _closed_memory(data):
    if not isinstance(data, dict) or set(data) != {
        "total_bytes",
        "available_bytes",
        "used_percent_reported",
    }:
        raise ValueError("Unsupported memory result schema.")
    total, available, percent = (
        data["total_bytes"],
        data["available_bytes"],
        data["used_percent_reported"],
    )
    if (
        type(total) is not int
        or type(available) is not int
        or not 0 < total <= 2**60
        or not 0 <= available <= total
    ):
        raise ValueError("Unsupported memory result values.")
    if type(percent) not in (int, float) or not math.isfinite(percent) or not 0 <= percent <= 100:
        raise ValueError("Unsupported memory result percentage.")
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_percent_reported": round(percent, 1),
    }


class RemoteReadStore(LocalApprovalStore):
    def __init__(self):
        super().__init__()
        with self.connect() as db:
            db.executescript(
                """CREATE TABLE IF NOT EXISTS remote_read_devices (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, revoked INTEGER NOT NULL DEFAULT0);
                CREATE TABLE IF NOT EXISTS remote_read_requests (
                id TEXT PRIMARY KEY, device_id TEXT NOT NULL, action TEXT NOT NULL,
                expires REAL NOT NULL, state TEXT NOT NULL, result TEXT, result_expires REAL);
            """.replace("DEFAULT0", "DEFAULT 0")
            )

    @staticmethod
    def _device(db, token):
        digest = _digest(token)
        row = db.execute(
            "SELECT id FROM remote_read_devices WHERE token_hash=? AND revoked=0", (digest,)
        ).fetchone()
        if not row:
            raise ValueError("Device token invalid/revoked; no request/result access.")
        return row[0]

    def provision_local(self):
        # Local operator interface only. Never expose provisioning or decisions over HTTP.
        key, token = uuid.uuid4().hex, secrets.token_urlsafe(48)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            if db.execute("SELECT count(*) FROM remote_read_devices").fetchone()[0] >= 50:
                raise ValueError("Local device capacity reached; review retention locally.")
            db.execute("INSERT INTO remote_read_devices VALUES(?,?,0)", (key, _digest(token)))
        return key, token

    def revoke_local(self, device_id):
        _id(device_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "UPDATE remote_read_devices SET revoked=1 WHERE id=? AND revoked=0",
                    (device_id,),
                ).rowcount
                != 1
            ):
                raise ValueError("Device missing/already revoked.")
            db.execute(
                "UPDATE remote_read_requests SET state='revoked',result=NULL,result_expires=NULL WHERE device_id=?",
                (device_id,),
            )

    def request_read(self, token, action):
        if action != ACTION:
            raise ValueError(
                "Only the fixed memory_snapshot action is supported; no command arguments."
            )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            device = self._device(db, token)
            # Expired output removed on queueing only; expiry checks protect other reads too.
            db.execute(
                "DELETE FROM remote_read_requests WHERE expires<=? AND (result_expires IS NULL OR result_expires<=?)",
                (time.time(), time.time()),
            )
            if db.execute("SELECT count(*) FROM remote_read_requests").fetchone()[0] >= 100:
                raise ValueError("Local request capacity reached.")
            if (
                db.execute(
                    "SELECT count(*) FROM remote_read_requests WHERE device_id=? AND state IN ('pending_local_review','running_local_read')",
                    (device,),
                ).fetchone()[0]
                >= 5
            ):
                raise ValueError("Device pending request limit reached.")
            key = uuid.uuid4().hex
            db.execute(
                "INSERT INTO remote_read_requests(id,device_id,action,expires,state) VALUES(?,?,?,?,?)",
                (key, device, ACTION, time.time() + REQUEST_TTL, "pending_local_review"),
            )
        return {
            "request_id": key,
            "action": ACTION,
            "state": "pending_local_review",
            "expires_in_seconds": REQUEST_TTL,
            "executed": False,
        }

    def inspect_local(self, request_id):
        _id(request_id)
        with self.connect() as db:
            self._active(db)
            row = db.execute(
                "SELECT r.device_id,r.action,r.expires,r.state,d.revoked FROM remote_read_requests r JOIN remote_read_devices d ON d.id=r.device_id WHERE r.id=?",
                (request_id,),
            ).fetchone()
        if (
            not row
            or row[2] <= time.time()
            or row[3] != "pending_local_review"
            or row[4]
            or row[1] != ACTION
        ):
            raise ValueError("Request missing/expired/decided/revoked or unsupported.")
        return {"request_id": request_id, "device_id": row[0], "action": ACTION}

    def review_local(self, request_id, expected_device, approved):
        _id(request_id)
        _id(expected_device)
        if type(approved) is not bool:
            raise ValueError("Explicit local boolean decision required.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            row = db.execute(
                "SELECT r.action,r.expires,r.state,d.revoked FROM remote_read_requests r JOIN remote_read_devices d ON d.id=r.device_id WHERE r.id=? AND r.device_id=?",
                (request_id, expected_device),
            ).fetchone()
            if (
                not row
                or row[0] != ACTION
                or row[1] <= time.time()
                or row[2] != "pending_local_review"
                or row[3]
            ):
                raise ValueError("Request changed/expired/replayed/revoked.")
            db.execute(
                "UPDATE remote_read_requests SET state=? WHERE id=?",
                ("running_local_read" if approved else "denied", request_id),
            )
        if not approved:
            return {"state": "denied", "executed": False}
        # Consumed before collecting. No queue-retry after failure. Only fixed code, no registry lookup/shell.
        try:
            data = _closed_memory(memory_snapshot())
            encoded = json.dumps(data, allow_nan=False, separators=(",", ":"))
            if len(encoded) > 512:
                raise ValueError("Unexpected output size.")
            state = "completed"
        except Exception:
            encoded, state = None, "failed"
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._active(db)
            except ValueError:
                state, encoded = "stopped", None
            revoked = db.execute(
                "SELECT revoked FROM remote_read_devices WHERE id=?", (expected_device,)
            ).fetchone()
            if not revoked or revoked[0]:
                state, encoded = "revoked", None
            changed = db.execute(
                "UPDATE remote_read_requests SET state=?,result=?,result_expires=? WHERE id=? AND state='running_local_read'",
                (state, encoded, time.time() + RESULT_TTL, request_id),
            ).rowcount
            if changed != 1:
                state = "result_unavailable"
        return {"state": state, "executed": True, "result_disclosed_locally": False}

    def cancel_request(self, token, request_id):
        _id(request_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Stop blocks reads/new work, but authenticated privacy cancellation remains available.
            device = self._device(db, token)
            row = db.execute(
                "SELECT action,state,expires,result_expires FROM remote_read_requests WHERE id=? AND device_id=?",
                (request_id, device),
            ).fetchone()
            if not row or row[0] != ACTION:
                raise ValueError("Request unavailable for this device.")
            previous, expires, result_expires = row[1:]
            known = {
                "pending_local_review",
                "running_local_read",
                "completed",
                "denied",
                "failed",
                "stopped",
                "revoked",
                "cancelled_before_read",
                "cancelled_result_suppressed",
                "result_cleared",
            }
            if previous not in known:
                raise ValueError("Unsupported stored request state.")
            if previous == "pending_local_review":
                state = "cancelled_before_read"
            elif previous == "running_local_read":
                state = "cancelled_result_suppressed"
            elif previous == "completed":
                state = "result_cleared"
            else:
                state = previous
            # Idempotent, owner-bound and irreversible for this request. Never dispatch a collector.
            db.execute(
                "UPDATE remote_read_requests SET state=?,result=NULL,result_expires=? WHERE id=? AND device_id=?",
                (
                    state,
                    result_expires if result_expires is not None else expires,
                    request_id,
                    device,
                ),
            )
        return {
            "request_id": request_id,
            "action": ACTION,
            "state": state,
            "result": None,
            "cancel_acknowledged": True,
            "collection_prevented": state == "cancelled_before_read",
            "running_operation_termination_verified": False,
            "notice": "Pending cancellation prevents this request from starting; if already dispatched, only result publication/access is suppressed. A read may already have happened. No OS/process kill, undo, secure erasure or recall of an already returned/displayed copy. No retry or approval is created.",
        }

    def read_result(self, token, request_id):
        _id(request_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            device = self._device(db, token)
            row = db.execute(
                "SELECT action,expires,state,result,result_expires FROM remote_read_requests WHERE id=? AND device_id=?",
                (request_id, device),
            ).fetchone()
        if not row:
            raise ValueError("Request unavailable for this device.")
        action, expires, state, raw, result_expires = row
        if action != ACTION:
            raise ValueError("Unsupported stored action.")
        if state in ("pending_local_review", "running_local_read") and expires <= time.time():
            return {"request_id": request_id, "action": ACTION, "state": "expired", "result": None}
        if result_expires is not None and result_expires <= time.time():
            return {
                "request_id": request_id,
                "action": ACTION,
                "state": "result_expired",
                "result": None,
            }
        return {
            "request_id": request_id,
            "action": ACTION,
            "state": state,
            "result": _closed_memory(json.loads(raw)) if raw and state == "completed" else None,
            "source": "Fixed laptop-local memory metric read after local review, not complete system health",
            "result_ttl_seconds": RESULT_TTL,
            "captured_at_unix": result_expires - RESULT_TTL
            if result_expires is not None and state == "completed"
            else None,
            "device_display_verified": False,
        }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="AETHER laptop-local paired read-only review")
    parser.add_argument("action", choices=["pair", "revoke", "review"])
    parser.add_argument("identifier", nargs="?")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Use an interactive terminal on the trusted laptop; no piped approval.")
    store = RemoteReadStore()
    if args.action == "pair":
        if (
            input(
                "Type PAIR to issue one dedicated remote-read device token; enter it only in the intended phone, never chat: "
            )
            != "PAIR"
        ):
            return
        key, token = store.provision_local()
        print("Device ID:", key)
        print("One-time token display, keep private:", token)
        return
    if args.action == "revoke":
        key = _id(args.identifier)
        print("Exact device ID:", key)
        if (
            input("Type REVOKE to block this device and clear its remote-read results: ")
            == "REVOKE"
        ):
            store.revoke_local(key)
            print("Revoked.")
        return
    item = store.inspect_local(args.identifier)
    print("Exact request ID:", item["request_id"])
    print("Requesting opaque device ID:", item["device_id"])
    print(
        "Action: memory_snapshot. Reads total/available RAM bytes and reported used percent only, no machine/user/file/process names. A short-lived result is released to this device token over the configured connection. Queueing/phone confirmation is not approval. Expires120seconds after creation. No shell or fallback."
    )
    answer = input(
        "Type SHARE MEMORY to approve this one exact read/result disclosure; anything else denies: "
    )
    result = store.review_local(item["request_id"], item["device_id"], answer == "SHARE MEMORY")
    print("State:", result["state"])


if __name__ == "__main__":
    main()
