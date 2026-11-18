"""All child processes mocked. This does not execute project code or pytest."""
import asyncio
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from aether.devops.python_tests import preview_python_tests, run_python_tests
from aether.tools.builtin_tools import build_registry
from aether.tools.registry import Risk


@pytest.fixture
def project(tmp_path):
    root = tmp_path.resolve() / 'project with spaces'
    (root/'tests').mkdir(parents=True)
    (root/'tests'/'test_example.py').write_text('raise AssertionError("never execute")')
    return str(root)


@pytest.mark.parametrize('selection', ['../tests', 'tests/../app', '-q', '/tests', 'tests//x', 'tests\\x', 'tests/-x', 'tests/./test_example.py', 'tests/missing.py'])
def test_invalid_selection_never_spawns(project, selection, monkeypatch):
    child = Mock(side_effect=AssertionError('No process permitted'))
    monkeypatch.setattr(subprocess, 'run', child)
    assert not run_python_tests(project, selection)['success']
    child.assert_not_called()


@pytest.mark.parametrize('timeout', [True, 0, 301, '60'])
def test_invalid_timeout_denied(project, timeout):
    assert not preview_python_tests(project, timeout=timeout)['success']


def test_preview_fixed_no_shell_no_install_and_output_scope(project):
    plan = preview_python_tests(project, 'tests/test_example.py', 30)
    assert plan['success'] and plan['shell'] is False
    assert plan['argv'][1:5] == ['-I', '-B', '-m', 'pytest']
    assert plan['argv'][-1] == str(Path(project)/'tests/test_example.py')
    assert 'not a sandbox' in plan['notice']
    assert 'not frozen' in plan['notice']
    assert 'discards' in plan['output_policy']


@pytest.mark.parametrize('code,ok', [(0,True),(1,False),(2,False),(3,False),(4,False),(5,False),(6,False),(-9,False)])
def test_only_exit_code_observed_without_output_or_secret_env(project, monkeypatch, code, ok):
    child = Mock(return_value=Mock(returncode=code))
    monkeypatch.setattr(subprocess, 'run', child)
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'never disclose')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--bad-option')
    monkeypatch.setenv('PYTHONPATH', '/private/modules')
    result = run_python_tests(project)
    assert result['success'] is ok and result['exit_code'] == code
    assert not result['output_retained'] and not result['tests_count_verified']
    assert not result['child_process_completion_verified']
    kwargs = child.call_args.kwargs
    assert kwargs['shell'] is False and kwargs['check'] is False
    assert kwargs['stdout'] == subprocess.DEVNULL and kwargs['stderr'] == subprocess.DEVNULL
    assert kwargs['stdin'] == subprocess.DEVNULL
    assert kwargs['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
    assert 'AWS_SECRET_ACCESS_KEY' not in kwargs['env']
    assert 'PYTEST_ADDOPTS' not in kwargs['env'] and 'PYTHONPATH' not in kwargs['env']
    child.assert_called_once()


def test_timeout_no_child_stop_success_or_retry(project, monkeypatch):
    child = Mock(side_effect=subprocess.TimeoutExpired(['private'], 5))
    monkeypatch.setattr(subprocess, 'run', child)
    result = run_python_tests(project, timeout=5)
    assert not result['success'] and result['timed_out']
    assert not result['child_process_completion_verified']
    assert not result['automatic_retry']
    assert 'private' not in str(result)
    child.assert_called_once()


def test_error_redacted_no_retry(project, monkeypatch):
    child = Mock(side_effect=OSError('secret exception'))
    monkeypatch.setattr(subprocess, 'run', child)
    result = run_python_tests(project)
    assert not result['success'] and 'secret exception' not in str(result)
    child.assert_called_once()


def test_changed_symlink_selection_denied(project, monkeypatch, tmp_path):
    target = tmp_path/'outside.py'
    target.write_text('never execute')
    link = Path(project)/'tests'/'linked.py'
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip('Test host symlink unavailable')
    child = Mock(side_effect=AssertionError('No process permitted'))
    monkeypatch.setattr(subprocess, 'run', child)
    assert not run_python_tests(project, 'tests/linked.py')['success']
    child.assert_not_called()


def test_registry_exact_fresh_approval_stop_and_argument_freeze(project, tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path/'security.db'))
    registry = build_registry(force=True)
    tool = registry.get('run_python_tests')
    assert tool.risk == Risk.HIGH and not tool.allow_auto_approve and not tool.allow_always
    called = Mock(return_value={'success':True})
    tool.handler = called
    assert asyncio.run(registry.execute(tool.name, {'project':project}, auto_approve=True)).cancelled
    called.assert_not_called()
    async def approve(tool, args):
        assert args['_preview']['project'] == project
        args['project'] = 'changed'
        return True
    assert asyncio.run(registry.execute(tool.name, {'project':project}, confirm=approve)).ok
    called.assert_called_once_with(project=project)
    called.reset_mock()
    from aether.security import SecurityStore
    async def stop(tool, args):
        SecurityStore().set_stop(True)
        return True
    assert not asyncio.run(registry.execute(tool.name, {'project':project}, confirm=stop)).ok
    called.assert_not_called()


def test_registry_keeps_nonzero_exit_context_without_raw_output(project, tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path/'security.db'))
    monkeypatch.setattr(subprocess, 'run', Mock(return_value=Mock(returncode=5)))
    async def approve(tool, args):
        return True
    result = asyncio.run(build_registry(force=True).execute('run_python_tests', {'project':project}, confirm=approve))
    assert not result.ok
    assert 'status 5' in result.error and 'no tests' in result.error
    assert 'unverified' in result.error and 'No retry' in result.error


def test_selection_revalidated_after_confirmation(project, tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path/'security.db'))
    child = Mock(side_effect=AssertionError('No process permitted'))
    monkeypatch.setattr(subprocess, 'run', child)
    async def approve(tool, args):
        (Path(project)/'tests'/'test_example.py').rename(Path(project)/'removed.py')
        return True
    result = asyncio.run(build_registry(force=True).execute('run_python_tests',
        {'project':project, 'selection':'tests/test_example.py'}, confirm=approve))
    assert not result.ok
    child.assert_not_called()
