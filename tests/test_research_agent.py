import asyncio

import pytest

from aether.draft_workspace import DraftStore
from aether.site_watch import SiteWatchStore
from aether.youtube_summary import _video_id, summarize_youtube


@pytest.fixture
def watch(tmp_path):
    return SiteWatchStore(tmp_path / 'watch.db')


def fake_fetch_factory(pages):
    def fetch(url):
        return pages[url], 'text/html'
    return fetch


def test_watch_add_validation(watch):
    with pytest.raises(ValueError):
        watch.add('http://localhost/admin')
    with pytest.raises(ValueError):
        watch.add('https://example.com', interval_seconds=60)
    with pytest.raises(ValueError):
        watch.add('https://example.com', enabled='yes')
    out = watch.add('https://example.com', label='Example', enabled=True)
    assert out['interval_seconds'] == 3600 and out['enabled'] is True
    assert 'cue to look' in out['notice']


def test_watch_baseline_unchanged_changed(watch):
    watch.add('https://example.com', enabled=True)
    pages = {'https://example.com': b'<html>one</html>'}
    fetch = fake_fetch_factory(pages)
    first = watch.check(now=1000.0, fetch=fetch)
    assert first[0]['outcome'] == 'baseline'
    # Inside the interval: skipped entirely.
    assert watch.check(now=1001.0, fetch=fetch) == []
    second = watch.check(now=5000.0, fetch=fetch)
    assert second[0]['outcome'] == 'unchanged'
    pages['https://example.com'] = b'<html>two</html>'
    third = watch.check(now=9000.0, fetch=fetch)
    assert third[0]['outcome'] == 'changed' and 'ads and timestamps' in third[0]['note']


def test_watch_error_recorded_once_and_enable_flow(watch):
    watch.add('https://example.com', enabled=False)
    def boom(url):
        raise OSError('no route')
    assert watch.check(fetch=boom) == []  # disabled watches are not checked
    watch_id = watch.list()[0]['id']
    watch.set_enabled(watch_id, True)
    out = watch.check(now=1000.0, fetch=boom)
    assert out[0]['outcome'] == 'error'
    events = watch.events(watch_id)
    assert len(events) == 1 and events[0]['outcome'] == 'error'
    watch.remove(watch_id)
    assert watch.list() == [] and watch.events() == []


def test_video_id_extraction():
    assert _video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    assert _video_id('https://youtu.be/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    assert _video_id('https://www.youtube.com/shorts/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    with pytest.raises(ValueError):
        _video_id('https://vimeo.com/12345')
    with pytest.raises(ValueError):
        _video_id('https://www.youtube.com/watch?v=short')


PAGE = b'<html>"captionTracks":[{"baseUrl":"https://www.youtube.com/api/timedtext?v=dQw4w9WgXcQ"}]</html>'
TRANSCRIPT = (b'<transcript><text start="0">Dogs are great pets.</text>'
              b'<text start="2">They need daily walks and training.</text>'
              b'<text start="5">A good routine keeps them healthy.</text></transcript>')


def test_youtube_summary_from_captions():
    fetch = fake_fetch_factory({
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ': PAGE,
        'https://www.youtube.com/api/timedtext?v=dQw4w9WgXcQ': TRANSCRIPT,
    })
    out = summarize_youtube('https://youtu.be/dQw4w9WgXcQ', fetch=fetch)
    assert out['video_id'] == 'dQw4w9WgXcQ'
    excerpts = out['summary']['excerpts']
    assert excerpts and 'pets' in excerpts[0]['text']
    assert 'not new claims' in out['notice']


def test_youtube_summary_no_captions_is_honest():
    fetch = fake_fetch_factory({'https://www.youtube.com/watch?v=dQw4w9WgXcQ': b'<html>no captions here</html>'})
    with pytest.raises(ValueError, match='no caption track'):
        summarize_youtube('https://www.youtube.com/watch?v=dQw4w9WgXcQ', fetch=fetch)


@pytest.fixture
def drafts(tmp_path):
    return DraftStore(tmp_path / 'drafts.db')


def test_draft_lifecycle(drafts):
    with pytest.raises(ValueError):
        drafts.create('tweet', 't', 'b')
    with pytest.raises(ValueError):
        drafts.create('linkedin_post', '', 'b')
    out = drafts.create('linkedin_post', 'Launch post', 'Draft body one.')
    assert out['status'] == 'draft' and 'never' in out['notice'] or 'Nothing is sent' in out['notice']
    draft_id = out['id']
    assert drafts.get(draft_id)['body'] == 'Draft body one.'
    drafts.update(draft_id, 'Draft body two.')
    assert drafts.get(draft_id)['body'] == 'Draft body two.'
    marked = drafts.mark_reviewed(draft_id)
    assert marked['status'] == 'reviewed' and 'not an approval' in marked['notice']
    with pytest.raises(ValueError):
        drafts.update(draft_id, 'too late')
    assert drafts.list('reviewed')[0]['id'] == draft_id
    drafts.delete(draft_id)
    assert drafts.list() == []


def test_draft_bound(drafts):
    for i in range(100):
        drafts.create('other', f't{i}', 'b')
    with pytest.raises(ValueError):
        drafts.create('other', 'one more', 'b')


def test_tools_registered_and_executable(tmp_path, monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SITEWATCH_DB', str(tmp_path / 'watch.db'))
    monkeypatch.setenv('AETHER_DRAFTS_DB', str(tmp_path / 'drafts.db'))
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'security.db'))
    registry = build_registry(force=True)
    assert len(registry.names('research')) == 14  # 13 site-watch/draft tools + youtube_search
    assert asyncio.run(registry.execute('site_watch_add', {'url': 'https://example.com'})).ok
    assert asyncio.run(registry.execute('site_watch_list')).data['data'][0]['enabled'] == 0
    assert asyncio.run(registry.execute('draft_create', {'kind': 'report', 'title': 'T', 'body': 'B'})).ok
    assert len(asyncio.run(registry.execute('draft_list')).data['data']) == 1
    SecurityStore().set_stop(True)
    assert not asyncio.run(registry.execute('site_watch_add', {'url': 'https://example.org'})).ok
    assert asyncio.run(registry.execute('site_watch_events')).ok
