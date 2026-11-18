"""Opt-in native OS credential storage. No plaintext/chained backend fallback.

No secret-valued tools, HTTP routes or printing. This does not encrypt existing
.env files, backups, provider SDK memory, or a compromised logged-in account.
"""
from __future__ import annotations

import os

NAMES = frozenset({'GEMINI_API_KEY', 'OPENROUTER_API_KEY', 'GROQ_API_KEY', 'ELEVENLABS_API_KEY', 'AETHER_API_TOKEN', 'SECRET_KEY', 'GOOGLE_OAUTH_CLIENT_SECRET', 'WHATSAPP_ACCESS_TOKEN', 'GITHUB_ALERT_WEBHOOK_SECRET'})
BACKENDS = frozenset({('keyring.backends.Windows', 'WinVaultKeyring'), ('keyring.backends.macOS', 'Keyring'), ('keyring.backends.SecretService', 'Keyring')})
SERVICE = 'AETHER.local.credentials.v1'


def _backend():
    try:
        import keyring
        backend = keyring.get_keyring()
        if (type(backend).__module__, type(backend).__name__) not in BACKENDS:
            raise ValueError('Unsupported credential backend.')
        return backend
    except Exception:
        raise RuntimeError('AETHER native credential store unavailable or unsupported; no plaintext fallback.') from None


def secret(name: str, legacy: str = '') -> str:
    if name not in NAMES:
        raise ValueError('Credential name is not supported.')
    mode = os.environ.get('AETHER_SECRET_BACKEND', 'legacy-env')
    if mode == 'legacy-env':
        return legacy
    if mode != 'os-keyring':
        raise RuntimeError('Unknown AETHER credential mode; no fallback.')
    try:
        value = _backend().get_password(SERVICE, name)
        if value is not None and not isinstance(value, str):
            raise ValueError('Invalid credential result.')
        return value or ''
    except Exception:
        raise RuntimeError('AETHER credential read failed; no plaintext fallback.') from None


def store_secret(name: str, value: str) -> None:
    if name not in NAMES or not isinstance(value, str) or not value.strip() or len(value) > 16384 or '\x00' in value:
        raise ValueError('Supported credential name and a bounded nonempty secret required.')
    try:
        _backend().set_password(SERVICE, name, value)
    except Exception:
        raise RuntimeError('AETHER credential save failed; no plaintext fallback.') from None


def main():
    import argparse
    import getpass
    import sys
    parser = argparse.ArgumentParser(description='Save a credential in the native OS store. Never displays saved values.')
    parser.add_argument('action', choices=['put'])
    parser.add_argument('name', choices=sorted(NAMES))
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit('An owner-operated interactive terminal is required.')
    first = getpass.getpass('Credential (hidden): ')
    second = getpass.getpass('Repeat credential (hidden): ')
    if first != second:
        raise SystemExit('Values differ; nothing saved.')
    try:
        store_secret(args.name, first)
    except Exception:
        raise SystemExit('Native credential save failed; nothing printed and no plaintext fallback.') from None
    finally:
        first = second = ''  # Best effort reference release, not Python memory wiping.
    print('Credential saved in native OS storage. Existing plaintext copies were not removed.')


if __name__ == '__main__':
    main()
