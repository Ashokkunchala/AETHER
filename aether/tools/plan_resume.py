"""Resumable read-only multi-step tool plans with bounded SQLite checkpoints.

A saved plan is a list of SAFE, non-confirmation tool calls with dependencies.
Each completed step is checkpointed in the shared local database, so a plan
interrupted by a failure or a process restart can resume from its last
incomplete step instead of starting over.

Boundaries, matching the runtime-event history rules:
- Only SAFE read-only tools without a confirmation requirement can be saved.
  Mutating or confirmation-gated steps stay interactive-only, because an
  approval given before a restart must never silently authorize a later run.
- Step arguments are stored locally so the plan can resume, but they are
  rejected when they look credential-shaped, are capped in size, and are never
  returned by status or events. Runtime events keep the allow-listed schema
  (no prompts, arguments, raw errors or credentials).
- Plans are bounded in count, size and step count. This is a local
  convenience store, not a distributed job queue.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from aether.tools.orchestrator import MAX_TASKS_PER_PLAN, ToolTask, ToolTaskOrchestrator
from aether.tools.registry import Risk, ToolRegistry, ToolResult

_PLAN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:password|passwd|token|secret|api[_-]?key)\s*[:=]|\bAKIA[0-9A-Z]{16}\b",
    re.IGNORECASE,
)
_MAX_PLANS = 50
_MAX_PLAN_BYTES = 65536
_MAX_STEP_ARGS_BYTES = 4096
_TASK_KEYS = {"task_id", "tool", "args", "depends_on", "timeout_seconds", "retries"}
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    """Open the shared local database and initialize the plan tables."""
    path = Path(Settings().aether_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=2)
    conn.execute("PRAGMA busy_timeout=2000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS resumable_plans ("
        "plan_id TEXT PRIMARY KEY, created TEXT NOT NULL, updated TEXT NOT NULL, "
        "definition TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS resumable_plan_steps ("
        "plan_id TEXT NOT NULL, task_id TEXT NOT NULL, status TEXT NOT NULL, "
        "elapsed REAL, updated TEXT NOT NULL, PRIMARY KEY (plan_id, task_id))"
    )
    return conn


def _scan_secret(value: Any) -> bool:
    """Return True when any string in a nested value looks credential-shaped."""
    if isinstance(value, str):
        return bool(_SECRET.search(value))
    if isinstance(value, dict):
        return any(_scan_secret(key) or _scan_secret(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_scan_secret(item) for item in value)
    return False


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _validate_definition(plan_id: str, tasks: Any, registry: ToolRegistry) -> list[ToolTask]:
    if not isinstance(plan_id, str) or not _PLAN_ID.fullmatch(plan_id):
        raise ValueError("Plan id must be 1-64 characters of letters, digits, '-' or '_' and start alphanumeric.")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("A plan needs a non-empty list of tasks.")
    if len(tasks) > MAX_TASKS_PER_PLAN:
        raise ValueError(f"Task plans are limited to {MAX_TASKS_PER_PLAN} steps")
    try:
        encoded = json.dumps(tasks)
    except (TypeError, ValueError):
        raise ValueError("Plan tasks must be JSON-serializable.") from None
    if len(encoded.encode("utf-8")) > _MAX_PLAN_BYTES:
        raise ValueError("Plan definition is too large.")

    tool_tasks: list[ToolTask] = []
    for index, raw in enumerate(tasks):
        if not isinstance(raw, dict) or set(raw) - _TASK_KEYS:
            raise ValueError(f"Task {index + 1} has an unknown shape; allowed keys: {sorted(_TASK_KEYS)}")
        tool_name = raw.get("tool")
        tool = registry.get(tool_name) if isinstance(tool_name, str) else None
        if tool is None:
            raise ValueError(f"Task {raw.get('task_id') or index + 1} references an unknown tool.")
        if tool.risk != Risk.SAFE or tool.confirm_required:
            raise ValueError(
                "Only SAFE read-only tools without a confirmation step can be saved for resume; "
                f"'{tool_name}' must stay interactive."
            )
        args = raw.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError(f"Task {raw.get('task_id') or index + 1} args must be an object.")
        if len(json.dumps(args).encode("utf-8")) > _MAX_STEP_ARGS_BYTES:
            raise ValueError(f"Task {raw.get('task_id') or index + 1} args are too large.")
        if _scan_secret(args):
            raise ValueError("Redact the credential-shaped value and save only non-secret arguments.")
        depends_on = raw.get("depends_on") or ()
        if not isinstance(depends_on, (list, tuple)) or not all(isinstance(dep, str) for dep in depends_on):
            raise ValueError(f"Task {raw.get('task_id') or index + 1} depends_on must be a list of task ids.")
        tool_tasks.append(
            ToolTask(
                task_id=str(raw.get("task_id") or ""),
                tool=tool_name,
                args=args,
                depends_on=tuple(depends_on),
                timeout_seconds=float(raw.get("timeout_seconds", 30.0)),
                retries=int(raw.get("retries", 0)),
            )
        )
    ToolTaskOrchestrator(registry)._validate(tool_tasks)
    return tool_tasks


def save_plan(plan_id: str, tasks: Any, registry: ToolRegistry) -> dict[str, Any]:
    """Validate and persist a read-only plan; idempotent for identical saves."""
    tool_tasks = _validate_definition(plan_id, tasks, registry)
    definition = json.dumps(tasks, separators=(",", ":"))
    now = _now()
    with _lock, closing(_connect()) as db:
        row = db.execute(
            "SELECT definition FROM resumable_plans WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if row is not None:
            if row[0] != definition:
                raise ValueError(f"Plan '{plan_id}' already exists with a different definition.")
            created = False
        else:
            count = int(db.execute("SELECT COUNT(*) FROM resumable_plans").fetchone()[0])
            if count >= _MAX_PLANS:
                raise ValueError(f"At most {_MAX_PLANS} saved plans are kept; forget one first.")
            db.execute(
                "INSERT INTO resumable_plans(plan_id, created, updated, definition) VALUES(?,?,?,?)",
                (plan_id, now, now, definition),
            )
            for task in tool_tasks:
                db.execute(
                    "INSERT INTO resumable_plan_steps(plan_id, task_id, status, elapsed, updated) "
                    "VALUES(?,?,?,?,?)",
                    (plan_id, task.task_id, "pending", None, now),
                )
            db.commit()
            created = True
    return {"plan_id": plan_id, "steps": len(tool_tasks), "created": created,
            "message": "plan saved" if created else "plan already saved with the same definition"}


def _load(plan_id: str) -> tuple[list[dict[str, Any]], dict[str, str]] | None:
    with closing(_connect()) as db:
        row = db.execute(
            "SELECT definition FROM resumable_plans WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if row is None:
            return None
        steps = {
            task_id: status
            for task_id, status in db.execute(
                "SELECT task_id, status FROM resumable_plan_steps WHERE plan_id=?", (plan_id,)
            )
        }
    return json.loads(row[0]), steps


def plan_status(plan_id: str) -> dict[str, Any]:
    """Report per-step status without arguments, outputs or secrets."""
    loaded = _load(plan_id)
    if loaded is None:
        raise KeyError(f"Unknown plan: {plan_id}")
    definition, steps = loaded
    ordered = []
    for raw in definition:
        ordered.append({
            "task_id": str(raw.get("task_id") or ""),
            "tool": str(raw.get("tool") or ""),
            "status": steps.get(str(raw.get("task_id") or ""), "pending"),
        })
    counts: dict[str, int] = {}
    for step in ordered:
        counts[step["status"]] = counts.get(step["status"], 0) + 1
    done = bool(ordered) and all(step["status"] == "success" for step in ordered)
    return {"plan_id": plan_id, "done": done, "counts": counts, "steps": ordered}


def list_plans() -> dict[str, Any]:
    """List saved plan ids with per-status step counts; no arguments or outputs."""
    with closing(_connect()) as db:
        rows = db.execute(
            "SELECT p.plan_id, s.status, COUNT(*) FROM resumable_plans p "
            "LEFT JOIN resumable_plan_steps s ON s.plan_id=p.plan_id "
            "GROUP BY p.plan_id, s.status ORDER BY p.created"
        ).fetchall()
    plans: dict[str, dict[str, Any]] = {}
    for plan_id, status, count in rows:
        entry = plans.setdefault(plan_id, {"plan_id": plan_id, "counts": {}})
        if status is not None:
            entry["counts"][status] = count
    return {"plans": list(plans.values()), "count": len(plans)}


def forget_plan(plan_id: str) -> dict[str, Any]:
    """Remove one saved plan and its checkpoints from the local store."""
    with _lock, closing(_connect()) as db:
        removed = db.execute("DELETE FROM resumable_plans WHERE plan_id=?", (plan_id,)).rowcount
        db.execute("DELETE FROM resumable_plan_steps WHERE plan_id=?", (plan_id,))
        db.commit()
    if not removed:
        raise KeyError(f"Unknown plan: {plan_id}")
    return {"plan_id": plan_id, "message": "plan forgotten"}


async def run_plan(plan_id: str, registry: ToolRegistry, on_event=None) -> dict[str, Any]:
    """Run or resume a saved plan, checkpointing every settled step.

    Steps already checkpointed as successful are seeded as completed and never
    re-executed, so a restart or an earlier failure resumes where it stopped.
    """
    loaded = _load(plan_id)
    if loaded is None:
        raise KeyError(f"Unknown plan: {plan_id}")
    definition, steps = loaded
    tool_tasks = _validate_definition(plan_id, definition, registry)

    seeded: dict[str, ToolResult] = {}
    for task in tool_tasks:
        if steps.get(task.task_id) == "success":
            seeded[task.task_id] = ToolResult(
                task.tool, True, data={"message": "completed in an earlier run"}
            )

    def checkpoint(event: dict[str, Any]) -> None:
        kind = event.get("type")
        task_id = event.get("task_id")
        if kind in {"task_end", "task_skipped"} and isinstance(task_id, str):
            status = "success" if event.get("success") is True else (
                "skipped" if kind == "task_skipped" else "failed"
            )
            elapsed = event.get("elapsed")
            with _lock, closing(_connect()) as db:
                db.execute(
                    "UPDATE resumable_plan_steps SET status=?, elapsed=?, updated=? "
                    "WHERE plan_id=? AND task_id=?",
                    (status, elapsed if isinstance(elapsed, (int, float)) else None,
                     _now(), plan_id, task_id),
                )
                db.execute(
                    "UPDATE resumable_plans SET updated=? WHERE plan_id=?", (_now(), plan_id)
                )
                db.commit()
            from aether.telemetry import record_runtime_event
            record_runtime_event(
                "task", action="plan_step", tool=str(event.get("tool") or ""),
                task_id=f"plan-{plan_id}",
                success=event.get("success") if isinstance(event.get("success"), bool) else None,
                elapsed=event.get("elapsed"),
            )
        if on_event:
            try:
                on_event(event)
            except Exception:
                pass

    await ToolTaskOrchestrator(registry).run(
        tool_tasks, on_event=checkpoint, seeded_results=seeded
    )
    return plan_status(plan_id)
