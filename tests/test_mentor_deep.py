import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from jarvis.mentor import MentorStore
from jarvis.mentor_deep import DeepMentor, TRACKS


@pytest.fixture
def mentor(tmp_path):
    return DeepMentor(MentorStore(tmp_path / "mentor.db"))


def answer(mentor, session, right=True):
    with mentor.store.connect() as db:
        perm = json.loads(db.execute("SELECT permutation FROM mentor_deep_sessions WHERE id=?", (session["session_id"],)).fetchone()[0])
    track, number = session["lesson_id"].rsplit("-", 1)
    expected = TRACKS[track][1][int(number) - 1][4]
    choices = [i for i, n in enumerate(perm) if n in expected] if right else [i for i, n in enumerate(perm) if n not in expected]
    return mentor.submit(session["session_id"], choices, "I checked evidence, unsafe options and the next verification step.")


def test_three_levels_each_track_and_every_objective_feedback(mentor):
    assert len(mentor.catalog()) == 12
    for track in TRACKS:
        for locked in (2, 3):
            with pytest.raises(ValueError): mentor.start(f"{track}-{locked}")
        for level in (1, 2, 3):
            for _ in range(2):
                session = mentor.start(f"{track}-{level}")
                assert session["teaching_notes"] and session["lab"] and session["source"]
                result = answer(mentor, session)
                assert result["objective_decisions_correct"]
                assert not result["reasoning_automatically_graded"]
                assert result["self_review_rubric"]
    assert all(row["unlocked"] for row in mentor.progress()["lessons"])


def test_wrong_answer_resets_streak_prioritizes_remediation_and_survives_reopen(mentor):
    answer(mentor, mentor.start("python-1"))
    answer(mentor, mentor.start("python-1"), False)
    reopened = DeepMentor(mentor.store)
    row = next(row for row in reopened.progress()["lessons"] if row["id"] == "python-1")
    assert row["attempts"] == 2 and row["incorrect"] == 1
    assert row["consecutive_objective_passes"] == 0
    with pytest.raises(ValueError):
        mentor.start("python-2")


def test_replay_and_expiry_are_refused(mentor):
    session = mentor.start("aws-1")
    answer(mentor, session)
    with pytest.raises(ValueError):
        answer(mentor, session)
    session = mentor.start("aws-1")
    with mentor.store.connect() as db:
        db.execute("UPDATE mentor_deep_sessions SET expires='2000-01-01T00:00:00+00:00'")
    with pytest.raises(ValueError):
        answer(mentor, session)


@pytest.mark.parametrize("choices", [[True], [1.0], [], [0, 0], [3], "0", None])
def test_invalid_decisions_no_record(mentor, choices):
    session = mentor.start("backend-1")
    with pytest.raises(ValueError):
        mentor.submit(session["session_id"], choices, "This explanation is long enough.")
    with mentor.store.connect() as db:
        assert db.execute("SELECT count(*) FROM mentor_deep_attempts").fetchone()[0] == 0


def test_atomic_single_answer_under_race(mentor):
    session = mentor.start("python-1")
    def once(_):
        try:
            return answer(mentor, session)["objective_decisions_correct"]
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(once, range(4))) == 1


def test_clear_is_scoped_and_does_not_erase_starter(mentor):
    mentor.store.submit("linux", 1)
    answer(mentor, mentor.start("python-1"))
    with pytest.raises(ValueError):
        mentor.clear("yes")
    assert mentor.clear("CLEAR DEEP MENTOR PROGRESS")["cleared"]
    assert mentor.store.progress()["passed_checkpoints"] == 1
    assert all(not row.get("attempts") for row in mentor.progress()["lessons"])


def test_registered_deep_paths_respect_stop_and_clear_confirmation(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    from jarvis.tools.builtin_tools import build_registry
    from jarvis.security import SecurityStore
    registry = build_registry(force=True)
    async def run():
        assert (await registry.execute("mentor_deep_start", {"lesson_id": "python-1"})).ok
        assert not (await registry.execute("mentor_deep_clear", {"confirmation": "CLEAR DEEP MENTOR PROGRESS"})).ok
        SecurityStore().set_stop(True)
        assert not (await registry.execute("mentor_deep_start", {"lesson_id": "python-1"})).ok
        assert (await registry.execute("mentor_deep_progress")).ok
    asyncio.run(run())
