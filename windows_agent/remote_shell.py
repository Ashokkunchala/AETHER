"""Per-device guarded-shell command request/result path; execution only after laptop-local review.

The phone submits one exact command string. Nothing executes from the network:
the laptop operator reviews the exact stored command in an interactive local
terminal and approves or denies. The hard blocked list can never be approved
past, every execution is synchronous with a fixed timeout, and the bounded
output is released only to the requesting device token for a short lifetime.
"""

from __future__ import annotations

import json
import platform
import sys
import time
import uuid

from windows_agent.local_approval import LocalApprovalStore
from windows_agent.remote_read import _digest, _id

ACTION = "shell_command"
REQUEST_TTL = 120
RESULT_TTL = 120
MAX_COMMAND_CHARS = 300
MAX_STREAM_CHARS = 4000
MAX_RESULT_BYTES = 16384
EXECUTION_TIMEOUT = 60


def _command(value):
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_COMMAND_CHARS:
        raise ValueError("One exact command of 1-300 characters is required.")
    if value != value.strip() or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("Plain printable single-line command text only; no controls or padding.")
    return value


def _classify(command):
    from aether.control.shell import classify

    return classify(command)


def _execute(command):
    if platform.system() != "Windows":
        raise ValueError("Remote laptop commands run on Windows only.")
    from aether.control.shell import run as guarded_run

    outcome = guarded_run(command, timeout=EXECUTION_TIMEOUT)
    timed_out = "timed out" in str(outcome.get("error", "")).lower()
    return {
        "classification": outcome.get("classification"),
        "exit_code": outcome.get("returncode") if not timed_out else None,
        "timed_out": timed_out,
        "stdout": str(outcome.get("stdout") or "")[:MAX_STREAM_CHARS],
        "stderr": str(outcome.get("stderr") or outcome.get("error") or "")[:MAX_STREAM_CHARS],
    }


def _closed_result(data):
    if not isinstance(data, dict) or set(data) != {
        "classification",
        "exit_code",
        "timed_out",
        "stdout",
        "stderr",
    }:
        raise ValueError("Unsupported command result schema.")
    if data["classification"] not in ("safe", "confirm"):
        raise ValueError("Unsupported stored classification.")
    if data["exit_code"] is not None and type(data["exit_code"]) is not int:
        raise ValueError("Unsupported exit code.")
    if type(data["timed_out"]) is not bool:
        raise ValueError("Unsupported timeout flag.")
    for key in ("stdout", "stderr"):
        if not isinstance(data[key], str) or len(data[key]) > MAX_STREAM_CHARS:
            raise ValueError("Unsupported captured output.")
    return {
        "classification": data["classification"],
        "exit_code": data["exit_code"],
        "timed_out": data["timed_out"],
        "stdout": data["stdout"],
        "stderr": data["stderr"],
    }


class RemoteShellStore(LocalApprovalStore):
    def __init__(self):
        super().__init__()
        with self.connect() as db:
            db.executescript(
                """CREATE TABLE IF NOT EXISTS remote_read_devices (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, revoked INTEGER NOT NULL DEFAULT0);
                CREATE TABLE IF NOT EXISTS remote_shell_requests (
                id TEXT PRIMARY KEY, device_id TEXT NOT NULL, action TEXT NOT NULL, command TEXT NOT NULL,
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

    def request_command(self, token, command):
        command = _command(command)
        classification = _classify(command)
        if classification == "blocked":
            raise ValueError(
                "Command is on the hard blocked list; it cannot be queued, approved or executed."
            )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            device = self._device(db, token)
            db.execute(
                "DELETE FROM remote_shell_requests WHERE expires<=? AND (result_expires IS NULL OR result_expires<=?)",
                (time.time(), time.time()),
            )
            if db.execute("SELECT count(*) FROM remote_shell_requests").fetchone()[0] >= 100:
                raise ValueError("Local request capacity reached.")
            if (
                db.execute(
                    "SELECT count(*) FROM remote_shell_requests WHERE device_id=? AND state IN ('pending_local_review','running_local_command')",
                    (device,),
                ).fetchone()[0]
                >= 5
            ):
                raise ValueError("Device pending request limit reached.")
            key = uuid.uuid4().hex
            db.execute(
                "INSERT INTO remote_shell_requests(id,device_id,action,command,expires,state) VALUES(?,?,?,?,?,?)",
                (key, device, ACTION, command, time.time() + REQUEST_TTL, "pending_local_review"),
            )
        return {
            "request_id": key,
            "action": ACTION,
            "classification": classification,
            "state": "pending_local_review",
            "expires_in_seconds": REQUEST_TTL,
            "executed": False,
        }

    def inspect_local(self, request_id):
        _id(request_id)
        with self.connect() as db:
            self._active(db)
            row = db.execute(
                "SELECT r.device_id,r.action,r.command,r.expires,r.state,d.revoked FROM remote_shell_requests r JOIN remote_read_devices d ON d.id=r.device_id WHERE r.id=?",
                (request_id,),
            ).fetchone()
        if (
            not row
            or row[3] <= time.time()
            or row[4] != "pending_local_review"
            or row[5]
            or row[1] != ACTION
        ):
            raise ValueError("Request missing/expired/decided/revoked or unsupported.")
        return {
            "request_id": request_id,
            "device_id": row[0],
            "action": ACTION,
            "command": row[2],
            "classification": _classify(row[2]),
        }

    def review_local(self, request_id, expected_device, approved):
        _id(request_id)
        _id(expected_device)
        if type(approved) is not bool:
            raise ValueError("Explicit local boolean decision required.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            row = db.execute(
                "SELECT r.action,r.command,r.expires,r.state,d.revoked FROM remote_shell_requests r JOIN remote_read_devices d ON d.id=r.device_id WHERE r.id=? AND r.device_id=?",
                (request_id, expected_device),
            ).fetchone()
            if (
                not row
                or row[0] != ACTION
                or row[2] <= time.time()
                or row[3] != "pending_local_review"
                or row[4]
            ):
                raise ValueError("Request changed/expired/replayed/revoked.")
            command = row[1]
            db.execute(
                "UPDATE remote_shell_requests SET state=? WHERE id=?",
                ("running_local_command" if approved else "denied", request_id),
            )
        if not approved:
            return {"state": "denied", "executed": False}
        # Re-classify the exact stored command at decision time; blocked can never run.
        try:
            if _classify(command) == "blocked":
                raise ValueError("Command became blocked; approval refused.")
            data = _closed_result(_execute(command))
            encoded = json.dumps(data, allow_nan=False, separators=(",", ":"))
            if len(encoded) > MAX_RESULT_BYTES:
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
                "UPDATE remote_shell_requests SET state=?,result=?,result_expires=? WHERE id=? AND state='running_local_command'",
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
                "SELECT action,state,expires,result_expires FROM remote_shell_requests WHERE id=? AND device_id=?",
                (request_id, device),
            ).fetchone()
            if not row or row[0] != ACTION:
                raise ValueError("Request unavailable for this device.")
            previous, expires, result_expires = row[1:]
            known = {
                "pending_local_review",
                "running_local_command",
                "completed",
                "denied",
                "failed",
                "stopped",
                "revoked",
                "cancelled_before_review",
                "cancelled_result_suppressed",
                "result_cleared",
            }
            if previous not in known:
                raise ValueError("Unsupported stored request state.")
            if previous == "pending_local_review":
                state = "cancelled_before_review"
            elif previous == "running_local_command":
                state = "cancelled_result_suppressed"
            elif previous == "completed":
                state = "result_cleared"
            else:
                state = previous
            # Idempotent, owner-bound and irreversible for this request. Never dispatches execution.
            db.execute(
                "UPDATE remote_shell_requests SET state=?,result=NULL,result_expires=? WHERE id=? AND device_id=?",
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
            "execution_prevented": state == "cancelled_before_review",
            "running_operation_termination_verified": False,
            "notice": "Pending cancellation prevents this command from starting; a command already running finishes or hits its fixed60second timeout and only result publication/access is suppressed. No OS/process kill, undo, secure erasure or recall of an already returned/displayed copy. No retry or approval is created.",
        }

    def read_result(self, token, request_id):
        _id(request_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            device = self._device(db, token)
            row = db.execute(
                "SELECT action,expires,state,result,result_expires FROM remote_shell_requests WHERE id=? AND device_id=?",
                (request_id, device),
            ).fetchone()
        if not row:
            raise ValueError("Request unavailable for this device.")
        action, expires, state, raw, result_expires = row
        if action != ACTION:
            raise ValueError("Unsupported stored action.")
        if state in ("pending_local_review", "running_local_command") and expires <= time.time():
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
            "result": _closed_result(json.loads(raw)) if raw and state == "completed" else None,
            "source": "One exact locally reviewed command executed synchronously with a fixed60second cap; bounded captured output, not a live terminal, persistent session or background task",
            "result_ttl_seconds": RESULT_TTL,
            "captured_at_unix": result_expires - RESULT_TTL
            if result_expires is not None and state == "completed"
            else None,
            "device_display_verified": False,
        }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="AETHER laptop-local paired command review")
    parser.add_argument("action", choices=["review"])
    parser.add_argument("identifier", nargs="?")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Use an interactive terminal on the trusted laptop; no piped approval.")
    store = RemoteShellStore()
    item = store.inspect_local(args.identifier)
    print("Exact request ID:", item["request_id"])
    print("Requesting opaque device ID:", item["device_id"])
    print("Guarded classification:", item["classification"])
    print("Exact command:", item["command"])
    print(
        "Action: shell_command. Runs this one exact stored command synchronously, capped at60seconds, and releases bounded captured stdout/stderr to this device token for120seconds. Output can contain private data. Queueing/phone confirmation is not approval. The hard blocked list can never be approved past. No chained approval, session, background task or remote stop of a running command. Expires120seconds after creation. Pairing uses python -m windows_agent.remote_read pair; devices are shared."
    )
    answer = input(
        "Type RUN COMMAND to approve this one exact execution/output disclosure; anything else denies: "
    )
    result = store.review_local(item["request_id"], item["device_id"], answer == "RUN COMMAND")
    print("State:", result["state"])


if __name__ == "__main__":
    main()
