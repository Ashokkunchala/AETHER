import subprocess

import pytest

from aether.devops.command_plan import MAX_PLAN_COMMANDS, plan_commands


def test_plan_classifies_without_executing(monkeypatch):
    def fail_run(*args, **kwargs):
        raise AssertionError("plan_commands must never execute")

    monkeypatch.setattr(subprocess, "run", fail_run)
    result = plan_commands(["git log --oneline", "rm -rf /", "terraform plan", "docker ps"])
    assert result["executed"] is False
    by_command = {row["command"]: row["classification"] for row in result["commands"]}
    assert by_command["git log --oneline"] == "safe"
    assert by_command["rm -rf /"] == "blocked"
    assert by_command["terraform plan"] == "confirm"
    assert by_command["docker ps"] == "confirm"
    assert result["blocked"] == 1
    assert result["total"] == 4


def test_plan_blocked_cannot_be_approved():
    result = plan_commands(["diskpart"])
    row = result["commands"][0]
    assert row["classification"] == "blocked"
    assert "approval cannot unblock" in row["next_step"].lower()


def test_plan_validates_input():
    with pytest.raises(ValueError, match="non-empty list"):
        plan_commands([])
    with pytest.raises(ValueError, match="at most"):
        plan_commands(["echo hi"] * (MAX_PLAN_COMMANDS + 1))
    with pytest.raises(ValueError, match="non-empty string"):
        plan_commands(["   "])
    with pytest.raises(ValueError, match="500 characters"):
        plan_commands(["x" * 501])
