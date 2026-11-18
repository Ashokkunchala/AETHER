"""Bounded runtime event history with a strict low-sensitivity schema."""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from collections import deque
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings

_EVENT_LIMIT = 200
_events: deque[dict[str, Any]] = deque(maxlen=_EVENT_LIMIT)
_lock = threading.Lock()
_next_id = 1


def _connect_history() -> sqlite3.Connection:
    """Open the shared local database and initialize bounded event history."""
    path = Path(Settings().jarvis_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=2)
    conn.execute("PRAGMA busy_timeout=2000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS runtime_event_history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, "
        "payload TEXT NOT NULL)"
    )
    return conn


def record_runtime_event(category: str, **fields: Any) -> int:
    """Store a small event summary; arbitrary text, args and credentials are discarded."""
    global _next_id
    if category not in {"provider", "tool", "task", "error"}:
        return 0
    event: dict[str, Any] = {
        "category": category,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    for key in ("provider", "model", "tool", "action", "task_id", "risk", "error_type"):
        value = fields.get(key)
        if isinstance(value, str) and value:
            event[key] = value[:100]
    if isinstance(fields.get("success"), bool):
        event["success"] = fields["success"]
    elapsed = fields.get("elapsed")
    if isinstance(elapsed, (int, float)) and math.isfinite(elapsed) and elapsed >= 0:
        event["elapsed"] = round(float(elapsed), 3)
    attempt = fields.get("attempt")
    if isinstance(attempt, int) and 0 < attempt <= 3:
        event["attempt"] = attempt

    with _lock:
        try:
            with closing(_connect_history()) as db:
                cursor = db.execute(
                    "INSERT INTO runtime_event_history(timestamp,payload) VALUES(?,?)",
                    (event["timestamp"], json.dumps(event, separators=(",", ":"))),
                )
                event_id = int(cursor.lastrowid)
                db.execute(
                    "DELETE FROM runtime_event_history WHERE id NOT IN "
                    "(SELECT id FROM runtime_event_history ORDER BY id DESC LIMIT ?)",
                    (_EVENT_LIMIT,),
                )
                db.commit()
        except (OSError, sqlite3.Error, ValueError):
            # Keep runtime behavior available if the local history store is unavailable.
            event_id = _next_id
            _next_id += 1
        event["id"] = event_id
        _events.append(event)
    return event_id


def runtime_events(after_id: int = 0, limit: int = 50) -> dict[str, Any]:
    """Read bounded recent events after a monotonic cursor."""
    after_id = max(0, int(after_id))
    limit = max(1, min(100, int(limit)))
    with _lock:
        try:
            with closing(_connect_history()) as db:
                rows = db.execute(
                    "SELECT id,payload FROM runtime_event_history WHERE id>? "
                    "ORDER BY id DESC LIMIT ?",
                    (after_id, limit),
                ).fetchall()
                oldest = db.execute(
                    "SELECT MIN(id),MAX(id) FROM runtime_event_history"
                ).fetchone()
            events = []
            for event_id, payload in reversed(rows):
                event = json.loads(payload)
                event["id"] = event_id
                events.append(event)
            return {"events": events, "oldest_id": oldest[0] or 0,
                    "latest_id": oldest[1] or 0, "retained": _EVENT_LIMIT,
                    "storage": "sqlite"}
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError):
            events = [dict(event) for event in _events if event["id"] > after_id][-limit:]
            latest_id = _events[-1]["id"] if _events else 0
            oldest_id = _events[0]["id"] if _events else 0
            return {"events": events, "oldest_id": oldest_id, "latest_id": latest_id,
                    "retained": _EVENT_LIMIT, "storage": "volatile"}


def provider_health_summary() -> dict[str, Any]:
    """Summarize bounded recorded provider outcomes without calling a provider.

    The summary is derived only from the low-sensitivity runtime-event store.
    Quota, remaining budget, account health and future availability are not
    measured by local request timing.
    """
    snapshot = runtime_events(after_id=0, limit=100)
    grouped: dict[str, dict[str, Any]] = {}
    for event in snapshot["events"]:
        if event.get("category") != "provider" or not isinstance(event.get("provider"), str):
            continue
        provider = event["provider"]
        row = grouped.setdefault(provider, {
            "provider": provider,
            "events": 0,
            "successes": 0,
            "failures": 0,
            "models_seen": [],
            "latency_samples": [],
            "latest_result": "unknown",
            "latest_event_at": None,
        })
        row["events"] += 1
        row["latest_result"] = "unknown"
        if event.get("success") is True:
            row["successes"] += 1
            row["latest_result"] = "success"
        elif event.get("success") is False:
            row["failures"] += 1
            row["latest_result"] = "failure"
        if isinstance(event.get("model"), str) and event["model"] not in row["models_seen"]:
            row["models_seen"].append(event["model"])
        if isinstance(event.get("elapsed"), (int, float)):
            row["latency_samples"].append(float(event["elapsed"]))
        row["latest_event_at"] = event.get("timestamp")

    providers = []
    for row in grouped.values():
        samples = row.pop("latency_samples")
        attempts = row["successes"] + row["failures"]
        row["success_rate"] = round(row["successes"] / attempts, 4) if attempts else None
        row["latency_seconds"] = {
            "samples": len(samples),
            "average": round(sum(samples) / len(samples), 3) if samples else None,
            "minimum": round(min(samples), 3) if samples else None,
            "maximum": round(max(samples), 3) if samples else None,
        }
        row["models_seen"] = row["models_seen"][:10]
        row["quota_reported"] = False
        providers.append(row)
    providers.sort(key=lambda item: item["provider"])
    return {
        "providers": providers,
        "provider_count": len(providers),
        "storage": snapshot["storage"],
        "retained_events": snapshot["retained"],
        "bounded_sample_limit": 100,
        "measured_only": True,
        "quota_reported": False,
        "notice": "Recorded local provider request summaries only. No provider, network, quota or billing API was called; latest_result is the latest retained event, not account health or future availability. The bounded sample can omit older events and does not include prompts, arguments or credentials.",
    }
