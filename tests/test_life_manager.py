from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

TOKEN = "test-token-that-is-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def client_for(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_API_TOKEN", TOKEN)
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "life.sqlite3"))
    return TestClient(app)


def test_life_manager_requires_authentication(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        assert client.get("/api/life/tasks").status_code == 401
        assert client.get("/life").status_code == 200


def test_tasks_create_prioritize_complete_and_delete(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        created = client.post("/api/life/tasks", headers=AUTH, json={
            "title": "Prepare interview", "details": "Review Linux and AWS",
            "due_at": "2026-11-18T15:00:00+05:30", "priority": 2,
        })
        assert created.status_code == 201
        task = created.json()
        assert task["priority"] == 2
        assert task["due_at"] == "2026-11-18T09:30:00+00:00"

        updated = client.patch(f"/api/life/tasks/{task['id']}", headers=AUTH,
                               json={"status": "done"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "done"
        assert client.get("/api/life/summary", headers=AUTH).json()["tasks"]["done"] == 1
        assert client.delete(f"/api/life/tasks/{task['id']}", headers=AUTH).status_code == 204
        assert client.delete(f"/api/life/tasks/{task['id']}", headers=AUTH).status_code == 404


def test_task_rejects_timezone_naive_deadline(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        response = client.post("/api/life/tasks", headers=AUTH, json={
            "title": "No ambiguous time", "due_at": "2026-11-18T15:00:00",
        })
        assert response.status_code == 422


def test_notes_and_expenses_are_persistent(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        note = client.post("/api/life/notes", headers=AUTH, json={
            "title": "Meeting notes", "body": "Follow up with the team", "kind": "meeting",
        })
        assert note.status_code == 201
        assert client.get("/api/life/notes", headers=AUTH).json()["items"][0]["body"] == "Follow up with the team"

        expense = client.post("/api/life/expenses", headers=AUTH, json={
            "amount": 245.5, "currency": "INR", "category": "Food",
            "note": "Lunch", "spent_on": "2026-11-16",
        })
        assert expense.status_code == 201
        report = client.get("/api/life/expenses?month=2026-11", headers=AUTH).json()
        assert report["total"] == 245.5
        assert report["by_category"][0]["category"] == "Food"


def test_calendar_events_are_saved_as_drafts_only(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        event = client.post("/api/life/events", headers=AUTH, json={
            "title": "Interview", "starts_at": "2026-11-20T15:00:00+05:30",
            "ends_at": "2026-11-20T16:00:00+05:30", "location": "Online",
        })
        assert event.status_code == 201
        assert event.json()["status"] == "draft"
        assert client.get("/api/life/events", headers=AUTH).json()["items"][0]["title"] == "Interview"

        invalid = client.post("/api/life/events", headers=AUTH, json={
            "title": "Invalid range", "starts_at": "2026-11-20T16:00:00+05:30",
            "ends_at": "2026-11-20T15:00:00+05:30",
        })
        assert invalid.status_code == 422
