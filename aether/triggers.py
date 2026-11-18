"""Opt-in event-triggered runs of saved read-only plans.

A trigger rule watches the bounded local runtime-event history. When a new
event matches the rule's category (and optional action/tool), the referenced
saved read-only plan runs once, bounded by a per-rule cooldown.

Boundaries, matching the proactive and plan stores:
- Rules are created disabled; enabling is an explicit opt-in.
- Only saved read-only plans can be referenced, so a trigger can never start
  a mutating or confirmation-gated action. Approvals never carry into a
  triggered run.
- Matching is at-most-once: the event cursor advances before a plan runs, so
  a crash or a failing plan does not retry the same events.
- Rules are bounded in count and cooldown. A rule watching the 'task'
  category can react to plan step events, including its own; the cooldown is
  the only frequency bound. This is a local automation convenience, not a
  scheduler for mutating work or a guarantee of delivery.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RULE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_CATEGORIES = {"provider", "tool", "task", "error"}
_MAX_RULES = 20
_MIN_COOLDOWN = 300
_MAX_COOLDOWN = 86400


def _db_path() -> Path:
    return Path(os.environ.get("AETHER_TRIGGERS_DB") or Path.home() / ".aether" / "triggers.db")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TriggerStore:
    """SQLite store for trigger rules and the event cursor."""

    def __init__(self, path: Path | None = None):
        self.path = path or _db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS trigger_rules ("
                "rule_id TEXT PRIMARY KEY, category TEXT NOT NULL, action TEXT, "
                "tool TEXT, plan_id TEXT NOT NULL, cooldown_seconds INTEGER NOT NULL, "
                "enabled INTEGER NOT NULL, last_fired TEXT, created TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS trigger_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=2)
        conn.execute("PRAGMA busy_timeout=2000")
        return conn

    def configure(self, rule_id: str, category: str, plan_id: str,
                  action: str | None = None, tool: str | None = None,
                  cooldown_seconds: int = 3600, enabled: bool = False) -> dict[str, Any]:
        if not isinstance(rule_id, str) or not _RULE_ID.fullmatch(rule_id):
            raise ValueError("Rule id must be 1-64 characters of letters, digits, '-' or '_' and start alphanumeric.")
        if category not in _CATEGORIES:
            raise ValueError(f"Category must be one of {sorted(_CATEGORIES)}.")
        for label, value in (("action", action), ("tool", tool)):
            if value is not None and (not isinstance(value, str) or not value or len(value) > 100):
                raise ValueError(f"{label} filter must be a short non-empty string.")
        cooldown = int(cooldown_seconds)
        if not _MIN_COOLDOWN <= cooldown <= _MAX_COOLDOWN:
            raise ValueError(f"Cooldown must be between {_MIN_COOLDOWN} and {_MAX_COOLDOWN} seconds.")
        from aether.tools.plan_resume import _load
        if _load(plan_id) is None:
            raise ValueError(f"Unknown saved read-only plan: {plan_id}")
        now = _utcnow().isoformat(timespec="seconds")
        with closing(self._connect()) as db:
            exists = db.execute(
                "SELECT 1 FROM trigger_rules WHERE rule_id=?", (rule_id,)
            ).fetchone()
            if not exists:
                count = int(db.execute("SELECT COUNT(*) FROM trigger_rules").fetchone()[0])
                if count >= _MAX_RULES:
                    raise ValueError(f"At most {_MAX_RULES} trigger rules are kept; delete one first.")
            db.execute(
                "INSERT INTO trigger_rules(rule_id, category, action, tool, plan_id, "
                "cooldown_seconds, enabled, last_fired, created) VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(rule_id) DO UPDATE SET category=excluded.category, "
                "action=excluded.action, tool=excluded.tool, plan_id=excluded.plan_id, "
                "cooldown_seconds=excluded.cooldown_seconds, enabled=excluded.enabled",
                (rule_id, category, action, tool, plan_id, cooldown, 1 if enabled else 0,
                 None, now),
            )
            db.commit()
        return {"rule_id": rule_id, "category": category, "plan_id": plan_id,
                "cooldown_seconds": cooldown, "enabled": bool(enabled),
                "message": "trigger rule saved"}

    def rules(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT rule_id, category, action, tool, plan_id, cooldown_seconds, enabled, "
                "last_fired FROM trigger_rules ORDER BY created"
            ).fetchall()
        return [
            {"rule_id": r[0], "category": r[1], "action": r[2], "tool": r[3],
             "plan_id": r[4], "cooldown_seconds": r[5], "enabled": bool(r[6]),
             "last_fired": r[7]}
            for r in rows
        ]

    def delete(self, rule_id: str) -> dict[str, Any]:
        with closing(self._connect()) as db:
            removed = db.execute("DELETE FROM trigger_rules WHERE rule_id=?", (rule_id,)).rowcount
            db.commit()
        if not removed:
            raise KeyError(f"Unknown trigger rule: {rule_id}")
        return {"rule_id": rule_id, "message": "trigger rule deleted"}

    def _get_state(self, key: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM trigger_state WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else None

    def _set_state(self, key: str, value: str) -> None:
        with closing(self._connect()) as db:
            db.execute(
                "INSERT INTO trigger_state(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            db.commit()

    def cursor(self) -> int:
        value = self._get_state("event_cursor")
        return int(value) if value is not None else 0

    def set_cursor(self, value: int) -> None:
        self._set_state("event_cursor", str(int(value)))

    def initialized(self) -> bool:
        return self._get_state("initialized") == "1"

    def mark_initialized(self) -> None:
        self._set_state("initialized", "1")

    def mark_fired(self, rule_id: str, when: str) -> None:
        with closing(self._connect()) as db:
            db.execute(
                "UPDATE trigger_rules SET last_fired=? WHERE rule_id=?", (when, rule_id)
            )
            db.commit()


def _matches(rule: dict[str, Any], event: dict[str, Any]) -> bool:
    if event.get("category") != rule["category"]:
        return False
    if rule.get("action") and event.get("action") != rule["action"]:
        return False
    if rule.get("tool") and event.get("tool") != rule["tool"]:
        return False
    return True


class TriggerRunner:
    """A tick invoked by the existing backend scheduler, at most once a minute."""

    def __init__(self, registry_factory=None, clock=time.monotonic, now_fn=_utcnow):
        from aether.tools.builtin_tools import build_registry
        self.registry_factory = registry_factory or build_registry
        self.clock = clock
        self.now_fn = now_fn
        self.next_check = 0.0

    async def tick(self) -> None:
        now = self.clock()
        if now < self.next_check:
            return
        self.next_check = now + 60
        path = _db_path()
        if not path.is_file():
            return
        store = TriggerStore(path)
        enabled = [rule for rule in store.rules() if rule["enabled"]]
        if not enabled:
            return

        from aether.telemetry import record_runtime_event, runtime_events
        if not store.initialized():
            # First run with rules: start from the newest known event so old
            # history never retroactively fires a fresh rule.
            store.set_cursor(int(runtime_events(limit=1)["latest_id"]))
            store.mark_initialized()
            return
        cursor = store.cursor()
        snapshot = runtime_events(after_id=cursor, limit=100)
        events = snapshot["events"]
        if not events:
            return
        # Advance before running: matching is at-most-once per event.
        store.set_cursor(max(int(event["id"]) for event in events))

        registry = self.registry_factory()
        for rule in enabled:
            if not any(_matches(rule, event) for event in events):
                continue
            last_fired = rule.get("last_fired")
            if last_fired:
                try:
                    elapsed = (self.now_fn() - datetime.fromisoformat(last_fired)).total_seconds()
                except ValueError:
                    elapsed = float("inf")
                if elapsed < rule["cooldown_seconds"]:
                    continue
            fired_at = self.now_fn().isoformat(timespec="seconds")
            try:
                from aether.tools.plan_resume import run_plan
                status = await run_plan(rule["plan_id"], registry)
                store.mark_fired(rule["rule_id"], fired_at)
                record_runtime_event(
                    "task", action="trigger_fire", task_id=f"trigger-{rule['rule_id']}",
                    success=bool(status.get("done")),
                )
            except Exception:
                # A failing plan must not stop other rules or the scheduler.
                record_runtime_event(
                    "task", action="trigger_fire", task_id=f"trigger-{rule['rule_id']}",
                    success=False,
                )


def register_trigger_tools(registry):
    from aether.tools.registry import Risk, Tool

    def handler_for(method):
        def handler(**kwargs):
            return {"success": True, "data": getattr(TriggerStore(), method)(**kwargs)}
        return handler

    definitions = [
        ("trigger_configure",
         "Create or update an event trigger rule that runs a saved read-only plan when a matching local runtime event arrives. Disabled unless enabled=true. Checks roughly once a minute while the backend runs; matching is at-most-once and cooldown-bounded. Mutating tools can never be triggered.",
         "configure", Risk.LOW,
         {
             "rule_id": {"type": "string", "description": "1-64 characters: letters, digits, '-' or '_', starting alphanumeric."},
             "category": {"type": "string", "enum": ["provider", "tool", "task", "error"]},
             "plan_id": {"type": "string", "description": "Saved read-only plan id from plan_save_readonly."},
             "action": {"type": "string", "description": "Optional exact event action filter."},
             "tool": {"type": "string", "description": "Optional exact event tool filter."},
             "cooldown_seconds": {"type": "integer", "minimum": 300, "maximum": 86400},
             "enabled": {"type": "boolean"},
         },
         ["rule_id", "category", "plan_id"]),
        ("trigger_rules",
         "List saved event trigger rules, their filters, cooldowns and last fired time.",
         "rules", Risk.SAFE, {}, []),
        ("trigger_delete",
         "Delete one event trigger rule. Running plans and saved plans are not affected.",
         "delete", Risk.LOW,
         {"rule_id": {"type": "string"}}, ["rule_id"]),
    ]
    for name, description, method, risk, properties, required in definitions:
        registry.register(Tool(
            name=name, description=description,
            parameters={"type": "object", "properties": properties, "required": required},
            handler=handler_for(method), risk=risk, category="triggers",
        ))
