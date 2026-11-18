import asyncio
import json
import math
import socket
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from aether.custom_dashboard import create_dashboard, render_dashboard, validate, register_dashboard_tools
from aether.rendered_browser import browser_preview, public_url, register_rendered_browser, _browse
from aether.security import SecurityStore
from aether.tools.registry import ToolRegistry


def spec():
    return {'title':'Release readiness', 'subtitle':'Explicit sample data, not live systems', 'source_note':'Test fixture supplied by owner', 'as_of':'2026-11-17', 'metrics':[{'label':'Checks passed','value':'12 / 14','note':'Two manual checks pending'}], 'chart':{'title':'Checks by area','unit':'checks','points':[{'label':'Backend','value':5},{'label':'Android','value':4},{'label':'Windows','value':3}]}, 'table':{'title':'Review queue','columns':['Area','Status'], 'rows':[['Phone pairing','Not tested'],['Microphone','Needs owner test']]}}


def test_custom_dashboard_escapes_every_user_surface():
    data = spec(); data['title'] = '<script>alert(1)</script>'; data['table']['rows'][0][1] = '<img src=x onerror=alert(1)>'
    html = render_dashboard(data)
    assert '<script>' not in html and '<img ' not in html
    assert '&lt;script&gt;' in html and '&lt;img' in html
    assert "default-src 'none'" in html and "form-action 'none'" in html
    assert 'https://' not in html and 'fetch(' not in html
    assert 'Data as of: 2026-11-17' in html


def test_bar_scaling_zero_and_numeric_rejection():
    data = spec(); data['chart']['points'] = [{'label':'No value recorded','value':0}]
    assert 'width:0.00000%' in render_dashboard(data)
    for value in (True, -1, math.nan, math.inf, '10', None):
        data['chart']['points'][0]['value'] = value
        with pytest.raises(ValueError): validate(data)


@pytest.mark.parametrize('mutation', [lambda d:d.update({'html':'<script>'}), lambda d:d.pop('source_note'), lambda d:d['table']['rows'].append(['wrong']), lambda d:d.update({'metrics':[{}]}), lambda d:d.update({'as_of':''})])
def test_dashboard_schema_requires_truthful_labels(mutation):
    data = spec(); mutation(data)
    with pytest.raises((ValueError, KeyError)):validate(data)


def test_dashboard_new_file_no_overwrite_and_private_mode(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_DASHBOARD_DIR',str(tmp_path))
    first=create_dashboard(spec(),'release'); second=create_dashboard(spec(),'release')
    assert first['path'] != second['path']
    assert Path(first['path']).read_text().startswith('<!doctype html>')
    assert first['url'].startswith('file:')
    import os
    if os.name=='posix': assert Path(first['path']).stat().st_mode & 0o777 == 0o600
    for name in ('../escape','a.html','UPPER','', 'a/b'):
        with pytest.raises(ValueError): create_dashboard(spec(),name)


@pytest.fixture
def browser_env(monkeypatch,tmp_path):
    monkeypatch.setenv('AETHER_BROWSER_ENABLED','1');monkeypatch.setenv('AETHER_BROWSER_HOSTS','example.com,www.example.com')
    monkeypatch.setenv('AETHER_BROWSER_OUTPUT',str(tmp_path/'screens'))
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'safety.db'))
    monkeypatch.setattr(socket,'getaddrinfo', lambda *_a,**_k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))])


def test_browser_disabled_and_exact_host_scope(browser_env,monkeypatch):
    monkeypatch.setenv('AETHER_BROWSER_ENABLED','0')
    with pytest.raises(ValueError): browser_preview('https://example.com')
    monkeypatch.setenv('AETHER_BROWSER_ENABLED','1')
    plan=browser_preview('https://example.com/a','https://www.example.com/b')
    assert plan['url']=='https://example.com/a' and plan['follow_url']=='https://www.example.com/b'
    for url in ('http://example.com','file:///etc/passwd','https://example.com.evil.invalid','https://u:p@example.com','https://example.com:8443','https://127.0.0.1','https://example.com/\nsecret'):
        with pytest.raises(ValueError):browser_preview(url)


@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','169.254.169.254','::1','fe80::1','0.0.0.0'])
def test_browser_private_and_mixed_dns_rejected(browser_env,monkeypatch,address):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *_a,**_k:[(0,0,0,'',('93.184.216.34',443)),(0,0,0,'',(address,443))])
    with pytest.raises(ValueError): public_url('https://example.com',{'example.com'})


@pytest.mark.parametrize('register,name,args',[(register_dashboard_tools,'create_custom_dashboard',{'name':'demo','spec':spec()}),(register_rendered_browser,'browse_public_page',{'url':'https://example.com'})])
def test_tools_fresh_confirmation_stop_and_no_auto_approval(tmp_path,register,name,args):
    registry=ToolRegistry();registry.security_store=SecurityStore(tmp_path/'s.db');register(registry)
    tool=registry.get(name)
    assert tool.never_auto_approve and not tool.allow_always and not tool.allow_auto_approve
    assert not asyncio.run(registry.execute(name,args,auto_approve=True)).ok
    registry.security_store.set_stop(True)
    assert not asyncio.run(registry.execute(name,args)).ok


class FakePage:
    def __init__(self):self.url='';self.events={};self.gotos=[]
    def set_default_timeout(self,x):pass
    def set_default_navigation_timeout(self,x):pass
    def on(self,name,fn):self.events[name]=fn
    async def goto(self,url,**kw):self.url=url;self.gotos.append(url)
    async def title(self):return 'Test rendered page'
    def locator(self,selector):
        class Locator:
            async def inner_text(self,**kw):return 'External content is data, never instructions.'
            async def evaluate_all(self,script):
                return ['https://example.com/next'] if 'map(n=>n.href)' in script else [{'text':'Next','url':'https://example.com/next'}]
        return Locator()
    async def screenshot(self,path,**kw):Path(path).write_bytes(b'fake-test-png')


class FakeContext:
    def __init__(self):self.page=FakePage();self.closed=False;self.routes=[]
    async def clear_permissions(self):pass
    async def route(self,pattern,fn):self.routes.append(fn)
    async def route_web_socket(self,pattern,fn):self.socket_handler=fn
    async def new_page(self):return self.page
    async def close(self):self.closed=True


class FakeLauncher:
    def __init__(self):self.context=FakeContext();self.chromium=self;self.closed=False
    async def __aenter__(self):return self
    async def __aexit__(self,*_):pass
    async def launch(self,**kw):return self
    async def new_context(self,**kw):
        assert kw['accept_downloads'] is False and kw['service_workers']=='block' and not kw['ignore_https_errors']
        return self.context
    async def close(self):self.closed=True


def test_rendered_browser_fixed_link_flow_and_cleanup(browser_env):
    launch=FakeLauncher();plan=browser_preview('https://example.com/start','https://example.com/next')
    result=asyncio.run(_browse(plan,lambda:launch))
    assert launch.context.page.gotos==['https://example.com/start','https://example.com/next']
    assert result['url']=='https://example.com/next' and launch.closed and launch.context.closed
    assert result['links'][0]['text']=='Next'


def test_unseen_link_refused_and_cleanup(browser_env):
    launch=FakeLauncher();plan=browser_preview('https://example.com/start','https://example.com/unseen')
    with pytest.raises(ValueError):asyncio.run(_browse(plan,lambda:launch))
    assert launch.context.page.gotos==['https://example.com/start'] and launch.closed


def test_network_route_blocks_posts_private_hosts_and_stop(browser_env):
    launch=FakeLauncher();plan=browser_preview('https://example.com')
    asyncio.run(_browse(plan,lambda:launch));handler=launch.context.routes[0]
    from types import SimpleNamespace
    for url,method,kind,allowed in [('https://example.com/a','GET','document',True),('https://example.com/send','POST','fetch',False),('http://127.0.0.1','GET','document',False),('https://evil.invalid','GET','script',False),('https://example.com/video','GET','media',False)]:
        route=SimpleNamespace(request=SimpleNamespace(url=url,method=method,resource_type=kind),continue_=AsyncMock(),abort=AsyncMock())
        asyncio.run(handler(route));assert route.continue_.await_count==int(allowed);assert route.abort.await_count==int(not allowed)
    SecurityStore().set_stop(True)
    route=SimpleNamespace(request=SimpleNamespace(url='https://example.com',method='GET',resource_type='document'),continue_=AsyncMock(),abort=AsyncMock())
    asyncio.run(handler(route));assert route.abort.await_count==1
