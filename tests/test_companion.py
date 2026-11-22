from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.companion import GREETINGS, daypart_for
from app.main import app

pytestmark = pytest.mark.usefixtures("manual_scheduler")

TOKEN = "test-token-that-is-at-least-32-characters"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_API_TOKEN", TOKEN)
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "aether.sqlite3"))
    return TestClient(app)


def test_daypart_for_boundaries():
    assert daypart_for(0) == "night"
    assert daypart_for(4) == "night"
    assert daypart_for(5) == "morning"
    assert daypart_for(11) == "morning"
    assert daypart_for(12) == "afternoon"
    assert daypart_for(16) == "afternoon"
    assert daypart_for(17) == "evening"
    assert daypart_for(20) == "evening"
    assert daypart_for(21) == "night"
    assert daypart_for(23) == "night"


def test_greeting_requires_device_token(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        response = client.get("/api/companion/greeting")
    assert response.status_code == 401


def test_greeting_returns_read_only_daily_snapshot(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        created = client.post("/api/reminders", headers=HEADERS, json={
            "title": "Call Amma",
            "due_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        })
        assert created.status_code == 201
        response = client.get("/api/companion/greeting?timezone=Asia/Kolkata", headers=HEADERS)
        assert response.status_code == 200
        body = response.json()
        assert body["greeting"] in GREETINGS.values()
        assert body["daypart"] in GREETINGS
        assert body["date"] == datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        assert body["memory_enabled"] is True
        assert body["counts"]["reminders_overdue"] == 1
        assert body["counts"]["reminders_due_today"] == 0
        assert body["counts"]["tasks_due_today"] == 0
        assert "Read-only" in body["notice"]


def test_greeting_rejects_bad_timezone(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        response = client.get("/api/companion/greeting?timezone=Not/AZone", headers=HEADERS)
    assert response.status_code == 422


def test_memory_settings_default_on_and_toggle(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        settings = client.get("/api/memory/settings", headers=HEADERS)
        assert settings.status_code == 200
        assert settings.json()["memory_enabled"] is True

        saved = client.post("/api/memories", headers=HEADERS,
                            json={"text": "Prefers funny mode", "category": "preference"})
        assert saved.status_code == 201

        off = client.put("/api/memory/settings", headers=HEADERS, json={"enabled": False})
        assert off.status_code == 200
        assert off.json()["memory_enabled"] is False

        blocked = client.post("/api/memories", headers=HEADERS,
                              json={"text": "Likes storytelling", "category": "preference"})
        assert blocked.status_code == 409

        # Existing memories stay viewable and clearable while memory is off.
        items = client.get("/api/memories", headers=HEADERS).json()["items"]
        assert [item["text"] for item in items] == ["Prefers funny mode"]
        assert client.delete("/api/memories", headers=HEADERS).status_code == 204

        on = client.put("/api/memory/settings", headers=HEADERS, json={"enabled": True})
        assert on.json()["memory_enabled"] is True
        again = client.post("/api/memories", headers=HEADERS,
                            json={"text": "Likes storytelling", "category": "preference"})
        assert again.status_code == 201


def test_memory_toggle_controls_chat_context(monkeypatch, tmp_path):
    from app import personal_data

    monkeypatch.setenv("AETHER_API_TOKEN", TOKEN)
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "aether.sqlite3"))
    with setup_client(monkeypatch, tmp_path) as client:
        client.post("/api/memories", headers=HEADERS,
                    json={"text": "Enjoys Telugu comedy", "category": "preference"})
        assert "Enjoys Telugu comedy" in personal_data.get_memory_context()
        client.put("/api/memory/settings", headers=HEADERS, json={"enabled": False})
        assert personal_data.get_memory_context() == ""
        client.put("/api/memory/settings", headers=HEADERS, json={"enabled": True})
        assert "Enjoys Telugu comedy" in personal_data.get_memory_context()
