"""Security/privacy overview of implemented paths, not a safety attestation."""
from __future__ import annotations

import os


def security_manager_status():
    return {
        'name': 'AETHER',
        'credential_mode': os.environ.get('AETHER_SECRET_BACKEND', 'legacy-env'),
        'local_registry_policy_selected': bool(os.environ.get('AETHER_ACCESS_POLICY')),
        'policy_notice': 'Selected does not mean validated: active policy is checked fail-closed on each registry dispatch and after confirmation. No policy means legacy risk/approval behavior, not hardened roles. Policy is local configuration, not per-user/device account RBAC.',
        'four_levels': {'READ': 'Allowlisted reads', 'SUGGEST': 'Allowlisted reads and marked suggestion tools; no execution promotion', 'EXECUTE': 'Allowlisted low-risk actions with fresh review', 'CRITICAL': 'Allowlisted higher-risk actions with fresh explicit review; no automatic approval'},
        'auth': 'Existing master/device hashed bearer tokens, revocation, one-use websocket tickets and session revalidation remain. Bearer credentials are not hardware attestation or account/tenant separation.',
        'communication': 'Android HTTPS client refuses cleartext. Private HTTPS/CA setup and real device acceptance still required; local backend/helper are not made remotely secure by this status.',
        'alerts': 'Enhanced backend exposes a master-only local audit cursor at /api/security/alerts for invalid-token attempts, registration/revocation and issued websocket sessions. No push delivery or complete login detector.',
        'scans': 'Optional owner-run ClamAV single-file scan or pip-audit exact-pinned requirement scan. Nothing auto-installed/scanned/fixed; dependency scanning discloses package names/versions after interactive approval.',
        'stop': 'Existing registry emergency stop blocks not-yet-started writes; it is not an OS kill switch, rollback, provider cancellation or block on every backend write route.',
        'privacy': 'Existing memory review/correction/expiry/purge controls remain. Expiry excludes future context only; prior sends, histories, exports/backups and document indexes are separate.',
        'notice': 'A source capability inventory, not verified device configuration, malware-free status, encryption-at-rest guarantee, tamper-proof auditing, production hardening or permission to act.'}


def register_security_manager(registry):
    from jarvis.tools.registry import Risk, Tool
    registry.register(Tool(name='security_manager_status', description='Read AETHER security/privacy capability inventory and limits. No credential values, scan, setting change, or safety guarantee.', parameters={'type': 'object', 'properties': {}, 'additionalProperties': False}, handler=security_manager_status, risk=Risk.SAFE, category='security'))
