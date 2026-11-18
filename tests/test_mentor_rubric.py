import asyncio
import json

import pytest

from aether.mentor import MentorStore
from aether.mentor_deep import DeepMentor
from aether.mentor_rubric import evaluate_reasoning


GOOD = (
    "Use finally to release resources, propagate cancellation after cleanup, and cite observed evidence. "
    "I reject swallowing cancellation and reporting success as unsafe. The next step is to verify the "
    "approved execution and completed outcome."
)


def test_rubric_signals_cover_correct_concepts_and_reject_unsafe_choice():
    result = evaluate_reasoning("python-1", GOOD)
    assert result["concept_coverage_percent"] == 100
    assert result["covered_concepts"] == ["Release resources in finally", "Propagate cancellation"]
    assert result["missing_concepts"] == []
    assert result["possible_unsafe_endorsements"] == []
    assert result["unsafe_choice_review"][0]["status"] == "rejected_or_warned"
    assert result["boundary_signals_present"] >= 3
    assert result["rubric_signals_complete"] is True
    assert result["reasoning_automatically_graded"] is False
    assert result["correctness_verified"] is False
    assert result["mastery_assessed"] is False
    assert result["lab_executed"] is False


def test_missing_concept_is_incomplete_not_failed_as_mastery():
    result = evaluate_reasoning("python-1", "Use finally to release resources, check the evidence, and verify the result.")
    assert result["concept_coverage_percent"] == 50
    assert result["missing_concepts"] == ["Propagate cancellation"]
    assert result["rubric_signals_complete"] is False
    assert result["mastery_assessed"] is False


def test_unnegated_unsafe_choice_is_flagged():
    result = evaluate_reasoning("python-1", "I would swallow cancellation and report success immediately without another check.")
    assert result["possible_unsafe_endorsements"] == ["Swallow cancellation and report success"]
    assert result["rubric_signals_complete"] is False


def test_result_is_deterministic_and_omits_answer_text():
    unique = "unique learner wording about cooperative cancellation"
    answer = GOOD + " This " + unique + " stays local."
    first = evaluate_reasoning("python-1", answer)
    second = evaluate_reasoning("python-1", answer)
    assert first == second
    assert unique not in json.dumps(first)


@pytest.mark.parametrize("lesson_id", ["", "python", "unknown-1", "python-4", "python-1-extra"])
def test_invalid_lesson_id(lesson_id):
    with pytest.raises(ValueError):
        evaluate_reasoning(lesson_id, GOOD)


@pytest.mark.parametrize("answer", ["", "short", "x" * 4001, None, 123])
def test_invalid_answer(answer):
    with pytest.raises(ValueError):
        evaluate_reasoning("python-1", answer)


def test_secret_shaped_answer_is_refused():
    with pytest.raises(ValueError):
        evaluate_reasoning("python-1", "-----BEGIN PRIVATE KEY-----\n" + GOOD)


def test_deep_submit_returns_signal_review_without_claiming_grade(tmp_path):
    mentor = DeepMentor(MentorStore(tmp_path / "mentor.db"))
    session = mentor.start("python-1")
    with mentor.store.connect() as db:
        permutation = json.loads(db.execute("SELECT permutation FROM mentor_deep_sessions WHERE id=?", (session["session_id"],)).fetchone()[0])
    choices = [index for index, original in enumerate(permutation) if original in {0, 1}]
    result = mentor.submit(session["session_id"], choices, GOOD)
    assert result["objective_decisions_correct"] is True
    assert result["reasoning_automatically_graded"] is False
    assert result["rubric_signal_review"]["rubric_signals_complete"] is True
    assert result["rubric_signal_review"]["mastery_assessed"] is False


def test_registered_safe_rubric_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry

    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute("mentor_evaluate_reasoning", {"lesson_id": "python-1", "reasoning": GOOD}))
    assert result.ok
    assert result.data["rubric_signals_complete"] is True
