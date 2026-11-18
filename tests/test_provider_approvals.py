"""Mocked provider boundary tests. Never contact Google or Meta."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import integrations, provider_approvals
from app.core.auth import token_auth
from aether.security import SecurityStore

TOKEN = 'aether-provider-approval-test-token-long-enough'
AUTH = {'Authorization': 'Bearer ' + TOKEN}


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv('AETHER_API_TOKEN', TOKEN)
    monkeypatch.setenv('AETHER_DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'security.db'))
    monkeypatch.setattr(integrations.settings, 'aether_db_path', str(tmp_path / 'test.db'))
    monkeypatch.setattr(integrations.settings, 'secret_key', 'test-secret-key-with-at-least-32-chars')
    monkeypatch.setattr(integrations.settings, 'whatsapp_access_token', 'synthetic-only')
    monkeypatch.setattr(integrations.settings, 'whatsapp_phone_number_id', 'synthetic-phone-id')
    token_auth._init_device_table()
    app = FastAPI()
    app.include_router(integrations.router)
    sends = []

    async def fake_send(payload):
        sends.append(payload)
        return {'id': 'mock-only'}
    monkeypatch.setattr(integrations, '_send_gmail', fake_send)
    monkeypatch.setattr(integrations, '_send_whatsapp', fake_send)
    with TestClient(app) as client:
        yield client, sends


def draft(client, headers=AUTH):
    result = client.post('/api/integrations/gmail/drafts', headers=headers,
                         json={'to': 'test@example.invalid', 'subject': 'Mock', 'body': 'Exact mock body'})
    assert result.status_code == 201, result.text
    return result.json()


def approve(client, key, headers=AUTH):
    return client.post(f'/api/integrations/approvals/{key}/approve', headers=headers)


def test_bound_single_use_and_no_hash_disclosure(env):
    client, sends = env
    data = draft(client)
    assert data['expires_at']
    listed = client.get('/api/integrations/approvals', headers=AUTH)
    assert 'requester_hash' not in listed.text and 'account_binding' not in listed.text
    assert approve(client, data['id']).status_code == 200
    assert approve(client, data['id']).status_code == 404
    assert sends == [data['payload']]
    assert provider_approvals.execution_check.get() is None


def test_other_device_cannot_list_approve_or_reject(env):
    client, sends = env
    first = token_auth.issue_device_token('first')
    second = token_auth.issue_device_token('second')
    a = {'Authorization': 'Bearer ' + first['token']}
    b = {'Authorization': 'Bearer ' + second['token']}
    key = draft(client, a)['id']
    assert client.get('/api/integrations/approvals', headers=b).json()['items'] == []
    assert approve(client, key, b).status_code == 404
    assert client.post(f'/api/integrations/approvals/{key}/reject', headers=b).status_code == 404
    assert approve(client, key, a).status_code == 200
    assert len(sends) == 1


@pytest.mark.parametrize('expiry', ['2000-01-01T00:00:00+00:00', '', 'not-a-date', '2099-01-01T00:00:00'])
def test_expired_or_malformed_expiry_never_sends(env, expiry):
    client, sends = env
    key = draft(client)['id']
    with integrations._connect() as db:
        db.execute('UPDATE approval_requests SET expires_at=? WHERE id=?', (expiry, key))
    assert approve(client, key).status_code == 409
    assert not sends


def test_legacy_unbound_rows_are_not_upgraded(env):
    client, sends = env
    with integrations._connect() as db:
        db.execute("INSERT INTO approval_requests(provider,action,payload_json,created_at) VALUES('gmail','send','{}',?)", (integrations._now(),))
        key = db.execute('SELECT max(id) FROM approval_requests').fetchone()[0]
    assert approve(client, key).status_code == 404
    assert client.get('/api/integrations/approvals', headers=AUTH).json()['items'] == []
    assert not sends


def test_rotation_revocation_and_stop(env, monkeypatch):
    client, sends = env
    key = draft(client)['id']
    SecurityStore().set_stop(True)
    assert approve(client, key).status_code == 409
    assert client.post('/api/integrations/gmail/drafts', headers=AUTH, json={'to':'a@b.invalid','subject':'Mock','body':'Mock'}).status_code == 409
    SecurityStore().set_stop(False)
    monkeypatch.setenv('AETHER_API_TOKEN', TOKEN + 'rotated')
    assert approve(client, key).status_code == 401
    monkeypatch.setenv('AETHER_API_TOKEN', TOKEN)
    device = token_auth.issue_device_token('revoked')
    headers = {'Authorization': 'Bearer ' + device['token']}
    key = draft(client, headers)['id']
    with integrations._connect() as db:
        db.execute('UPDATE devices SET revoked_at=? WHERE device_id=?', (integrations._now(), device['device_id']))
    assert approve(client, key, headers).status_code == 401
    assert not sends


def test_google_reconnect_disconnect_and_token_refresh(env):
    client, sends = env
    credentials = {'access_token':'mock','refresh_token':'mock-refresh', 'expires_at':(datetime.now(UTC)+timedelta(hours=1)).isoformat()}
    integrations._save_provider('google', credentials, new_generation=True)
    key = draft(client)['id']
    integrations._save_provider('google', {**credentials, 'access_token':'refreshed'})
    assert approve(client, key).status_code == 200  # Refresh is not reconnect.
    key = draft(client)['id']
    integrations._save_provider('google', credentials, new_generation=True)
    assert approve(client, key).status_code == 409
    assert client.get('/api/integrations/approvals', headers=AUTH).json()['items'] == []
    key = draft(client)['id']
    assert client.post('/api/integrations/google/disconnect', headers=AUTH).status_code == 200
    assert approve(client, key).status_code == 409
    assert len(sends) == 1


def test_whatsapp_config_change_invalidates(env, monkeypatch):
    client, sends = env
    data = client.post('/api/integrations/whatsapp/drafts', headers=AUTH,
                       json={'to':'919876543210', 'body':'Mock only'}).json()
    monkeypatch.setattr(integrations.settings, 'whatsapp_phone_number_id', 'different-phone')
    assert approve(client, data['id']).status_code == 409
    assert not sends


def test_concurrent_approval_claims_send_once(env):
    client, sends = env
    key = draft(client)['id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: approve(client, key).status_code, range(4)))
    assert results.count(200) == 1
    assert len(sends) == 1


def test_safety_store_failure_blocks_send(env, monkeypatch):
    client, sends = env
    key = draft(client)['id']
    def fail(*args):
        raise OSError('mock unavailable')
    monkeypatch.setattr(provider_approvals.SecurityStore, 'stopped', fail)
    assert approve(client, key).status_code == 503
    assert not sends


def test_recheck_after_async_google_refresh_stops_network_write(env, monkeypatch):
    client, sends = env
    key = draft(client)['id']
    posts = []
    async def token():
        SecurityStore().set_stop(True)
        return 'mock-token'
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def request(self, *args, **kwargs):
            posts.append(args)
            raise AssertionError('Network write should never start')
    async def real_boundary(payload):
        return await integrations._google('POST', '/mock', body=payload)
    monkeypatch.setattr(integrations, '_send_gmail', real_boundary)
    monkeypatch.setattr(integrations, '_google_access_token', token)
    monkeypatch.setattr(integrations.httpx, 'AsyncClient', FakeClient)
    assert approve(client, key).status_code == 409
    assert not posts
    assert provider_approvals.execution_check.get() is None


@pytest.mark.parametrize('change', ['revoke', 'reconnect', 'expire'])
def test_changes_during_google_token_wait_block_write(env, monkeypatch, change):
    client, sends = env
    device = token_auth.issue_device_token('changing')
    headers = {'Authorization': 'Bearer ' + device['token']}
    key = draft(client, headers)['id']
    writes = []
    async def token():
        if change == 'revoke':
            token_auth.revoke_device(device['device_id'])
        elif change == 'reconnect':
            integrations._save_provider('google', {'access_token':'mock-new'}, new_generation=True)
        else:
            with integrations._connect() as db:
                db.execute('UPDATE approval_requests SET expires_at=? WHERE id=?', ('2000-01-01T00:00:00+00:00', key))
        return 'mock-token'
    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def request(self, *args, **kwargs):
            writes.append(args)
            raise AssertionError('Unexpected network write')
    async def real_boundary(payload):
        return await integrations._google('POST', '/mock', body=payload)
    monkeypatch.setattr(integrations, '_send_gmail', real_boundary)
    monkeypatch.setattr(integrations, '_google_access_token', token)
    monkeypatch.setattr(integrations.httpx, 'AsyncClient', FakeClient)
    assert approve(client, key, headers).status_code == (401 if change == 'revoke' else 409)
    assert not writes


def test_parallel_schema_upgrade_is_additive(env):
    client, sends = env
    # Force old schema while retaining an unbound pending request from the older writer.
    import sqlite3
    with sqlite3.connect(integrations.settings.aether_db_path) as db:
        db.executescript('''
            CREATE TABLE approval_requests (
              id INTEGER PRIMARY KEY, provider TEXT NOT NULL, action TEXT NOT NULL,
              payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
              result_json TEXT, created_at TEXT NOT NULL, decided_at TEXT);
            CREATE TABLE integration_secrets (
              provider TEXT PRIMARY KEY, encrypted_value TEXT NOT NULL, updated_at TEXT NOT NULL);
            INSERT INTO approval_requests(provider,action,payload_json,created_at)
              VALUES('gmail','send','{}','2026-11-16');
        ''')
    def upgrade(_):
        with integrations._connect() as db:
            return db.execute('SELECT status,requester_hash FROM approval_requests WHERE id=1').fetchone()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(upgrade, range(4)))
    assert all(tuple(row) == ('pending', None) for row in rows)
    assert approve(client, 1).status_code == 404
    assert not sends


def test_stale_google_refresh_cannot_overwrite_reconnected_credentials(env):
    client, sends = env
    integrations._save_provider('google', {'access_token':'old'}, new_generation=True)
    with integrations._connect() as db:
        old_binding = provider_approvals.account(db, 'google', integrations.settings)
    integrations._save_provider('google', {'access_token':'new'}, new_generation=True)
    from fastapi import HTTPException
    with pytest.raises(HTTPException, match='409'):
        integrations._save_provider('google', {'access_token':'stale-refresh'}, expected_binding=old_binding)
    assert integrations._provider('google')['access_token'] == 'new'
    assert not sends
