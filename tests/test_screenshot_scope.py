"""Mocked screenshot boundary checks. Never capture any actual screen."""
import asyncio

import pytest

from jarvis.control.screenshot_request import preview_screenshot
from jarvis.tools.builtin_tools import build_registry


@pytest.fixture
def setup(tmp_path,monkeypatch):
    from jarvis.control import screen
    from jarvis.security import SecurityStore
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    calls=[]
    monkeypatch.setattr(screen,'_capture_screenshot',lambda path,region:calls.append((path,region)) or {'success':True,'path':path})
    reg=build_registry(force=True)
    return reg, calls, {'scope':'full_screen','path':str(tmp_path/'capture.png')},SecurityStore()


def test_missing_confirmation_and_auto_approve_never_capture(setup):
    reg,calls,args,_=setup
    result=asyncio.run(reg.execute('screenshot',args,auto_approve=True))
    assert result.cancelled and calls==[]
    tool=reg.get('screenshot')
    assert tool.confirm_required and not tool.allow_always and not tool.allow_auto_approve
    assert tool.never_auto_approve and tool.confirmation_preview


def test_denial_no_capture_and_exact_privacy_preview(setup):
    reg,calls,args,_=setup
    async def deny(tool,preview):
        assert preview['_preview']['scope']=='full_screen'
        assert preview['_preview']['destination']==args['path']
        assert 'private data' in preview['_preview']['privacy']
        assert 'No image upload' in preview['_preview']['effect']
        return False
    assert asyncio.run(reg.execute('screenshot',args,confirm=deny)).cancelled
    assert calls==[]


def test_fresh_confirmation_each_capture_and_frozen_scope(setup):
    reg,calls,args,_=setup
    confirmations=[]
    async def yes(tool,preview):
        confirmations.append(preview)
        preview['path']='untrusted-changed.png'
        return True
    assert asyncio.run(reg.execute('screenshot',args,confirm=yes)).ok
    assert asyncio.run(reg.execute('screenshot',args,confirm=yes)).ok
    assert len(confirmations)==2 and calls==[(args['path'],None)]*2


def test_exact_region_and_stop_during_approval(setup):
    reg,calls,args,store=setup
    args.update(scope='region',left=-100,top=0,width=200,height=300)
    async def yes(tool,preview):
        assert preview['_preview']['region']=={'left':-100,'top':0,'width':200,'height':300}
        return True
    assert asyncio.run(reg.execute('screenshot',args,confirm=yes)).ok
    assert calls[0][1]=={'left':-100,'top':0,'width':200,'height':300}
    calls.clear()
    async def stop(tool,preview):
        store.set_stop(True)
        return True
    assert not asyncio.run(reg.execute('screenshot',args,confirm=stop)).ok and not calls


@pytest.mark.parametrize('change',[{'scope':None},{'scope':'all'},{'scope':'region'},{'left':0},{'path':'relative.png'},{'path':'https://private.example/capture.png'},{'path':'//server/share/capture.png'},{'scope':'region','left':0,'top':0,'width':True,'height':1},{'scope':'region','left':0,'top':0,'width':0,'height':1},{'scope':'region','left':0,'top':0,'width':16000,'height':16000}])
def test_bad_or_implicit_scope_fails_before_confirmation(setup,change):
    reg,calls,args,_=setup;args.update(change)
    async def should_not_ask(*a):raise AssertionError('Invalid scope must fail before prompt')
    assert not asyncio.run(reg.execute('screenshot',args,confirm=should_not_ask)).ok and not calls


def test_existing_destination_and_symlink_refused(tmp_path):
    path=tmp_path/'exists.png';path.write_text('preserve')
    with pytest.raises(ValueError):preview_screenshot('full_screen',str(path))
    link=tmp_path/'link.png';link.symlink_to(path)
    with pytest.raises(ValueError):preview_screenshot('full_screen',str(link))
    assert path.read_text()=='preserve'


def test_parent_missing_or_noncanonical_refused(tmp_path):
    with pytest.raises(ValueError):preview_screenshot('full_screen',str(tmp_path/'missing'/'shot.png'))
    parent=tmp_path/'real';parent.mkdir();link=tmp_path/'alias';link.symlink_to(parent,target_is_directory=True)
    with pytest.raises(ValueError):preview_screenshot('full_screen',str(link/'shot.png'))


def test_preview_has_no_capture_or_write(tmp_path):
    result=preview_screenshot('full_screen',str(tmp_path/'preview.png'))
    assert result['success'] and list(tmp_path.iterdir())==[]


def test_legacy_direct_and_voice_fail_closed(monkeypatch):
    from jarvis.control import screen
    from jarvis.core.agent.voice_tools import _screenshot
    def fail(*a):raise AssertionError('No direct capture')
    monkeypatch.setattr(screen,'_capture_screenshot',fail)
    assert not screen.screenshot()['success']
    class Fake:
        screenshot=fail
    assert not _screenshot(Fake(),{})['success']


def test_legacy_controllers_no_capture_import_or_success():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    controller=(root/'jarvis/control/system_controller.py').read_text().split('    def screenshot(',1)[1].split('    def shutdown(',1)[0]
    assert 'mss' not in controller and '"success": False' in controller
    unified=(root/'jarvis/core/jarvis_unified.py').read_text()
    assert 'result = self.laptop.screenshot()' not in unified and 'No capture performed.' in unified


def test_exclusive_output_creation_with_synthetic_pixels(tmp_path,monkeypatch):
    import sys
    import types

    from jarvis.control.screen import _capture_screenshot
    class FakeCapture:
        monitors=[{'left':0,'top':0,'width':1,'height':1}]
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def grab(self,region):return types.SimpleNamespace(rgb=b'\0\0\0',size=(1,1))
    tools=types.ModuleType('mss.tools');tools.to_png=lambda *a:b'synthetic-png-bytes'
    mss=types.ModuleType('mss');mss.mss=FakeCapture;mss.tools=tools
    monkeypatch.setitem(sys.modules,'mss',mss);monkeypatch.setitem(sys.modules,'mss.tools',tools)
    path=tmp_path/'capture.png'
    assert _capture_screenshot(str(path),None)['success']
    assert path.read_bytes()==b'synthetic-png-bytes'
    assert not _capture_screenshot(str(path),None)['success']
    assert path.read_bytes()==b'synthetic-png-bytes'
