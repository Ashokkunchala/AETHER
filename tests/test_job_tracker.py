from datetime import UTC, datetime, timedelta

import pytest

from aether.job_tracker import JobTracker


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_JOBS_DB", str(tmp_path / "jobs.db"))
    return JobTracker()


def today(offset=0):
    return (datetime.now(UTC).date() + timedelta(days=offset)).isoformat()


def test_add_list_and_summary(tracker):
    key = tracker.add("DevOps Engineer", "Example Corp", "applied", url="https://example.com/jobs/1",
                      applied_day=today(), follow_up_day=today(7), notes="referral from Sasi")["id"]
    tracker.add("SRE", "Other Ltd", "saved")
    listing = tracker.list()
    assert listing["count"] == 2
    first = [a for a in listing["applications"] if a["id"] == key][0]
    assert first["company"] == "Example Corp" and first["status"] == "applied"
    assert tracker.list(status="saved")["count"] == 1
    summary = tracker.summary()
    assert summary["total"] == 2 and summary["by_status"]["applied"] == 1
    assert "not a pipeline forecast" in summary["notice"]


def test_update_records_status_history_and_requires_change(tracker):
    key = tracker.add("DevOps Engineer", "Example Corp", "applied")["id"]
    result = tracker.update(key, status="interview", notes="L1 Monday 3 PM", follow_up_day=today(2))
    assert set(result["updated_fields"]) == {"status", "notes", "follow_up_day"}
    with tracker.connect() as db:
        history = db.execute("SELECT status FROM status_history WHERE application_id=? ORDER BY recorded", (key,)).fetchall()
    assert [h[0] for h in history] == ["applied", "interview"]
    with pytest.raises(ValueError):
        tracker.update(key)
    with pytest.raises(ValueError):
        tracker.update(999, status="offer")


def test_followups_due_only_open_and_not_future(tracker):
    tracker.add("A", "CoA", "applied", follow_up_day=today(-1))
    tracker.add("B", "CoB", "interview", follow_up_day=today())
    tracker.add("C", "CoC", "applied", follow_up_day=today(3))
    tracker.add("D", "CoD", "rejected", follow_up_day=today(-2))
    due = tracker.followups_due("Asia/Kolkata")
    assert {row["role"] for row in due["due"]} == {"A", "B"}
    assert due["timezone"] == "Asia/Kolkata"


def test_remove_requires_exact_confirmation(tracker):
    key = tracker.add("DevOps Engineer", "Example Corp", "applied")["id"]
    with pytest.raises(ValueError):
        tracker.remove(key, "yes delete")
    with pytest.raises(ValueError):
        tracker.remove(key, f"REMOVE APPLICATION {key + 1}")
    assert tracker.remove(key, f"REMOVE APPLICATION {key}")["removed"] == key
    assert tracker.summary()["total"] == 0
    with pytest.raises(ValueError):
        tracker.remove(key, f"REMOVE APPLICATION {key}")


@pytest.mark.parametrize("field,value", [
    ("role", ""), ("role", "a\nb"), ("company", "x" * 200),
    ("status", "hired"), ("url", "http://insecure.example"), ("url", "notaurl"),
    ("applied_day", "28-11-2026"), ("applied_day", today(1)),
    ("follow_up_day", "tomorrow"), ("notes", "n" * 2000),
])
def test_refuses_invalid_input(tracker, field, value):
    base = {"role": "DevOps Engineer", "company": "Example Corp", "status": "applied"}
    base[field] = value
    with pytest.raises(ValueError):
        tracker.add(**base)


def test_update_validates_ids_and_fields(tracker):
    with pytest.raises(ValueError):
        tracker.update("1", status="offer")
    key = tracker.add("R", "C", "saved")["id"]
    with pytest.raises(ValueError):
        tracker.update(key, status="maybe")
    with pytest.raises(ValueError):
        tracker.update(key, follow_up_day="soon")


def test_registry_wiring_and_risk_levels():
    from aether.tools.builtin_tools import build_registry, reset_controllers
    from aether.tools.registry import Risk
    reset_controllers()
    registry = build_registry(force=True)
    names = {t.name for t in registry.tools.values()}
    expected = {"job_add", "job_update", "job_list", "job_followups_due", "job_summary", "job_remove"}
    assert expected <= names
    risks = {registry.get(n).risk for n in ("job_add", "job_update")}
    assert risks == {Risk.LOW}
    assert {registry.get(n).risk for n in ("job_list", "job_followups_due", "job_summary")} == {Risk.SAFE}
    remove = registry.get("job_remove")
    assert remove.risk == Risk.HIGH and remove.requires_confirmation and remove.never_auto_approve
    assert all(registry.get(n).category == "jobs" for n in expected)


def test_execute_through_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_JOBS_DB", str(tmp_path / "jobs.db"))
    from aether.tools.builtin_tools import build_registry, reset_controllers
    reset_controllers()
    registry = build_registry(force=True)
    import asyncio
    result = asyncio.run(registry.execute("job_add", {"role": "DevOps Engineer", "company": "Example Corp", "status": "applied"}))
    assert result.ok and result.data["stored"] is True
    listed = asyncio.run(registry.execute("job_summary", {}))
    assert listed.ok and listed.data["total"] == 1
