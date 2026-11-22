import sqlite3
from datetime import date, timedelta

import pytest

from aether.mentor import LESSONS, MentorStore
from aether.mentor_certs import CERTS, cert_plan, list_cert_plans


def test_cert_templates_reference_only_existing_lessons():
    plans = list_cert_plans()
    assert len(plans) == len(CERTS) == 6
    for plan in plans:
        assert plan["lessons"], plan["cert_id"]
        for lesson in plan["lessons"]:
            assert lesson["lesson_id"] in LESSONS
            assert lesson["title"] == LESSONS[lesson["lesson_id"]]["title"]
        assert plan["session_count"] == len(plan["lessons"])


def test_cert_plan_preview_is_dated_and_persists_nothing(tmp_path):
    store = MentorStore(tmp_path / "mentor.db")
    result = cert_plan("aws-saa", "2026-12-01", 45, store=store)
    assert result["persisted"] is False
    assert result["label"] == CERTS["aws-saa"]["label"]
    sessions = result["sessions"]
    assert len(sessions) == len(CERTS["aws-saa"]["lessons"])
    assert sessions[0]["date"] == "2026-12-01"
    assert sessions[0]["minutes"] == 45
    assert sessions[1]["date"] == (date(2026, 12, 1) + timedelta(days=1)).isoformat()
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM mentor_plan").fetchone()[0] == 0


def test_cert_plan_persist_saves_local_sessions(tmp_path):
    store = MentorStore(tmp_path / "mentor.db")
    result = cert_plan("cka", "2026-12-05", 30, persist=True, store=store)
    assert result["persisted"] is True
    assert len(result["saved_sessions"]) == len(CERTS["cka"]["lessons"])
    progress = store.progress("2026-12-05")
    assert {row["lesson_id"] for row in progress["sessions"]} == set(CERTS["cka"]["lessons"])


def test_cert_plan_rejects_bad_input(tmp_path):
    store = MentorStore(tmp_path / "mentor.db")
    with pytest.raises(ValueError, match="Unknown certification"):
        cert_plan("ccie", "2026-12-01")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        cert_plan("aws-ccp", "01/12/2026")
    with pytest.raises(ValueError, match="10 to 120"):
        cert_plan("aws-ccp", "2026-12-01", 5)
    with pytest.raises(ValueError, match="10 to 120"):
        cert_plan("aws-ccp", "2026-12-01", 121)
