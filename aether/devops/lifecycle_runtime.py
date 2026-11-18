"""Disabled-by-default local typed execution engine. No HTTP or model approval endpoint.

The engine owns durable claims and reconciliation. Drivers never retry writes.
Production entry is a local CLI with target-hash allowlisting and TTY review.
Injected drivers are for tests, not an alternate remote authorization surface.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

from aether.devops.lifecycle_design import design_lifecycle_change
from aether.security import SecurityStore


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class LifecycleEngine:
    def __init__(self, path, driver, safety, generation, enabled=False):
        if not isinstance(generation, str) or not generation or len(generation) > 128:
            raise ValueError("Explicit connection generation required.")
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.resolve() != self.path or self.path.is_symlink() or str(self.path).startswith(("//", "\\\\")):
            raise ValueError("Absolute local nonsymlink database required.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600); os.close(fd)
        self.driver, self.safety, self.generation, self.enabled = driver, safety, generation, enabled
        import psutil
        self.boot = str(psutil.boot_time())
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS lifecycle_requests(
                id TEXT PRIMARY KEY, plan TEXT NOT NULL, scope TEXT NOT NULL,
                preflight TEXT NOT NULL, evidence TEXT NOT NULL, generation TEXT NOT NULL,
                expires REAL NOT NULL, state TEXT NOT NULL, result TEXT, expires_mono REAL, boot TEXT);
                CREATE TABLE IF NOT EXISTS lifecycle_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
            columns = {row[1] for row in db.execute("PRAGMA table_info(lifecycle_requests)")}
            for name, kind in (("expires_mono", "REAL"), ("boot", "TEXT")):
                if name not in columns: db.execute("ALTER TABLE lifecycle_requests ADD COLUMN " + name + " " + kind)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def guard(self):
        if not self.enabled:
            raise ValueError("Typed live execution is disabled. No provider access.")
        if self.safety.stopped():
            raise ValueError("Emergency stop is active.")
        with self.connect() as db:
            row = db.execute("SELECT value FROM lifecycle_settings WHERE key='revoked'").fetchone()
            if row and row[0] == "1":
                raise ValueError("Local lifecycle connection revoked; new store/generation and review required.")

    def create(self, plan_json):
        self.guard()
        proposal = design_lifecycle_change(plan_json)
        plan = proposal["supplied_unverified_scope"]
        evidence = self.driver.preflight(plan)
        if not isinstance(evidence, dict) or evidence.get("target_verified") is not True:
            raise ValueError("Live identity/target/precondition evidence unavailable.")
        encoded = json.dumps(evidence, sort_keys=True, allow_nan=False)
        if len(encoded.encode()) > 16000:
            raise ValueError("Bounded preflight evidence required.")
        self.guard()
        key = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM lifecycle_requests WHERE expires<=? AND state IN ('pending','approved','cancelled','expired')", (time.time(),))
            if db.execute("SELECT count(*) FROM lifecycle_requests").fetchone()[0] >= 100:
                raise ValueError("Local request cap reached. Review/archive the store locally; never silently drop unknown outcomes.")
            db.execute("INSERT INTO lifecycle_requests VALUES(?,?,?,?,?,?,?,?,NULL,?,?)", (key, json.dumps(plan, sort_keys=True), proposal["proposal_sha256"], digest(evidence), encoded, self.generation, time.time() + 120, "pending", time.monotonic() + 120, self.boot))
        return self.inspect(key)

    def inspect(self, key):
        if not isinstance(key, str) or len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Exact local request ID required.")
        with self.connect() as db:
            row = db.execute("SELECT * FROM lifecycle_requests WHERE id=?", (key,)).fetchone()
        if not row:
            raise ValueError("Request not found.")
        return dict(row)

    def _validate(self, row):
        self.guard()
        if row["generation"] != self.generation or row["expires"] <= time.time() or row["boot"] != self.boot or not row["expires_mono"] or row["expires_mono"] <= time.monotonic():
            raise ValueError("Connection changed or approval expired.")
        plan = json.loads(row["plan"])
        if design_lifecycle_change(row["plan"])["proposal_sha256"] != row["scope"]:
            raise ValueError("Stored scope changed.")
        if digest(json.loads(row["evidence"])) != row["preflight"]:
            raise ValueError("Stored evidence changed.")
        return plan

    def approve_local(self, key):
        # Only this TTY boundary can create a live approval. No boolean argument/API.
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError("Review on the trusted local terminal, never piped or via remote/model inputs.")
        row = self.inspect(key); self._validate(row)
        if row["state"] != "pending":
            raise ValueError("Request is not pending.")
        print("AETHER exact live proposal:", row["plan"])
        print("Live preflight evidence:", row["evidence"])
        print("Risks: may incur ongoing UNBOUNDED provider charges, lose data, interrupt service or trigger workflow effects. No automatic undo. This software does not enforce a dollar budget. Approve only after reviewing provider cost/budget controls and all external effects. Expiry is 120s from preflight.")
        phrase = "APPROVE COST AND EFFECTS " + row["scope"][:12]
        if input("Type " + phrase + ": ") != phrase:
            self.cancel(key); return {"approved": False}
        self._validate(row)
        with self.connect() as db:
            changed = db.execute("UPDATE lifecycle_requests SET state='approved' WHERE id=? AND state='pending' AND scope=? AND preflight=? AND generation=? AND expires>?", (key, row["scope"], row["preflight"], self.generation, time.time())).rowcount
            if changed != 1:
                raise ValueError("Request changed, cancelled, expired or already approved.")
        return {"approved": True, "request_id": key}

    def execute(self, key):
        row = self.inspect(key); plan = self._validate(row)
        if row["state"] != "approved":
            raise ValueError("Exact local approval required; no replay/retry.")
        fresh = self.driver.preflight(plan)
        if digest(fresh) != row["preflight"]:
            with self.connect() as db:
                db.execute("UPDATE lifecycle_requests SET state='stale' WHERE id=? AND state='approved'", (key,))
            raise ValueError("Live scope/evidence drift. New proposal and approval required.")
        self._validate(row)
        with self.connect() as db:
            changed = db.execute("UPDATE lifecycle_requests SET state='dispatching' WHERE id=? AND state='approved' AND generation=? AND scope=? AND preflight=? AND expires>?", (key, self.generation, row["scope"], row["preflight"], time.time())).rowcount
            if changed != 1:
                raise ValueError("Approval already claimed, cancelled, revoked or expired.")
        def before_write():
            self._validate(self.inspect(key))
            if self.inspect(key)["state"] != "dispatching":
                raise ValueError("Dispatch suppressed by cancellation or changed state.")
        try:
            before_write()
            # Driver must invoke guard at its network-write entry, after client setup.
            receipt = self.driver.dispatch(plan, before_write)
            # Acceptance alone is never success. Cancellation can suppress publication.
            with self.connect() as db:
                db.execute("UPDATE lifecycle_requests SET state='verification_required',result=? WHERE id=? AND state='dispatching'", (json.dumps(receipt, allow_nan=False), key))
        except Exception:
            with self.connect() as db:
                db.execute("UPDATE lifecycle_requests SET state='outcome_unknown',result=NULL WHERE id=? AND state IN ('dispatching','cancellation_requested')", (key,))
            return {"state": "outcome_unknown", "external_outcome_verified": False, "automatic_retry": False}
        return self.reconcile(key)

    def reconcile(self, key):
        self.guard()
        row = self.inspect(key)
        if row["generation"] != self.generation:
            raise ValueError("Use the original account/connection generation to reconcile.")
        if row["state"] not in ("dispatching", "verification_required", "outcome_unknown", "cancellation_requested"):
            raise ValueError("No reconcilable operation. Never redispatch terminal requests.")
        # Expiry blocks writes, not explicitly requested read-only outcome reconciliation.
        plan = json.loads(row["plan"])
        if design_lifecycle_change(row["plan"])["proposal_sha256"] != row["scope"]:
            raise ValueError("Stored scope changed.")
        try:
            verified = self.driver.verify(plan, json.loads(row["result"]) if row["result"] else None)
        except Exception:
            verified = False
        self.guard()
        state = "verified" if verified is True else "outcome_unknown"
        with self.connect() as db:
            db.execute("UPDATE lifecycle_requests SET state=?,result=NULL WHERE id=? AND state IN ('dispatching','verification_required','outcome_unknown','cancellation_requested')", (state, key))
        return {"request_id": key, "state": state, "external_outcome_verified": verified is True,
                "application_health_verified": False, "automatic_retry": False,
                "notice": "Resource observation is not proof this request alone caused the state. Cancellation does not undo provider effects."}

    def cancel(self, key):
        self.inspect(key)
        with self.connect() as db:
            db.execute("UPDATE lifecycle_requests SET state=CASE WHEN state IN ('pending','approved') THEN 'cancelled' WHEN state IN ('dispatching','verification_required','outcome_unknown') THEN 'cancellation_requested' ELSE state END WHERE id=?", (key,))
        return {"state": self.inspect(key)["state"], "remote_termination_verified": False}

    def revoke(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR REPLACE INTO lifecycle_settings VALUES('revoked','1')")
            db.execute("UPDATE lifecycle_requests SET state=CASE WHEN state IN ('pending','approved') THEN 'revoked' WHEN state IN ('dispatching','verification_required','outcome_unknown') THEN 'cancellation_requested' ELSE state END")


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="AETHER local typed live lifecycle, disabled by default")
    parser.add_argument("action", choices=["prepare", "review", "execute", "status", "cancel", "reconcile", "revoke"])
    parser.add_argument("value", nargs="?")
    args = parser.parse_args(argv)
    # No credentials, clients, DB or network are accessed before explicit local opt-in.
    if os.getenv("AETHER_ENABLE_TYPED_LIVE") != "I_REVIEWED_REAL_TARGETS":
        parser.error("Disabled. Owner must approve actual targets and local setup before enabling typed live access.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Local interactive terminal required for all live lifecycle commands.")
    from aether.devops.lifecycle_drivers import LiveDrivers
    engine = LifecycleEngine(Path.home() / ".aether" / "typed-lifecycle.db", LiveDrivers(), SecurityStore(), os.getenv("AETHER_TYPED_CONNECTION_GENERATION", ""), enabled=True)
    if args.action == "prepare":
        if not args.value or len(args.value.encode()) > 8192:
            parser.error("Supply exact plan JSON <=8KiB, no credentials.")
        proposal = design_lifecycle_change(args.value)
        allowed = os.getenv("AETHER_TYPED_ALLOWED_SCOPE_SHA256", "").split(",")
        if proposal["proposal_sha256"] not in allowed:
            parser.error("Exact canonical scope digest is not locally allowlisted; no provider read performed.")
        result = engine.create(args.value)
    elif args.action == "revoke":
        engine.revoke(); result = {"revoked": True}
    else:
        method = {"review": engine.approve_local, "execute": engine.execute, "status": engine.inspect, "cancel": engine.cancel, "reconcile": engine.reconcile}[args.action]
        if args.action in ("review", "execute") and engine.inspect(args.value)["scope"] not in os.getenv("AETHER_TYPED_ALLOWED_SCOPE_SHA256", "").split(","):
            parser.error("Scope no longer locally allowlisted; live action blocked.")
        result = method(args.value)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
