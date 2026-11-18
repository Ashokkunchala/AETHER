"""Passive setup inventory. No device/provider probe, imports of optional SDKs,
secret-store lookup, DB initialization, directory creation or automatic repair.
Presence/configuration is not a working connection or runtime test.
"""
from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import re
import sys


PACKAGES = {
    'local_api': ('fastapi', 'uvicorn'),
    'provider_chat': ('google-genai',),
    'public_browser': ('playwright',),
    'local_documents': ('pypdf', 'python-docx'),
    'native_secret_store': ('keyring',),
    'microphone_packages': ('sounddevice', 'numpy'),
}


def _packages():
    result = {}
    for capability, names in PACKAGES.items():
        found = []
        missing = []
        for name in names:
            try:
                # Metadata only, never import/initialize the package or its SDK.
                importlib.metadata.version(name)
                found.append(name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(name)
            except Exception:
                missing.append(name)
        result[capability] = {'metadata_present': found, 'missing_or_unreadable': missing, 'runtime_tested': False}
    return result


def _file_scope():
    value = os.environ.get('AETHER_FILE_ROOTS', '')
    if not value:
        return {'state': 'off', 'configured_count': 0, 'folders_examined': False}
    try:
        roots = json.loads(value) if len(value) <= 16384 else None
        valid = isinstance(roots, list) and 1 <= len(roots) <= 10 and all(isinstance(r, str) and 0 < len(r) <= 1024 and not any(ord(c) < 32 for c in r) for r in roots)
        return {'state': 'configuration_present' if valid else 'invalid_configuration', 'configured_count': len(roots) if valid else 0, 'folders_examined': False}
    except (ValueError, TypeError, RecursionError):
        return {'state': 'invalid_configuration', 'configured_count': 0, 'folders_examined': False}


def _browser_scope():
    enabled = os.environ.get('AETHER_BROWSER_ENABLED', '') == '1'
    raw = os.environ.get('AETHER_BROWSER_HOSTS', '')
    hosts = [h.strip().lower() for h in raw.split(',')] if len(raw) <= 8192 else []
    valid = bool(1 <= len(hosts) <= 20 and all(re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', h) for h in hosts))
    return {'state': 'off' if not enabled else 'configuration_present' if valid else 'invalid_or_missing_hosts', 'configured_host_count': len(set(hosts)) if valid else 0, 'dns_checked': False, 'browser_binary_checked': False, 'runtime_tested': False}


def report():
    python_ok = sys.version_info >= (3, 11)
    packages = _packages()
    missing_base = packages['local_api']['missing_or_unreadable'] + packages['provider_chat']['missing_or_unreadable']
    return {
        'name': 'AETHER passive setup preflight',
        'schema_version': 1,
        'python_supported': python_ok,
        'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        'os_family': platform.system(),
        'base_metadata_present': not missing_base,
        'packages': packages,
        'provider_key_environment_present': bool(os.environ.get('GEMINI_API_KEY', '').strip()),
        'provider_key_notice': 'Environment presence only. No .env file or native secret store read, no credential validation or provider request.',
        'browser': _browser_scope(),
        'file_discovery': _file_scope(),
        'security_configuration': {
            'owner_policy_path_present': bool(os.environ.get('AETHER_ACCESS_POLICY', '')),
            'typed_live_opt_in_present': os.environ.get('AETHER_ENABLE_TYPED_LIVE', '') == '1',
            'notice': 'Configuration presence only. Policy/stop databases, permissions, targets and live clients not inspected. An enabled variable is not authorization.',
        },
        'not_tested': ['microphone/speaker/voice', 'Android installation/permissions', 'Windows hardware/UI', 'private HTTPS and pairing', 'model access/quota/cost', 'browser binary/website compatibility', 'folder access/content', 'emergency stop/policy validity', 'cloud targets'],
        'notice': 'Passive inventory, not a health/security certification or permission to act. Nothing installed/repaired, no application files/databases intentionally created (use Python -B to avoid bytecode cache writes), device/audio/ADB/provider/network probes not run. Package metadata can be stale. Run only the next exact owner-reviewed setup/test steps from the guides.',
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Passive AETHER setup inventory, no device/provider probes')
    parser.add_argument('--strict-base', action='store_true', help='Exit1 if Python floor or base package metadata is missing; not a readiness verdict.')
    args = parser.parse_args()
    result = report()
    print(json.dumps(result, indent=2))
    if args.strict_base and (not result['python_supported'] or not result['base_metadata_present']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
