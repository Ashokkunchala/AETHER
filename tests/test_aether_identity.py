"""Naming changes must not rename compatibility paths or invent a wake model."""
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aether_cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_cli_name_preserves_command_but_displays_aether():
    result = CliRunner().invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'AETHER Personal AI' in result.output
    assert app.info.name == 'aether'


@pytest.mark.parametrize('name', [
    'android/app/src/main/java/com/ashok/aether/MainActivity.kt',
    'android/app/src/main/java/com/ashok/aether/LiveVoiceController.kt',
    'android/app/src/main/java/com/ashok/aether/ReminderWorker.kt',
    'windows_agent/agent.py', 'windows_agent/reminder_notifier.py',
])
def test_active_native_display_names(name):
    source = (ROOT / name).read_text()
    assert re.search(r'\bAETHER\b', source)
    assert 'com.ashok.aether' in source if name.endswith('.kt') else True


def test_android_modes_and_live_parameters_keep_existing_storage_and_auth():
    activity = (ROOT / 'android/app/src/main/java/com/ashok/aether/MainActivity.kt').read_text()
    live = (ROOT / 'android/app/src/main/java/com/ashok/aether/LiveVoiceController.kt').read_text()
    for mode in ('friendly', 'funny', 'professional', 'calm', 'motivational'):
        assert f'"{mode}" to ' in activity
    assert '"aether_reminder_settings"' in activity
    assert 'liveVoiceController.start(base, activeToken, personalityMode, language)' in activity
    assert '&mode=' in live and '&language=' in live
    assert 'URLEncoder.encode(mode.take(40)' in live
    assert 'URLEncoder.encode(language.take(8)' in live
    assert '"Authorization", "Bearer $token"' in live
    assert 'ticket=' in live


def test_local_voice_reuses_persisted_style_but_explicit_persona_wins(tmp_path, monkeypatch):
    # Constructor-only test: no numerical/audio operation is used.
    import importlib.util
    import sys
    from types import ModuleType

    if importlib.util.find_spec("numpy") is None:
        monkeypatch.setitem(sys.modules, "numpy", ModuleType("numpy"))
    from aether import personality_modes
    from aether.core.voice.gemini_live_client import DEFAULT_PERSONA, GeminiLiveClient

    store = personality_modes.ModeStore(tmp_path / 'style.json')
    store.set('calm')
    monkeypatch.setattr(personality_modes, '_default_store', store)
    client = GeminiLiveClient('synthetic-not-a-provider-key')
    assert 'You are AETHER' in DEFAULT_PERSONA
    assert 'Mode: CALM' in client.system_instruction
    assert 'do not encourage dependence' in client.system_instruction
    explicit = GeminiLiveClient('synthetic-not-a-provider-key', system_instruction='Explicit caller persona')
    assert explicit.system_instruction == 'Explicit caller persona'
    assert client.connected is False and client._client is None


def test_local_neural_wake_model_not_falsely_renamed():
    source = (ROOT / 'aether/core/wakeword/wakeword_detector.py').read_text()
    assert 'model_name="aether"' in source
    readme = (ROOT / 'README.md').read_text()
    assert 'No custom AETHER neural model is bundled' in readme
    assert 'not "Hey AETHER"' in readme
