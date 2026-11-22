import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.usefixtures("manual_scheduler")

TOKEN = "test-token-that-is-at-least-32-characters"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_API_TOKEN", TOKEN)
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "aether.sqlite3"))
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    return TestClient(app)


def test_audit_endpoint_requires_device_token(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        assert client.get("/api/devops/audit").status_code == 401


def test_audit_endpoint_returns_recorded_events(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    from aether.security import SecurityStore

    store = SecurityStore()
    store.audit("run_shell", "started")
    store.audit("run_shell", "succeeded")
    store.audit("plan_commands", "succeeded")

    with setup_client(monkeypatch, tmp_path) as client:
        response = client.get("/api/devops/audit?limit=10", headers=HEADERS)
        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) == 3
        assert events[0]["tool"] == "plan_commands"  # newest first
        assert {event["outcome"] for event in events} == {"started", "succeeded"}
        # Arguments, outputs and credentials are never recorded.
        assert all(set(event) == {"id", "ts", "tool", "outcome"} for event in events)


def test_execution_audit_tool_reads_same_log(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import _execution_audit

    SecurityStore().audit("review_k8s", "succeeded")
    result = _execution_audit(5)
    assert result["events"][0]["tool"] == "review_k8s"
    assert "No arguments" in result["notice"]
