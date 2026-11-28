"""Regression tests for ability wiring found by end-to-end verification.

These execute tools through the real registry path (the same one brain.py
uses), not just registration checks, so a handler that cannot run with its
declared schema fails here.
"""
from __future__ import annotations

import asyncio
import webbrowser
from datetime import date


def _registry():
    from aether.tools.builtin_tools import build_registry, reset_controllers
    reset_controllers()
    return build_registry(force=True)


def _run(registry, name, args):
    async def approve(tool, a):
        return True
    return asyncio.run(registry.execute(name, args, confirm=approve))


class TestOpenWebsite:
    def test_opens_url_visibly_through_registry(self, monkeypatch):
        opened = []
        monkeypatch.setattr(webbrowser, "open", lambda url, new=0: opened.append(url) or True)
        result = _run(_registry(), "open_website", {"url": "youtube.com"})
        assert result.ok
        assert opened == ["https://youtube.com"]
        assert "youtube.com" in str(result.data)

    def test_browser_refusal_is_honest(self, monkeypatch):
        monkeypatch.setattr(webbrowser, "open", lambda url, new=0: False)
        result = _run(_registry(), "open_website", {"url": "example.com"})
        assert not result.ok
        assert "browser" in str(result.error).lower()

    def test_rejects_empty_url(self):
        result = _run(_registry(), "open_website", {"url": "  "})
        assert not result.ok


class TestYoutubePlayWiring:
    def test_plays_canonical_watch_url_through_registry(self, monkeypatch):
        opened = []
        monkeypatch.setattr(webbrowser, "open", lambda url, new=0: opened.append(url) or True)
        result = _run(_registry(), "youtube_play", {"video": "dQw4w9WgXcQ"})
        assert result.ok
        assert opened == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]

    def test_rejects_non_youtube_url(self):
        result = _run(_registry(), "youtube_play", {"video": "https://example.com/not-a-video"})
        assert not result.ok


class TestBriefingJobFollowups:
    def test_briefing_includes_due_job_followups(self, monkeypatch, tmp_path):
        db = tmp_path / "jobs.db"
        monkeypatch.setenv("AETHER_JOBS_DB", str(db))
        from aether.job_tracker import JobTracker
        JobTracker().add(role="DevOps Engineer", company="Example Corp", status="applied",
                         follow_up_day=date.today().isoformat())

        registry = _registry()
        briefing_tool = registry.get("daily_briefing")
        result = briefing_tool.handler()
        assert result["success"] is True
        assert "job_followups_due" in result
        assert result["job_followups_due"][0]["company"] == "Example Corp"
        assert "follow-up" in result["summary"]

    def test_briefing_omits_section_without_tracker_db(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AETHER_JOBS_DB", str(tmp_path / "missing.db"))
        result = _registry().get("daily_briefing").handler()
        assert result["success"] is True
        assert "job_followups_due" not in result
