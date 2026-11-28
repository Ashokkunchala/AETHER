import pytest

from aether.interview_practice import BANK, TOPICS, InterviewPractice


@pytest.fixture
def practice(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_PRACTICE_DB", str(tmp_path / "practice.db"))
    return InterviewPractice()


def test_topics_cover_bank():
    result = InterviewPractice.topics()
    assert result["total"] == len(BANK)
    assert sum(t["questions"] for t in result["topics"]) == len(BANK)
    assert {"aws", "ci-cd", "docker", "kubernetes", "linux", "terraform", "monitoring", "behavioral"} <= set(TOPICS)


def test_next_question_cycles_least_shown(practice):
    seen = set()
    total = sum(1 for t, _, _ in BANK if t == "aws")
    for _ in range(total):
        q = practice.next_question("aws")
        assert q["topic"] == "aws" and q["self_check_points"]
        seen.add(q["question_id"])
    assert len(seen) == total  # every aws question before any repeat


def test_next_question_deterministic_after_record(practice):
    first = practice.next_question("docker")["question_id"]
    practice.record(first, "ok")
    again = practice.next_question("docker")
    assert again["question_id"] != first  # unrated/less-shown questions come first


def test_record_and_progress(practice):
    q = practice.next_question("kubernetes")
    result = practice.record(q["question_id"], "hard", "revisit probes")
    assert result["recorded"] is True and result["topic"] == "kubernetes"
    progress = practice.progress()
    assert progress["practised_at_least_once"] >= 1
    assert progress["per_topic"]["kubernetes"]["ratings"]["hard"] == 1
    assert "not a skill score" in progress["notice"]


@pytest.mark.parametrize("topic", ["AWS", "devops", "", "aws "])
def test_refuses_unknown_topic(practice, topic):
    with pytest.raises(ValueError):
        practice.next_question(topic)


@pytest.mark.parametrize("args", [
    {"question_id": -1, "rating": "ok"},
    {"question_id": len(BANK), "rating": "ok"},
    {"question_id": "0", "rating": "ok"},
    {"question_id": 0, "rating": "great"},
    {"question_id": 0, "rating": "ok", "notes": "x" * 600},
    {"question_id": 0, "rating": "ok", "notes": "a\nb"},
])
def test_record_refuses_invalid(practice, args):
    with pytest.raises(ValueError):
        practice.record(**args)


def test_registry_wiring_and_risk_levels():
    from aether.tools.builtin_tools import build_registry, reset_controllers
    from aether.tools.registry import Risk
    reset_controllers()
    registry = build_registry(force=True)
    expected = {"interview_topics", "interview_question", "interview_record", "interview_progress"}
    names = {t.name for t in registry.tools.values()}
    assert expected <= names
    assert registry.get("interview_topics").risk == Risk.SAFE
    assert registry.get("interview_progress").risk == Risk.SAFE
    assert {registry.get(n).risk for n in ("interview_question", "interview_record")} == {Risk.LOW}
    assert all(registry.get(n).category == "practice" for n in expected)
    assert not any(registry.get(n).requires_confirmation for n in expected)


def test_execute_through_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_PRACTICE_DB", str(tmp_path / "practice.db"))
    import asyncio
    from aether.tools.builtin_tools import build_registry, reset_controllers
    reset_controllers()
    registry = build_registry(force=True)
    result = asyncio.run(registry.execute("interview_question", {"topic": "linux"}))
    assert result.ok and result.data["topic"] == "linux"
    rec = asyncio.run(registry.execute("interview_record", {"question_id": result.data["question_id"], "rating": "confident"}))
    assert rec.ok and rec.data["recorded"] is True
