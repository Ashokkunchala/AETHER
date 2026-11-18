"""Mock every input backend: these tests never press real media keys."""
from types import SimpleNamespace

import pytest

from aether.control import input_ctl


@pytest.fixture
def pressed(monkeypatch):
    values = []
    monkeypatch.setattr(input_ctl, '_HAS_KEYBOARD', True)
    monkeypatch.setattr(input_ctl, '_HAS_PYAUTOGUI', True)
    monkeypatch.setattr(input_ctl, '_keyboard', SimpleNamespace(press_and_release=lambda key: values.append(('keyboard', key))))
    monkeypatch.setattr(input_ctl, 'pyautogui', SimpleNamespace(press=lambda key: values.append(('pyautogui', key))))
    return values


@pytest.mark.parametrize('key', ['play', 'pause', ' PLAY ', 'Pause'])
def test_absolute_state_never_falls_back_to_toggle(key, pressed):
    result = input_ctl.press_media(key)
    assert result['success'] is False
    assert result['playback_verified'] is False
    assert 'no key was sent' in result['error']
    assert pressed == []


@pytest.mark.parametrize(('key', 'expected'), [
    ('play_pause', 'playpause'), ('next', 'nexttrack'), ('previous', 'prevtrack'),
    ('prev', 'prevtrack'), ('volume_up', 'volumeup'), ('volume_down', 'volumedown'),
    ('mute', 'volumemute'),
])
def test_explicit_key_retains_mapping_but_never_claims_playback(key, expected, pressed):
    result = input_ctl.press_media(key)
    assert result['success'] and result['key'] == expected
    assert pressed == [('keyboard', expected)]
    assert result['playback_verified'] is False
    assert 'not app-specific' in result['scope']
    assert 'not verified' in result['message']


def test_pyautogui_fallback_has_same_truthful_result(pressed, monkeypatch):
    monkeypatch.setattr(input_ctl, '_HAS_KEYBOARD', False)
    result = input_ctl.press_media('play_pause')
    assert result['success'] and result['playback_verified'] is False
    assert pressed == [('pyautogui', 'playpause')]


def test_missing_and_failing_backends_never_report_success(pressed, monkeypatch):
    monkeypatch.setattr(input_ctl, '_keyboard', SimpleNamespace(press_and_release=lambda _: (_ for _ in ()).throw(OSError('injected failure'))))
    assert input_ctl.press_media('next')['success'] is False
    assert pressed == []
    monkeypatch.setattr(input_ctl, '_HAS_KEYBOARD', False)
    monkeypatch.setattr(input_ctl, '_HAS_PYAUTOGUI', False)
    assert input_ctl.press_media('next')['success'] is False
    assert pressed == []


@pytest.mark.parametrize('key', [None, 123, 'unknown-media-key'])
def test_bad_key_cannot_reach_a_backend(key, pressed):
    assert input_ctl.press_media(key)['success'] is False
    assert pressed == []
