import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from aether.wellness_journal import WellnessJournal, schedule_wellness_prompt


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_WELLNESS_DB", str(tmp_path / "wellness.db"))
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "backend.db"))
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    from app.personal_data import _connect
    with _connect() as db: pass
    return WellnessJournal()


def today():
    return datetime.now(UTC).date().isoformat()


def test_manual_unknown_zero_overlaps_and_correction(journal):
    journal.log_day(today(), "UTC", walk_minutes=20, activity_minutes=20, steps=0, habits=["meditation"])
    report = journal.report(today(), today(), "UTC")
    assert report["manual_totals"]["walk_minutes"] == {"recorded_days": 1, "total": 20}
    assert report["manual_totals"]["steps"] == {"recorded_days": 1, "total": 0}
    assert report["manual_totals"]["hydration_ml"]["recorded_days"] == 0
    assert report["habit_logged_days"] == {"meditation": 1}
    journal.log_day(today(), "UTC", hydration_ml=500)
    report = journal.report(today(), today(), "UTC")
    assert report["manual_totals"]["walk_minutes"]["recorded_days"] == 0
    assert "not fitness improvement" in report["notice"]


@pytest.mark.parametrize("field,value", [("steps", True), ("walk_minutes", -1), ("run_minutes", 1441), ("hydration_ml", float("nan")), ("steps", 2.5), ("habits", ["x", "x"]), ("habits", "x"), ("habits", ["a\nb"])])
def test_refuses_invalid_metrics_and_habit_ambiguity(journal, field, value):
    with pytest.raises(ValueError): journal.log_day(today(), "UTC", **{field: value})


def test_future_and_unknown_timezone_refused(journal):
    future = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    with pytest.raises(ValueError): journal.log_day(future, "UTC")
    with pytest.raises(Exception): journal.log_day(today(), "Not/AZone")
    with pytest.raises(ValueError): journal.report(future, future, "UTC")


def test_sleep_cross_midnight_and_dst_elapsed_not_quality(journal):
    result = journal.log_sleep("2026-11-01T00:30:00-04:00", "2026-11-01T02:30:00-05:00", "America/New_York")
    assert result["time_in_reported_interval_hours"] == 3
    result = journal.log_sleep("2026-11-01T00:30:00-04:00", "2026-11-01T02:30:00-05:00", "America/New_York", "2026-11-01T00:00:00-04:00", "2026-11-01T02:00:00-05:00")
    report = journal.report("2026-11-01", "2026-11-01", "America/New_York")
    assert report["sleep"]["intervals_recorded"] == 1
    assert report["sleep"]["mean_reported_interval_hours"] == 3
    assert report["days"][0]["sleep_routine_offsets_minutes"] == {"bedtime": 30, "wake": 30}
    assert "not measured sleep duration" in result["notice"]
    assert journal.report("2026-11-01", "2026-11-01", "UTC")["other_timezone_records_excluded"] == 1


@pytest.mark.parametrize("begin,end", [("2026-01-01T22:00:00", "2026-01-02T06:00:00"), ("2026-01-02T06:00:00Z", "2026-01-01T22:00:00Z"), ("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z")])
def test_sleep_ambiguous_or_invalid_intervals(journal, begin, end):
    with pytest.raises(ValueError): journal.log_sleep(begin, end, "UTC")


def test_plan_and_exact_comparisons_not_health_assessment(journal):
    journal.plan(today(), "UTC", "Rest or a comfortable walk", ["My familiar dal/rice/vegetables meal"], "Check ingredients; no allergen safety verified", 20, 0)
    assert journal.day(today())["records"]["plan"]["meals"] == ["My familiar dal/rice/vegetables meal"]
    journal.log_day(today(), "UTC", walk_minutes=10, run_minutes=0)
    report = journal.report(today(), today(), "UTC")
    assert report["recorded_goal_comparisons"]["walk"] == {"comparable_days": 1, "met_recorded_days": 0}
    assert report["recorded_goal_comparisons"]["run"]["met_recorded_days"] == 1
    assert journal.weekly(today(), "UTC")["partial_week"]
    with pytest.raises(ValueError): journal.plan(today(), "UTC", "run", ["food"], "", 1000)


def test_unlogged_days_not_missed_and_legacy_not_double_counted(journal):
    start = (datetime.now(UTC).date() - timedelta(days=6)).isoformat()
    report = journal.weekly(start, "UTC")
    assert len(report["days"]) == 7 and not report["partial_week"]
    assert all(row["values"]["steps"] is None for row in report["days"])
    assert "legacy" in report["sources"] and "unlogged does not mean inactive" in report["notice"]


def test_resources_no_autoplay_and_no_medical_fluid_prescription():
    result = WellnessJournal.resources(); template = WellnessJournal.planning_template()
    assert not result["opened"] and not template["saved"]
    assert "external" in result["notice"].lower()
    assert "Stop if pain" in result["exercise_safety"]
    assert "not a fixed daily volume" in template["hydration"]
    assert "not breath holding" in template["meditation"]


def test_day_erase_exact_confirmation_and_separate_reminders(journal):
    journal.log_day(today(), "UTC", steps=100)
    with pytest.raises(ValueError): journal.erase_day(today(), "yes")
    assert journal.erase_day(today(), "ERASE WELLNESS DAY " + today())["deleted"]["wellness_daily"] == 1
    assert not journal.report(today(), today(), "UTC")["days"][0]["manual_activity_recorded"]


def test_prompt_uses_existing_backend_duplicate_protection_and_no_send(journal):
    due = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    first = schedule_wellness_prompt("hydration", due, "Consider a drink if appropriate")
    second = schedule_wellness_prompt("hydration", due, "Consider a drink if appropriate")
    assert first["created"] and not second["created"] and first["reminder_id"] == second["reminder_id"]
    assert "not a sent notification" in first["notice"]
    from app.personal_data import _connect
    with _connect() as db:
        row = db.execute("SELECT * FROM reminders WHERE id=?", (first["reminder_id"],)).fetchone()
        assert row["recurrence"] == "none" and row["completed"] == 0
    with pytest.raises(ValueError): schedule_wellness_prompt("medication", due, "invalid")
    with pytest.raises(ValueError): schedule_wellness_prompt("meditation", "2020-01-01T00:00:00Z", "past")


def test_concurrent_identical_prompt_deduplicates(journal):
    due = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    def create(_): return schedule_wellness_prompt("meditation", due, "Optional quiet pause")
    with ThreadPoolExecutor(max_workers=4) as pool: result = list(pool.map(create, range(4)))
    assert sum(row["created"] for row in result) == 1
    assert len({row["reminder_id"] for row in result}) == 1


def test_registry_confirmation_stop_and_existing_review_preserved(journal):
    from aether.tools.builtin_tools import build_registry
    from aether.security import SecurityStore
    registry = build_registry(force=True)
    assert "weekly_wellness_review" in registry.tools
    assert len(registry.names("wellness")) == 10
    async def run():
        assert (await registry.execute("wellness_log_day", {"day": today(), "timezone": "UTC", "steps": 42})).ok
        due = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        assert not (await registry.execute("wellness_schedule_prompt", {"kind": "hydration", "title": "Drink if wanted", "due_at": due}, auto_approve=True)).ok
        async def yes(*_): return True
        assert (await registry.execute("wellness_schedule_prompt", {"kind": "meditation", "title": "Pause if wanted", "due_at": due}, confirm=yes)).ok
        SecurityStore().set_stop(True)
        assert not (await registry.execute("wellness_log_day", {"day": today(), "timezone": "UTC"})).ok
        assert (await registry.execute("wellness_weekly_summary", {"start_day": today(), "timezone": "UTC"})).ok
    asyncio.run(run())


def test_prompt_does_not_initialize_or_migrate_an_unrelated_backend(journal, monkeypatch, tmp_path):
    path = tmp_path / "missing.db"
    monkeypatch.setenv("AETHER_DB_PATH", str(path))
    due = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with pytest.raises(ValueError): schedule_wellness_prompt("hydration", due, "Optional drink")
    assert not path.exists()
