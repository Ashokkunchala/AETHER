"""Deterministic free-text rubric signals for mentor practice.

This is transparent phrase/signal review, not semantic grading or mastery
assessment. It never executes a lab or stores the submitted answer.
"""
from __future__ import annotations

import math
import re
import unicodedata

_TOKEN = re.compile(r"[a-z0-9]+")
_NEGATION = re.compile(
    r"\b(?:no|not|never|avoid|avoids|avoided|refuse|refused|reject|rejected|"
    r"incorrect|wrong|unsafe|risky|do\s+not|don't|cannot|can't|must\s+not|"
    r"should\s+not|shouldn't)\b"
)
_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}",
    re.IGNORECASE,
)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for", "from",
    "in", "into", "is", "it", "its", "of", "on", "or", "over", "the", "their",
    "then", "this", "to", "under", "with", "without",
}

_SYNONYMS = {
    "account": {"account", "identity"},
    "action": {"action", "operation", "effect"},
    "approval": {"approval", "approved", "approve", "permission", "authorized", "authorisation", "authorization"},
    "cancel": {"cancel", "cancelled", "canceled", "cancellation"},
    "cleanup": {"cleanup", "clean", "release", "released", "close", "closed"},
    "complete": {"complete", "completed", "completion", "finished", "done"},
    "concurrent": {"concurrent", "concurrency", "parallel", "race", "racing"},
    "decision": {"decision", "choice", "logic"},
    "deploy": {"deploy", "deployment", "release", "rollout"},
    "error": {"error", "errors", "failure", "failed", "exception"},
    "evidence": {"evidence", "observed", "observation", "output", "result", "status", "log", "logs", "telemetry"},
    "external": {"external", "outside", "remote", "provider", "service"},
    "group": {"group", "grouped", "together", "atomic"},
    "identity": {"identity", "id", "identifier", "key", "fingerprint", "uid"},
    "limit": {"limit", "limited", "bound", "bounded", "budget", "cap"},
    "new": {"new", "fresh", "unique"},
    "owner": {"owner", "user", "operator", "controller", "autoscaler"},
    "ready": {"ready", "readiness", "available", "availability"},
    "report": {"report", "reported", "reporting", "claim", "claimed"},
    "retry": {"retry", "retries", "reattempt", "backoff"},
    "review": {"review", "reviewed", "inspect", "inspected", "check", "checked", "examine", "examined"},
    "rollback": {"rollback", "roll", "back", "revert", "undo"},
    "safe": {"safe", "safety", "unsafe", "risk", "risky"},
    "same": {"same", "stable", "matching", "exact"},
    "stale": {"stale", "old", "outdated", "changed"},
    "state": {"state", "status", "condition", "phase"},
    "success": {"success", "successful", "succeeded"},
    "stop": {"stop", "stopped", "halt", "cancel", "cancelled"},
    "timeout": {"timeout", "timed", "deadline", "expired"},
    "transaction": {"transaction", "atomic", "commit", "rollback"},
    "unknown": {"unknown", "uncertain", "unclear", "unverified", "missing"},
    "verify": {"verify", "verified", "verification", "validate", "validated", "test", "tested", "check", "checked", "measure", "measured", "reconcile", "reconciled"},
    "version": {"version", "revision", "generation", "resourceversion"},
    "worker": {"worker", "task", "coroutine", "process"},
    "write": {"write", "writes", "written", "update", "updated", "send", "sent"},
}

_BOUNDARY_SIGNALS = {
    "scenario_evidence": {
        "evidence", "observed", "observation", "status", "output", "result", "log", "telemetry", "scenario",
    },
    "unsafe_choice_rejection": {
        "unsafe", "risk", "risky", "avoid", "reject", "rejected", "refuse", "refused", "not", "never",
    },
    "unknown_or_next_check": {
        "unknown", "uncertain", "unverified", "check", "checked", "verify", "verified", "inspect", "test", "tested",
    },
    "authority_execution_outcome_boundary": {
        "approval", "approved", "permission", "authorized", "execute", "executed", "accepted", "completed", "verified",
    },
}

_NOTICE = (
    "Deterministic rubric signals only: phrase/synonym coverage can miss a good answer "
    "or reward a poor one. This is not semantic correctness, mastery, certification, "
    "interview readiness, code execution or proof a lab was performed. Review the "
    "reference reasoning and source. The supplied answer is not stored by this evaluator; "
    "chat/model logging is controlled by the calling workflow."
)


def _tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return _TOKEN.findall(normalized)


def _variants(term: str) -> set[str]:
    variants = {term}
    if term.endswith("ies") and len(term) > 3:
        variants.add(term[:-3] + "y")
    if term.endswith("s") and len(term) > 3:
        variants.add(term[:-1])
    else:
        variants.add(term + "s")
    return variants | _SYNONYMS.get(term, set())


def _concept_terms(concept: str) -> list[str]:
    terms = []
    for token in _tokens(concept):
        if token not in _STOPWORDS and token not in terms:
            terms.append(token)
    if not terms:
        raise ValueError("Lesson rubric concept has no reviewable terms.")
    return terms[:8]


def _matched_terms(concept: str, token_set: set[str]) -> list[str]:
    matched = []
    for term in _concept_terms(concept):
        if _variants(term) & token_set:
            matched.append(term)
    return matched


def _covers(concept: str, token_set: set[str]) -> tuple[bool, list[str]]:
    matched = _matched_terms(concept, token_set)
    required = len(_concept_terms(concept))
    if required <= 2:
        threshold = required
    else:
        threshold = max(2, math.ceil(required * 0.6))
    return len(matched) >= threshold, matched


def _segments(answer: str) -> list[tuple[set[str], bool]]:
    parts = re.split(r"[.!?;\n]+", answer)
    return [(set(_tokens(part)), bool(_NEGATION.search(unicodedata.normalize("NFKD", part).casefold()))) for part in parts if part.strip()]


def _unsafe_status(concept: str, segments: list[tuple[set[str], bool]]) -> str:
    mentioned = False
    rejected = False
    for token_set, negated in segments:
        covers, _matched = _covers(concept, token_set)
        if covers:
            mentioned = True
            if negated:
                rejected = True
            else:
                return "possible_endorsement"
    if rejected:
        return "rejected_or_warned"
    return "mentioned" if mentioned else "not_mentioned"


def _signal_review(token_set: set[str]) -> list[dict[str, object]]:
    rows = []
    for name, terms in _BOUNDARY_SIGNALS.items():
        matched = sorted(term for term in terms if term in token_set)
        rows.append({"signal": name, "present": bool(matched), "matched_terms": matched})
    return rows


def evaluate_reasoning(lesson_id: str, reasoning: str) -> dict[str, object]:
    """Return transparent rubric signals for one deep-mentor lesson answer."""
    from jarvis.mentor_deep import TRACKS, _lesson

    if not isinstance(reasoning, str) or not 10 <= len(reasoning.strip()) <= 4000:
        raise ValueError("Explain reasoning in 10-4000 characters, without secrets.")
    if _SECRET.search(reasoning):
        raise ValueError("Remove credentials, tokens or private keys before rubric review.")
    track, _level, row = _lesson(lesson_id)
    token_set = set(_tokens(reasoning))
    correct = [row[3][index] for index in row[4]]
    incorrect = [text for index, text in enumerate(row[3]) if index not in row[4]]
    covered = []
    missing = []
    matches = {}
    for concept in correct:
        is_covered, matched = _covers(concept, token_set)
        matches[concept] = matched
        (covered if is_covered else missing).append(concept)
    segments = _segments(reasoning)
    unsafe = [
        {"concept": concept, "status": _unsafe_status(concept, segments)}
        for concept in incorrect
    ]
    signals = _signal_review(token_set)
    present_signals = sum(bool(row["present"]) for row in signals)
    unsafe_endorsements = [row["concept"] for row in unsafe if row["status"] == "possible_endorsement"]
    percent = round((len(covered) / len(correct)) * 100) if correct else 0
    return {
        "lesson_id": lesson_id,
        "concept_coverage_percent": percent,
        "covered_concepts": covered,
        "missing_concepts": missing,
        "matched_concept_terms": matches,
        "unsafe_choice_review": unsafe,
        "possible_unsafe_endorsements": unsafe_endorsements,
        "boundary_signals": signals,
        "boundary_signals_present": present_signals,
        "rubric_signals_complete": not missing and not unsafe_endorsements and present_signals >= 3,
        "reasoning_automatically_graded": False,
        "correctness_verified": False,
        "mastery_assessed": False,
        "lab_executed": False,
        "source": TRACKS[track][0],
        "notice": _NOTICE,
    }


def register_rubric_tools(registry):
    from jarvis.tools.registry import Risk, Tool

    tool = Tool(
        name="mentor_evaluate_reasoning",
        description="Evaluate a supplied free-text deep-mentor explanation against transparent concept/risk/boundary phrase signals for one exact lesson. Not semantic correctness, mastery grading, code execution or lab evidence; does not store the answer.",
        parameters={
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string", "description": "Exact ID from mentor_deep_catalog."},
                "reasoning": {"type": "string", "maxLength": 4000, "description": "Redacted free-text explanation, 10-4000 characters."},
            },
            "required": ["lesson_id", "reasoning"],
            "additionalProperties": False,
        },
        handler=evaluate_reasoning,
        risk=Risk.SAFE,
        category="mentor",
    )
    registry.register(tool)
