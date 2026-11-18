"""Exact approval and execution-time guards for dormant local-write tools."""
import asyncio

import pytest

from app import life_manager
from app.personal_local_tools import build_local_registry
from aether.security import SecurityStore
from aether.tools.registry import Risk


@pytest.fixture
def registry(monkeypatch, tmp_path):
    monkeypatch.setenv('AETHER_DB_PATH', str(tmp_path / 'life.db'))
    result = build_local_registry(lambda: True)
    result.security_store = SecurityStore(tmp_path / 'safety.db')
    return result


async def yes(tool, args):
    return True


async def no(tool, args):
    return False


def run(registry, name='create_saved_task', args=None, confirm=yes, auto_approve=False):
    return asyncio.run(registry.execute(name, args or {'title': 'Test task'}, confirm=confirm, auto_approve=auto_approve))


def test_allowlist_and_all_writes_are_non_bypassable(registry):
    assert len(registry) == 13
    writers = [tool for tool in registry.tools.values() if tool.category == 'personal_local']
    assert len(writers) == 5
    assert all(tool.risk == Risk.MEDIUM and tool.confirm_required and tool.never_auto_approve and not tool.allow_always and not tool.allow_auto_approve for tool in writers)
    assert registry.get('run_shell') is None
    assert registry.get('send_email') is None
    assert registry.get('delete_task') is None
    for confirm in (None, no):
        assert not run(registry, confirm=confirm, auto_approve=True).ok
    assert life_manager.list_tasks()['items'] == []


def test_exact_normalized_preview_and_frozen_arguments(registry):
    observed = {}
    async def approval(tool, args):
        observed.update(args['_preview'])
        args['title'] = 'tampered after preview'
        return True
    result = run(registry, args={'title': '  Original  ', 'due_at': '2026-11-16T20:00:00+05:30'}, confirm=approval)
    assert result.ok
    assert observed['values']['title'] == 'Original'
    assert observed['values']['due_at'] == '2026-11-16T14:30:00Z'
    assert result.data['record']['title'] == 'Original'


@pytest.mark.parametrize('name,args', [
    ('create_saved_task', {'title': 'bad', 'due_at': '2026-11-16T10:00:00'}),
    ('create_saved_task', {'title': 'bad', 'recipient': 'someone'}),
    ('log_personal_expense', {'amount': .001, 'category': 'food', 'spent_on': '2026-11-16'}),
    ('log_personal_expense', {'amount': 1, 'currency': 'USD', 'category': 'food', 'spent_on': '2026-11-16'}),
    ('draft_calendar_event', {'title': 'bad', 'starts_at': '2026-11-16T10:00:00Z', 'ends_at': '2026-11-16T09:00:00Z'}),
])
def test_bad_arguments_fail_before_asking(registry, name, args):
    async def forbidden(tool, args):
        raise AssertionError('Invalid values must never reach approval')
    assert not run(registry, name, args, forbidden).ok


def test_session_revoked_after_approval_blocks_write(registry):
    state = {'active': True}
    other = build_local_registry(lambda: state['active'])
    other.security_store = registry.security_store
    async def approval(tool, args):
        state['active'] = False
        return True
    assert not run(other, confirm=approval).ok
    assert life_manager.list_tasks()['items'] == []


def test_emergency_stop_after_approval_blocks_write(registry):
    async def approval(tool, args):
        registry.security_store.set_stop(True)
        return True
    assert not run(registry, confirm=approval).ok
    assert life_manager.list_tasks()['items'] == []


def test_stale_task_cannot_overwrite_another_writer(registry):
    task = life_manager.create_task(life_manager.TaskInput(title='Original'))
    args = {'task_id': task['id'], 'expected_updated_at': task['updated_at'], 'status': 'done'}
    async def approval(tool, values):
        life_manager.update_task(task['id'], life_manager.TaskPatch(title='Other writer'))
        return True
    result = run(registry, 'change_saved_task_status', args, approval)
    assert not result.ok
    actual = life_manager.list_tasks()['items'][0]
    assert actual['title'] == 'Other writer' and actual['status'] == 'open'


def test_task_status_changes_only_exact_current_record(registry):
    task = life_manager.create_task(life_manager.TaskInput(title='Original'))
    result = run(registry, 'change_saved_task_status', {'task_id': task['id'], 'expected_updated_at': task['updated_at'], 'status': 'done'})
    assert result.ok and result.data['record']['status'] == 'done'


@pytest.mark.parametrize('name,args,reader', [
    ('save_personal_note', {'title': 'Note', 'body': 'Keep this private'}, life_manager.list_notes),
    ('log_personal_expense', {'amount': 25.5, 'category': 'Food', 'spent_on': '2026-11-16'}, life_manager.list_expenses),
    ('draft_calendar_event', {'title': 'Draft', 'starts_at': '2026-11-16T12:00:00Z'}, life_manager.list_events),
])
def test_approved_records_use_existing_store(registry, name, args, reader):
    assert run(registry, name, args).ok
    assert len(reader()['items']) == 1
    if name == 'draft_calendar_event':
        assert reader()['items'][0]['status'] == 'draft'


def test_live_guard_is_mandatory():
    with pytest.raises(ValueError):
        build_local_registry(None)
