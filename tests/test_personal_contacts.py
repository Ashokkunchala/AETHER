"""Google Contacts tests use synthetic records and mocked HTTP only."""
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import integrations, personal_contacts

TOKEN = 'aether-contacts-test-token-at-least-32-characters'
AUTH = {'Authorization': 'Bearer ' + TOKEN}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('AETHER_API_TOKEN', TOKEN)
    monkeypatch.setenv('AETHER_DB_PATH', str(tmp_path / 'contacts.db'))
    monkeypatch.setattr(integrations.settings, 'aether_db_path', str(tmp_path / 'contacts.db'))
    monkeypatch.setattr(integrations.settings, 'secret_key', TOKEN)
    monkeypatch.setattr(integrations.settings, 'google_oauth_client_id', 'mock-client')
    monkeypatch.setattr(integrations.settings, 'google_oauth_client_secret', 'mock-secret')
    monkeypatch.setattr(integrations.settings, 'google_oauth_redirect_uri', 'http://localhost/api/integrations/google/callback')
    app = FastAPI()
    app.include_router(personal_contacts.router)
    app.include_router(integrations.router)
    with TestClient(app) as result:
        yield result


def authorize(monkeypatch, scope=personal_contacts.CONTACTS_SCOPE):
    monkeypatch.setattr(integrations, '_provider', lambda _: {'scope': scope})
    async def access():
        return 'mock-access-token'
    monkeypatch.setattr(integrations, '_google_access_token', access)


def mock_api(monkeypatch, status=200, payload=None):
    requests = []
    original = httpx.AsyncClient
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json=payload if payload is not None else {'results': []})
    monkeypatch.setattr(personal_contacts.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    sleeps = []
    async def wait(seconds):
        sleeps.append(seconds)
    monkeypatch.setattr(personal_contacts.asyncio, 'sleep', wait)
    return requests, sleeps


def test_contacts_scope_is_explicit_opt_in_not_default(client):
    base = client.get('/api/integrations/google/connect', headers=AUTH)
    assert base.status_code == 200
    params = parse_qs(urlparse(base.json()['authorization_url']).query)
    assert personal_contacts.CONTACTS_SCOPE not in params['scope'][0]
    opted = client.get('/api/integrations/google/connect?include_contacts=true', headers=AUTH)
    params = parse_qs(urlparse(opted.json()['authorization_url']).query)
    assert personal_contacts.CONTACTS_SCOPE in params['scope'][0]
    assert 'state' in params and params['prompt'] == ['consent']


def test_auth_and_grant_required_before_network(client, monkeypatch):
    assert client.get('/api/contacts/search?q=Mock').status_code == 401
    authorize(monkeypatch, 'https://www.googleapis.com/auth/gmail.readonly')
    requests, _ = mock_api(monkeypatch)
    assert client.get('/api/contacts/search?q=Mock', headers=AUTH).status_code == 409
    assert client.get('/api/contacts/status', headers=AUTH).json()['authorized'] is False
    assert requests == []


def test_warmup_then_prefix_search_returns_separate_bounded_contacts(client, monkeypatch):
    authorize(monkeypatch)
    person = {'resourceName': 'people/mock', 'names': [{'displayName': '<script>Mock</script>'}], 'emailAddresses': [{'value': 'mock@example.invalid'}], 'phoneNumbers': [{'value': '+10000000000'}], 'organizations': [{'name': 'Test only'}], 'biographies': [{'value': 'Must not return'}]}
    requests, sleeps = mock_api(monkeypatch, payload={'results': [{'person': person}] * 3})
    response = client.get('/api/contacts/search?q=Mo&limit=2', headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data['items']) == 2
    assert data['items'][0]['names'] == ['<script>Mock</script>']
    assert 'biographies' not in data['items'][0]
    assert [r.url.params['query'] for r in requests] == ['', 'Mo']
    assert all(r.method == 'GET' and r.url.host == 'people.googleapis.com' for r in requests)
    assert all(r.url.params['readMask'] == personal_contacts.READ_MASK for r in requests)
    assert sleeps == [5]
    assert 'mock-access-token' not in response.text
    assert 'not a full address book' in data['notice'].lower()


@pytest.mark.parametrize('code,expected', [(401,409), (403,409), (429,429), (500,502)])
def test_provider_errors_are_actionable_and_redacted(client, monkeypatch, code, expected):
    authorize(monkeypatch)
    requests, _ = mock_api(monkeypatch, code, {'error': 'mock-access-token private provider detail'})
    response = client.get('/api/contacts/search?q=Mo', headers=AUTH)
    assert response.status_code == expected
    assert 'mock-access-token' not in response.text
    assert len(requests) == 1


def test_empty_search_and_over_limit_rejected(client, monkeypatch):
    authorize(monkeypatch)
    requests, _ = mock_api(monkeypatch)
    for query in ['?q=  ', '?q=Mo&limit=31', '?q=']:
        assert client.get('/api/contacts/search' + query, headers=AUTH).status_code == 422
    assert requests == []
