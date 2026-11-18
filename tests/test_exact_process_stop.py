"""No real process inspection, termination or waiting."""
import asyncio
import os

import pytest

from aether.control.process_stop import preview_process_stop, stop_exact_process
from aether.tools.builtin_tools import build_registry


@pytest.fixture
def setup(monkeypatch,tmp_path):
    import psutil
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    args={'pid':999123,'expected_create_time':123.5,'expected_executable':str(tmp_path/'editor.exe')}
    class Fake:
        pid=999123
        started=123.5
        stopped=0
        timeout=False
        def create_time(self):return self.started
        def exe(self):return args['expected_executable']
        def name(self):return 'editor.exe'
        def is_running(self):return True
        def parents(self):return []
        def terminate(self):self.stopped+=1
        def wait(self,timeout):
            assert timeout==5
            if self.timeout:raise psutil.TimeoutExpired(timeout)
            return None
    fake=Fake()
    monkeypatch.setattr(psutil,'Process',lambda pid:fake)
    return args,fake,build_registry(force=True)


def test_exact_stop_waits_for_exit(setup):
    args,fake,_=setup
    assert preview_process_stop(**args)['pid']==args['pid'] and fake.stopped==0
    result=stop_exact_process(**args)
    assert fake.stopped==1 and result['exit_verified'] and not result['work_saved_verified']


@pytest.mark.parametrize('delta',[{'pid':True},{'pid':0},{'pid':4},{'pid':os.getpid()},{'expected_create_time':float('nan')},{'expected_create_time':float('inf')},{'expected_create_time':0},{'expected_create_time':123.6},{'expected_executable':'editor.exe'},{'expected_executable':'//server/editor.exe'}])
def test_bad_or_reused_identity_no_termination(setup,delta):
    args,fake,_=setup;args.update(delta)
    with pytest.raises(ValueError):stop_exact_process(**args)
    assert fake.stopped==0


def test_executable_mismatch_no_termination(setup,monkeypatch):
    args,fake,_=setup;monkeypatch.setattr(fake,'exe',lambda:'/other/editor.exe')
    with pytest.raises(ValueError):stop_exact_process(**args)
    assert fake.stopped==0


def test_timeout_not_success_no_kill(setup):
    args,fake,_=setup;fake.timeout=True
    result=stop_exact_process(**args)
    assert not result['success'] and not result['exit_verified'] and fake.stopped==1


def test_critical_and_ancestor_refused(setup,monkeypatch):
    args,fake,_=setup;monkeypatch.setattr(fake,'name',lambda:'lsass.exe')
    with pytest.raises(ValueError):stop_exact_process(**args)
    monkeypatch.setattr(fake,'name',lambda:'editor.exe');monkeypatch.setattr(fake,'parents',lambda:[fake])
    with pytest.raises(ValueError):stop_exact_process(**args)
    assert fake.stopped==0


def test_exact_identity_rechecked_after_fresh_confirmation(setup):
    args,fake,registry=setup
    assert asyncio.run(registry.execute('kill_process',args,auto_approve=True)).cancelled
    async def yes(*a):fake.started=999;return True
    assert not asyncio.run(registry.execute('kill_process',args,confirm=yes)).ok and fake.stopped==0


def test_close_and_kill_require_new_prompt_each_time(setup):
    args,fake,registry=setup
    async def yes(*a):return True
    for name in ['close_app','kill_process']:
        assert asyncio.run(registry.execute(name,args,confirm=yes)).ok
        assert asyncio.run(registry.execute(name,args,auto_approve=True)).cancelled
    assert fake.stopped==2


def test_legacy_name_stop_fails_closed():
    from aether.control.apps import close_app
    from aether.control.process import terminate_process
    from aether.tools.system.app_control import close_app as other
    assert not close_app('editor')['success']
    assert not terminate_process('editor',True)['success']
    assert not other('editor')['success']


def test_denied_and_emergency_stop_during_confirmation(setup):
    from aether.security import SecurityStore
    args,fake,registry=setup
    async def no(*a):return False
    assert asyncio.run(registry.execute('kill_process',args,confirm=no)).cancelled
    async def stopped(*a):SecurityStore().set_stop(True);return True
    assert not asyncio.run(registry.execute('kill_process',args,confirm=stopped)).ok and fake.stopped==0


def test_query_denied_and_disappeared_process_never_report_success(setup,monkeypatch):
    import psutil
    args,fake,registry=setup
    async def yes(*a):return True
    for error in [psutil.AccessDenied(args['pid']),psutil.NoSuchProcess(args['pid'])]:
        def denied():raise error
        monkeypatch.setattr(fake,'exe',denied)
        assert not asyncio.run(registry.execute('kill_process',args,confirm=yes)).ok
    assert fake.stopped==0


def test_wait_error_never_reported_as_verified(setup,monkeypatch):
    args,fake,registry=setup
    def unknown(**kw):raise RuntimeError('wait failed')
    monkeypatch.setattr(fake,'wait',unknown)
    async def yes(*a):return True
    result=asyncio.run(registry.execute('kill_process',args,confirm=yes))
    assert not result.ok and fake.stopped==1
