"""Never inspect or launch a real default handler or user file."""
import asyncio
from unittest.mock import Mock

import pytest

from jarvis.control import files
from jarvis.control.laptop import LaptopController
from jarvis.tools.builtin_tools import build_registry
from jarvis.tools.registry import Risk
from jarvis.tools.system.file_ops import open_file


@pytest.mark.parametrize('path', ['C:\\app.exe', 'C:\\task.cmd', 'C:\\shortcut.lnk',
                                  'C:\\report.pdf', 'C:\\folder', 'https://example.invalid',
                                  '..', None, '', '\\\\server\\share\\app.exe'])
def test_all_legacy_paths_fail_before_resolution_and_launch(path, monkeypatch):
    launch = Mock(side_effect=AssertionError('No OS launch permitted'))
    resolve = Mock(side_effect=AssertionError('No path read permitted'))
    monkeypatch.setattr(files.os, 'startfile', launch, raising=False)
    monkeypatch.setattr(files, 'resolve', resolve)
    for call in [files.open_path, LaptopController().open_path, open_file]:
        result = call(path)
        assert result['success'] is False and 'disabled' in result['error']
    launch.assert_not_called()
    resolve.assert_not_called()


def test_registry_denies_before_prompt_handler_or_auto_bypass(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path/'security.db'))
    registry = build_registry(force=True)
    tool = registry.get('open_path')
    assert tool.risk == Risk.HIGH and tool.never_auto_approve
    assert not tool.allow_always and not tool.allow_auto_approve
    handler = Mock(side_effect=AssertionError('Must not reach launcher'))
    tool.handler = handler
    async def approve(tool, args):
        raise AssertionError('Disabled path must not ask for unusable approval')
    result = asyncio.run(registry.execute('open_path', {'path':'C:\\app.exe'}, confirm=approve, auto_approve=True))
    assert not result.ok and 'disabled' in result.error
    handler.assert_not_called()
