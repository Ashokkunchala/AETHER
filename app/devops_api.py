"""Read-only HTTP view of the local execution audit log.

Every guarded tool execution is already recorded by the security store (tool
name, timestamp, outcome - never arguments, outputs or credentials). This
endpoint lets the dashboard show that history. It changes nothing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aether.security import SecurityStore
from app.personal_data import require_device_token

router = APIRouter(prefix="/api/devops", tags=["devops"])


@router.get("/audit", dependencies=[Depends(require_device_token)])
def execution_audit(limit: int = 50):
    """Newest-first execution audit events: tool, timestamp, outcome."""
    return {
        "events": SecurityStore().events(limit),
        "notice": (
            "Local audit of tool executions only: tool name, timestamp and outcome. "
            "No command arguments, outputs or credentials are stored."
        ),
    }
