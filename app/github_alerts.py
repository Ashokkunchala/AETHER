"""Opt-in verified GitHub workflow-run reports to the existing local inbox.

No GitHub/API call, model, remote notification send or remediation is performed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.config import get_settings

router = APIRouter()
settings = get_settings()
_MAX_BODY = 262144
_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
_GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _configuration():
    secret = settings.github_alert_webhook_secret
    raw = settings.github_alert_repositories
    if (
        not isinstance(secret, str)
        or not 32 <= len(secret) <= 1024
        or not isinstance(raw, str)
        or len(raw) > 8192
    ):
        raise HTTPException(503, "GitHub alerts are disabled or misconfigured.")
    repos = {}
    for item in raw.split(";"):
        if not item.strip():
            continue
        parts = item.strip().split("=")
        if (
            len(parts) != 2
            or not re.fullmatch(r"[1-9][0-9]{0,18}", parts[0])
            or not _NAME.fullmatch(parts[1])
        ):
            raise HTTPException(503, "GitHub alerts are disabled or misconfigured.")
        identity = int(parts[0])
        if identity in repos or len(repos) >= 50:
            raise HTTPException(503, "GitHub alerts are disabled or misconfigured.")
        repos[identity] = parts[1]
    if not repos:
        raise HTTPException(503, "GitHub alerts are disabled or misconfigured.")
    return secret.encode("utf-8"), repos


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _integer(value):
    return type(value) is int and 1 <= value <= 9_223_372_036_854_775_807


def _report(payload, repos, now):
    if not isinstance(payload, dict):
        raise ValueError("Expected an object")
    if payload.get("action") != "completed":
        return None
    repo = payload.get("repository")
    run = payload.get("workflow_run")
    if not isinstance(repo, dict) or not isinstance(run, dict):
        raise ValueError("Missing run/repository")
    repo_id = repo.get("id")
    name = repo.get("full_name")
    if (
        not _integer(repo_id)
        or repo_id not in repos
        or not isinstance(name, str)
        or name.casefold() != repos[repo_id].casefold()
    ):
        raise ValueError("Repository not configured")
    run_id, attempt = run.get("id"), run.get("run_attempt")
    if not _integer(run_id) or not _integer(attempt) or attempt > 1000000:
        raise ValueError("Invalid exact run identity")
    if run.get("status") != "completed":
        raise ValueError("Incomplete run")
    conclusion = run.get("conclusion")
    if conclusion not in {"failure", "timed_out", "startup_failure"}:
        return None
    updated = run.get("updated_at")
    if not isinstance(updated, str) or not _TIME.fullmatch(updated):
        raise ValueError("Missing bounded timestamp")
    stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    if stamp < now - timedelta(hours=24) or stamp > now + timedelta(minutes=5):
        return None
    url = run.get("html_url")
    # Keep only an exact safe HTTPS run URL actually present in the signed payload.
    if (
        not isinstance(url, str)
        or url.casefold() != f"https://github.com/{repos[repo_id]}/actions/runs/{run_id}".casefold()
    ):
        raise ValueError("Unexpected run URL")
    return {
        "repository_id": repo_id,
        "run_id": run_id,
        "attempt": attempt,
        "name": repos[repo_id],
        "conclusion": conclusion,
        "updated": updated,
        "url": url,
    }


def _enqueue(report, delivery):
    from app.integrations import _connect

    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS github_alert_receipts (
            repository_id INTEGER NOT NULL, run_id INTEGER NOT NULL,
            attempt INTEGER NOT NULL, delivery_hash TEXT NOT NULL UNIQUE,
            received_at TEXT NOT NULL, notification_id INTEGER NOT NULL,
            PRIMARY KEY(repository_id, run_id, attempt))""")
        # The existing connector finishes its migration transaction before yield.
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        key = (report["repository_id"], report["run_id"], report["attempt"])
        delivery_hash = hashlib.sha256(delivery.lower().encode()).hexdigest()
        exists = db.execute(
            "SELECT 1 FROM github_alert_receipts WHERE (repository_id=? AND run_id=? AND attempt=?) OR delivery_hash=?",
            (*key, delivery_hash),
        ).fetchone()
        if exists:
            return False
        # Bounded retention without deleting replay receipts. Refuse at capacity.
        if db.execute("SELECT count(*) FROM github_alert_receipts").fetchone()[0] >= 10000:
            raise HTTPException(
                503,
                "GitHub alert receipt capacity reached. Review local retention before enabling more alerts.",
            )
        now = datetime.now(UTC).isoformat()
        body = (
            f"Signed webhook reported {report['conclusion']} for {report['name']}, run {report['run_id']}, "
            f"attempt {report['attempt']}, updated {report['updated']}. Historical report, not current status or root cause. "
            f"Review: {report['url']}"
        )
        notification = db.execute(
            "INSERT INTO aether_notifications(title,body,channel,created_at) VALUES(?,?,?,?)",
            ("GitHub Actions failure reported", body, "github_actions", now),
        )
        db.execute(
            "INSERT INTO github_alert_receipts VALUES(?,?,?,?,?,?)",
            (*key, delivery_hash, now, notification.lastrowid),
        )
        return True


@router.post("/github/actions-webhook")
async def github_actions_webhook(request: Request):
    secret, repos = _configuration()
    signature = request.headers.get("x-hub-signature-256", "")
    if not re.fullmatch(r"sha256=[0-9a-f]{64}", signature):
        raise HTTPException(401, "Webhook signature required.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > _MAX_BODY:
            raise HTTPException(413, "Webhook exceeds the 262144-byte limit.")
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid webhook signature.")
    event = request.headers.get("x-github-event", "")
    delivery = request.headers.get("x-github-delivery", "")
    if not _GUID.fullmatch(delivery):
        raise HTTPException(400, "A valid delivery identifier is required.")
    if event != "workflow_run":
        return {"status": "ignored_event", "enqueued": False}
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "JSON webhook required.")
    try:
        payload = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
        )
        report = _report(payload, repos, datetime.now(UTC))
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise HTTPException(400, "Invalid or out-of-scope workflow report.") from None
    if report is None:
        return {"status": "ignored_action_conclusion_or_time", "enqueued": False}
    try:
        queued = await run_in_threadpool(_enqueue, report, delivery)
    except sqlite3.Error:
        raise HTTPException(
            503, "Local alert storage unavailable; no delivery success claimed."
        ) from None
    return {
        "status": "queued" if queued else "duplicate",
        "enqueued": queued,
        "device_delivery_verified": False,
        "current_run_status_verified": False,
    }
