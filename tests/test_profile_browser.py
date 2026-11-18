"""Tests for signed-in profile browsing and reviewed form fill. No real accounts."""
import asyncio
import socket

import pytest

from aether.profile_browser import (
    _field_kind,
    _validate_fields,
    browse_profile_page,
    browse_profile_preview,
    fill_form_preview,
    fill_reviewed_form,
    profile_login,
    profile_login_preview,
)


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_BROWSER_ENABLED', '1')
    monkeypatch.setenv('AETHER_BROWSER_HOSTS', 'example.com')
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'security.db'))
    monkeypatch.setenv('AETHER_BROWSER_OUTPUT', str(tmp_path / 'out'))
    monkeypatch.setenv('AETHER_BROWSER_PROFILE', str(tmp_path / 'profile'))
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))])
    yield


def test_previews_require_enable(monkeypatch):
    monkeypatch.delenv('AETHER_BROWSER_ENABLED')
    for fn in (profile_login_preview, browse_profile_preview):
        with pytest.raises(ValueError):
            fn('https://example.com/')
    with pytest.raises(ValueError):
        fill_form_preview('https://example.com/', [{'selector': '#a', 'value': 'x'}])


def test_previews_reject_private_or_unknown_hosts(monkeypatch):
    with pytest.raises(ValueError):
        browse_profile_preview('https://other.com/')
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.1.5', 443))])
    with pytest.raises(ValueError):
        browse_profile_preview('https://example.com/')


def test_validate_fields_bounds():
    with pytest.raises(ValueError):
        _validate_fields([])
    with pytest.raises(ValueError):
        _validate_fields([{'selector': '#a', 'value': 'x'}] * 11)
    with pytest.raises(ValueError):
        _validate_fields([{'selector': '#a', 'value': 'x'}, {'selector': '#a', 'value': 'y'}])
    with pytest.raises(ValueError):
        _validate_fields([{'selector': '#a', 'value': 'x', 'extra': 1}])
    with pytest.raises(ValueError):
        _validate_fields([{'selector': '', 'value': 'x'}])
    with pytest.raises(ValueError):
        _validate_fields([{'selector': '#a', 'value': 'x\x01'}])
    plan = _validate_fields([{'selector': '#q', 'value': 'hello', 'label': 'Search'}])
    assert plan == [{'selector': '#q', 'value': 'hello', 'label': 'Search'}]


def test_validate_fields_refuses_sensitive_selectors():
    for selector in ('#password', 'input[name="user_pass"]', '#card-number', '#one_time_code', '#cvv2'):
        with pytest.raises(ValueError):
            _validate_fields([{'selector': selector, 'value': 'x'}])
    plan = _validate_fields([{'selector': '#passport-number', 'value': 'x'}])
    assert plan[0]['selector'] == '#passport-number'  # substring inside a longer word is fine


def test_field_kind():
    assert _field_kind({'tag': 'textarea'})
    assert _field_kind({'tag': 'INPUT', 'type': None})
    assert _field_kind({'tag': 'input', 'type': 'email'})
    assert not _field_kind({'tag': 'input', 'type': 'password'})
    assert not _field_kind({'tag': 'input', 'type': 'hidden'})
    assert not _field_kind({'tag': 'input', 'type': 'checkbox'})
    assert not _field_kind({'tag': 'select'})


FORM_PAGE = '''<html><body>
<form id="f" action="/submit" method="post">
<input id="q" name="query" type="text">
<input id="pw" name="password" type="password">
<input id="card" name="card_number" type="text">
<textarea id="note" name="note"></textarea>
<input id="ro" name="ro" type="text" readonly>
<button id="go" type="submit">Go</button>
</form></body></html>'''


class _FixtureLauncher:
    """Real Chromium, but every request is fulfilled locally and headless is forced."""

    def __init__(self, page_html):
        self.page_html = page_html
        self.requests = []

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self.pw = await async_playwright().start()
        return self

    async def __aexit__(self, *_):
        await self.pw.stop()

    class _Chromium:
        def __init__(self, outer):
            self.outer = outer

        async def launch_persistent_context(self, user_data_dir, **kwargs):
            kwargs['headless'] = True
            context = await self.outer.pw.chromium.launch_persistent_context(user_data_dir, **kwargs)
            outer = self.outer

            async def fulfill(real_route):
                outer.requests.append((real_route.request.method, real_route.request.url))
                await real_route.fulfill(status=200, content_type='text/html', body=outer.page_html)
            # Registered first: guarded handlers added later by the module take
            # precedence and fall through to this fulfillment on continue_.
            await context.route('**/*', fulfill)
            return context

    @property
    def chromium(self):
        return _FixtureLauncher._Chromium(self)


@pytest.fixture
def launcher():
    return _FixtureLauncher(FORM_PAGE)


async def _instant_wait(prompt):
    return ''


def test_profile_login_owner_driven(tmp_path, launcher):
    result = asyncio.run(profile_login('https://example.com/login', wait_done=_instant_wait, launcher=launcher))
    assert result['profile_ready'] is True
    assert (tmp_path / 'profile').exists()


def test_browse_profile_page_returns_text(launcher):
    result = asyncio.run(browse_profile_page('https://example.com/form', launcher=launcher))
    assert 'Go' in result['text']
    assert result['screenshot_path'].endswith('.png')
    assert all(method == 'GET' for method, _url in launcher.requests)


def test_fill_reviewed_form_fills_safe_fields_only(launcher):
    fields = [
        {'selector': '#q', 'value': 'hello world', 'label': 'Query'},
        {'selector': '#note', 'value': 'a note'},
        {'selector': '#pw', 'value': 'should-never'},
        {'selector': '#card', 'value': '4111111111111111'},
        {'selector': '#ro', 'value': 'x'},
        {'selector': '#missing', 'value': 'x'},
    ]
    result = asyncio.run(fill_reviewed_form('https://example.com/form', fields, wait_done=_instant_wait, launcher=launcher))
    by_selector = {item['selector']: item for item in result['refused']}
    assert '#pw' in by_selector  # password type refused at fill time
    assert '#card' in by_selector  # name="card_number" matches sensitive pattern at fill time
    assert '#ro' in by_selector  # read-only refused
    assert '#missing' in by_selector  # zero matches refused
    assert [item['selector'] for item in result['filled']] == ['#q', '#note']
    assert result['submitted'] is False
    assert not any(method == 'POST' for method, _url in launcher.requests)
