from __future__ import annotations

import asyncio

import pytest

from aether.tools.plan_resume import (
    forget_plan,
    list_plans,
    plan_status,
    run_plan,
    save_plan,
)
from aether.tools.registry import Risk, Tool, ToolRegistry


@pytest.fixture(autouse=True)
def isolated_plan_store(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "plans.sqlite3"))


def _registry(**handlers):
    registry = ToolRegistry()
    for name, handler in handlers.items():
        registry.register(Tool(
            name=name,
            description=f"test tool {name}",
            parameters={"type": "object", "properties": {}},
            handler=handler,
            risk=Risk.SAFE,
            category="system",
        ))
    return registry


def _steps(*ids):
    return [{"task_id": task_id, "tool": f"tool_{task_id}"} for task_id in ids]


def test_saved_plan_runs_and_checkpoints_every_step():
    calls = []
    registry = _registry(
        tool_a=lambda: calls.append("a") or {"message": "a done"},
        tool_b=lambda: calls.append("b") or {"message": "b done"},
    )
    assert save_plan("daily-check", _steps("a", "b"), registry)["created"] is True
    result = asyncio.run(run_plan("daily-check", registry))
    assert result["done"] is True
    assert result["counts"] == {"success": 2}
    assert sorted(calls) == ["a", "b"]


def test_resume_never_reexecutes_successful_steps():
    calls = []
    registry = _registry(
        tool_a=lambda: calls.append("a") or {"message": "a done"},
        tool_b=lambda: (_ for _ in ()).throw(RuntimeError("temporary outage")),
    )
    save_plan("flaky", _steps("a", "b"), registry)
    asyncio.run(run_plan("flaky", registry))
    status = plan_status("flaky")
    assert status["counts"] == {"success": 1, "failed": 1}

    recovered = _registry(
        tool_a=lambda: calls.append("a-again") or {"message": "a done"},
        tool_b=lambda: calls.append("b") or {"message": "b done"},
    )
    result = asyncio.run(run_plan("flaky", recovered))
    assert result["done"] is True
    assert calls == ["a", "b"]


def test_failed_dependency_marks_dependents_skipped_until_resume():
    registry = _registry(
        tool_a=lambda: (_ for _ in ()).throw(RuntimeError("down")),
        tool_b=lambda: {"message": "b done"},
    )
    save_plan("chain", [
        {"task_id": "a", "tool": "tool_a"},
        {"task_id": "b", "tool": "tool_b", "depends_on": ["a"]},
    ], registry)
    asyncio.run(run_plan("chain", registry))
    assert plan_status("chain")["counts"] == {"failed": 1, "skipped": 1}

    calls = []
    recovered = _registry(
        tool_a=lambda: calls.append("a") or {"message": "a done"},
        tool_b=lambda: calls.append("b") or {"message": "b done"},
    )
    result = asyncio.run(run_plan("chain", recovered))
    assert result["done"] is True
    assert calls == ["a", "b"]


def test_save_rejects_mutating_confirmation_and_unknown_tools():
    registry = _registry(tool_a=lambda: {"message": "ok"})
    from aether.tools.registry import Tool as _Tool
    registry.register(_Tool(
        name="writer", description="writes", parameters={"type": "object", "properties": {}},
        handler=lambda: {"message": "wrote"}, risk=Risk.MEDIUM, category="system",
    ))
    with pytest.raises(ValueError, match="unknown tool"):
        save_plan("bad1", [{"task_id": "x", "tool": "nope"}], registry)
    with pytest.raises(ValueError, match="interactive"):
        save_plan("bad2", [{"task_id": "x", "tool": "writer"}], registry)


def test_save_rejects_credential_shaped_and_oversized_arguments():
    registry = _registry(tool_a=lambda: {"message": "ok"})
    with pytest.raises(ValueError, match="credential-shaped"):
        save_plan("bad3", [{"task_id": "a", "tool": "tool_a",
                            "args": {"headers": {"authorization": "api_key=abc"}}}], registry)
    with pytest.raises(ValueError, match="too large"):
        save_plan("bad4", [{"task_id": "a", "tool": "tool_a",
                            "args": {"blob": "x" * 5000}}], registry)


def test_save_rejects_bad_ids_cycles_and_conflicting_redefinition():
    registry = _registry(**{f"tool_{c}": (lambda: {"message": "ok"}) for c in "ab"})
    with pytest.raises(ValueError, match="Plan id"):
        save_plan("bad id!", _steps("a"), registry)
    with pytest.raises(ValueError, match="cycle"):
        save_plan("bad5", [
            {"task_id": "a", "tool": "tool_a", "depends_on": ["b"]},
            {"task_id": "b", "tool": "tool_b", "depends_on": ["a"]},
        ], registry)
    save_plan("fixed", _steps("a"), registry)
    assert save_plan("fixed", _steps("a"), registry)["created"] is False
    with pytest.raises(ValueError, match="different definition"):
        save_plan("fixed", _steps("b"), registry)


def test_status_and_list_hide_arguments_and_outputs():
    registry = _registry(tool_a=lambda: {"message": "ok", "value": 42})
    save_plan("quiet", [{"task_id": "a", "tool": "tool_a",
                         "args": {"path": "/home/owner/private-note.txt"}}], registry)
    asyncio.run(run_plan("quiet", registry))
    status = plan_status("quiet")
    listing = list_plans()
    for payload in (status, listing):
        assert "private-note" not in repr(payload)
        assert "42" not in repr(payload)
    assert status["steps"][0]["status"] == "success"
    assert listing["plans"][0]["counts"] == {"success": 1}


def test_forget_removes_only_the_named_plan():
    registry = _registry(**{f"tool_{c}": (lambda: {"message": "ok"}) for c in "ab"})
    save_plan("keep", [{"task_id": "a", "tool": "tool_a"}], registry)
    save_plan("drop", [{"task_id": "b", "tool": "tool_b"}], registry)
    assert forget_plan("drop")["message"] == "plan forgotten"
    with pytest.raises(KeyError):
        plan_status("drop")
    assert [p["plan_id"] for p in list_plans()["plans"]] == ["keep"]
    with pytest.raises(KeyError):
        forget_plan("drop")


def test_plan_survives_a_fresh_store_connection():
    registry = _registry(tool_a=lambda: {"message": "ok"})
    save_plan("restart", _steps("a"), registry)
    asyncio.run(run_plan("restart", registry))
    # A new connection (as after a process restart) still sees the checkpoint.
    assert plan_status("restart")["done"] is True
    result = asyncio.run(run_plan("restart", registry))
    assert result["done"] is True


def test_plan_steps_record_runtime_events_without_arguments():
    registry = _registry(tool_a=lambda: {"message": "ok"})
    save_plan("events", [{"task_id": "a", "tool": "tool_a",
                          "args": {"path": "/secret-place"}}], registry)
    asyncio.run(run_plan("events", registry))
    from aether.telemetry import runtime_events
    snapshot = runtime_events(limit=50)
    plan_events = [e for e in snapshot["events"] if e.get("task_id") == "plan-events"]
    assert plan_events and all(e["action"] == "plan_step" for e in plan_events)
    assert "secret-place" not in repr(plan_events)
    assert all(e["tool"] == "tool_a" for e in plan_events)
