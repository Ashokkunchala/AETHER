from fastapi.testclient import TestClient

from app.main import app
from app import integrations

TOKEN = "aether-integration-test-token-with-32-characters"


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
