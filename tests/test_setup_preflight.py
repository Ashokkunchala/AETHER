from __future__ import annotations

import builtins
import importlib.metadata
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis import setup_preflight as preflight


def test_inventory_no_network_subprocess_sdk_import_or_writes(monkeypatch):
    def denied(*a, **k):
        raise AssertionError('Side effect forbidden')
    monkeypatch.setattr(socket, 'socket', denied)
    monkeypatch.setattr(subprocess, 'run', denied)
    monkeypatch.setattr(subprocess, 'Popen', denied)
    monkeypatch.setattr(Path, 'mkdir', denied)
    monkeypatch.setattr(Path, 'write_text', denied)
    monkeypatch.setattr(Path, 'write_bytes', denied)
    monkeypatch.setattr(importlib.metadata, 'version', lambda name: 'test-metadata')
    original = builtins.__import__
    def guarded(name, *a, **k):
        assert not name.startswith(('google', 'playwright', 'keyring', 'sounddevice', 'jarvis.security', 'jarvis.config'))
        return original(name, *a, **k)
    monkeypatch.setattr(builtins, '__import__', guarded)
    result = preflight.report()
    assert result['base_metadata_present']
    assert not result['browser']['runtime_tested']
    assert result['not_tested']


def test_secret_paths_and_hosts_not_printed(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'PRIVATE-GEMINI-KEY')
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'PRIVATE-VOICE-KEY')
    monkeypatch.setenv('AETHER_ACCESS_POLICY', '/private/user/policy.json')
    monkeypatch.setenv('AETHER_FILE_ROOTS', '["/private/user/documents"]')
    monkeypatch.setenv('AETHER_BROWSER_HOSTS', 'private-example.com')
    monkeypatch.setenv('AETHER_BROWSER_ENABLED', '1')
    result = preflight.report()
    rendered = json.dumps(result)
    for private in ['PRIVATE-GEMINI-KEY', 'PRIVATE-VOICE-KEY', '/private/user', 'private-example.com']:
        assert private not in rendered
    assert result['provider_key_environment_present']
    assert result['browser']['configured_host_count'] == 1
    assert result['file_discovery']['configured_count'] == 1
    assert not result['file_discovery']['folders_examined']


def test_broken_metadata_never_prints_exception(monkeypatch):
    def fail(name):
        raise RuntimeError('SECRET exception from import metadata')
    monkeypatch.setattr(importlib.metadata, 'version', fail)
    rendered = json.dumps(preflight.report())
    assert 'SECRET' not in rendered
    assert not preflight.report()['base_metadata_present']


@pytest.mark.parametrize('value', ['not json', '{}', '[]', '[1]', '["x\\nsecret"]', '["' + 'x' * 1025 + '"]'])
def test_bad_file_configuration(monkeypatch, value):
    monkeypatch.setenv('AETHER_FILE_ROOTS', value)
    result = preflight._file_scope()
    assert result['state'] == 'invalid_configuration'
    assert not result['folders_examined']


@pytest.mark.parametrize('value', ['', '*.example.com', 'https://example.com', '127.0.0.1', 'u:p@example.com', 'example.com\nsecret'])
def test_bad_host_configuration(monkeypatch, value):
    monkeypatch.setenv('AETHER_BROWSER_ENABLED', '1')
    monkeypatch.setenv('AETHER_BROWSER_HOSTS', value)
    assert preflight._browser_scope()['state'] == 'invalid_or_missing_hosts'


def test_off_defaults_and_no_dotenv_read(monkeypatch):
    for name in ['GEMINI_API_KEY', 'AETHER_FILE_ROOTS', 'AETHER_BROWSER_ENABLED', 'AETHER_ACCESS_POLICY', 'AETHER_ENABLE_TYPED_LIVE']:
        monkeypatch.delenv(name, raising=False)
    result = preflight.report()
    assert result['browser']['state'] == result['file_discovery']['state'] == 'off'
    assert not result['provider_key_environment_present']
    assert not result['security_configuration']['typed_live_opt_in_present']


def test_cli_strict_base_exit_is_metadata_only(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['preflight', '--strict-base'])
    monkeypatch.setattr(preflight, '_packages', lambda: {name: {'missing_or_unreadable': list(names), 'metadata_present': [], 'runtime_tested': False} for name, names in preflight.PACKAGES.items()})
    with pytest.raises(SystemExit) as error:
        preflight.main()
    assert error.value.code == 1
    assert 'not a health/security certification' in capsys.readouterr().out
