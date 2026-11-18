"""Exact local approved-executable resolution; no shell/PATH/alias fallback."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

MAX_CONFIG_BYTES = 64_000


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate allowlist keys are refused.')
        result[key] = value
    return result


def _config_path():
    return Path(os.environ.get('AETHER_APPROVED_APPS_FILE', str(Path.home() / '.aether' / 'approved_apps.json'))).expanduser()


def _resolve(app_name, expected_executable, expected_sha256):
    if not isinstance(app_name, str) or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', app_name) is None:
        raise ValueError('Use an exact approved application ID, not a path, alias, URI or command.')
    if not isinstance(expected_sha256, str) or re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('Supply the exact expected lower-case executable SHA256.')
    if not isinstance(expected_executable, str) or not expected_executable or len(expected_executable) > 2000 or expected_executable.startswith(('\\\\', '//')):
        raise ValueError('Supply the exact non-network executable path.')
    target = Path(expected_executable)
    if not target.is_absolute() or target.suffix.lower() != '.exe' or ':' in target.name or target.resolve() != target or not target.is_file() or target.is_symlink():
        raise ValueError('Approved target must be an existing canonical absolute local .exe, not a symlink/script/URI.')
    config = _config_path()
    if not config.is_file() or config.is_symlink() or config.resolve() != config:
        raise ValueError('No canonical local approved-app allowlist is configured. No applications are approved by default.')
    with config.open('rb') as stream:
        payload = stream.read(MAX_CONFIG_BYTES + 1)
    if len(payload) > MAX_CONFIG_BYTES:
        raise ValueError('Allowlist exceeds64KB.')
    try:
        document = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('Allowlist must be valid UTF-8 JSON without duplicate keys.') from exc
    if (
        not isinstance(document, dict)
        or set(document) != {'version', 'apps'}
        or type(document['version']) is not int
        or document['version'] != 1
        or not isinstance(document['apps'], dict)
        or len(document['apps']) > 100
    ):
        raise ValueError('Expected version1 allowlist with at most100 app entries.')
    entry = document['apps'].get(app_name)
    if not isinstance(entry, dict) or set(entry) != {'executable', 'sha256'} or entry['executable'] != expected_executable or entry['sha256'] != expected_sha256:
        raise ValueError('Application ID/executable/hash does not exactly match the local approved allowlist.')
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError('Executable content changed. Review/update local approval before launching.')
    return target


def resolve_approved_app(app_name, expected_executable, expected_sha256):
    """Return the exact approved executable after local allowlist/content checks."""
    return _resolve(app_name, expected_executable, expected_sha256)


def preview_approved_app(app_name, expected_executable, expected_sha256):
    target = resolve_approved_app(app_name, expected_executable, expected_sha256)
    return {
        'success': True,
        'app_id': app_name,
        'executable': str(target),
        'sha256': expected_sha256,
        'effect': 'Start this exact allowlisted executable, with no command-line arguments or shell, after fresh confirmation. No elevation requested.',
        'limits': 'Allowlist/hash is not malware/signature verification or a sandbox. Application startup can have its own side effects/network. Local account/config and concurrent path changes must be trusted. PID/start request is not UI readiness.',
    }


def launch_approved_app(app_name, expected_executable, expected_sha256):
    target = resolve_approved_app(app_name, expected_executable, expected_sha256)
    import subprocess
    proc = subprocess.Popen([str(target)], shell=False, cwd=str(target.parent))
    return {
        'success': True,
        'app_id': app_name,
        'executable': str(target),
        'pid': proc.pid,
        'launch_requested': True,
        'application_ready_verified': False,
        'elevated_requested': False,
    }
