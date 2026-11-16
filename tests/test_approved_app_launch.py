"""Fake executable bytes and Popen only. Never start a real application."""
import asyncio
import hashlib
import json

import pytest

from jarvis.control.approved_apps import launch_approved_app, preview_approved_app
from jarvis.tools.builtin_tools import build_registry


@pytest.fixture
def setup(tmp_path,monkeypatch):
    path=tmp_path/'app.exe';path.write_bytes(b'fake not executable')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    config=tmp_path/'approved.json'
    doc={'version':1,'apps':{'editor':{'executable':str(path),'sha256':digest}}};config.write_text(json.dumps(doc))
    monkeypatch.setenv('JARVIS_APPROVED_APPS_FILE',str(config))
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    calls=[]
    import subprocess
    def fake(args,**kwargs):
        calls.append((args,kwargs))
        return type('Process',(),{'pid':123})()
    monkeypatch.setattr(subprocess,'Popen',fake)
    return {'app_name':'editor','expected_executable':str(path),'expected_sha256':digest},config,doc,calls,build_registry(force=True)


def test_exact_local_entry_no_shell_fallback_or_args(setup):
    args,_,_,calls,_=setup
    result=launch_approved_app(**args)
    assert calls[0][0]==[args['expected_executable']] and calls[0][1]['shell'] is False
    assert result['launch_requested'] and not result['application_ready_verified']


def test_no_default_allowlist(setup,monkeypatch,tmp_path):
    args,_,_,calls,_=setup
    monkeypatch.setenv('JARVIS_APPROVED_APPS_FILE',str(tmp_path/'missing.json'))
    with pytest.raises(ValueError):launch_approved_app(**args)
    assert not calls


@pytest.mark.parametrize('change',[{'app_name':'edit'},{'app_name':'EDITOR'},{'app_name':'cmd & calc'},{'app_name':'https://github.com'},{'expected_sha256':'0'*64},{'expected_executable':'app.exe'},{'expected_executable':'https://evil/app.exe'},{'expected_executable':'//server/app.exe'}])
def test_exact_match_only(setup,change):
    args,_,_,calls,_=setup;args.update(change)
    with pytest.raises(ValueError):launch_approved_app(**args)
    assert not calls


def test_content_changed_blocks_even_same_path(setup):
    from pathlib import Path
    args,_,_,calls,_=setup;Path(args['expected_executable']).write_bytes(b'changed')
    with pytest.raises(ValueError):launch_approved_app(**args)
    assert not calls


def test_duplicate_or_unknown_config_fields_refused(setup):
    args,config,doc,calls,_=setup
    config.write_text('{"version":1,"version":1,"apps":{}}')
    with pytest.raises(ValueError):preview_approved_app(**args)
    doc['extra']=True;config.write_text(json.dumps(doc))
    with pytest.raises(ValueError):preview_approved_app(**args)
    assert not calls


def test_fresh_confirmation_no_auto_and_preview_does_not_launch(setup):
    args,_,_,calls,registry=setup
    assert preview_approved_app(**args)['executable']==args['expected_executable'] and not calls
    assert asyncio.run(registry.execute('open_app',args,auto_approve=True)).cancelled and not calls
    async def deny(tool,preview):
        assert preview['_preview']['sha256']==args['expected_sha256']
        return False
    assert asyncio.run(registry.execute('open_app',args,confirm=deny)).cancelled and not calls
    async def yes(*a):return True
    assert asyncio.run(registry.execute('open_app',args,confirm=yes)).ok and len(calls)==1
    assert asyncio.run(registry.execute('open_app',args,auto_approve=True)).cancelled and len(calls)==1


def test_allowlist_revocation_during_prompt_rechecked(setup):
    args,config,doc,calls,registry=setup
    async def yes(*a):
        doc['apps'].clear();config.write_text(json.dumps(doc));return True
    assert not asyncio.run(registry.execute('open_app',args,confirm=yes)).ok and not calls


def test_config_redirect_during_confirmation_cannot_change_frozen_target(setup,tmp_path):
    args,config,doc,calls,registry=setup
    async def yes(tool,preview):
        other=tmp_path/'other.exe';other.write_bytes(b'other')
        doc['apps']['editor']={'executable':str(other),'sha256':hashlib.sha256(b'other').hexdigest()}
        config.write_text(json.dumps(doc));return True
    assert not asyncio.run(registry.execute('open_app',args,confirm=yes)).ok and not calls


def test_emergency_stop_and_missing_fields_fail_closed(setup):
    from jarvis.security import SecurityStore
    args,_,_,calls,registry=setup
    async def yes(*a):return True
    assert not asyncio.run(registry.execute('open_app',{'app_name':'editor'},confirm=yes)).ok
    SecurityStore().set_stop(True)
    assert not asyncio.run(registry.execute('open_app',args,confirm=yes)).ok and not calls


def test_legacy_direct_launch_and_voice_refuse_without_os_calls():
    from jarvis.control.apps import launch_app
    from jarvis.core.agent.voice_tools import _open_app
    assert not launch_app('notepad')['success']
    assert not launch_app('cmd /c something')['success']
    class Fake:
        def open_app(self,*a):raise AssertionError('No direct launch')
    assert not _open_app(Fake(),{'name':'notepad'})['success']
