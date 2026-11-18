import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from aether import offline_workflows as workflows
from aether.security import SecurityStore
from aether.tools.registry import ToolRegistry


def spec():
    return {'title': 'Offline supplied snapshot review', 'steps': [
        {'operation': 'terraform_plan', 'inputs': {'document': {'format_version': '1.2', 'resource_changes': []}}},
        {'operation': 'security_groups', 'inputs': {'document': {'SecurityGroups': []}}},
    ]}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'stop.db'))
    return workflows.WorkflowStore(tmp_path / 'workflows.db')


def next_args(store, identity):
    p = store.next_preview(identity)
    return {'workflow_id': identity, 'expected_digest': p['digest'], 'expected_position': p['position'], 'expected_input_digest': p['input_digest']}


def test_save_resume_one_step_and_reopen(store):
    data = spec()
    identity = store.create(data)['workflow_id']
    data['steps'][0]['inputs']['document']['format_version'] = 'bad'
    result = store.run_next(**next_args(store, identity))
    assert result['state'] == 'completed' and result['position'] == 0
    reopened = workflows.WorkflowStore(store.path)
    states = [s['state'] for s in reopened.status(identity)['steps']]
    assert states == ['completed', 'pending']
    assert reopened.result(identity, 0)['result'] == result['result']
    assert 'inputs' not in json.dumps(reopened.status(identity))
    assert reopened.run_next(**next_args(reopened, identity))['position'] == 1
    with pytest.raises(ValueError):
        reopened.next_preview(identity)


@pytest.mark.parametrize('operation', ['run_shell', 'browse_public_page', 'import', '__import__', 'eval', 'aws_start', 'delete_file'])
def test_arbitrary_execution_never_dispatches(store, operation):
    data = spec(); data['steps'][0]['operation'] = operation
    with pytest.raises(ValueError):
        store.create(data)


def test_strict_schema_and_size(store):
    for bad in [{}, {'title': 'x', 'steps': []}, {'title': 'x', 'steps': spec()['steps'] * 6}, {'title': '\n', 'steps': spec()['steps']}, {'title': 'x', 'steps': [{'operation': 'terraform_plan', 'inputs': {'path': '/private'}}]}]:
        with pytest.raises(ValueError):
            store.create(bad)
    data = spec(); data['steps'][0]['inputs']['document']['big'] = 'x' * 262144
    with pytest.raises(ValueError):
        store.create(data)
    data = spec(); data['steps'][0]['inputs']['document']['bad'] = float('nan')
    with pytest.raises(ValueError):
        store.create(data)


@pytest.mark.parametrize('field,value', [('expected_digest', 'wrong'), ('expected_position', True), ('expected_position', 1), ('expected_input_digest', 'wrong')])
def test_exact_review_binding(store, field, value):
    identity = store.create(spec())['workflow_id']; args = next_args(store, identity);args[field] = value
    with pytest.raises(ValueError):
        store.run_next(**args)
    assert store.status(identity)['steps'][0]['state'] == 'pending'


def test_failed_step_blocks_resume_no_exception_leak(store, monkeypatch):
    identity = store.create(spec())['workflow_id']
    monkeypatch.setattr(workflows, '_analyze', lambda *_: (_ for _ in ()).throw(ValueError('SECRET input content')))
    result = store.run_next(**next_args(store, identity))
    assert result['state'] == 'failed' and 'SECRET' not in json.dumps(result)
    with pytest.raises(ValueError):
        store.next_preview(identity)


def test_crash_claim_is_unresolved_and_never_replayed(store):
    identity = store.create(spec())['workflow_id']
    with store.connect() as db:
        db.execute("UPDATE offline_steps SET state='running',claim='crashed' WHERE workflow=? AND position=0", (identity,))
    reopened = workflows.WorkflowStore(store.path)
    assert reopened.status(identity)['steps'][0]['state'] == 'running'
    with pytest.raises(ValueError):
        reopened.next_preview(identity)


def test_atomic_claim_only_one_analyzer(store, monkeypatch):
    identity = store.create(spec())['workflow_id'];args = next_args(store, identity)
    started = threading.Event(); release = threading.Event();calls = []
    def analyze(*_):
        calls.append(1);started.set();assert release.wait(5);return {'value': 'done'}
    monkeypatch.setattr(workflows, '_analyze', analyze)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(store.run_next, **args)
        assert started.wait(5)
        second = pool.submit(store.run_next, **args)
        with pytest.raises(ValueError):
            second.result(timeout=5)
        release.set()
        assert first.result(timeout=5)['state'] == 'completed'
    assert len(calls) == 1


def test_cancel_running_suppresses_and_pending_blocked(store, monkeypatch):
    identity = store.create(spec())['workflow_id']
    def analyze(*_):
        store.cancel(identity)
        return {'private': 'must not escape'}
    monkeypatch.setattr(workflows, '_analyze', analyze)
    result = store.run_next(**next_args(store, identity))
    assert result['state'] == 'cancelled' and 'must not escape' not in json.dumps(result)
    assert store.result(identity, 0)['result'] is None
    assert all(s['state'] == 'cancelled' for s in store.status(identity)['steps'])


def test_stop_before_and_after_analyzer(store, monkeypatch):
    SecurityStore().set_stop(True)
    with pytest.raises(RuntimeError):
        store.create(spec())
    SecurityStore().set_stop(False)
    identity = store.create(spec())['workflow_id'];args = next_args(store, identity)
    def analyze(*_):
        SecurityStore().set_stop(True)
        return {'private': 'discard'}
    monkeypatch.setattr(workflows, '_analyze', analyze)
    assert store.run_next(**args)['state'] == 'cancelled'
    assert store.result(identity, 0)['result'] is None


def test_changed_input_after_review_refused(store):
    identity = store.create(spec())['workflow_id'];args = next_args(store, identity)
    with store.connect() as db:
        db.execute('UPDATE offline_steps SET inputs=? WHERE workflow=? AND position=0', ('{"document":{}}', identity))
    with pytest.raises(ValueError):
        store.run_next(**args)


def test_registry_review_and_stop(store, monkeypatch):
    monkeypatch.setenv('AETHER_OFFLINE_WORKFLOW_DB', str(store.path))
    registry = ToolRegistry();registry.security_store = SecurityStore();workflows.register_offline_workflows(registry)
    for name in ['offline_workflow_create', 'offline_workflow_run_next', 'offline_workflow_cancel', 'offline_workflow_result']:
        tool = registry.get(name)
        assert tool.never_auto_approve and not tool.allow_always and not tool.allow_auto_approve
    assert not asyncio.run(registry.execute('offline_workflow_create', {'spec': spec()}, auto_approve=True)).ok


def test_all_fixed_operations_are_real_offline_analyzers():
    assert workflows._analyze('security_groups', {'document': {'SecurityGroups': []}})['groups_reviewed'] == 0
    assert workflows._analyze('terraform_plan', {'document': {'format_version': '1.1', 'resource_changes': []}})['changes'] == []
    cost = workflows._analyze('daily_costs', {'daily': [{'date': f'2026-01-0{n}', 'amount': '1'} for n in range(1, 5)], 'currency': 'USD', 'complete_days': True, 'increase_percent': 50, 'minimum_increase': 5})
    assert cost
    slo = workflows._analyze('slo_budget', {'windows': [{'start': '2026-01-01T00:00:00Z', 'end': '2026-01-02T00:00:00Z', 'total_events': 1000, 'good_events': 999}], 'target_percent': '99.9', 'complete_window': True, 'event_definition': 'Fictional eligible requests with successful replies'})
    assert slo['objective_met']


def test_registry_rechecks_reviewed_input_digest_after_confirmation(store, monkeypatch):
    monkeypatch.setenv('AETHER_OFFLINE_WORKFLOW_DB', str(store.path))
    identity = store.create(spec())['workflow_id']; args = next_args(store, identity)
    registry = ToolRegistry();registry.security_store = SecurityStore();workflows.register_offline_workflows(registry)
    async def approve(tool, shown):
        assert shown['_preview']['input_digest'] == args['expected_input_digest']
        with store.connect() as db:
            db.execute('UPDATE offline_steps SET inputs=? WHERE workflow=? AND position=0', ('{"document":{}}', identity))
        return True
    result = asyncio.run(registry.execute('offline_workflow_run_next', args, confirm=approve))
    assert not result.ok
    assert store.status(identity)['steps'][0]['state'] == 'pending'


def test_failed_analyzer_is_not_successful_registry_result(store, monkeypatch):
    monkeypatch.setenv('AETHER_OFFLINE_WORKFLOW_DB', str(store.path))
    identity = store.create(spec())['workflow_id'];args = next_args(store, identity)
    monkeypatch.setattr(workflows, '_analyze', lambda *_: (_ for _ in ()).throw(ValueError('SECRET')))
    registry = ToolRegistry();registry.security_store = SecurityStore();workflows.register_offline_workflows(registry)
    async def approve(*_):
        return True
    result = asyncio.run(registry.execute('offline_workflow_run_next', args, confirm=approve))
    assert not result.ok and 'SECRET' not in result.error
    assert store.status(identity)['steps'][0]['state'] == 'failed'
