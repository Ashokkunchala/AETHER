import asyncio
import datetime as dt
import ipaddress
import json
import ssl
import sys
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from fastapi.testclient import TestClient

from windows_agent import remote_read_https as mod
from windows_agent.remote_read import RemoteReadStore


@pytest.fixture
def certificates(tmp_path):
    def create(host='192.168.1.2', expired=False, mismatch=False, san=True, ca=False, server=True):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = dt.datetime.now(dt.timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
        builder = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(days=1)).not_valid_after(now+dt.timedelta(days=1 if expired else 30))
        builder = builder.add_extension(x509.BasicConstraints(ca=ca,path_length=None),critical=True)
        if server:
            builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        if san:
            try:
                typed = x509.IPAddress(ipaddress.ip_address(host))
            except ValueError:
                typed = x509.DNSName(host)
            builder = builder.add_extension(x509.SubjectAlternativeName([typed]), critical=False)
        cert = builder.sign(key, hashes.SHA256())
        cert_path, key_path = tmp_path / 'cert.pem', tmp_path / 'key.pem'
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        if mismatch:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        return cert_path, key_path
    return create


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_AGENT_APPROVAL_DB', str(tmp_path / 'approval.db'))
    store = RemoteReadStore();device, token = store.provision_local()
    return TestClient(mod.make_app('aether.example'), base_url='https://aether.example'), store, device, token


def auth(token):
    return {'Authorization': 'Bearer ' + token}


def test_dedicated_surface_queue_only_local_approval_and_private_result(client, monkeypatch):
    from windows_agent import remote_read
    http, store, device, token = client
    calls = []
    monkeypatch.setattr(remote_read, 'memory_snapshot', lambda: calls.append('read') or {'total_bytes': 1000, 'available_bytes': 400, 'used_percent_reported': 60.0})
    response = http.post('/v1/remote-read/requests', json={'action': 'memory_snapshot'}, headers=auth(token))
    assert response.status_code == 201 and not response.json()['executed'] and not calls
    request = response.json()['request_id'];path = '/v1/remote-read/requests/' + request
    assert http.get(path, headers=auth(token)).json()['state'] == 'pending_local_review'
    store.review_local(request, device, True)
    result = http.get(path, headers=auth(token))
    assert result.status_code == 200 and result.json()['result']['total_bytes'] == 1000 and calls == ['read']
    assert result.headers['cache-control'] == 'no-store'
    assert result.headers['x-content-type-options'] == 'nosniff'
    assert http.post(path+'/cancel', json={}, headers=auth(token)).json()['state'] == 'result_cleared'


@pytest.mark.parametrize('path', ['/docs','/redoc','/openapi.json','/health','/exec','/v1/tools','/v1/remote-read/requests/','/v1/remote-read/pair','/v1/remote-read/requests/'+'a'*32+'/approve','/v1/remote-read/requests/'+'a'*32+'/review','/v1/remote-read/requests/'+'a'*32+'/execute'])
def test_no_agent_docs_pair_execute_proxy_or_redirect_routes(client,path):
    http,_,_,token = client
    assert http.post(path,json={},headers=auth(token),follow_redirects=False).status_code == 404
    assert http.get(path,headers=auth(token),follow_redirects=False).status_code == 404


@pytest.mark.parametrize('headers', [{}, {'Host':'evil.example'}, {'Host':'aether.example.evil.example'}, {'Host':'aether.example:8443'}, {'Origin':'https://aether.example'}, {'Content-Encoding':'gzip'}, {'Transfer-Encoding':'chunked'}])
def test_host_browser_origin_encoding_and_missing_auth_refused(client,headers):
    http,_,_,token = client
    values = auth(token) if headers else {}
    values.update(headers)
    assert http.post('/v1/remote-read/requests', json={'action':'memory_snapshot'}, headers=values).status_code in (400,404)


def test_cleartext_forwarded_proto_cannot_upgrade(client):
    _,_,_,token = client
    http = TestClient(mod.make_app('aether.example'),base_url='http://aether.example')
    assert http.post('/v1/remote-read/requests',json={'action':'memory_snapshot'},headers={**auth(token),'X-Forwarded-Proto':'https'}).status_code == 404


def test_query_extra_fields_wrong_action_and_legacy_token_refused(client):
    http,_,_,token=client
    assert http.post('/v1/remote-read/requests?approved=true',json={'action':'memory_snapshot'},headers=auth(token)).status_code==404
    for data in [{'action':'shell'},{'action':'memory_snapshot','approved':True}]:
        assert http.post('/v1/remote-read/requests',json=data,headers=auth(token)).status_code==422
    assert http.post('/v1/remote-read/requests',json={'action':'memory_snapshot'},headers=auth('x'*48)).status_code==409


def test_body_size_duplicate_headers_and_rate_limit(client):
    http,_,_,token=client
    assert http.post('/v1/remote-read/requests',content=b'x'*257,headers={**auth(token),'Content-Type':'application/json'}).status_code==400
    duplicate=[('Authorization','Bearer '+token),('Authorization','Bearer '+token)]
    assert http.post('/v1/remote-read/requests',json={'action':'memory_snapshot'},headers=duplicate).status_code==400
    for _ in range(121):
        response=http.get('/v1/remote-read/requests/'+'a'*32,headers=auth(token))
    assert response.status_code==429


def test_asgi_body_mismatch_bound_and_duplicate_host_reject():
    async def check(body, length, expected, duplicate=False):
        called=[];sent=[]
        async def next_app(*_):
            called.append(1)
        guard=mod.Boundary(next_app,'aether.example')
        headers=[(b'host',b'aether.example'),(b'authorization',b'Bearer '+b'x'*48),(b'content-length',str(length).encode()),(b'content-type',b'application/json')]
        if duplicate:headers.append((b'host',b'aether.example'))
        scope={'type':'http','scheme':'https','path':'/v1/remote-read/requests','method':'POST','headers':headers,'query_string':b''}
        async def receive():return {'type':'http.request','body':body,'more_body':False}
        async def send(item):sent.append(item)
        await guard(scope,receive,send)
        assert not called and sent[0]['status']==expected
    asyncio.run(check(b'x'*300,2,413))
    asyncio.run(check(b'x',2,400))
    asyncio.run(check(b'{}',2,404,True))


@pytest.mark.parametrize('host',['https://host.example','*.example.com','localhost','EXAMPLE.com','host.example:443','192.168.1.999','host.example/path','user@host.example','-host.example','host..example','[::1]'])
def test_bad_host_refused(host):
    with pytest.raises(ValueError):mod.make_app(host)


def test_launch_plan_offline_precise_certificate(certificates):
    cert,key=certificates()
    plan=mod.launch_plan('192.168.1.2','192.168.1.2',cert,key)
    assert plan['port']==443 and len(plan['certificate_sha256'])==64
    assert 'PRIVATE KEY' not in json.dumps(plan) and str(key) not in json.dumps(plan)
    cert,key=certificates('aether.example')
    assert mod.launch_plan('10.0.0.4','aether.example',cert,key)['host']=='aether.example'


@pytest.mark.parametrize('bind',['0.0.0.0','127.0.0.1','8.8.8.8','169.254.1.2','224.0.0.1','100.64.0.1','::1'])
def test_no_wildcard_public_loopback_linklocal_multicast_or_cgnat_launch(certificates,bind):
    cert,key=certificates()
    with pytest.raises(ValueError):mod.launch_plan(bind,'192.168.1.2',cert,key)


def test_certificate_expiry_mismatch_key_san_and_ip_bind_refused(certificates):
    for settings in [{'expired':True},{'mismatch':True},{'san':False},{'ca':True},{'server':False}]:
        cert,key=certificates(**settings)
        with pytest.raises((ValueError,ssl.SSLError,x509.ExtensionNotFound)):
            mod.launch_plan('192.168.1.2','192.168.1.2',cert,key)
    cert,key=certificates()
    with pytest.raises(ValueError):mod.launch_plan('192.168.1.3','192.168.1.2',cert,key)
    with pytest.raises(ValueError):mod.launch_plan('192.168.1.2','other.example',cert,key)


def test_main_default_is_offline_no_uvicorn_or_network(certificates,monkeypatch,capsys):
    cert,key=certificates()
    monkeypatch.setattr(sys,'argv',['remote-read-https','--bind','192.168.1.2','--host','192.168.1.2','--cert',str(cert),'--key',str(key)])
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(isatty=lambda:False))
    import uvicorn
    monkeypatch.setattr(uvicorn,'run',lambda *a,**k:pytest.fail('No listener allowed'))
    mod.main()
    assert 'Phone trust' in capsys.readouterr().out


def test_launch_exact_tty_approval_and_hardened_fixed_server_args(certificates,monkeypatch):
    cert,key=certificates()
    monkeypatch.setattr(sys,'argv',['remote-read-https','--bind','192.168.1.2','--host','192.168.1.2','--cert',str(cert),'--key',str(key),'--serve'])
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(isatty=lambda:True));monkeypatch.setattr(sys,'stdout',SimpleNamespace(isatty=lambda:True,write=lambda _:None,flush=lambda:None))
    import uvicorn
    calls=[];monkeypatch.setattr(uvicorn,'run',lambda *a,**k:calls.append((a,k)))
    monkeypatch.setattr('builtins.input',lambda _: 'yes')
    with pytest.raises(SystemExit):mod.main()
    assert not calls
    monkeypatch.setattr('builtins.input',lambda _: 'EXPOSE READ-ONLY 192.168.1.2:443')
    mod.main()
    args,values=calls[0]
    assert isinstance(args[0],mod.Boundary)
    assert values['host']=='192.168.1.2' and values['port']==443
    assert values['workers']==1 and not values['proxy_headers'] and not values['access_log'] and not values['server_header']
    assert values['limit_concurrency']==16 and values['timeout_keep_alive']==5


def test_real_loopback_https_trust_hostname_and_no_plaintext(tmp_path, certificates, monkeypatch):
    import socket
    import threading
    import time
    import httpx
    import uvicorn
    cert,key=certificates('127.0.0.1')
    monkeypatch.setenv('JARVIS_AGENT_APPROVAL_DB',str(tmp_path/'tls-store.db'))
    store=RemoteReadStore();_,token=store.provision_local()
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    config=uvicorn.Config(mod.make_app('127.0.0.1'),host='127.0.0.1',port=port,ssl_certfile=str(cert),ssl_keyfile=str(key),ssl_version=ssl.PROTOCOL_TLS_SERVER,proxy_headers=False,access_log=False,log_level='critical')
    config.load()
    assert config.ssl.minimum_version >= ssl.TLSVersion.TLSv1_2
    server=uvicorn.Server(config)
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
    thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started and thread.is_alive() and time.monotonic()<deadline:
            time.sleep(0.01)
        assert server.started
        context=ssl.create_default_context(cafile=str(cert))
        with httpx.Client(verify=context,trust_env=False,timeout=3) as http:
            headers={**auth(token),'Host':'127.0.0.1'}
            result=http.post(f'https://127.0.0.1:{port}/v1/remote-read/requests',headers=headers,json={'action':'memory_snapshot'})
            assert result.status_code==201 and result.json()['state']=='pending_local_review'
            assert result.json()['executed'] is False
            with pytest.raises(httpx.ConnectError):
                http.get(f'https://localhost:{port}/v1/remote-read/requests/'+'a'*32,headers=headers)
        with httpx.Client(trust_env=False,timeout=3) as untrusted:
            with pytest.raises(httpx.ConnectError):
                untrusted.get(f'https://127.0.0.1:{port}/v1/remote-read/requests/'+'a'*32)
    finally:
        server.should_exit=True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()


def test_no_noninteractive_serve_or_config_change_after_review(certificates,monkeypatch):
    cert,key=certificates()
    monkeypatch.setattr(sys,'argv',['remote-read-https','--bind','192.168.1.2','--host','192.168.1.2','--cert',str(cert),'--key',str(key),'--serve'])
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(isatty=lambda:False))
    import uvicorn
    monkeypatch.setattr(uvicorn,'run',lambda *a,**k:pytest.fail('No launch'))
    with pytest.raises(SystemExit):mod.main()
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(isatty=lambda:True));monkeypatch.setattr(sys,'stdout',SimpleNamespace(isatty=lambda:True,write=lambda _:None,flush=lambda:None))
    def change(_):
        certificates()
        return 'EXPOSE READ-ONLY 192.168.1.2:443'
    monkeypatch.setattr('builtins.input',change)
    with pytest.raises(SystemExit):mod.main()


def test_websocket_no_upgrade_or_app_dispatch():
    sent=[]
    async def app(*_):pytest.fail('No upgrade')
    async def receive():pytest.fail('No read')
    async def send(item):sent.append(item)
    asyncio.run(mod.Boundary(app,'aether.example')({'type':'websocket'},receive,send))
    assert sent==[{'type':'websocket.close','code':1008}]


def test_body_deadline_refuses_without_app_dispatch(monkeypatch):
    async def run():
        sent=[]
        async def app(*_):pytest.fail('No dispatch')
        async def receive():return {'type':'http.request','body':b'{}','more_body':False}
        async def send(item):sent.append(item)
        async def timed_out(coroutine,timeout):
            coroutine.close()
            assert 0 < timeout <= 5
            raise asyncio.TimeoutError
        monkeypatch.setattr(mod.asyncio,'wait_for',timed_out)
        scope={'type':'http','scheme':'https','path':'/v1/remote-read/requests','method':'POST','headers':[(b'host',b'aether.example'),(b'authorization',b'Bearer '+b'x'*48),(b'content-length',b'2'),(b'content-type',b'application/json')],'query_string':b''}
        await mod.Boundary(app,'aether.example')(scope,receive,send)
        assert sent[0]['status']==408
    asyncio.run(run())
