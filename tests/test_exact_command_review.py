"""Mock-only generic command gates; never execute a shell or elevate."""
import asyncio
from unittest.mock import Mock

import pytest

from jarvis.control.command_preview import command_preview, process_start_preview
from jarvis.tools.builtin_tools import build_registry
from jarvis.tools.registry import Risk


@pytest.mark.parametrize('command', ['', '   ', 'x\x00y', 'x'*8001, None, 'diskpart'])
def test_invalid_commands_fail_before_review(command):
    assert command_preview(command)['success'] is False


def test_preview_preserves_exact_syntax_and_cwd():
    command = 'echo "quoted" && tool --flag\nsecond'
    preview = command_preview(command, 30, 'C:\\reviewed folder')
    assert preview['command'] == command
    assert preview['cwd'] == 'C:\\reviewed folder'
    assert preview['shell'] is True
    assert 'model provider' in preview['notice']
    assert 'cancellation' in preview['notice']


@pytest.mark.parametrize('elevated', [True, 'false', 1, None])
def test_elevation_refused_in_preview_and_primitive(monkeypatch, elevated):
    from jarvis.control.process import start_process
    popen = Mock(side_effect=AssertionError('Must not execute'))
    monkeypatch.setattr('subprocess.Popen', popen)
    assert process_start_preview('editor', elevated)['success'] is False
    assert start_process('editor', elevated)['success'] is False
    popen.assert_not_called()


def test_registry_fresh_exact_approval_and_stop(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path/'security.db'))
    registry = build_registry(force=True)
    for name in ['run_shell', 'start_process']:
        tool = registry.get(name)
        assert tool.risk == Risk.HIGH and tool.never_auto_approve
        assert not tool.allow_always and not tool.allow_auto_approve
        calls = []
        tool.handler = lambda **kw: calls.append(kw) or {'success': True}
        result = asyncio.run(registry.execute(name, {'command':'echo approved'}, auto_approve=True))
        assert result.cancelled and not calls
        async def deny(tool, args):
            assert args['_preview']['command'] == 'echo approved'
            return False
        result = asyncio.run(registry.execute(name, {'command':'echo approved'}, confirm=deny, auto_approve=True))
        assert result.cancelled and not calls
        async def approve(tool, args):
            args['command'] = 'different'
            return True
        result = asyncio.run(registry.execute(name, {'command':'echo approved'}, confirm=approve, auto_approve=True))
        assert result.ok and calls == [{'command':'echo approved'}]
        calls.clear()
        from jarvis.security import SecurityStore
        async def stop(tool, args):
            SecurityStore().set_stop(True)
            return True
        result = asyncio.run(registry.execute(name, {'command':'echo approved'}, confirm=stop))
        assert not result.ok and not calls
        SecurityStore().set_stop(False)
