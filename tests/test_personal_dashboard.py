from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import app

TOKEN = "test-token-that-is-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
KOLKATA = ZoneInfo("Asia/Kolkata")


def client_for(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_API_TOKEN", TOKEN)
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "life.sqlite3"))
    return TestClient(app)


def _seed_notification(db_path, title, read=False):
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS aether_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'general', due_at TEXT, delivered_at TEXT,
        read_at TEXT, created_at TEXT NOT NULL)""")
    conn.execute(
        "INSERT INTO aether_notifications(title,body,channel,read_at,created_at) VALUES(?,?,?,?,?)",
        (title, "notification body", "reminder", now if read else None, now))
    conn.commit()
    conn.close()


def test_dashboard_requires_authentication(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        assert client.get("/api/life/dashboard").status_code == 401


def test_dashboard_empty_database(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        response = client.get("/api/life/dashboard", headers=AUTH)
        assert response.status_code == 200
        data = response.json()
        today = datetime.now(KOLKATA).date().isoformat()
        assert data["date"] == today
        assert data["timezone"] == "Asia/Kolkata"
        assert data["top_priorities"] == []
        # Background workers may create the reminder/notification stores at any
        # time, so only the empty contents are stable here; table absence is
        # covered by test_dashboard_marks_missing_stores_unavailable.
        assert data["reminders"]["counts"] == {"overdue": 0, "due_today": 0, "upcoming": 0}
        assert data["notifications"]["unread"] == 0
        assert data["notifications"]["latest"] == []
        assert data["expenses"]["totals"] == []
        assert data["integrations"] == {
            "google_connected": False,
            "whatsapp_configured": False,
            "notice": "Configured or connected only; not a live delivery check.",
        }
        assert data["partial"] is False
        assert data["invalid_records_skipped"] == 0
        assert data["saved"] is False


def test_dashboard_aggregates_today(monkeypatch, tmp_path):
    today = datetime.now(KOLKATA).date()
    with client_for(monkeypatch, tmp_path) as client:
        task = client.post("/api/life/tasks", headers=AUTH, json={
            "title": "Pay electricity bill", "priority": 1,
            "due_at": datetime.combine(today, datetime.min.time(), KOLKATA).isoformat(),
        })
        assert task.status_code == 201
        event = client.post("/api/life/events", headers=AUTH, json={
            "title": "Interview",
            "starts_at": datetime.combine(today, datetime.min.time().replace(hour=15), KOLKATA).isoformat(),
            "ends_at": datetime.combine(today, datetime.min.time().replace(hour=16), KOLKATA).isoformat(),
        })
        assert event.status_code == 201
        expense = client.post("/api/life/expenses", headers=AUTH, json={
            "amount": 245.5, "currency": "INR", "category": "Utilities",
            "note": "Electricity", "spent_on": today.isoformat(),
        })
        assert expense.status_code == 201
        day_start = datetime.combine(today, datetime.min.time(), KOLKATA)
        for title, due in (
            ("Overdue bill", day_start - timedelta(hours=1)),
            ("Today reminder", day_start + timedelta(minutes=30)),
            ("Later reminder", day_start + timedelta(days=2)),
        ):
            created = client.post("/api/reminders", headers=AUTH,
                                  json={"title": title, "due_at": due.isoformat()})
            assert created.status_code == 201
        _seed_notification(tmp_path / "life.sqlite3", "Reminder: Overdue bill")

        data = client.get("/api/life/dashboard", headers=AUTH,
                          params={"timezone": "Asia/Kolkata"}).json()
        assert data["date"] == today.isoformat()
        assert [row["title"] for row in data["top_priorities"]] == ["Pay electricity bill"]
        assert data["task_counts"]["due_today"] == 1
        assert [row["title"] for row in data["calendar_drafts"]] == ["Interview"]
        reminders = data["reminders"]
        assert reminders["available"] is True
        assert reminders["counts"] == {"overdue": 1, "due_today": 1, "upcoming": 1}
        assert reminders["overdue"][0]["title"] == "Overdue bill"
        assert reminders["due_today"][0]["due_local"].endswith("+05:30")
        notifications = data["notifications"]
        assert notifications["unread"] == 1
        assert notifications["latest"][0]["title"] == "Reminder: Overdue bill"
        assert notifications["latest"][0]["read"] is False
        assert data["expenses"]["month"] == today.strftime("%Y-%m")
        assert data["expenses"]["totals"] == [
            {"currency": "INR", "amount": "245.50", "count": 1}]
        assert data["partial"] is False


def test_dashboard_keeps_currencies_separate(monkeypatch, tmp_path):
    today = datetime.now(KOLKATA).date()
    with client_for(monkeypatch, tmp_path) as client:
        assert client.post("/api/life/expenses", headers=AUTH, json={
            "amount": 100, "currency": "INR", "category": "Food",
            "note": "Lunch", "spent_on": today.isoformat(),
        }).status_code == 201
        db_path = tmp_path / "life.sqlite3"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO life_expenses(amount,currency,category,note,spent_on,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (40, "USD", "Travel", "Taxi", today.isoformat(), datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()
        totals = client.get("/api/life/dashboard", headers=AUTH).json()["expenses"]["totals"]
        assert totals == [{"currency": "INR", "amount": "100.00", "count": 1},
                          {"currency": "USD", "amount": "40.00", "count": 1}]


def test_dashboard_marks_missing_stores_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "fresh.sqlite3"))
    from app.personal_dashboard import _notifications, _reminders

    day = datetime.now(KOLKATA).date()
    start = datetime.combine(day, datetime.min.time(), KOLKATA).astimezone(UTC)
    reminders = _reminders(KOLKATA, start, start + timedelta(days=1))
    assert reminders["available"] is False
    assert reminders["counts"] == {"overdue": 0, "due_today": 0, "upcoming": 0}
    notifications = _notifications()
    assert notifications["available"] is False
    assert notifications["unread"] == 0


def test_dashboard_rejects_unknown_timezone_and_bad_date(monkeypatch, tmp_path):
    with client_for(monkeypatch, tmp_path) as client:
        assert client.get("/api/life/dashboard", headers=AUTH,
                          params={"timezone": "Nowhere/Special"}).status_code == 422
        assert client.get("/api/life/dashboard", headers=AUTH,
                          params={"plan_date": "2026-13-40"}).status_code == 422
