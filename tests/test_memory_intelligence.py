import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.usefixtures("manual_scheduler")

TOKEN = "test-token-that-is-at-least-32-characters"


def setup_client(monkeypatch, tmp_path):
    monkeypatch.setenv("AETHER_API_TOKEN", TOKEN)
    monkeypatch.setenv("AETHER_DB_PATH", str(tmp_path / "aether.sqlite3"))
    return TestClient(app), {"Authorization": "Bearer " + TOKEN}


def save(client, headers, text, category="general"):
    response = client.post("/api/memories", headers=headers, json={"text": text, "category": category})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_memory_categories_vocabulary():
    from aether.memory.intelligence import MEMORY_CATEGORIES, memory_categories
    result = memory_categories()
    names = {item["name"] for item in result["categories"]}
    for expected in ["personal", "conversational", "projects", "technical", "learning", "tasks", "work", "context"]:
        assert expected in names
    assert MEMORY_CATEGORIES["work"].startswith("Resume")


def test_secret_shaped_memory_save_is_refused(monkeypatch, tmp_path):
    client, headers = setup_client(monkeypatch, tmp_path)
    with client:
        for text in [
            "my password is hunter2",
            "token: ghp_" + "a" * 30,
            "api key = sk-" + "b" * 30,
            "-----BEGIN PRIVATE KEY-----",
        ]:
            refused = client.post("/api/memories", headers=headers, json={"text": text})
            assert refused.status_code == 422, text
            assert "vault" in refused.json()["detail"]
        assert client.get("/api/memories", headers=headers).json()["items"] == []
        ok = client.post("/api/memories", headers=headers, json={"text": "Prefers Telugu replies", "category": "personal"})
        assert ok.status_code == 201
        memory_id = ok.json()["id"]
        refused_put = client.put(f"/api/memories/{memory_id}", headers=headers, json={"text": "password: secret1"})
        assert refused_put.status_code == 422
        assert client.get("/api/memories", headers=headers).json()["items"][0]["text"] == "Prefers Telugu replies"


def test_sensitive_scan_flags_ids_without_echoing_values(monkeypatch, tmp_path):
    client, headers = setup_client(monkeypatch, tmp_path)
    with client:
        save(client, headers, "Prefers Telugu replies", "personal")
        # Insert a secret-shaped row directly (the API refuses it) to simulate legacy data.
        from app.personal_data import _connect, _now
        with _connect() as db:
            cur = db.execute("INSERT INTO memories(text,category,created_at) VALUES(?,?,?)",
                             ("backup key ghp_" + "c" * 30, "technical", _now()))
            legacy_id = cur.lastrowid
        from aether.memory.intelligence import scan_memories_for_secrets
        result = scan_memories_for_secrets()
        assert result["records_scanned"] == 2
        assert result["flagged"] == [{"memory_id": legacy_id, "reasons": ["github personal access token"]}]
        assert "ghp_" not in str(result)


def test_digest_is_extractive_counts_and_terms(monkeypatch, tmp_path):
    client, headers = setup_client(monkeypatch, tmp_path)
    with client:
        save(client, headers, "AETHER repo uses FastAPI and SQLite", "projects")
        save(client, headers, "AETHER android uses Kotlin", "projects")
        save(client, headers, "Completed Python decorators", "learning")
        from aether.memory.intelligence import summarize_memories
        result = summarize_memories()
        digests = {item["category"]: item for item in result["digests"]}
        assert digests["projects"]["record_count"] == 2
        assert "aether" in digests["projects"]["frequent_terms"]
        assert digests["learning"]["record_count"] == 1
        assert "not an LLM" in result["notice"]
        only = summarize_memories("projects")
        assert {item["category"] for item in only["digests"]} == {"projects"}


def test_conflict_candidates_are_same_subject_different_claim(monkeypatch, tmp_path):
    client, headers = setup_client(monkeypatch, tmp_path)
    with client:
        first = save(client, headers, "Favorite editor is VS Code", "personal")
        second = save(client, headers, "Favorite editor is Neovim", "personal")
        save(client, headers, "Favorite editor is Neovim", "technical")  # different category: not grouped
        save(client, headers, "Unrelated fact about weather", "personal")
        from aether.memory.intelligence import conflict_candidates
        result = conflict_candidates()
        groups = result["candidate_groups"]
        assert len(groups) == 1
        assert groups[0]["category"] == "personal"
        assert set(groups[0]["memory_ids"]) == {first, second}
        assert "not contradiction" in result["notice"]


def test_semantic_search_honest_when_local_stack_missing(monkeypatch, tmp_path):
    client, headers = setup_client(monkeypatch, tmp_path)
    with client:
        save(client, headers, "Prefers concise answers", "personal")
        import aether.memory.intelligence as mod
        monkeypatch.setattr(mod, "_semantic_collection", lambda: (None, None, None))
        result = mod.semantic_search_memories("concise replies")
        assert result["available"] is False and result["results"] == []
        assert "never a network" in result["notice"] or "no fallback remote embedding" in result["notice"]
        with pytest.raises(ValueError):
            mod.semantic_search_memories("   ")
        with pytest.raises(ValueError):
            mod.semantic_search_memories("ok", limit=0)


def test_registry_wires_memory_intelligence_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    from aether.tools.builtin_tools import build_registry
    registry = build_registry(force=True)
    for name in ["memory_categories", "memory_digest", "memory_review_conflict_candidates", "memory_scan_sensitive", "memory_semantic_search"]:
        tool = registry.get(name)
        assert tool.category == "memory"
        assert tool.confirm_required is False
