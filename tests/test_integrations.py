from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import integrations
from app.main import app

TOKEN = "aether-integration-test-token-with-32-characters"


pytestmark = pytest.mark.usefixtures("manual_scheduler")


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_API_TOKEN", TOKEN)
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "aether.sqlite3"))
    monkeypatch.setattr(integrations.settings, "jarvis_db_path", str(tmp_path / "aether.sqlite3"))
    monkeypatch.setattr(integrations.settings, "secret_key", "test-secret-key-that-is-at-least-32-characters")
    monkeypatch.setattr(integrations.settings, "google_oauth_client_id", "")
    monkeypatch.setattr(integrations.settings, "google_oauth_client_secret", "")
    monkeypatch.setattr(integrations.settings, "document_allowed_roots", "")
    monkeypatch.setattr(integrations.settings, "whatsapp_access_token", "")
    monkeypatch.setattr(integrations.settings, "whatsapp_phone_number_id", "")
    return TestClient(app)


def test_integrations_require_device_auth(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        assert client.get("/api/integrations/status").status_code == 401
        response = client.get("/api/integrations/status", headers={"Authorization": f"Bearer {TOKEN}"})
        assert response.status_code == 200
        assert response.json()["google"]["connected"] is False


def test_calendar_mutations_are_approval_requests(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        response = client.post("/api/integrations/calendar/proposals", headers=headers, json={
            "action": "create", "title": "Interview", "start": "2026-11-20T09:30:00+05:30",
            "end": "2026-11-20T10:30:00+05:30", "location": "Online",
        })
        assert response.status_code == 201
        approval_id = response.json()["id"]
        pending = client.get("/api/integrations/approvals", headers=headers).json()["items"]
        assert pending[0]["id"] == approval_id
        rejected = client.post(f"/api/integrations/approvals/{approval_id}/reject", headers=headers)
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert client.post(f"/api/integrations/approvals/{approval_id}/reject", headers=headers).status_code == 404


def test_calendar_proposal_validates_time_range(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        response = client.post("/api/integrations/calendar/proposals",
            headers={"Authorization": f"Bearer {TOKEN}"}, json={
                "action": "create", "title": "Invalid", "start": "2026-11-20T10:00:00+05:30",
                "end": "2026-11-20T09:00:00+05:30",
            })
        assert response.status_code == 422


def test_unconfigured_google_and_document_roots_fail_closed(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        assert client.get("/api/integrations/google/connect", headers=headers).status_code == 503
        assert client.get("/api/integrations/documents/search?q=resume", headers=headers).status_code == 503


def test_whatsapp_draft_requires_official_cloud_api_configuration(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        response = client.post("/api/integrations/whatsapp/drafts",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"to": "919876543210", "body": "Hello"})
        assert response.status_code == 503



def test_due_reminders_enter_shared_notification_inbox(monkeypatch, tmp_path):
    from app.integrations import dispatch_due_reminders
    from app.personal_data import _connect as personal_connect

    with setup_client(monkeypatch, tmp_path) as client:
        due = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        db = personal_connect()
        try:
            db.execute(
                "INSERT INTO reminders(title,due_at,created_at,recurrence) VALUES(?,?,?,'none')",
                ("Pay electricity bill", due, datetime.now(UTC).isoformat()),
            )
            db.commit()
        finally:
            db.close()

        assert dispatch_due_reminders() == 1
        response = client.get("/api/integrations/notifications",
                              headers={"Authorization": f"Bearer {TOKEN}"})
        assert response.status_code == 200
        assert response.json()["items"][0]["title"] == "Reminder: Pay electricity bill"


def test_document_search_stays_inside_configured_root(monkeypatch, tmp_path):
    root = tmp_path / "authorized"
    root.mkdir()
    (root / "resume.txt").write_text("AETHER platform engineer resume", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("AETHER private secret", encoding="utf-8")

    with setup_client(monkeypatch, tmp_path) as client:
        monkeypatch.setattr(integrations.settings, "document_allowed_roots", str(root))
        response = client.get("/api/integrations/documents/search?q=platform+engineer",
                              headers={"Authorization": f"Bearer {TOKEN}"})
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["path"].endswith("resume.txt")
