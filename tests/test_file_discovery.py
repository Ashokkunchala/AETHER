from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis import file_discovery as files
from jarvis.security import SecurityStore
from jarvis.tools.registry import ToolRegistry


@pytest.fixture
def scope(tmp_path, monkeypatch):
    root = tmp_path / 'selected'
    root.mkdir()
    monkeypatch.setenv('AETHER_FILE_ROOTS', json.dumps([str(root)]))
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'security.db'))
    return root


def test_disabled_and_exact_selected_root(scope, monkeypatch):
    for setting in ['', '{}', '[]', '[1]', 'not json']:
        monkeypatch.setenv('AETHER_FILE_ROOTS', setting)
        with pytest.raises(ValueError):
            files.preview(str(scope))
    monkeypatch.setenv('AETHER_FILE_ROOTS', json.dumps([str(scope)]))
    child = scope / 'child'
    child.mkdir()
    with pytest.raises(ValueError):
        files.preview(str(child))
    assert files.preview(str(scope))['root'] == str(scope)


@pytest.mark.parametrize('value', ['relative', '/', '//server/share', '\\\\server\\share', 'bad\npath'])
def test_bad_root_values_rejected(scope, monkeypatch, value):
    monkeypatch.setenv('AETHER_FILE_ROOTS', json.dumps([value]))
    with pytest.raises(ValueError):
        files.preview(value)


@pytest.mark.parametrize('query,mode', [('a\nb', 'search'), ('x' * 101, 'search'), ('x', 'move'), (None, 'plan')])
def test_bad_search_rejected(scope, query, mode):
    with pytest.raises(ValueError):
        files.preview(str(scope), query, mode)


def test_names_only_search_and_plan_no_mutation(scope, monkeypatch):
    (scope / 'Report.PDF').write_text('secret contents never returned')
    (scope / 'photo.jpg').write_bytes(b'not necessarily an image')
    (scope / 'run.exe').write_bytes(b'no execution')
    sub = scope / 'notes'
    sub.mkdir()
    (sub / 'REPORT.txt').write_text('other text')
    before = {str(p): p.read_bytes() for p in scope.rglob('*') if p.is_file()}
    def no_content_reads(*args, **kwargs):
        raise AssertionError('File contents must not be read')
    monkeypatch.setattr(Path, 'read_bytes', no_content_reads)
    result = files.discover_files(str(scope), 'report', 'plan')
    assert {r['relative_path'] for r in result['files']} == {'Report.PDF', str(Path('notes') / 'REPORT.txt')}
    assert all(r['suggested_group'] == 'Documents' for r in result['files'])
    assert 'secret contents' not in json.dumps(result)
    assert files._group('run.exe') == 'Review manually'
    assert files._group('fake.jpg') == 'Images'  # extension only, no content claim
    monkeypatch.undo()
    assert before == {str(p): p.read_bytes() for p in scope.rglob('*') if p.is_file()}


def test_hidden_links_fifo_and_reparse_skipped(scope):
    (scope / 'ok.txt').write_text('visible')
    (scope / '.secret').write_text('hidden')
    hidden = scope / '.git'
    hidden.mkdir()
    (hidden / 'config').write_text('hidden')
    if os.name == 'posix':
        (scope / 'alias').symlink_to(scope / 'ok.txt')
        (scope / 'loop').symlink_to(scope, target_is_directory=True)
        os.mkfifo(scope / 'pipe')
    result = files.discover_files(str(scope))
    assert [x['relative_path'] for x in result['files']] == ['ok.txt']
    assert result['skipped_entries'] >= 2
    assert files._link(SimpleNamespace(st_mode=0, st_file_attributes=0x400))


def test_root_and_parent_links_rejected(scope, monkeypatch):
    if os.name != 'posix':
        pytest.skip('POSIX symlink fixture')
    alias = scope.parent / 'alias'
    alias.symlink_to(scope, target_is_directory=True)
    for path in [alias, alias / 'child']:
        monkeypatch.setenv('AETHER_FILE_ROOTS', json.dumps([str(path)]))
        with pytest.raises((OSError, ValueError)):
            files.preview(str(path))


@pytest.mark.parametrize('limit_name,limit', [('MAX_RESULTS', 2), ('MAX_ENTRIES', 2), ('MAX_SECONDS', 0)])
def test_hard_limits_are_honest(scope, monkeypatch, limit_name, limit):
    for n in range(6):
        (scope / f'item-{n}.txt').write_text('x')
    monkeypatch.setattr(files, limit_name, limit)
    result = files.discover_files(str(scope))
    assert not result['bounded_walk_finished']
    assert result['limits_or_errors']
    assert len(result['files']) <= 2


def test_depth_limit(scope, monkeypatch):
    child = scope / 'sub'
    child.mkdir()
    (child / 'not-visited.txt').write_text('x')
    monkeypatch.setattr(files, 'MAX_DEPTH', 0)
    result = files.discover_files(str(scope))
    assert not result['files']
    assert 'depth limit reached' in result['limits_or_errors']


def test_unreadable_folder_partial_not_absent(scope, monkeypatch):
    monkeypatch.setattr(os, 'scandir', lambda *_: (_ for _ in ()).throw(PermissionError('private')))
    result = files.discover_files(str(scope))
    assert result['files'] == []
    assert not result['bounded_walk_finished']
    assert 'unreadable or changed folders skipped' in result['limits_or_errors']


def test_stop_before_and_during_discards(scope, monkeypatch):
    monkeypatch.setattr(files, '_stopped', lambda: True)
    with pytest.raises(RuntimeError):
        files.discover_files(str(scope))
    (scope / 'a.txt').write_text('x')
    checks = iter([False, False, True])
    monkeypatch.setattr(files, '_stopped', lambda: next(checks))
    with pytest.raises(RuntimeError):
        files.discover_files(str(scope))


def test_registry_fresh_review_and_real_stop(scope):
    registry = ToolRegistry()
    registry.security_store = SecurityStore()
    files.register_file_discovery(registry)
    tool = registry.get('discover_local_files')
    assert tool.never_auto_approve and not tool.allow_always and not tool.allow_auto_approve
    assert not asyncio.run(registry.execute(tool.name, {'root': str(scope)}, auto_approve=True)).ok
    registry.security_store.set_stop(True)
    assert not asyncio.run(registry.execute(tool.name, {'root': str(scope)})).ok
