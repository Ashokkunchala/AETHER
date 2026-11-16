"""Credential identity, revocation and fail-closed approval regression tests."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app import ws
from app.core.auth import token_auth
from app.core.ws_sessions import SessionIdentity, TicketStore
from app.main_enhanced import app

MASTER = 'mock-master-token-for-websocket-tests-only-123456'


@pytest.fixture(autouse=True)
def isolated_auth(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_API_TOKEN', MASTER)
    monkeypatch.setenv('JARVIS_DB_PATH', str(tmp_path / 'auth.sqlite3'))
    from app.core.config import get_settings
    get_settings.cache_clear()
    token_auth._init_device_table()
    monkeypatch.setattr(ws, '_tickets', TicketStore())
    yield
    get_settings.cache_clear()


def identity(token=MASTER):
    return SessionIdentity.authenticate(f'Bearer {token}')


def ticket(client, token=MASTER):
    result = client.post('/api/ws-ticket', headers={'Authorization': f'Bearer {token}'})
    assert result.status_code == 200
    return result.json()['ticket']


def fake_brain(monkeypatch):
    class Registry:
        def __len__(self):
            return 0

    class Brain:
        registry = Registry()
        active_model = 'mock'
        configured = True

        def provider_candidates(self):
            return []

        async def ask(self, message, confirm, auto_approve):
            assert auto_approve is False
            approved = await confirm(SimpleNamespace(name='mock', description='Mock only',
                                                      category='test', risk=SimpleNamespace(name='HIGH')),
                                     {'value': message})
            yield {'type': 'done', 'approved': approved}

    monkeypatch.setattr(ws, 'JarvisBrain', Brain)


def test_ticket_expiry_and_capacity(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr('app.core.ws_sessions.time.monotonic', lambda: clock[0])
    store = TicketStore(ttl=5, capacity=1)
    issued = store.issue(identity())
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        store.issue(identity())
    clock[0] = 15.0
    assert store.consume(issued) is None
    fresh = store.issue(identity())
    assert store.consume(fresh).kind == 'legacy'
    assert store.consume(fresh) is None


def test_ticket_is_bound_to_revocable_device():
    device = token_auth.issue_device_token('mock phone')
    session = identity(device['token'])
    store = TicketStore()
    issued = store.issue(session)
    assert session.device_id == device['device_id']
    assert device['token'] not in repr(session)
    token_auth.revoke_device(device['device_id'])
    assert not session.is_active()
    assert store.consume(issued) is None


def test_master_rotation_invalidates_issued_ticket(monkeypatch):
    store = TicketStore()
    issued = store.issue(identity())
    monkeypatch.setenv('JARVIS_API_TOKEN', 'rotated-master-token-for-websocket-tests-123456')
    assert store.consume(issued) is None


@pytest.mark.parametrize('frame', [
    {'type': 'approve', 'id': 'one'},
    {'type': 'approve', 'id': 'one', 'approved': 'false'},
    {'type': 'approve', 'id': 'one', 'approved': 1},
    {'type': 'approve', 'id': 'one', 'approved': None},
    {'type': 'approve', 'id': 'one', 'approved': True, 'actor': 'other'},
    {'type': 'chat', 'message': 'x', 'auto_approve': 'yes'},
])
def test_approval_frames_are_strict(frame):
    with pytest.raises(ValidationError):
        ws.IncomingFrame.model_validate(frame)


def test_malformed_frame_does_not_approve_and_replay_fails(monkeypatch):
    fake_brain(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect('/ws?ticket=' + ticket(client)) as socket:
            assert socket.receive_json()['type'] == 'ready'
            socket.send_json({'type': 'chat', 'message': 'mock only'})
            prompt = socket.receive_json()
            socket.send_json({'type': 'approve', 'id': prompt['id'], 'approved': 'false'})
            assert socket.receive_json()['error'] == 'invalid frame'
            socket.send_json({'type': 'approve', 'id': prompt['id'], 'approved': False})
            assert socket.receive_json() == {'type': 'done', 'approved': False}
            socket.send_json({'type': 'approve', 'id': prompt['id'], 'approved': True})
            assert socket.receive_json()['error'] == 'unknown or expired approval'


def test_revocation_after_prompt_prevents_approval(monkeypatch):
    fake_brain(monkeypatch)
    device = token_auth.issue_device_token('mock phone')
    with TestClient(app) as client:
        with client.websocket_connect('/ws?ticket=' + ticket(client, device['token'])) as socket:
            socket.receive_json()
            socket.send_json({'type': 'chat', 'message': 'mock only'})
            prompt = socket.receive_json()
            token_auth.revoke_device(device['device_id'])
            socket.send_json({'type': 'approve', 'id': prompt['id'], 'approved': True})
            with pytest.raises(WebSocketDisconnect) as exc:
                socket.receive_json()
            assert exc.value.code == 4401


def test_approval_from_another_session_is_refused(monkeypatch):
    fake_brain(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect('/ws?ticket=' + ticket(client)) as first:
            first.receive_json()
            first.send_json({'type': 'chat', 'message': 'mock only'})
            prompt = first.receive_json()
            with client.websocket_connect('/ws?ticket=' + ticket(client)) as second:
                second.receive_json()
                second.send_json({'type': 'approve', 'id': prompt['id'], 'approved': True})
                assert second.receive_json()['error'] == 'unknown or expired approval'
            first.send_json({'type': 'approve', 'id': prompt['id'], 'approved': True})
            assert first.receive_json() == {'type': 'done', 'approved': True}


def test_unanswered_approval_times_out_closed(monkeypatch):
    fake_brain(monkeypatch)
    monkeypatch.setattr(ws, '_APPROVAL_TIMEOUT_SECONDS', 0.02)
    with TestClient(app) as client:
        with client.websocket_connect('/ws?ticket=' + ticket(client)) as socket:
            socket.receive_json()
            socket.send_json({'type': 'chat', 'message': 'mock only'})
            prompt = socket.receive_json()
            assert prompt['type'] == 'confirm'
            assert socket.receive_json() == {'type': 'done', 'approved': False}
