"""Reviewed-open tests use fake bytes and mocked Popen only; no real app/file launch."""
import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from aether.control.reviewed_open import (
    open_reviewed_path,
    plan_reviewed_open,
    preview_reviewed_open,
)
from aether.tools.builtin_tools import build_registry
from aether.tools.registry import Risk


def _write_json(path, document):
    path.write_text(json.dumps(document), encoding='utf-8')


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    root = tmp_path / 'Documents'
    root.mkdir()
    handler = tmp_path / 'handler.exe'
    handler.write_bytes(b'fake reviewed handler')
    handler_digest = hashlib.sha256(handler.read_bytes()).hexdigest()
    document = root / 'report.txt'
    document.write_bytes(b'reviewed local document')
    folder = root / 'folder'
    folder.mkdir()
    (folder / 'one.txt').write_text('one', encoding='utf-8')

    approved_config = tmp_path / 'approved_apps.json'
    _write_json(approved_config, {
        'version': 1,
        'apps': {'viewer': {'executable': str(handler), 'sha256': handler_digest}},
    })
    reviewed_config = tmp_path / 'reviewed_open.json'
    _write_json(reviewed_config, {
        'version': 1,
        'handlers': {'documents': {
            'app': 'viewer',
            'roots': [str(root)],
            'targets': ['file', 'folder'],
            'extensions': ['.txt'],
        }},
    })
    monkeypatch.setenv('AETHER_APPROVED_APPS_FILE', str(approved_config))
    monkeypatch.setenv('AETHER_REVIEWED_OPEN_FILE', str(reviewed_config))
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'security.db'))
    monkeypatch.delenv('AETHER_ACCESS_POLICY', raising=False)

    calls = []
    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=4321)
    monkeypatch.setattr('aether.control.reviewed_open.subprocess.Popen', fake_popen)
    return SimpleNamespace(
        root=root, handler=handler, handler_digest=handler_digest,
        document=document, folder=folder, approved_config=approved_config,
        reviewed_config=reviewed_config, calls=calls,
    )


def _open_args(reviewed, path=None):
    selected = path or reviewed.document
    plan = plan_reviewed_open('documents', str(selected))
    return {
        'handler_id': 'documents',
        'path': str(selected),
        'expected_kind': plan['kind'],
        'expected_digest': plan['digest'],
        'expected_handler_app': plan['handler_app'],
        'expected_handler_executable': str(reviewed.handler),
        'expected_handler_sha256': reviewed.handler_digest,
    }


def test_plan_hashes_file_without_launching(reviewed):
    plan = plan_reviewed_open('documents', str(reviewed.document))
    assert plan['success'] and plan['kind'] == 'file'
    assert plan['digest'] == hashlib.sha256(b'reviewed local document').hexdigest()
    assert plan['handler_app'] == 'viewer'
    assert reviewed.calls == []


def test_plan_fingerprints_folder_listing_without_launching(reviewed):
    plan = plan_reviewed_open('documents', str(reviewed.folder))
    assert plan['success'] and plan['kind'] == 'folder' and len(plan['digest']) == 64
    assert plan['size_bytes'] is None
    assert reviewed.calls == []


def test_open_revalidates_and_launches_exact_handler_with_one_path_arg(reviewed):
    args = _open_args(reviewed)
    assert 'No shell' in preview_reviewed_open(**args)['effect']
    result = open_reviewed_path(**args)
    assert result['success'] and result['launch_requested']
    assert reviewed.calls == [([str(reviewed.handler), str(reviewed.document)], {'shell': False, 'cwd': str(reviewed.handler.parent)})]
    assert result['application_ready_verified'] is False and result['default_association_used'] is False


def test_no_default_reviewed_open_config(reviewed, monkeypatch, tmp_path):
    monkeypatch.setenv('AETHER_REVIEWED_OPEN_FILE', str(tmp_path / 'missing.json'))
    with pytest.raises(ValueError, match='No canonical'):
        plan_reviewed_open('documents', str(reviewed.document))
    assert reviewed.calls == []


@pytest.mark.parametrize('field,value', [
    ('handler_id', 'DOCUMENTS'),
    ('handler_id', 'documents;calc'),
    ('path', 'relative.txt'),
    ('path', '//server/share/report.txt'),
    ('expected_kind', 'directory'),
    ('expected_digest', '0' * 64),
    ('expected_handler_app', 'other'),
    ('expected_handler_sha256', '0' * 64),
])
def test_exact_request_mismatch_or_shape_refused(reviewed, field, value):
    args = _open_args(reviewed)
    args[field] = value
    with pytest.raises(ValueError):
        preview_reviewed_open(**args)
    assert reviewed.calls == []


def test_path_outside_root_and_unapproved_extension_refused(reviewed, tmp_path):
    outside = tmp_path / 'outside.txt'
    outside.write_text('outside', encoding='utf-8')
    with pytest.raises(ValueError, match='outside'):
        plan_reviewed_open('documents', str(outside))
    blocked = reviewed.root / 'macro.docm'
    blocked.write_text('not reviewed', encoding='utf-8')
    with pytest.raises(ValueError, match='extension'):
        plan_reviewed_open('documents', str(blocked))
    assert reviewed.calls == []


def test_blocked_extension_cannot_be_configured(reviewed):
    config = json.loads(reviewed.reviewed_config.read_text(encoding='utf-8'))
    config['handlers']['documents']['extensions'].append('.docm')
    _write_json(reviewed.reviewed_config, config)
    macro = reviewed.root / 'macro.docm'
    macro.write_text('active content', encoding='utf-8')
    with pytest.raises(ValueError, match='active-content'):
        plan_reviewed_open('documents', str(macro))
    assert reviewed.calls == []


def test_symlink_target_refused(reviewed):
    linked = reviewed.root / 'linked.txt'
    try:
        linked.symlink_to(reviewed.document)
    except OSError:
        pytest.skip('symlink unavailable')
    with pytest.raises(ValueError, match='canonical|symlink'):
        plan_reviewed_open('documents', str(linked))
    assert reviewed.calls == []


def test_file_change_invalidates_reviewed_digest(reviewed):
    args = _open_args(reviewed)
    reviewed.document.write_bytes(b'changed after review')
    with pytest.raises(ValueError, match='changed|matches'):
        open_reviewed_path(**args)
    assert reviewed.calls == []


def test_folder_listing_change_invalidates_reviewed_digest(reviewed):
    args = _open_args(reviewed, reviewed.folder)
    (reviewed.folder / 'two.txt').write_text('two', encoding='utf-8')
    with pytest.raises(ValueError, match='changed|matches'):
        open_reviewed_path(**args)
    assert reviewed.calls == []


def test_handler_executable_change_invalidates_review(reviewed):
    args = _open_args(reviewed)
    reviewed.handler.write_bytes(b'changed handler')
    with pytest.raises(ValueError, match='changed|match'):
        open_reviewed_path(**args)
    assert reviewed.calls == []


def test_malformed_or_ambiguous_config_refused(reviewed):
    reviewed.reviewed_config.write_text('{"version":1,"version":1,"handlers":{}}', encoding='utf-8')
    with pytest.raises(ValueError):
        plan_reviewed_open('documents', str(reviewed.document))
    config = {'version': 1, 'handlers': {'documents': {
        'app': 'viewer', 'roots': [str(reviewed.root)], 'targets': ['file'], 'extensions': ['.txt'], 'extra': True,
    }}}
    _write_json(reviewed.reviewed_config, config)
    with pytest.raises(ValueError, match='exactly'):
        plan_reviewed_open('documents', str(reviewed.document))
    assert reviewed.calls == []


def test_registry_requires_fresh_confirmation_and_never_auto_approves(reviewed):
    registry = build_registry(force=True)
    tool = registry.get('open_reviewed_path')
    assert tool.risk == Risk.MEDIUM and tool.requires_confirmation
    assert tool.never_auto_approve and not tool.allow_auto_approve and not tool.allow_always
    args = _open_args(reviewed)
    assert asyncio.run(registry.execute('open_reviewed_path', args)).cancelled
    assert asyncio.run(registry.execute('open_reviewed_path', args, auto_approve=True)).cancelled
    async def deny(_tool, preview):
        assert preview['_preview']['digest'] == args['expected_digest']
        return False
    assert asyncio.run(registry.execute('open_reviewed_path', args, confirm=deny)).cancelled
    assert reviewed.calls == []
    async def approve(_tool, _preview):
        return True
    result = asyncio.run(registry.execute('open_reviewed_path', args, confirm=approve))
    assert result.ok and len(reviewed.calls) == 1


def test_document_change_during_confirmation_fails_closed(reviewed):
    registry = build_registry(force=True)
    args = _open_args(reviewed)
    async def approve(_tool, _preview):
        reviewed.document.write_bytes(b'changed during prompt')
        return True
    result = asyncio.run(registry.execute('open_reviewed_path', args, confirm=approve))
    assert not result.ok and reviewed.calls == []


def test_config_redirect_during_confirmation_fails_closed(reviewed):
    registry = build_registry(force=True)
    args = _open_args(reviewed)
    async def approve(_tool, _preview):
        config = json.loads(reviewed.reviewed_config.read_text(encoding='utf-8'))
        config['handlers']['documents']['app'] = 'other'
        _write_json(reviewed.reviewed_config, config)
        return True
    result = asyncio.run(registry.execute('open_reviewed_path', args, confirm=approve))
    assert not result.ok and reviewed.calls == []


def test_emergency_stop_blocks_reviewed_open(reviewed):
    from aether.security import SecurityStore
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    async def approve(_tool, _preview):
        raise AssertionError('stopped action must not prompt')
    result = asyncio.run(registry.execute('open_reviewed_path', _open_args(reviewed), confirm=approve))
    assert not result.ok and reviewed.calls == []


def test_owner_access_policy_covers_target_and_handler_paths(reviewed, tmp_path, monkeypatch):
    policy = tmp_path / 'policy.json'
    _write_json(policy, {
        'version': 1,
        'level': 'CRITICAL',
        'tools': {
            'plan_reviewed_open': {'level': 'READ', 'paths': {'path': [str(reviewed.root)]}},
            'open_reviewed_path': {'level': 'CRITICAL', 'paths': {
                'path': [str(reviewed.root)],
                'expected_handler_executable': [str(tmp_path)],
            }},
        },
    })
    monkeypatch.setenv('AETHER_ACCESS_POLICY', str(policy))
    registry = build_registry(force=True)
    args = _open_args(reviewed)
    async def approve(_tool, _preview):
        return True
    assert asyncio.run(registry.execute('open_reviewed_path', args, confirm=approve)).ok
    assert len(reviewed.calls) == 1


def test_owner_access_policy_rejects_missing_handler_path_and_extra_argument(reviewed, tmp_path, monkeypatch):
    policy = tmp_path / 'policy.json'
    _write_json(policy, {
        'version': 1,
        'level': 'CRITICAL',
        'tools': {'open_reviewed_path': {'level': 'CRITICAL', 'paths': {'path': [str(reviewed.root)]}}},
    })
    monkeypatch.setenv('AETHER_ACCESS_POLICY', str(policy))
    registry = build_registry(force=True)
    args = _open_args(reviewed)
    async def approve(_tool, _preview):
        return True
    missing_handler_path = asyncio.run(registry.execute('open_reviewed_path', args, confirm=approve))
    assert not missing_handler_path.ok
    args['unexpected'] = 'value'
    extra_argument = asyncio.run(registry.execute('open_reviewed_path', args, confirm=approve))
    assert not extra_argument.ok
    assert reviewed.calls == []
