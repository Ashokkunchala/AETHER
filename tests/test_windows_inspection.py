"""All OS APIs are mocked. No host service/startup/interface inspection."""
import asyncio
import sys
from types import SimpleNamespace

import pytest

from aether.control import windows_inspection as wi
from aether.tools.builtin_tools import build_registry


@pytest.fixture
def windows(monkeypatch):monkeypatch.setattr(wi.platform,'system',lambda:'Windows')


def test_unsupported_windows_sources_unknown_no_queries(monkeypatch):
    monkeypatch.setattr(wi.platform,'system',lambda:'Other')
    for handler in [wi.service_inventory,wi.startup_inventory]:
        result=handler();assert not result['success'] and result['partial'] and not result['items']


def test_service_snapshot_never_reads_binary_user_or_description(windows,monkeypatch):
    import psutil
    class Fake:
        def name(self):return 'example'
        def display_name(self):return 'Example'
        def status(self):return 'running'
        def start_type(self):return 'manual'
    monkeypatch.setattr(psutil,'win_service_iter',lambda:iter([Fake()]),raising=False)
    result=wi.service_inventory()
    assert result['success'] and not result['changes_made'] and not result['partial']
    assert set(result['items'][0])=={'name','display_name','state','start_type'}


def test_service_permission_failure_not_empty_healthy(windows,monkeypatch):
    import psutil
    class Denied:
        def name(self):raise PermissionError('secret omitted')
    monkeypatch.setattr(psutil,'win_service_iter',lambda:iter([Denied()]),raising=False)
    result=wi.service_inventory();assert not result['success'] and result['partial']
    assert 'secret omitted' not in str(result)


def test_service_bounds(windows,monkeypatch):
    import psutil
    fake=SimpleNamespace(name=lambda:'x',display_name=lambda:'x',status=lambda:'new_unknown_state',start_type=lambda:'weird')
    monkeypatch.setattr(psutil,'win_service_iter',lambda:iter([fake]*301),raising=False)
    result=wi.service_inventory();assert result['partial'] and len(result['items'])==300
    assert result['items'][0]['state']=='unknown'


def test_registry_only_fixed_sources_names_no_commands(windows,monkeypatch):
    opens=[]
    class Key:
        def __enter__(self):return self
        def __exit__(self,*a):pass
    def opened(hive,path,reserved,access):opens.append((hive,path,access));return Key()
    fake=SimpleNamespace(HKEY_CURRENT_USER=1,HKEY_LOCAL_MACHINE=2,KEY_WOW64_32KEY=32,KEY_WOW64_64KEY=64,KEY_READ=4,
        OpenKey=opened,QueryInfoKey=lambda key:(0,1,0),EnumValue=lambda key,i:('entry','secret command --password=x',1))
    monkeypatch.setitem(sys.modules,'winreg',fake)
    items,sources,partial=wi._registry_names()
    assert len(opens)==8 and len(items)==8 and len(sources)==8 and not partial
    assert all('CurrentVersion\\Run' in path for _,path,_ in opens)
    assert 'secret' not in str(items) and all(x['target_omitted'] for x in items)


def test_registry_absent_and_denied_distinct(windows,monkeypatch):
    def opened(hive,*a):
        if hive==1:raise FileNotFoundError()
        raise PermissionError('private')
    fake=SimpleNamespace(HKEY_CURRENT_USER=1,HKEY_LOCAL_MACHINE=2,KEY_WOW64_32KEY=32,KEY_WOW64_64KEY=64,KEY_READ=4,OpenKey=opened)
    monkeypatch.setitem(sys.modules,'winreg',fake)
    items,sources,partial=wi._registry_names()
    assert not items and partial and {x['state'] for x in sources}=={'absent','unavailable'}


def test_startup_partial_sources_and_folders_no_file_open(windows,monkeypatch,tmp_path):
    for variable in ['APPDATA','PROGRAMDATA']:
        root=tmp_path/variable;folder=root/'Microsoft/Windows/Start Menu/Programs/Startup';folder.mkdir(parents=True)
        (folder/'example.lnk').write_text('secret target should never be read')
        monkeypatch.setenv(variable,str(root))
    items,sources,partial=wi._folder_names()
    assert len(items)==2 and not partial and 'secret target' not in str(items)
    monkeypatch.setattr(wi,'_registry_names',lambda:(_ for _ in ()).throw(PermissionError()))
    result=wi.startup_inventory();assert result['success'] and result['partial'] and len(result['items'])==2


def test_network_link_not_internet_probe(monkeypatch):
    import psutil
    monkeypatch.setattr(psutil,'net_if_stats',lambda:{'example':SimpleNamespace(isup=True,speed=0,mtu=1500)})
    result=wi.network_link_inventory()
    assert result['items']==[{'name':'example','link_up':True,'reported_link_mbps':None,'mtu_bytes':1500}]
    assert result['success'] and not result['internet_reachability_verified'] and not result['changes_made']


def test_network_api_failure_unknown(monkeypatch):
    import psutil
    def denied():raise PermissionError('private detail')
    monkeypatch.setattr(psutil,'net_if_stats',denied)
    result=wi.network_link_inventory();assert not result['success'] and result['partial'] and 'private detail' not in str(result)


def test_new_reads_require_fresh_exact_approval_stop_rechecked(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    registry=build_registry(force=True);calls=[]
    for name in ['windows_service_inventory','windows_startup_inventory','network_link_inventory']:
        registry.get(name).handler=lambda:calls.append(name) or {'success':True}
        assert asyncio.run(registry.execute(name,auto_approve=True)).cancelled
        async def yes(tool,args):
            assert 'provider context' in args['_preview']['privacy'];return True
        assert asyncio.run(registry.execute(name,confirm=yes)).ok
        assert asyncio.run(registry.execute(name,auto_approve=True)).cancelled
    before=len(calls)
    async def stopped(*a):SecurityStore().set_stop(True);return True
    assert not asyncio.run(registry.execute('network_link_inventory',confirm=stopped)).ok and len(calls)==before
