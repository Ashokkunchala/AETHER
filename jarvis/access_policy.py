"""Owner-configured local registry policy. Never selected by model arguments.

Not a user/tenant identity system or an OS sandbox. Off until installed locally.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


class Permission(IntEnum):
    READ = 1
    SUGGEST = 2
    EXECUTE = 3
    CRITICAL = 4


# No arbitrary shell/process or policy/secret administration inside hardened mode.
DENIED = frozenset({'run_command', 'shell', 'shell_run', 'start_process', 'process_start', 'execute_command', 'run_shell'})

CRITICAL_NAMES = frozenset({'delete_file', 'android_delete_file', 'android_send_sms', 'android_share_text', 'android_call'})
DENIED_CATEGORIES = frozenset({'input', 'android_input', 'apps', 'android_apps'})


@dataclass(frozen=True)
class AccessDecision:
    confirm: bool
    fingerprint: str


def check_policy(tool, args) -> AccessDecision | None:
    """Load on EVERY call and after review. Missing/malformed active policy blocks.

    File contents are trusted local configuration, not a proposed model payload.
    Every tool must be named; risk/confirmation metadata can only strengthen it.
    """
    location = os.environ.get('AETHER_ACCESS_POLICY', '')
    if not location:
        return None  # Explicit compatibility mode, not claimed as hardened RBAC.
    path = Path(location)
    if not path.is_absolute() or path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError('Invalid owner policy file.')
    raw = path.read_bytes()
    if len(raw) > 65536:
        raise ValueError('Owner policy too large.')
    data = json.loads(raw)
    if set(data) != {'version', 'level', 'tools'} or data['version'] != 1 or type(data['version']) is not int:
        raise ValueError('Invalid owner policy schema.')
    maximum = Permission[data['level']]
    if not isinstance(data['tools'], dict) or len(data['tools']) > 300:
        raise ValueError('Invalid exact tool allowlist.')
    entry = data['tools'].get(tool.name)
    if tool.name in DENIED or tool.category in DENIED_CATEGORIES or not isinstance(entry, dict) or set(entry) - {'level', 'paths'} or 'level' not in entry:
        raise ValueError('Tool is not owner-allowlisted.')
    requested = Permission[entry['level']]
    intrinsic = Permission.READ if int(tool.risk) == 0 else Permission.EXECUTE if int(tool.risk) == 1 else Permission.CRITICAL
    required = max(requested, intrinsic, Permission.CRITICAL if tool.name in CRITICAL_NAMES else Permission.READ)
    if required > maximum:
        raise ValueError('Permission level does not allow this tool.')
    # Never weaken existing confirmations, regardless of the named role.
    confirm = required >= Permission.EXECUTE or tool.confirm_required
    paths = entry.get('paths', {})
    if not isinstance(paths, dict):
        raise ValueError('Invalid file argument restrictions.')
    for field, roots in paths.items():
        if not isinstance(roots, list) or not roots or any(not isinstance(r, str) or not Path(r).is_absolute() for r in roots):
            raise ValueError('Explicit absolute roots required.')
        value = args.get(field)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('Restricted file argument requires an exact absolute path.')
        target = Path(value).resolve(strict=True)
        if not any(target.is_relative_to(Path(root).resolve(strict=True)) for root in roots):
            raise ValueError('File path is outside owner-approved roots.')
        # Reject links in the lexical path as well as escaping resolutions.
        lexical = Path(value)
        if any(p.is_symlink() for p in [lexical, *lexical.parents]):
            raise ValueError('Symbolic links are not allowed in restricted file arguments.')
    # File handlers without exact argument coverage stay disabled in this mode.
    if tool.category in ('files', 'filesystem', 'file') and (not paths or set(args) - set(paths)):
        raise ValueError('File tool lacks complete exact-path argument coverage.')
    import hashlib
    return AccessDecision(confirm, hashlib.sha256(raw).hexdigest())
