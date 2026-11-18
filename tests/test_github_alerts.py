"""Synthetic signed inputs and temporary SQLite only, no GitHub/network/device send."""

import copy
import hashlib
import hmac
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import github_alerts, integrations

SECRET = "synthetic webhook secret never a real credential"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        github_alerts,
        "settings",
        SimpleNamespace(
            github_alert_webhook_secret=SECRET, github_alert_repositories="12345=example/project"
        ),
    )
    monkeypatch.setattr(
        integrations, "settings", SimpleNamespace(aether_db_path=str(tmp_path / "alerts.db"))
    )
    app = FastAPI()
    app.include_router(github_alerts.router, prefix="/api/integrations")
    with TestClient(app) as client:
        yield client


def payload():
    return {
        "action": "completed",
        "repository": {"id": 12345, "full_name": "example/project"},
        "workflow_run": {
            "id": 98765,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "failure",
            "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "html_url": "https://github.com/example/project/actions/runs/98765",
            "name": "untrusted instructions, never include this in alerts",
            "logs_url": "https://attacker.invalid",
        },
    }


def send(
    client,
    item=None,
    *,
    raw=None,
    event="workflow_run",
    delivery=None,
    secret=SECRET,
    signature=None,
    content_type="application/json",
):
    raw = json.dumps(item if item is not None else payload()).encode() if raw is None else raw
    headers = {
        "X-Hub-Signature-256": signature
        or "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(),
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery or str(uuid.uuid4()),
        "Content-Type": content_type,
    }
    return client.post("/api/integrations/github/actions-webhook", content=raw, headers=headers)


def rows():
    with integrations._connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM aether_notifications")]


def test_default_disabled_before_signature_or_storage(client, monkeypatch):
    github_alerts.settings.github_alert_webhook_secret = ""
    assert send(client).status_code == 503
    assert not rows()


@pytest.mark.parametrize("signature", ["sha1=123", "sha256=bad", "sha256=" + "0" * 64])
def test_signature_required_and_constant_body_bound(client, signature):
    assert send(client, signature=signature).status_code == 401
    assert not rows()


def test_tampered_body_does_not_enqueue(client):
    original = json.dumps(payload()).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), original, hashlib.sha256).hexdigest()
    assert send(client, raw=original + b" ", signature=signature).status_code == 401
    assert not rows()


def test_valid_report_only_safe_fields_historical_not_delivery_or_root_cause(client):
    result = send(client)
    assert result.status_code == 200 and result.json()["enqueued"]
    assert result.json()["device_delivery_verified"] is False
    assert result.json()["current_run_status_verified"] is False
    notification = rows()[0]
    assert notification["channel"] == "github_actions"
    assert "example/project" in notification["body"] and "run 98765" in notification["body"]
    assert "Historical report" in notification["body"]
    assert "untrusted instructions" not in str(notification) and "attacker.invalid" not in str(
        notification
    )


def test_replay_same_run_different_delivery_and_same_delivery_other_run_dedup(client):
    delivery = str(uuid.uuid4())
    assert send(client, delivery=delivery).json()["enqueued"]
    assert send(client, delivery=delivery).json()["status"] == "duplicate"
    assert send(client).json()["status"] == "duplicate"
    item = payload()
    item["workflow_run"]["id"] = 98766
    item["workflow_run"]["html_url"] = "https://github.com/example/project/actions/runs/98766"
    assert send(client, item, delivery=delivery).json()["status"] == "duplicate"
    assert len(rows()) == 1
    item = payload()
    item["workflow_run"]["run_attempt"] = 2
    assert send(client, item).json()["enqueued"]
    assert len(rows()) == 2


@pytest.mark.parametrize(
    "path,value",
    [
        ("repository.id", True),
        ("repository.id", 999),
        ("repository.full_name", "attacker/project"),
        ("workflow_run.id", True),
        ("workflow_run.id", 0),
        ("workflow_run.run_attempt", 0),
        ("workflow_run.run_attempt", 1000001),
        ("workflow_run.html_url", "https://attacker.invalid"),
        (
            "workflow_run.html_url",
            "https://github.com/example/project/actions/runs/98765?token=secret",
        ),
        ("workflow_run.status", "in_progress"),
        ("workflow_run.updated_at", "bad"),
        ("workflow_run.conclusion", []),
    ],
)
def test_out_of_scope_or_malformed_no_enqueue(client, path, value):
    item = payload()
    group, key = path.split(".")
    item[group][key] = value
    assert send(client, item).status_code == 400
    assert not rows()


@pytest.mark.parametrize(
    "kind", ["success", "cancelled", "neutral", "skipped", "action_required", None]
)
def test_non_failure_conclusions_ignored(client, kind):
    item = payload()
    item["workflow_run"]["conclusion"] = kind
    assert send(client, item).json()["enqueued"] is False
    assert not rows()


@pytest.mark.parametrize("hours", [-25, 1])
def test_stale_or_future_report_ignored_not_live_status(client, hours):
    item = payload()
    item["workflow_run"]["updated_at"] = (datetime.now(UTC) + timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert send(client, item).json()["enqueued"] is False
    assert not rows()


def test_event_action_delivery_content_type_and_size(client):
    assert send(client, event="ping").json()["status"] == "ignored_event"
    item = payload()
    item["action"] = "in_progress"
    assert send(client, item).json()["enqueued"] is False
    assert send(client, delivery="bad").status_code == 400
    assert send(client, content_type="text/plain").status_code == 415
    assert send(client, raw=b"x" * 262145).status_code == 413
    assert not rows()


@pytest.mark.parametrize(
    "raw", [b'{"action":"completed","action":"other"}', b'{"x":NaN}', b"bad", b"[]", b"\xff"]
)
def test_invalid_json_no_enqueue(client, raw):
    assert send(client, raw=raw).status_code == 400
    assert not rows()


def test_receipt_and_notification_atomic_rollback(client, monkeypatch):
    # Force receipt insertion to fail after the notification statement.
    with integrations._connect() as db:
        db.execute(
            "CREATE TABLE github_alert_receipts(repository_id INTEGER, run_id INTEGER, attempt INTEGER, delivery_hash TEXT, received_at TEXT, notification_id INTEGER CHECK(notification_id<0))"
        )
    assert send(client).status_code == 503
    assert not rows()


def test_same_run_racing_deliveries_enqueue_once(client):
    # Warm additive schema to keep this race about transaction claims, not first WAL setup.
    with integrations._connect():
        pass
    report = github_alerts._report(payload(), {12345: "example/project"}, datetime.now(UTC))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: github_alerts._enqueue(copy.deepcopy(report), str(uuid.uuid4())), range(4)
            )
        )
    assert sum(results) == 1 and len(rows()) == 1


def test_route_included_in_both_api_entrypoints():
    from app.main import app as minimal
    from app.main_enhanced import app as enhanced

    for app in [minimal, enhanced]:
        assert "/api/integrations/github/actions-webhook" in app.openapi()["paths"]


@pytest.mark.parametrize(
    "config",
    [
        "bad",
        "12345=example/project;12345=other/project",
        "0=example/project",
        "12345=https://attacker.invalid",
        ";",
    ],
)
def test_misconfigured_repository_map_fails_closed(client, config):
    github_alerts.settings.github_alert_repositories = config
    assert send(client).status_code == 503
    assert not rows()


@pytest.mark.parametrize("conclusion", ["timed_out", "startup_failure"])
def test_explicit_additional_failure_conclusions(client, conclusion):
    item = payload()
    item["workflow_run"]["conclusion"] = conclusion
    assert send(client, item).json()["enqueued"]
    assert conclusion in rows()[0]["body"]


def test_capacity_refuses_without_deleting_receipts_or_adding_notification(client):
    assert send(client).json()["enqueued"]
    with integrations._connect() as db:
        db.executemany(
            "INSERT INTO github_alert_receipts VALUES(?,?,?,?,?,?)",
            [(12345, index, 1, f"old-{index}", "old", 1) for index in range(1, 10000)],
        )
    item = payload()
    item["workflow_run"]["run_attempt"] = 2
    assert send(client, item).status_code == 503
    assert len(rows()) == 1
    with integrations._connect() as db:
        assert db.execute("SELECT count(*) FROM github_alert_receipts").fetchone()[0] == 10000


def test_disabling_then_reenable_retains_replay_receipt(client):
    assert send(client).json()["enqueued"]
    github_alerts.settings.github_alert_repositories = ""
    assert send(client).status_code == 503
    github_alerts.settings.github_alert_repositories = "12345=example/project"
    assert send(client).json()["status"] == "duplicate"
    assert len(rows()) == 1
