"""Companion API/local approval tests. Never open a real browser/device."""
import concurrent.futures
import io

import pytest
from fastapi.testclient import TestClient

from windows_agent.agent import app
from windows_agent.local_approval import LocalApprovalStore, main, validate_url

TOKEN='test-token-that-is-at-least-32-characters'
HEADERS={'Authorization':'Bearer '+TOKEN}


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('AETHER_AGENT_TOKEN',TOKEN)
    monkeypatch.setenv('AETHER_ALLOWED_URL_HOSTS','github.com')
    monkeypatch.setenv('AETHER_AGENT_APPROVAL_DB',str(tmp_path/'approval.db'))
    opened=[]
    monkeypatch.setattr('windows_agent.agent.webbrowser.open',lambda url,new=0:opened.append(url) or True)
    return LocalApprovalStore(),opened


def test_agent_requires_token(monkeypatch):
    monkeypatch.delenv('AETHER_AGENT_TOKEN',raising=False)
    with TestClient(app) as c:assert c.get('/v1/status').status_code==503


def test_caller_boolean_not_authority_and_no_approval_endpoint(setup):
    _,opened=setup
    with TestClient(app) as c:
        assert c.post('/v1/open-url',headers=HEADERS,json={'url':'https://github.com','confirmed':True}).status_code==422
        assert c.post('/v1/request-url',headers=HEADERS,json={'url':'https://github.com','confirmed':True}).status_code==422
        assert c.post('/v1/approve',headers=HEADERS,json={'approved':True}).status_code==404
    assert not opened


def test_requires_local_exact_review_once(setup):
    store,opened=setup
    with TestClient(app) as c:
        data=c.post('/v1/request-url',headers=HEADERS,json={'url':'https://github.com'}).json()
        key=data['request_id'];payload={'url':'https://github.com','request_id':key}
        assert not data['opened'] and not opened
        assert c.post('/v1/open-url',headers=HEADERS,json=payload).status_code==409
        assert store.inspect(key)=='https://github.com'
        store.decide_local(key,'https://github.com',True)
        assert c.post('/v1/open-url',headers=HEADERS,json={**payload,'url':'https://github.com/other'}).status_code==409
        result=c.post('/v1/open-url',headers=HEADERS,json=payload)
        assert result.status_code==200 and not result.json()['page_loaded_verified']
        assert c.post('/v1/open-url',headers=HEADERS,json=payload).status_code==409
    assert opened==['https://github.com']


@pytest.mark.parametrize('url',['http://github.com','https://github.com.evil','https://sub.github.com','https://user:pass@github.com','https://github.com:8443','https://github.com\n','https://github.com\\evil','https://github.com/a b','file:///tmp/a'])
def test_invalid_or_unapproved_url_denied(setup,url):
    _,opened=setup
    with pytest.raises(ValueError):validate_url(url)
    assert not opened


def test_empty_default_allowlist(setup,monkeypatch):
    monkeypatch.delenv('AETHER_ALLOWED_URL_HOSTS')
    with pytest.raises(ValueError):validate_url('https://github.com')


def test_expiry_rejection_rotation_revocation(setup,monkeypatch):
    store,_=setup
    key=store.request('https://github.com');store.decide_local(key,'https://github.com',False)
    with pytest.raises(ValueError):store.consume(key,'https://github.com')
    key=store.request('https://github.com');store.decide_local(key,'https://github.com',True)
    monkeypatch.setenv('AETHER_AGENT_TOKEN','rotated-token-that-is-also-at-least-32-characters')
    with pytest.raises(ValueError):store.consume(key,'https://github.com')
    monkeypatch.setenv('AETHER_AGENT_TOKEN',TOKEN)
    store.set_stop(True);store.set_stop(False)
    with pytest.raises(ValueError):store.consume(key,'https://github.com')
    key=store.request('https://github.com')
    with store.connect() as db:db.execute('UPDATE url_requests SET expires=0 WHERE id=?',(key,))
    with pytest.raises(ValueError):store.decide_local(key,'https://github.com',True)


def test_allowlist_change_and_stop_before_execution(setup,monkeypatch):
    store,opened=setup
    key=store.request('https://github.com');store.decide_local(key,'https://github.com',True)
    monkeypatch.setenv('AETHER_ALLOWED_URL_HOSTS','example.com')
    with pytest.raises(ValueError):store.consume(key,'https://github.com')
    monkeypatch.setenv('AETHER_ALLOWED_URL_HOSTS','github.com');store.set_stop(True)
    with pytest.raises(ValueError):store.consume(key,'https://github.com')
    with pytest.raises(ValueError):store.request('https://github.com')
    assert not opened


def test_concurrent_consumption_single_winner(setup):
    store,_=setup
    key=store.request('https://github.com');store.decide_local(key,'https://github.com',True)
    def consume(_):
        try:store.consume(key,'https://github.com');return True
        except ValueError:return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:assert sum(pool.map(consume,range(6)))==1


def test_os_failure_consumes_approval_no_retry(setup,monkeypatch):
    store,_=setup
    key=store.request('https://github.com');store.decide_local(key,'https://github.com',True)
    monkeypatch.setattr('windows_agent.agent.webbrowser.open',lambda *a,**kw:False)
    with TestClient(app) as c:
        payload={'url':'https://github.com','request_id':key}
        assert c.post('/v1/open-url',headers=HEADERS,json=payload).status_code==502
        assert c.post('/v1/open-url',headers=HEADERS,json=payload).status_code==409


def test_pending_limit_and_token_not_stored(setup):
    store,_=setup
    for _ in range(100):store.request('https://github.com')
    with pytest.raises(ValueError):store.request('https://github.com')
    assert TOKEN.encode() not in store.path.read_bytes()


def test_noninteractive_approval_refused(setup,monkeypatch):
    store,_=setup;key=store.request('https://github.com')
    monkeypatch.setattr('sys.stdin',io.StringIO('OPEN\n'))
    with pytest.raises(SystemExit):main(['review',key])
    with pytest.raises(ValueError):store.consume(key,'https://github.com')


def test_interactive_review_shows_exact_target_and_denies_by_default(setup,monkeypatch,capsys):
    store,_=setup;key=store.request('https://github.com/a?b=c')
    class TTY(io.StringIO):
        def isatty(self):return True
    monkeypatch.setattr('sys.stdin',TTY());out=TTY();monkeypatch.setattr('sys.stdout',out)
    monkeypatch.setattr('builtins.input',lambda _: 'no')
    main(['review',key])
    assert 'https://github.com/a?b=c' in out.getvalue()
    with pytest.raises(ValueError):store.consume(key,'https://github.com/a?b=c')
