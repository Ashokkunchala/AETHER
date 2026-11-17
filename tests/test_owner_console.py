import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

from jarvis import owner_console as console
from jarvis.security import SecurityStore


def test_fixed_registry_excludes_shell_network_provider_and_browser():
    registry = console.registry()
    assert set(registry.names()) == console.ALLOWED


def test_noninteractive_console_refuses_before_dispatch(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['owner-console', 'preflight'])
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(isatty=lambda: False))
    with pytest.raises(SystemExit, match='Interactive owner terminal'):
        console.main()


def test_json_read_bounded_plain_file(tmp_path):
    source = tmp_path / 'spec.json';source.write_text('{"title":"data"}')
    assert console.load_json(str(source)) == {'title': 'data'}
    source.write_bytes(b'x' * 262145)
    with pytest.raises(ValueError):
        console.load_json(str(source))
    source.write_bytes(b'not json')
    with pytest.raises(ValueError):
        console.load_json(str(source))


@pytest.mark.parametrize('name', ['run_shell', 'browse_public_page', 'gmail_send', 'eval'])
def test_dispatch_rejects_nonfixed_tools(name):
    with pytest.raises(ValueError):
        asyncio.run(console.dispatch(name, {}, lambda *_: True))


def test_confirmation_exact_phrase_only(monkeypatch, capsys):
    tool = SimpleNamespace(name='test_tool', description='local only')
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr('builtins.input', lambda _: 'yes')
    assert not asyncio.run(console.terminal_confirmation(tool, {'spec': 'data'}))
    monkeypatch.setattr('builtins.input', lambda _: 'APPROVE test_tool')
    assert asyncio.run(console.terminal_confirmation(tool, {'spec': 'data'}))
    assert 'Nothing is sent to an AI/provider' in capsys.readouterr().out


def test_dashboard_created_only_after_registry_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'security.db'))
    monkeypatch.setenv('AETHER_DASHBOARD_DIR', str(tmp_path / 'dashboards'))
    spec = {'title': 'Sample', 'source_note': 'Fictional', 'as_of': '2026-11-17', 'metrics': [{'label': 'Count', 'value': '1', 'note': 'sample'}]}
    args = {'name': 'sample', 'spec': spec}
    async def reject(*_):
        return False
    async def approve(*_):
        return True
    assert not asyncio.run(console.dispatch('create_custom_dashboard', args, reject)).ok
    assert not (tmp_path / 'dashboards').exists()
    assert asyncio.run(console.dispatch('create_custom_dashboard', args, approve)).ok
    assert len(list((tmp_path / 'dashboards').glob('*.html'))) == 1
    SecurityStore().set_stop(True)
    assert not asyncio.run(console.dispatch('create_custom_dashboard', args, approve)).ok


def test_owner_console_parser_no_arbitrary_tools_or_yes_flag():
    with pytest.raises(SystemExit):
        console.parser().parse_args(['run-shell', 'ls'])
    with pytest.raises(SystemExit):
        console.parser().parse_args(['dashboard', '--spec', 'a', '--name', 'b', '--yes'])


def test_main_workflow_next_binds_step_before_prompt(tmp_path, monkeypatch, capsys):
    from jarvis.offline_workflows import WorkflowStore
    monkeypatch.setenv('AETHER_OFFLINE_WORKFLOW_DB', str(tmp_path / 'workflow.db'))
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'stop.db'))
    store = WorkflowStore()
    identity = store.create({'title': 'Mock', 'steps': [{'operation': 'terraform_plan', 'inputs': {'document': {'format_version': '1.2', 'resource_changes': []}}}]})['workflow_id']
    monkeypatch.setattr(sys, 'argv', ['owner-console', 'workflow-next', '--id', identity])
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr('builtins.input', lambda _: 'APPROVE offline_workflow_run_next')
    console.main()
    printed = capsys.readouterr().out
    assert 'expected_input_digest' in printed and '"state": "completed"' in printed
    assert store.status(identity)['steps'][0]['state'] == 'completed'
