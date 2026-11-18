import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.mentor import MentorStore
from jarvis.mentor_deep import DeepMentor


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "backend.db"))
    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    from app.personal_data import _connect
    with _connect():
        pass
    return DeepMentor(MentorStore())


def future(hours=2):
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def test_schedules_exact_review_prompt_without_sending(stores):
    due = future().replace("+00:00", "Z")
    result = stores.schedule_review_prompt("python-1", due)
    assert result["created"] is True
    assert result["lesson_title"] == "Cancellation cleanup"
    assert result["due_at"] == datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    assert "not a sent notification" in result["notice"]
    from app.personal_data import _connect
    with _connect() as db:
        row = db.execute("SELECT * FROM reminders WHERE id=?", (result["reminder_id"],)).fetchone()
        assert row["title"] == "AETHER mentor review: python-1 - Cancellation cleanup"
        assert row["due_at"] == result["due_at"]
        assert row["completed"] == 0 and row["recurrence"] == "none"


def test_identical_prompt_deduplicates(stores):
    due = future()
    first = stores.schedule_review_prompt("aws-2", due)
    second = stores.schedule_review_prompt("aws-2", due)
    assert first["created"] is True
    assert second["created"] is False
    assert first["reminder_id"] == second["reminder_id"]


def test_concurrent_identical_prompt_deduplicates(stores):
    due = future()
    def create(_):
        return stores.schedule_review_prompt("backend-1", due)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(create, range(4)))
    assert sum(result["created"] for result in results) == 1
    assert len({result["reminder_id"] for result in results}) == 1


def test_progress_due_is_reported_but_not_rewritten(stores):
    stores.start("python-1")
    progress_due = stores.progress()["lessons"][0]["next_review_utc"]
    assert progress_due is None
    due = future(3)
    result = stores.schedule_review_prompt("python-1", due)
    assert result["progress_next_review_utc"] is None
    assert stores.progress()["lessons"][0]["next_review_utc"] is None


@pytest.mark.parametrize("lesson_id", ["missing-1", "python-4", "python", "python-1-extra", "", None])
def test_unknown_lesson_rejected(stores, lesson_id):
    with pytest.raises(ValueError):
        stores.schedule_review_prompt(lesson_id, future())


@pytest.mark.parametrize("due_at", ["2020-01-01T00:00:00Z", "2099-01-01T00:00:00Z", "2026-11-18 10:00:00+00:00", "2026-11-18T10:00:00", "tomorrow", "", None])
def test_due_time_requires_exact_bounded_future_offset(stores, due_at):
    with pytest.raises(ValueError):
        stores.schedule_review_prompt("python-1", due_at)


def test_missing_backend_store_is_not_initialized(stores, tmp_path, monkeypatch):
    path = tmp_path / "missing-backend.db"
    monkeypatch.setenv("JARVIS_DB_PATH", str(path))
    with pytest.raises(ValueError):
        stores.schedule_review_prompt("python-1", future())
    assert not path.exists()


def test_registry_requires_fresh_confirmation_and_stop(stores):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    registry = build_registry(force=True)
    assert len(registry.names("mentor")) == 25
    async def run():
        due = future()
        assert not (await registry.execute("mentor_deep_schedule_review_prompt", {"lesson_id": "python-1", "due_at": due}, auto_approve=True)).ok
        async def yes(*_):
            return True
        approved = await registry.execute("mentor_deep_schedule_review_prompt", {"lesson_id": "python-1", "due_at": due}, confirm=yes)
        assert approved.ok and approved.data["created"] is True
        SecurityStore().set_stop(True)
        blocked = await registry.execute("mentor_deep_schedule_review_prompt", {"lesson_id": "python-1", "due_at": future(4)}, confirm=yes)
        assert not blocked.ok
        SecurityStore().set_stop(False)
    asyncio.run(run())
