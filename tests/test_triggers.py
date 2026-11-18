from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.tools.plan_resume import plan_status, save_plan
from jarvis.tools.registry import Risk, Tool, ToolRegistry
from jarvis.triggers import TriggerRunner, TriggerStore, _utcnow


@pytest.fixture(autouse=True)
def isolated_stores(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    monkeypatch.setenv("JARVIS_TRIGGERS_DB", str(tmp_path / "triggers.db"))


def _registry(calls=None):
    registry = ToolRegistry()
    registry.register(Tool(
        name="probe", description="read-only probe",
        parameters={"type": "object", "properties": {}},
        handler=lambda: (calls.append("probe") if calls is not None else None) or {"message": "ok"},
        risk=Risk.SAFE, category="system",
    ))
    return registry


def _save_plan(registry, plan_id="p1"):
    save_plan(plan_id, [{"task_id": "s1", "tool": "probe"}], registry)


def _runner(registry, clock, now_fn):
    return TriggerRunner(registry_factory=lambda: registry, clock=clock, now_fn=now_fn)


def _event(category, **fields):
    from jarvis.telemetry import record_runtime_event
    return record_runtime_event(category, **fields)


def test_configure_validation_and_rule_lifecycle():
    registry = _registry()
    _save_plan(registry)
    store = TriggerStore()
    with pytest.raises(ValueError, match="Rule id"):
        store.configure("bad id!", "provider", "p1")
    with pytest.raises(ValueError, match="Category"):
        store.configure("r1", "network", "p1")
    with pytest.raises(ValueError, match="Unknown saved read-only plan"):
        store.configure("r1", "provider", "missing")
    with pytest.raises(ValueError, match="Cooldown"):
        store.configure("r1", "provider", "p1", cooldown_seconds=60)
    with pytest.raises(ValueError, match="action filter"):
        store.configure("r1", "provider", "p1", action="")

    saved = store.configure("r1", "provider", "p1", tool="gemini", enabled=True)
    assert saved["enabled"] is True and saved["cooldown_seconds"] == 3600
    updated = store.configure("r1", "tool", "p1", cooldown_seconds=600)
    assert updated["category"] == "tool" and updated["cooldown_seconds"] == 600
    assert len(store.rules()) == 1
    assert store.delete("r1")["message"] == "trigger rule deleted"
    with pytest.raises(KeyError):
        store.delete("r1")


def test_first_tick_starts_cursor_without_retroactive_fire():
    calls = []
    registry = _registry(calls)
    _save_plan(registry)
    _event("provider", provider="gemini", success=True)
    store = TriggerStore()
    store.configure("r1", "provider", "p1", enabled=True)
    clock_value = [0.0]
    runner = _runner(registry, clock=lambda: clock_value[0], now_fn=_utcnow)
    asyncio.run(runner.tick())
    assert calls == []
    assert store.cursor() > 0


def test_matching_event_runs_plan_once_and_records_trigger():
    calls = []
    registry = _registry(calls)
    _save_plan(registry)
    store = TriggerStore()
    store.configure("r1", "provider", "p1", enabled=True)
    clock_value = [0.0]
    runner = _runner(registry, clock=lambda: clock_value[0], now_fn=_utcnow)
    asyncio.run(runner.tick())  # initializes cursor

    _event("provider", provider="gemini", success=False)
    clock_value[0] = 61
    asyncio.run(runner.tick())
    assert calls == ["probe"]
    assert plan_status("p1")["done"] is True
    assert store.rules()[0]["last_fired"]

    # The same events never fire again, even after the cooldown.
    clock_value[0] = 122
    asyncio.run(runner.tick())
    assert calls == ["probe"]

    from jarvis.telemetry import runtime_events
    fired = [e for e in runtime_events(limit=50)["events"]
             if e.get("task_id") == "trigger-r1" and e.get("action") == "trigger_fire"]
    assert fired and fired[-1]["success"] is True


def test_disabled_and_nonmatching_rules_do_not_fire():
    calls = []
    registry = _registry(calls)
    _save_plan(registry)
    store = TriggerStore()
    store.configure("off", "provider", "p1", enabled=False)
    store.configure("wrongcat", "error", "p1", enabled=True)
    store.configure("wrongtool", "provider", "p1", tool="groq", enabled=True)
    clock_value = [0.0]
    runner = _runner(registry, clock=lambda: clock_value[0], now_fn=_utcnow)
    asyncio.run(runner.tick())
    _event("provider", provider="gemini", success=True)
    clock_value[0] = 61
    asyncio.run(runner.tick())
    assert calls == []


def test_cooldown_blocks_immediate_refire():
    calls = []
    registry = _registry(calls)
    _save_plan(registry)
    store = TriggerStore()
    store.configure("r1", "provider", "p1", cooldown_seconds=300, enabled=True)
    now_value = [datetime(2026, 11, 18, 12, 0, tzinfo=UTC)]
    clock_value = [0.0]
    runner = _runner(registry, clock=lambda: clock_value[0], now_fn=lambda: now_value[0])
    asyncio.run(runner.tick())
    _event("provider", provider="gemini", success=True)
    clock_value[0] = 61
    asyncio.run(runner.tick())
    assert calls == ["probe"]

    # A new matching event inside the cooldown window does not refire.
    _event("provider", provider="gemini", success=True)
    now_value[0] = now_value[0] + timedelta(seconds=120)
    clock_value[0] = 122
    asyncio.run(runner.tick())
    assert calls == ["probe"]

    # After the cooldown it fires again; the finished plan resumes as done.
    _event("provider", provider="gemini", success=True)
    now_value[0] = now_value[0] + timedelta(seconds=400)
    clock_value[0] = 183
    asyncio.run(runner.tick())
    assert calls == ["probe"]


def test_failing_plan_records_failure_and_does_not_retry_same_events():
    calls = []
    registry = ToolRegistry()
    registry.register(Tool(
        name="probe", description="crashing probe",
        parameters={"type": "object", "properties": {}},
        handler=lambda: calls.append(1) or (_ for _ in ()).throw(RuntimeError("boom")),
        risk=Risk.SAFE, category="system",
    ))
    _save_plan(registry)
    store = TriggerStore()
    store.configure("r1", "provider", "p1", enabled=True)
    clock_value = [0.0]
    runner = _runner(registry, clock=lambda: clock_value[0], now_fn=_utcnow)
    asyncio.run(runner.tick())
    _event("provider", provider="gemini", success=True)
    clock_value[0] = 61
    asyncio.run(runner.tick())  # plan step fails; run_plan still returns

    assert len(calls) == 1
    clock_value[0] = 122
    asyncio.run(runner.tick())
    # The failure events the run emitted never re-trigger the rule.
    assert len(calls) == 1
    from jarvis.telemetry import runtime_events
    fired = [e for e in runtime_events(limit=50)["events"]
             if e.get("task_id") == "trigger-r1" and e.get("action") == "trigger_fire"]
    assert fired and fired[-1]["success"] is False


def test_rules_and_cursor_boundaries():
    registry = _registry()
    _save_plan(registry)
    store = TriggerStore()
    for index in range(20):
        store.configure(f"rule-{index}", "provider", "p1")
    with pytest.raises(ValueError, match="At most 20"):
        store.configure("rule-21", "provider", "p1")
    listing = store.rules()
    assert len(listing) == 20
    assert all(not row["enabled"] for row in listing)
    assert store.cursor() == 0
