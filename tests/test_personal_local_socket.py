"""Socket integration uses the real narrow registry and mocked brain, never providers."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import life_manager, ws
from app.core.auth import token_auth
from app.core.ws_sessions import TicketStore

TOKEN = 'aether-local-socket-test-token-at-least-32-characters'


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_API_TOKEN', TOKEN)
    monkeypatch.setenv('JARVIS_DB_PATH', str(tmp_path / 'local.db'))
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'safety.db'))
    token_auth._init_device_table()
    monkeypatch.setattr(ws, '_tickets', TicketStore())
    class Brain:
        active_model = 'mock'
        configured = True
        def __init__(self, registry=None, system_prompt=None):
            self.registry = registry
        def provider_candidates(self):
            return []
        async def ask(self, message, confirm, auto_approve):
            assert auto_approve is False
            result = await self.registry.execute('create_saved_task', {'title': message}, confirm=confirm, auto_approve=True)
            yield {'type': 'done', 'ok': result.ok}
    monkeypatch.setattr(ws, 'JarvisBrain', Brain)
    app = FastAPI()
    app.include_router(ws.router)
    with TestClient(app) as http:
        yield http


def connect(client, profile):
    token = client.post('/api/ws-ticket?profile=' + profile, headers={'Authorization': f'Bearer {TOKEN}'}).json()['ticket']
    return client.websocket_connect('/ws?ticket=' + token + '&profile=personal-local')


def prompt(socket):
    socket.send_json({'type': 'chat', 'message': 'Exact local task'})
    # Registry's lifecycle events aren't forwarded by this mock brain.
    return socket.receive_json()


def test_readonly_cannot_upgrade_through_query_string(client):
    with connect(client, 'personal-readonly') as socket:
        assert socket.receive_json()['tools'] == 8
        assert prompt(socket) == {'type': 'done', 'ok': False}
    assert life_manager.list_tasks()['items'] == []


def test_exact_local_preview_approve_and_replay(client):
    with connect(client, 'personal-local') as socket:
        ready = socket.receive_json()
        assert ready['tools'] == 13 and ready['profile'] == 'personal-local'
        request = prompt(socket)
        assert request['category'] == 'personal_local'
        assert request['args']['_preview']['values']['title'] == 'Exact local task'
        socket.send_json({'type': 'approve', 'id': request['id'], 'approved': True})
        assert socket.receive_json() == {'type': 'done', 'ok': True}
        socket.send_json({'type': 'approve', 'id': request['id'], 'approved': True})
        assert socket.receive_json()['error'] == 'unknown or expired approval'
    assert len(life_manager.list_tasks()['items']) == 1


def test_local_timeout_and_denial_fail_closed(client, monkeypatch):
    monkeypatch.setattr(ws, '_APPROVAL_TIMEOUT_SECONDS', .02)
    with connect(client, 'personal-local') as socket:
        socket.receive_json()
        prompt(socket)
        assert socket.receive_json() == {'type': 'done', 'ok': False}
    assert life_manager.list_tasks()['items'] == []


def test_disconnect_while_waiting_does_not_save(client):
    with connect(client, 'personal-local') as socket:
        socket.receive_json()
        prompt(socket)
    assert life_manager.list_tasks()['items'] == []


def test_local_explicit_denial(client):
    with connect(client, 'personal-local') as socket:
        socket.receive_json()
        request = prompt(socket)
        socket.send_json({'type': 'approve', 'id': request['id'], 'approved': False})
        assert socket.receive_json() == {'type': 'done', 'ok': False}
    assert life_manager.list_tasks()['items'] == []


def test_cancel_pending_write_does_not_save(client):
    with connect(client, 'personal-local') as socket:
        socket.receive_json()
        request = prompt(socket)
        socket.send_json({'type': 'cancel'})
        assert socket.receive_json()['error'] == 'turn cancelled'
        socket.send_json({'type': 'approve', 'id': request['id'], 'approved': True})
        assert socket.receive_json()['error'] == 'unknown or expired approval'
    assert life_manager.list_tasks()['items'] == []


def test_revocation_of_local_session_after_preview(client):
    from starlette.websockets import WebSocketDisconnect
    device = token_auth.issue_device_token('mock local device')
    ticket = client.post('/api/ws-ticket?profile=personal-local', headers={'Authorization': 'Bearer ' + device['token']}).json()['ticket']
    with client.websocket_connect('/ws?ticket=' + ticket) as socket:
        socket.receive_json()
        request = prompt(socket)
        token_auth.revoke_device(device['device_id'])
        socket.send_json({'type': 'approve', 'id': request['id'], 'approved': True})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert life_manager.list_tasks()['items'] == []


def test_new_turn_cannot_reactivate_cancelled_worker_context(client, monkeypatch):
    import asyncio
    import threading
    release = threading.Event()
    finished = threading.Event()
    errors = []
    class DelayedBrain:
        active_model = 'mock'
        configured = True
        def __init__(self, registry=None, system_prompt=None):
            self.registry = registry
        def provider_candidates(self):
            return []
        async def ask(self, message, confirm, auto_approve):
            if message == 'first':
                def late_handler():
                    try:
                        release.wait(3)
                        self.registry.get('create_saved_task').handler(title='Must not save')
                    except PermissionError:
                        errors.append('blocked')
                    finally:
                        finished.set()
                asyncio.create_task(asyncio.to_thread(late_handler))
                yield {'type': 'waiting_worker'}
                await asyncio.Event().wait()
            else:
                release.set()
                await asyncio.to_thread(finished.wait, 3)
                yield {'type': 'done'}
    monkeypatch.setattr(ws, 'JarvisBrain', DelayedBrain)
    try:
        with connect(client, 'personal-local') as socket:
            socket.receive_json()
            socket.send_json({'type': 'chat', 'message': 'first'})
            assert socket.receive_json()['type'] == 'waiting_worker'
            socket.send_json({'type': 'cancel'})
            assert socket.receive_json()['error'] == 'turn cancelled'
            socket.send_json({'type': 'chat', 'message': 'second'})
            assert socket.receive_json()['type'] == 'done'
        assert errors == ['blocked']
        assert life_manager.list_tasks()['items'] == []
    finally:
        release.set()
