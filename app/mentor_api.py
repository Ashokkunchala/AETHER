"""Read-only HTTP access to the local mentor subsystem.

The learning actions themselves (submitting checkpoints, saving plans,
interview answers) stay in the chat tool surface where each one carries its
own risk level and explanation. These endpoints let the web dashboard show
the catalog, objective checkpoints, progress and certification outlines
without going through chat. Nothing here executes a lab command, contacts a
certification provider or changes study data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from aether.mentor import MentorStore
from aether.mentor_certs import list_cert_plans
from app.personal_data import require_device_token

router = APIRouter(prefix="/api/mentor", tags=["mentor"])


def _store() -> MentorStore:
    return MentorStore()


def _call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/catalog", dependencies=[Depends(require_device_token)])
def mentor_catalog():
    """Starter learning domains and lesson IDs."""
    return {"items": _store().catalog()}


@router.get("/lessons/{lesson_id}", dependencies=[Depends(require_device_token)])
def mentor_lesson(lesson_id: str):
    """Lesson notes and the safe manual practice task. Never executes commands."""
    return _call(_store().lesson, lesson_id)


@router.get("/quiz/{lesson_id}", dependencies=[Depends(require_device_token)])
def mentor_quiz(lesson_id: str):
    """Objective multiple-choice checkpoint; the correct choice is not included."""
    return _call(_store().quiz, lesson_id)


@router.get("/progress", dependencies=[Depends(require_device_token)])
def mentor_progress(as_of: str | None = None):
    """Persisted checkpoints, weak areas and overdue study sessions."""
    return _call(_store().progress, as_of)


@router.get("/activity", dependencies=[Depends(require_device_token)])
def mentor_activity(start_date: str, end_date: str, timezone: str = "Asia/Kolkata"):
    """Objective-checkpoint attempts by local day for an explicit date range."""
    return _call(_store().daily_activity, start_date, end_date, timezone)


@router.get("/cert-plans", dependencies=[Depends(require_device_token)])
def mentor_cert_plans():
    """Certification study-plan outlines mapped to local starter lessons."""
    return {"items": list_cert_plans()}
