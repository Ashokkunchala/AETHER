"""Certification study-plan outlines mapped to AETHER's local mentor lessons.

Deterministic templates only: each certification maps to an ordered list of
the existing local starter lessons, paced one session per day. This is not an
official certification curriculum and not a pass guarantee. Persisting a plan
saves ordinary local mentor_plan sessions - no calendar events, reminders,
cloud accounts or exam registrations are created or contacted.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from aether.mentor import LESSONS, MentorStore

# Ordered local lesson IDs per certification outline. Every ID must exist in
# aether.mentor.LESSONS; a template referencing a missing lesson fails loudly
# at import time in tests rather than surprising a learner later.
CERTS: dict[str, dict[str, Any]] = {
    "aws-ccp": {
        "label": "AWS Certified Cloud Practitioner",
        "lessons": ["cloud", "security", "systems", "cicd"],
        "focus": "Cloud value, shared responsibility, basic architecture and delivery vocabulary.",
    },
    "aws-saa": {
        "label": "AWS Certified Solutions Architect - Associate",
        "lessons": ["cloud", "systems", "security", "infrastructure", "containers",
                    "observability", "backend", "cicd"],
        "focus": "Resilient, secure, cost-aware architectures; storage, compute, networking and IaC trade-offs.",
    },
    "az-104": {
        "label": "Microsoft Azure Administrator (AZ-104)",
        "lessons": ["cloud", "systems", "security", "infrastructure", "linux", "observability"],
        "focus": "Identity, governance, compute, storage, virtual networking and monitoring administration.",
    },
    "gcp-ace": {
        "label": "Google Cloud Associate Cloud Engineer",
        "lessons": ["cloud", "systems", "infrastructure", "containers", "observability", "cicd"],
        "focus": "Deploying and operating applications, services and access on Google Cloud.",
    },
    "cka": {
        "label": "Certified Kubernetes Administrator (CKA)",
        "lessons": ["containers", "linux", "systems", "observability", "security"],
        "focus": "Cluster architecture, workloads, scheduling, networking, storage and troubleshooting.",
    },
    "terraform-associate": {
        "label": "HashiCorp Certified: Terraform Associate",
        "lessons": ["infrastructure", "cloud", "cicd", "security"],
        "focus": "Workflow, state, modules, providers and safe plan/apply boundaries.",
    },
}

MAX_DAILY_MINUTES = 120
MIN_DAILY_MINUTES = 10


def _lessons_for(cert_id: str) -> list[str]:
    cert = CERTS[cert_id]
    missing = [key for key in cert["lessons"] if key not in LESSONS]
    if missing:
        raise ValueError(f"Certification template references unknown lessons: {', '.join(missing)}.")
    return list(cert["lessons"])


def list_cert_plans() -> list[dict[str, Any]]:
    """Available certification outlines with the local lessons each one uses."""
    plans = []
    for cert_id, cert in CERTS.items():
        lessons = _lessons_for(cert_id)
        plans.append({
            "cert_id": cert_id,
            "label": cert["label"],
            "focus": cert["focus"],
            "lessons": [{"lesson_id": key, "title": LESSONS[key]["title"]} for key in lessons],
            "session_count": len(lessons),
        })
    return plans


def cert_plan(cert_id: str, start_date: str, minutes: int = 30,
              *, persist: bool = False, store: MentorStore | None = None) -> dict[str, Any]:
    """Build a dated study outline for a certification; optionally save it locally.

    One lesson session per day starting at start_date. Persisting writes the
    same local mentor_plan rows as mentor_plan - nothing external is touched.
    """
    if cert_id not in CERTS:
        raise ValueError(
            f"Unknown certification {cert_id!r}. Available: {', '.join(sorted(CERTS))}."
        )
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        raise ValueError("start_date must use YYYY-MM-DD.") from None
    if type(minutes) is not int or not MIN_DAILY_MINUTES <= minutes <= MAX_DAILY_MINUTES:
        raise ValueError(
            f"Daily study time must be an integer from {MIN_DAILY_MINUTES} to {MAX_DAILY_MINUTES} minutes."
        )
    lessons = _lessons_for(cert_id)
    sessions = [
        {
            "lesson_id": key,
            "title": LESSONS[key]["title"],
            "date": (start + timedelta(days=i)).isoformat(),
            "minutes": minutes,
        }
        for i, key in enumerate(lessons)
    ]
    result: dict[str, Any] = {
        "cert_id": cert_id,
        "label": CERTS[cert_id]["label"],
        "focus": CERTS[cert_id]["focus"],
        "sessions": sessions,
        "persisted": False,
        "notice": (
            "Local study outline mapped to AETHER's starter lessons, not an official "
            "certification curriculum or a pass guarantee. Sessions cover foundational "
            "checkpoints only; combine with the provider's own exam guide and hands-on "
            "practice in a sandbox account you own. No calendar events, reminders or "
            "cloud changes were created."
        ),
    }
    if persist:
        target = store or MentorStore()
        saved = target.plan(lessons, start.isoformat(), minutes)
        result["persisted"] = True
        result["saved_sessions"] = saved["sessions"]
    return result


def register_cert_tools(registry):
    from aether.tools.registry import Risk, Tool

    def cert_catalog_handler(**kwargs):
        return {"success": True, "data": list_cert_plans()}

    def cert_plan_handler(cert_id, start_date, minutes=30, persist=False, **kwargs):
        value = cert_plan(cert_id, start_date, minutes, persist=bool(persist))
        return {"success": True, "data": value}

    registry.register(Tool(
        name="mentor_cert_catalog",
        description=(
            "List certification study-plan outlines (AWS, Azure, GCP, CKA, Terraform "
            "Associate) mapped to AETHER's local starter lessons. Read-only."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
        handler=cert_catalog_handler, risk=Risk.SAFE, category="mentor"))
    registry.register(Tool(
        name="mentor_cert_plan",
        description=(
            "Build a dated certification study outline, one local lesson session per day. "
            "Pass persist=true to save it as the local mentor study plan; never creates "
            "calendar events, reminders, cloud resources or exam registrations."
        ),
        parameters={"type": "object", "properties": {
            "cert_id": {"type": "string", "description": "One of: " + ", ".join(sorted(CERTS))},
            "start_date": {"type": "string", "description": "YYYY-MM-DD local start date"},
            "minutes": {"type": "integer", "description": "Daily study minutes, 10-120"},
            "persist": {"type": "boolean", "description": "Save the outline locally (default false: preview only)"},
        }, "required": ["cert_id", "start_date"]},
        handler=cert_plan_handler, risk=Risk.LOW, category="mentor"))
