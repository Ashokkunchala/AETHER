import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.usefixtures("manual_scheduler")

TOKEN = "test-token-that-is-at-least-32-characters"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_API_TOKEN", TOKEN)
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "aether.sqlite3"))
    monkeypatch.setenv("AETHER_MENTOR_DB", str(tmp_path / "mentor.db"))
    return TestClient(app)


def test_mentor_api_requires_device_token(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        assert client.get("/api/mentor/catalog").status_code == 401


def test_catalog_lesson_and_quiz(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        catalog = client.get("/api/mentor/catalog", headers=HEADERS)
        assert catalog.status_code == 200
        items = catalog.json()["items"]
        assert len(items) == 12
        domains = {item["id"] for item in items}
        for expected in ("programming", "backend", "frontend", "cicd", "cloud", "infrastructure",
                         "containers", "linux", "observability", "ai", "systems", "security"):
            assert expected in domains

        # "infrastructure" is the Terraform starter lesson id.
        lesson = client.get("/api/mentor/lessons/infrastructure", headers=HEADERS)
        assert lesson.status_code == 200
        body = lesson.json()
        assert "Terraform" in body["title"]
        assert body["practice"]
        assert body["source"].startswith("https://")

        quiz = client.get("/api/mentor/quiz/infrastructure", headers=HEADERS)
        assert quiz.status_code == 200
        qbody = quiz.json()
        assert qbody["question"]
        assert len(qbody["options"]) >= 2
        # The correct choice must not leak through the read-only API.
        assert "answer" not in qbody
        assert all("correct" not in option for option in qbody["options"])

        missing = client.get("/api/mentor/lessons/not-a-lesson", headers=HEADERS)
        assert missing.status_code == 422


def test_progress_and_activity(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        progress = client.get("/api/mentor/progress", headers=HEADERS)
        assert progress.status_code == 200
        body = progress.json()
        assert body["attempted_checkpoints"] == 0
        assert body["weak_areas"] == []
        assert body["starter_topics"] == 12

        activity = client.get(
            "/api/mentor/activity?start_date=2026-11-01&end_date=2026-11-30&timezone=Asia/Kolkata",
            headers=HEADERS)
        assert activity.status_code == 200

        bad = client.get("/api/mentor/progress?as_of=not-a-date", headers=HEADERS)
        assert bad.status_code == 422


def test_cert_plans_listing(monkeypatch, tmp_path):
    with setup_client(monkeypatch, tmp_path) as client:
        response = client.get("/api/mentor/cert-plans", headers=HEADERS)
        assert response.status_code == 200
        items = response.json()["items"]
        cert_ids = {item["cert_id"] for item in items}
        assert cert_ids == {"aws-ccp", "aws-saa", "az-104", "gcp-ace", "cka", "terraform-associate"}
        for item in items:
            assert item["lessons"]
