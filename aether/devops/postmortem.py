"""Draft a blameless incident post-mortem as Markdown.

Pure text formatting of caller-supplied, unverified claims. No facts are checked.
Caller text is preserved, not redacted or sanitized for publication.
"""

from __future__ import annotations

from typing import Any


def _bullets(items: list[str] | None, empty: str) -> str:
    items = [i.strip() for i in (items or []) if i and i.strip()]
    return "\n".join(f"- {i}" for i in items) if items else f"- {empty}"


def draft_postmortem(
    title: str,
    summary: str = "",
    impact: str = "",
    timeline: list[str] | None = None,
    root_cause: str = "",
    detection: str = "",
    resolution: str = "",
    action_items: list[str] | None = None,
) -> dict[str, Any]:
    fields = {"title": title, "summary": summary, "impact": impact,
              "root_cause": root_cause, "detection": detection, "resolution": resolution}
    for field, value in fields.items():
        limit = 200 if field == "title" else 10000
        if not isinstance(value, str) or len(value) > limit:
            return {"success": False, "error": f"{field} must be text of at most {limit} characters."}
    if "\n" in title or "\r" in title:
        return {"success": False, "error": "Title must be one line."}
    for field, items in (("timeline", timeline), ("action_items", action_items)):
        if items is not None and (not isinstance(items, list) or len(items) > 100 or
                                  any(not isinstance(item, str) or len(item) > 2000 for item in items)):
            return {"success": False, "error": f"{field} must be at most 100 text entries of at most 2000 characters each."}
    timeline = [item.strip() for item in (timeline or []) if item.strip()]
    action_items = [item.strip() for item in (action_items or []) if item.strip()]
    if not title.strip():
        return {"success": False, "error": "A title is required."}
    todo = "_Not provided - fill in before sharing._"
    md = f"""# Post-mortem: {title.strip()}

> DRAFT - caller-supplied claims, not independently verified. Review before sharing.
> Root cause, impact, chronology, recovery and follow-up ownership/dates are unverified.
> Caller wording is preserved, not redacted or sanitized; this is not a publication-ready artifact.

## Summary
{summary.strip() or todo}

## Impact
{impact.strip() or todo}

## Timeline
{_bullets(timeline, "No timeline provided. Add timestamped events (UTC or IST, say which).")}

## Root cause
{root_cause.strip() or todo}

## Detection
{detection.strip() or todo}

## Resolution
{resolution.strip() or todo}

## What went well / what did not
- _Fill in. Keep it about systems and process, not people._

## Action items
{_bullets(action_items, "None yet. Each item needs an owner and a date.")}
"""
    missing = [name for name, val in (("summary", summary), ("impact", impact), ("root_cause", root_cause), ("detection", detection), ("resolution", resolution)) if not val.strip()]
    if not (timeline or []):
        missing.append("timeline")
    if not action_items:
        missing.append("action_items")
    return {"success": True, "markdown": md, "missing_sections": missing,
            "draft_only": True, "caller_claims_verified": False, "root_cause_verified": False,
            "timeline_chronology_verified": False, "impact_verified": False,
            "recovery_verified": False, "action_owners_dates_verified": False,
            "sensitive_content_redacted": False, "shared": False, "followups_created": False,
            "timeline_entries_supplied": len(timeline), "action_items_supplied": len(action_items),
            "source": "https://sre.google/sre-book/postmortem-culture/",
            "limits": "Formats caller text only. Supplied root cause can be a hypothesis and is not verified by its presence; missing_sections means absent nonblank text, not correctness, completeness or acceptance. Timeline order/timezones/clock skew, impact, causal links, resolution/recovery, reviewer agreement, action owner/date/authority are not checked. Text remains caller-authored Markdown including links/markup and possible sensitive data; no redaction/sanitization or external link verification. Do not publish or render as trusted HTML without separate review/safe rendering. No facts inferred, remediation endorsed, owner assigned, task created, file written, message/share sent, source retrieved, network/model/provider call or production change. Tool results can enter model-backed desktop chat. This formatter is not a delivered File, approved report or completed postmortem process."}
