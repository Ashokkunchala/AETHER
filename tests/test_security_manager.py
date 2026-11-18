import asyncio
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from aether.access_policy import check_policy
from aether.security import SecurityStore
from aether.tools.registry import Risk, Tool, ToolRegistry


@pytest.fixture
def policy(tmp_path, monkeypatch):
    path = tmp_path / 'owner.json'
    monkeypatch.setenv('AETHER_ACCESS_POLICY', str(path))
    def save(level='READ', tools=None):
        path.write_text(json.dumps({'version': 1, 'level': level, 'tools': tools or {'read': {'level': 'READ'}}}))
    save()
    return path, save


def tool(name='read', risk=Risk.SAFE, category='test'):
    return Tool(name=name, description='test', parameters={}, handler=lambda **kw: kw, risk=risk, category=category)


def test_policy_off_is_explicit_compatibility(monkeypatch):
    monkeypatch.delenv('AETHER_ACCESS_POLICY', raising=False)
    assert check_policy(tool(), {}) is None


@pytest.mark.parametrize('level,allowed', [('READ', False), ('SUGGEST', False), ('EXECUTE', True), ('CRITICAL', True)])
def test_four_levels_cannot_promote_action(policy, level, allowed):
    _, save = policy; save(level, {'change': {'level': 'READ'}})
    if allowed:
        assert check_policy(tool('change', Risk.LOW), {}).confirm
    else:
        with pytest.raises(ValueError): check_policy(tool('change', Risk.LOW), {})


def test_suggestion_is_readonly_and_explicitly_marked(policy):
    _, save = policy; save('SUGGEST', {'recommend': {'level': 'SUGGEST'}})
    assert not check_policy(tool('recommend'), {}).confirm
    save('READ', {'recommend': {'level': 'SUGGEST'}})
    with pytest.raises(ValueError): check_policy(tool('recommend'), {})


@pytest.mark.parametrize('name,risk,category', [('run_shell', Risk.SAFE, 'test'), ('start_process', Risk.HIGH, 'test'), ('mouse_click', Risk.LOW, 'input')])
def test_unbounded_execution_disabled_even_allowlisted(policy, name, risk, category):
    _, save = policy; save('CRITICAL', {name: {'level': 'CRITICAL'}})
    with pytest.raises(ValueError): check_policy(tool(name, risk, category), {})


def test_critical_name_cannot_be_downgraded(policy):
    _, save = policy; save('EXECUTE', {'android_share_text': {'level': 'READ'}})
    with pytest.raises(ValueError): check_policy(tool('android_share_text', Risk.LOW), {})


@pytest.mark.parametrize('raw', ['{}', 'null', '{"version":true,"level":"READ","tools":{}}', 'not-json'])
def test_malformed_active_policy_fails_closed(policy, raw):
    path, _ = policy; path.write_text(raw)
    with pytest.raises((ValueError, TypeError)): check_policy(tool(), {})


def test_missing_and_unknown_allowlist_fail_closed(policy):
    path, _ = policy
    with pytest.raises(ValueError): check_policy(tool('new_plugin'), {})
    path.unlink()
    with pytest.raises(FileNotFoundError): check_policy(tool(), {})


def test_exact_root_traversal_symlink_and_uncovered_file_args(policy, tmp_path):
    _, save = policy; root = tmp_path / 'docs'; root.mkdir(); child = root / 'note.txt'; child.write_text('private')
    outside = tmp_path / 'outside.txt'; outside.write_text('outside')
    save('READ', {'read_file': {'level': 'READ', 'paths': {'path': [str(root)]}}})
    t = tool('read_file', category='files')
    assert check_policy(t, {'path': str(child)})
    for args in ({'path': str(outside)}, {'path': str(root / '..' / 'outside.txt')}, {'path': 'note.txt'}, {'path': str(child), 'other': str(outside)}):
        with pytest.raises(ValueError): check_policy(t, args)
    link = root / 'link.txt'
    try: link.symlink_to(child)
    except OSError: return
    with pytest.raises(ValueError): check_policy(t, {'path': str(link)})


def registry(tmp_path):
    r = ToolRegistry(); r.security_store = SecurityStore(tmp_path / 'safety.db'); calls = []
    r.register(Tool('change', 'local change', {}, lambda: calls.append(1), Risk.LOW))
    return r, calls


def test_hardened_low_action_requires_fresh_review_even_auto_approve(policy, tmp_path):
    _, save = policy; save('EXECUTE', {'change': {'level': 'EXECUTE'}})
    r, calls = registry(tmp_path)
    assert not asyncio.run(r.execute('change', {}, auto_approve=True)).ok
    assert not calls
    async def approve(review, _args):
        assert review.confirm_required and review.never_auto_approve
        assert not review.allow_always and not review.allow_auto_approve
        return True
    assert asyncio.run(r.execute('change', {}, confirm=approve, auto_approve=True)).ok
    assert calls == [1]


def test_recheck_policy_restriction_removal_and_stop_during_review(policy, tmp_path):
    path, save = policy
    r, calls = registry(tmp_path)
    for change in ('restrict', 'remove', 'stop'):
        save('EXECUTE', {'change': {'level': 'EXECUTE'}})
        async def approve(*_):
            if change == 'restrict': save('READ')
            elif change == 'remove': os.environ.pop('AETHER_ACCESS_POLICY')
            else: r.security_store.set_stop(True)
            return True
        assert not asyncio.run(r.execute('change', {}, confirm=approve)).ok
        assert not calls
        os.environ['AETHER_ACCESS_POLICY'] = str(path)
        r.security_store.set_stop(False)


def test_model_args_cannot_set_role_or_allowlist(policy, tmp_path):
    r, calls = registry(tmp_path)
    assert not asyncio.run(r.execute('change', {'level': 'CRITICAL', 'tools': {'change': {}}})).ok
    assert not calls


def test_native_secret_has_no_plaintext_fallback(monkeypatch):
    from aether import secret_store as s
    monkeypatch.setenv('AETHER_SECRET_BACKEND', 'os-keyring')
    class Backend:
        def get_password(self, service, name): return None
    monkeypatch.setattr(s, '_backend', lambda: Backend())
    assert s.secret('GEMINI_API_KEY', 'must-not-fallback') == ''
    monkeypatch.setattr(s, '_backend', lambda: (_ for _ in ()).throw(ValueError('SECRET-DO-NOT-ECHO')))
    with pytest.raises(RuntimeError) as error: s.secret('GEMINI_API_KEY', 'legacy-secret')
    assert 'SECRET-DO-NOT-ECHO' not in str(error.value) and 'legacy-secret' not in str(error.value)


def test_plaintext_and_chained_backend_refused(monkeypatch):
    from aether.secret_store import _backend
    monkeypatch.setitem(sys.modules, 'keyring', types.SimpleNamespace(get_keyring=lambda: object()))
    with pytest.raises(RuntimeError): _backend()


def test_supported_native_backend_store_and_server_reads(monkeypatch):
    from aether import secret_store as s
    data = {}
    class Backend:
        def get_password(self, service, name): return data.get((service, name))
        def set_password(self, service, name, value): data[(service, name)] = value
    monkeypatch.setattr(s, '_backend', lambda: Backend())
    monkeypatch.setenv('AETHER_SECRET_BACKEND', 'os-keyring')
    s.store_secret('GEMINI_API_KEY', 'not-a-real-test-key')
    s.store_secret('AETHER_API_TOKEN', 'x' * 40)
    from app.core.config import Settings
    settings = Settings(_env_file=None, gemini_api_key='ignored-plaintext')
    assert settings.gemini_api_key == 'not-a-real-test-key'
    assert settings.aether_api_token == 'x' * 40
    assert 'not-a-real-test-key' not in repr(settings)
    assert settings.groq_api_key == ''


def test_brain_credentials_use_native_store(monkeypatch):
    from aether import secret_store as s
    from aether.core.brain import AETHERBrain
    monkeypatch.setenv('AETHER_SECRET_BACKEND', 'os-keyring')
    class Backend:
        def get_password(self, service, name): return 'key-from-test-native-store' if name == 'OPENROUTER_API_KEY' else None
    monkeypatch.setattr(s, '_backend', lambda: Backend())
    assert AETHERBrain._configured_key('OPENROUTER_API_KEY') == 'key-from-test-native-store'


def test_scan_plan_exact_pins_no_invocation_or_unsafe_options(tmp_path, monkeypatch):
    from aether.security_scans import scan_plan
    p = tmp_path / 'pinned.txt'; p.write_text('example-package==1.0\n# note\n')
    monkeypatch.setattr(subprocess, 'run', lambda *_a, **_k: pytest.fail('Planning must not run a scanner'))
    plan = scan_plan('dependencies', str(p), str(tmp_path))
    assert '--disable-pip' in plan['command'] and '--no-deps' in plan['command'] and not plan['executed']
    assert 'sends these package names/versions' in plan['disclosure']
    for raw in ['https://attacker.invalid/x', '-r secret.txt', '--index-url https://x.invalid', 'x>=1', 'x==1;evil', 'x @ file:///tmp/x']:
        p.write_text(raw)
        with pytest.raises(ValueError): scan_plan('dependencies', str(p), str(tmp_path))


def test_scan_scope_and_missing_clam(tmp_path, monkeypatch):
    import shutil
    from aether.security_scans import scan_plan
    child = tmp_path / 'scan.txt'; child.write_text('test')
    root = tmp_path / 'root'; root.mkdir()
    with pytest.raises(ValueError): scan_plan('malware', str(child), str(root))
    monkeypatch.setattr(shutil, 'which', lambda _: None)
    with pytest.raises(ValueError): scan_plan('malware', str(child), str(tmp_path))


@pytest.mark.parametrize('code,status', [(0, 'no_findings_reported'), (1, 'findings_reported'), (2, 'scan_error')])
def test_clam_exit_codes_not_clean_on_error(tmp_path, monkeypatch, code, status):
    import shutil
    from aether.security_scans import scan_plan, _run_reviewed
    p = tmp_path / 'test.bin'; p.write_text('data')
    monkeypatch.setattr(shutil, 'which', lambda _: '/trusted/clamscan')
    def fake(command, **kw):
        assert command == ['/trusted/clamscan', '--no-summary', '--', str(p)]
        assert kw['shell'] is False and '--remove' not in command
        return types.SimpleNamespace(returncode=code)
    monkeypatch.setattr(subprocess, 'run', fake)
    assert _run_reviewed(scan_plan('malware', str(p), str(tmp_path)))['status'] == status


def test_scan_timeout_unknown(tmp_path, monkeypatch):
    import shutil
    from aether.security_scans import scan_plan, _run_reviewed
    p = tmp_path / 'test.bin'; p.write_text('data')
    monkeypatch.setattr(shutil, 'which', lambda _: '/trusted/clamscan')
    monkeypatch.setattr(subprocess, 'run', lambda *_a, **_kw: (_ for _ in ()).throw(subprocess.TimeoutExpired('clamscan', 120)))
    assert _run_reviewed(scan_plan('malware', str(p), str(tmp_path)))['status'] == 'unknown_timeout'


def test_status_does_not_claim_hardening(monkeypatch):
    from aether.security_manager import security_manager_status
    monkeypatch.delenv('AETHER_ACCESS_POLICY', raising=False)
    result = security_manager_status()
    assert result['local_registry_policy_selected'] is False
    assert 'not verified device' in result['notice']


def test_dependency_audit_incomplete_invalid_and_valid_result(tmp_path, monkeypatch):
    from aether.security_scans import scan_plan, _run_reviewed
    p = tmp_path / 'pinned.txt'; p.write_text('example==1.0')
    for payload, expected in [({'dependencies': [{'name': 'example', 'version': '1.0', 'vulns': []}]}, 'dependency_report_review_required'), ({'dependencies': [{'name': 'example', 'skip_reason': 'unavailable'}]}, 'unknown_incomplete_audit'), ({'dependencies': []}, 'unknown_incomplete_audit'), ({'not_an_audit': []}, 'unknown_invalid_audit')]:
        def fake(_command, **kw):
            kw['stdout'].write(json.dumps(payload).encode())
            return types.SimpleNamespace(returncode=0)
        monkeypatch.setattr(subprocess, 'run', fake)
        assert _run_reviewed(scan_plan('dependencies', str(p), str(tmp_path)))['status'] == expected


def test_reviewed_scanner_input_change_blocks_execution(tmp_path, monkeypatch):
    from aether.security_scans import scan_plan, _run_reviewed
    p = tmp_path / 'pinned.txt'; p.write_text('example==1.0')
    plan = scan_plan('dependencies', str(p), str(tmp_path))
    p.write_text('other-package==2.0')
    monkeypatch.setattr(subprocess, 'run', lambda *_a, **_kw: pytest.fail('Changed input must not execute'))
    with pytest.raises(ValueError): _run_reviewed(plan)
