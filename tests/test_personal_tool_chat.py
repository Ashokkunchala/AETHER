"""The personal browser profile must never inherit the desktop registry."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import life_manager, personal_data, ws
from app.core.auth import token_auth
from app.core.ws_sessions import TicketStore
from app.personal_tool_chat import _bounded, build_personal_registry

TOKEN = 'mock-personal-chat-token-for-tests-only-123456'


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_API_TOKEN', TOKEN)
    monkeypatch.setenv('JARVIS_DB_PATH', str(tmp_path / 'personal.sqlite3'))
    token_auth._init_device_table()
    monkeypatch.setattr(ws, '_tickets', TicketStore())


def test_personal_registry_has_only_eight_readers():
    registry = build_personal_registry()
    assert len(registry) == 8
    assert set(registry.names()) == {'list_personal_tasks', 'list_personal_notes',
        'list_calendar_drafts', 'list_personal_expenses', 'list_saved_reminders',
        'list_active_saved_memories', 'plan_saved_day', 'report_saved_expenses'}
    assert all(tool.risk == 0 for tool in registry.tools.values())
    assert registry.get('run_shell') is None
    assert registry.get('aws_change') is None
    assert registry.get('create_reminder') is None


def test_readers_use_existing_stores_and_exclude_expired_memories():
    task = life_manager.create_task(life_manager.TaskInput(title='Existing task'))
    personal_data.create_memory(personal_data.MemoryCreate(text='Active preference'))
    personal_data.create_memory(personal_data.MemoryCreate(
        text='Expired preference', expires_at='2020-01-01T00:00:00+00:00'))
    registry = build_personal_registry()
    result = registry.get('list_personal_tasks').handler()
    assert result['items'][0]['id'] == task['id']
    assert result['source'] == 'life_manager.tasks'
    memories = registry.get('list_active_saved_memories').handler()['items']
    assert [row['text'] for row in memories] == ['Active preference']


def test_listings_are_bounded_and_do_not_claim_totals():
    result = _bounded({'items': [{'title': 'x' * 1000}] * 51, 'total': 100}, 'test')
    assert result['returned'] == 50
    assert len(result['items'][0]['title']) == 600
    assert 'total' not in result
    assert 'not a complete history' in result['notice']


def test_ticket_profile_cannot_be_upgraded_in_socket_url(monkeypatch):
    observed = {}

    class Brain:
        active_model = 'mock'
        configured = True

        def __init__(self, registry=None, system_prompt=None):
            observed['registry'] = registry
            observed['prompt'] = system_prompt
            self.registry = registry

        def provider_candidates(self):
            return []

    monkeypatch.setattr(ws, 'JarvisBrain', Brain)
    app = FastAPI()
    app.include_router(ws.router)
    with TestClient(app) as client:
        response = client.post('/api/ws-ticket?profile=personal-readonly',
                               headers={'Authorization': f'Bearer {TOKEN}'})
        ticket = response.json()['ticket']
        with client.websocket_connect(f'/ws?ticket={ticket}&profile=legacy') as socket:
            ready = socket.receive_json()
            assert ready['profile'] == 'personal-readonly'
            assert ready['tools'] == 8
    assert observed['registry'].get('run_shell') is None
    assert 'AETHER' in observed['prompt']


def test_unknown_ticket_profile_is_rejected():
    app = FastAPI()
    app.include_router(ws.router)
    with TestClient(app) as client:
        response = client.post('/api/ws-ticket?profile=admin',
                               headers={'Authorization': f'Bearer {TOKEN}'})
    assert response.status_code == 422
