"""Plan-only preview for shell commands the user is considering.

Never executes anything. Each command is classified by the same guarded-shell
policy that run_shell uses, so the user can see - before approving anything -
which commands would need confirmation and which are blocked outright. This is
the default way AETHER looks at a DevOps task list: plan first, run later,
one fresh approval per command.
"""
from __future__ import annotations

from typing import Any

from aether.control.shell import MAX_OUTPUT, classify

MAX_PLAN_COMMANDS = 25
MAX_COMMAND_CHARS = 500


def plan_commands(commands: list[str]) -> dict[str, Any]:
    """Classify up to 25 candidate commands without running them."""
    if not isinstance(commands, list) or not commands:
        raise ValueError("Provide a non-empty list of command strings to preview.")
    if len(commands) > MAX_PLAN_COMMANDS:
        raise ValueError(f"Preview at most {MAX_PLAN_COMMANDS} commands at a time.")
    plan = []
    for item in commands:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Every command must be a non-empty string.")
        command = item.strip()
        if len(command) > MAX_COMMAND_CHARS:
            raise ValueError(f"Commands must be {MAX_COMMAND_CHARS} characters or fewer.")
        classification = classify(command)
        plan.append({
            "command": command,
            "classification": classification,
            "next_step": {
                "blocked": "Blocked outright by safety policy. Rephrase or drop it; approval cannot unblock it.",
                "confirm": "Run it with the run_shell tool; AETHER asks for your fresh approval first.",
                "safe": "Read-only by policy, but run_shell still asks for your fresh approval before running it.",
            }[classification],
        })
    blocked = sum(1 for row in plan if row["classification"] == "blocked")
    return {
        "commands": plan,
        "total": len(plan),
        "blocked": blocked,
        "executed": False,
        "notice": (
            "Plan-only preview. Nothing ran, and no output was captured. Execution happens "
            "only through run_shell with your fresh per-command approval; blocked commands "
            "can never be approved. Output caps and timeouts from the guarded shell apply "
            f"(max output {MAX_OUTPUT} characters)."
        ),
    }
