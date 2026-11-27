"""Tests for YouTube search and the validated playback handoff.

No network access: the fetch and opener layers are injected fixtures.
"""

from __future__ import annotations

import pytest

from aether.youtube_search import play_youtube, register_youtube_search, search_youtube

RESULTS_HTML = r"""
<html><body><script>var ytInitialData = {"contents":[
{"videoRenderer":{"videoId":"dQw4w9WgXcQ","title":{"runs":[{"text":"Never Gonna Give You Up"}]},"lengthText":{"simpleText":"3:33"}}},
{"videoRenderer":{"videoId":"abc123_-XYZ","title":{"runs":[{"text":"AWS ECS blue green &amp; deploy"}]},"ownerText":{}}},
{"videoRenderer":{"videoId":"dQw4w9WgXcQ","title":{"runs":[{"text":"Duplicate copy of the first video"}]}}},
{"playlistRenderer":{"playlistId":"PL123","title":{"simpleText":"A playlist, not a video"}}}
]}</script></body></html>
"""

EMPTY_HTML = "<html><body><script>var ytInitialData = {};</script></body></html>"


def _fixture_fetch(html_text=RESULTS_HTML):
    def fetch(url, max_bytes=None):
        assert url.startswith('https://www.youtube.com/results?search_query=')
        return html_text.encode('utf-8'), 'text/html'
    return fetch


class TestSearchYouTube:
    def test_parses_videos_and_dedupes(self):
        result = search_youtube('never gonna', fetch=_fixture_fetch())
        assert result['success'] is True
        assert [r['video_id'] for r in result['results']] == ['dQw4w9WgXcQ', 'abc123_-XYZ']
        assert result['results'][0]['url'] == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        assert result['results'][0]['title'] == 'Never Gonna Give You Up'
        # JSON-escaped characters in titles are unescaped.
        assert '&' in result['results'][1]['title']

    def test_respects_max_results(self):
        result = search_youtube('q', max_results=1, fetch=_fixture_fetch())
        assert len(result['results']) == 1

    def test_clamps_bad_max_results(self):
        result = search_youtube('q', max_results='junk', fetch=_fixture_fetch())
        assert result['success'] is True
        assert len(result['results']) == 2

    def test_empty_page_fails_honestly(self):
        result = search_youtube('q', fetch=_fixture_fetch(EMPTY_HTML))
        assert result['success'] is False
        assert 'never invented' in result['error'].lower() or 'layout' in result['error'].lower()

    def test_fetch_failure_fails_honestly(self):
        def boom(url, max_bytes=None):
            raise OSError('connection refused')
        result = search_youtube('q', fetch=boom)
        assert result['success'] is False
        assert 'connection refused' in result['error']

    @pytest.mark.parametrize('bad', ['', '   ', 'x' * 201])
    def test_rejects_bad_query(self, bad):
        result = search_youtube(bad, fetch=_fixture_fetch())
        assert result['success'] is False

    def test_results_carry_untrusted_note(self):
        result = search_youtube('q', fetch=_fixture_fetch())
        assert 'untrusted' in result['note'].lower()


class TestPlayYouTube:
    def _opener(self, opened):
        def open_url(url):
            opened.append(url)
            return True
        return open_url

    def test_bare_video_id_opens_canonical_url(self):
        opened = []
        result = play_youtube('dQw4w9WgXcQ', opener=self._opener(opened))
        assert result['success'] is True
        assert opened == ['https://www.youtube.com/watch?v=dQw4w9WgXcQ']
        assert 'not verified' in result['note']

    @pytest.mark.parametrize('video', [
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://youtu.be/dQw4w9WgXcQ',
        'https://www.youtube.com/shorts/dQw4w9WgXcQ',
        'youtube.com/watch?v=dQw4w9WgXcQ&t=10s',
    ])
    def test_accepts_youtube_url_shapes(self, video):
        opened = []
        result = play_youtube(video, opener=self._opener(opened))
        assert result['success'] is True
        assert opened == ['https://www.youtube.com/watch?v=dQw4w9WgXcQ']

    @pytest.mark.parametrize('video', [
        'https://vimeo.com/12345678901',
        'https://www.youtube.com.evil.example/watch?v=dQw4w9WgXcQ',
        'not-a-video-id',
        '',
    ])
    def test_rejects_non_youtube_and_garbage(self, video):
        opened = []
        result = play_youtube(video, opener=self._opener(opened))
        assert result['success'] is False
        assert opened == []

    def test_opener_failure_is_reported(self):
        def boom(url):
            raise OSError('no browser')
        result = play_youtube('dQw4w9WgXcQ', opener=boom)
        assert result['success'] is False
        assert 'no browser' in result['error']

    def test_laptop_style_error_dict_is_reported(self):
        opened = []
        def fail(url):
            opened.append(url)
            return {'success': False, 'error': 'browser blocked'}
        result = play_youtube('dQw4w9WgXcQ', opener=fail)
        assert result['success'] is False
        assert 'browser blocked' in result['error']


class TestRegistryIntegration:
    def test_tools_register_with_expected_risk(self):
        from aether.tools.builtin_tools import build_registry, reset_controllers
        from aether.tools.registry import Risk
        reset_controllers()
        registry = build_registry(force=True)
        search = registry.get('youtube_search')
        play = registry.get('youtube_play')
        assert search is not None and search.risk == Risk.SAFE
        assert play is not None and play.risk == Risk.LOW
        # Neither tool may ever require confirmation-free mutation.
        assert not search.confirm_required
        assert not play.confirm_required

    def test_search_handler_runs_through_registry(self):
        import asyncio
        from unittest.mock import patch
        from aether.tools.builtin_tools import build_registry, reset_controllers
        reset_controllers()
        registry = build_registry(force=True)
        with patch('aether.tools.net.web_tools._fetch', _fixture_fetch()):
            result = asyncio.run(registry.execute('youtube_search', {'query': 'ecs deploy'}))
        assert result.ok
        assert 'dQw4w9WgXcQ' in str(result.data)
