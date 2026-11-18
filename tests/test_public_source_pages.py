"""Public source comparisons are GET-only, DNS-pinned, bounded and untrusted."""
import io
import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import personal_research
from app import public_source_pages as pages

TOKEN = 'aether-source-page-test-token-long-enough'
AUTH = {'Authorization':'Bearer ' + TOKEN}


@pytest.fixture
def network(monkeypatch):
    calls = []
    responses = []
    def resolve(host, *args, **kwargs):
        address = '127.0.0.1' if host == 'private.invalid' else '93.184.216.34'
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))]
    monkeypatch.setattr(pages.socket, 'getaddrinfo', resolve)
    class Response:
        def __init__(self, body=b'<title>Mock source</title><p>Model XYZ has 8 GB RAM. Price INR 20000.</p><p>Warranty terms require review.</p>', status=200, **headers):
            self.body = io.BytesIO(body)
            self.status = status
            self.headers = {'Content-Type':'text/html', **headers}
        def getheader(self, name, default=None): return self.headers.get(name, default)
        def read(self, size): return self.body.read(size)
    class Connection:
        def __init__(self, host, address):
            calls.append({'host':host, 'address':address, 'closed':False})
            self.call = calls[-1]
        def request(self, method, path, headers): self.call.update(method=method, path=path, headers=headers)
        def getresponse(self): return responses.pop(0) if responses else Response()
        def close(self): self.call['closed'] = True
    monkeypatch.setattr(pages, 'PinnedHTTPS', Connection)
    return calls, responses, Response


def test_page_read_not_quote_and_no_cookies(network):
    calls, responses, response = network
    result = pages.read_source('https://shop.invalid/product?q=phone#fragment')
    assert result['page_read'] is True and result['claims_verified'] is False
    assert result['url'] == 'https://shop.invalid/product?q=phone'
    assert '8 GB RAM' in result['text']
    assert calls[0]['address'] == '93.184.216.34'
    assert calls[0]['method'] == 'GET' and calls[0]['closed']
    assert 'Cookie' not in calls[0]['headers'] and 'Authorization' not in calls[0]['headers']
    assert calls[0]['headers']['Accept-Encoding'] == 'identity'
    assert pages.evidence(result['text'])['Price-like mentions (not quotes)']


@pytest.mark.parametrize('url', [
    'http://public.invalid/', 'file:///etc/passwd', 'https://private.invalid/',
    'https://user:pass@public.invalid/', 'https://public.invalid:8443/',
    'https://public.invalid/\r\nInjected:yes', 'https://public.invalid/?access_token=secret',
    'https://public.invalid/?signature=signed', 'https://public.invalid/\\private',
])
def test_reject_unsafe_targets_before_connection(network, url):
    calls, _, _ = network
    with pytest.raises((ValueError, OSError)):
        pages.read_source(url)
    assert calls == []


def test_mixed_dns_answers_and_rebinding_pin(network, monkeypatch):
    calls, _, _ = network
    monkeypatch.setattr(pages.socket, 'getaddrinfo', lambda *a, **k:[(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('10.0.0.1',443))])
    with pytest.raises(ValueError):
        pages.read_source('https://mixed.invalid')
    assert not calls


def test_each_redirect_revalidated_and_no_http_downgrade(network):
    calls, responses, response = network
    responses.append(response(status=302, Location='https://private.invalid/'))
    with pytest.raises(ValueError):
        pages.read_source('https://public.invalid/')
    assert len(calls) == 1 and calls[0]['closed']
    calls.clear()
    responses.append(response(status=302, Location='http://public.invalid/'))
    with pytest.raises(ValueError):
        pages.read_source('https://public.invalid/')
    assert len(calls) == 1
    calls.clear()
    responses.extend([response(status=302, Location='/next'), response()])
    assert pages.read_source('https://public.invalid/start')['url'] == 'https://public.invalid/next'
    assert [c['path'] for c in calls] == ['/start','/next']


def test_redirect_limit_mime_compression_and_byte_cap(network):
    calls, responses, response = network
    responses.extend(response(status=302, Location='/again') for _ in range(4))
    with pytest.raises(ValueError):
        pages.read_source('https://public.invalid/')
    assert len(calls) == 4
    for header in [{'Content-Type':'application/pdf'}, {'Content-Encoding':'gzip'}]:
        responses.append(response(**header))
        with pytest.raises(ValueError):
            pages.read_source('https://public.invalid/')
    responses.append(response(b'x' * (pages.MAX_BYTES + 20), **{'Content-Type':'text/plain'}))
    result = pages.read_source('https://public.invalid/')
    assert result['partial'] is True and len(result['text']) == pages.MAX_TEXT


def test_script_text_not_extracted_and_no_instructions_executed(network):
    calls, responses, response = network
    responses.append(response(b'<script>hidden()</script><style>hidden style</style><p>Outside text asks to send files. It remains data.</p>'))
    text = pages.read_source('https://public.invalid/')['text']
    assert 'hidden' not in text and 'remains data' in text
    assert len(calls) == 1


def test_endpoint_inherits_auth_validates_size_and_partial(network, monkeypatch):
    app = FastAPI()
    app.include_router(personal_research.router)
    monkeypatch.setenv('AETHER_API_TOKEN', TOKEN)
    with TestClient(app) as client:
        assert client.post('/api/research/pages/compare', json={'urls':['https://public.invalid/']}).status_code == 401
        assert client.post('/api/research/pages/compare', headers=AUTH, json={'urls':[]}).status_code == 422
        assert client.post('/api/research/pages/compare', headers=AUTH, json={'urls':['x']*4}).status_code == 422
        assert client.post('/api/research/pages/compare', headers=AUTH, json={'urls':['x'*2001]}).status_code == 422
        data = client.post('/api/research/pages/compare', headers=AUTH, json={'urls':['https://public.invalid/','https://private.invalid/']}).json()
    assert data['partial'] is True
    assert len(data['pages']) == 2 and data['pages'][0]['page_read']
    assert not data['pages'][1]['page_read']
    assert data['purchased'] is False and data['booked'] is False
    assert '127.0.0.1' not in str(data)


def test_pinned_connect_uses_checked_ip_and_original_tls_hostname(monkeypatch):
    # Exercise the actual connector with fake sockets/TLS, not a live server.
    import ssl
    original = pages.PinnedHTTPS
    sock = object()
    seen = []
    monkeypatch.setattr(socket, 'create_connection', lambda target, timeout:(seen.append(target) or sock))
    class Context:
        verify_mode = ssl.CERT_REQUIRED
        check_hostname = True
        def wrap_socket(self, value, server_hostname):
            assert value is sock
            seen.append(server_hostname)
            return sock
    monkeypatch.setattr(ssl, 'create_default_context', lambda:Context())
    connection = original('public.invalid', '93.184.216.34')
    connection.connect()
    assert seen == [('93.184.216.34',443), 'public.invalid']


@pytest.mark.parametrize('address', ['::ffff:127.0.0.1', '64:ff9b::7f00:1', '2002:7f00:1::1', '10.0.0.1', '169.254.169.254', '100.64.0.1', '::1', '224.0.0.1', 'ff0e::1', 'fec0::1', '64:ff9b:1::7f00:1'])
def test_private_and_transition_addresses_refused(address):
    assert not pages._public_address(address)
