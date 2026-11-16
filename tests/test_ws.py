"""Regression tests for the authenticated browser WebSocket bridge."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main_enhanced import app

TOKEN = "test-token-that-is-at-least-32-characters"


def _issue_ticket(client: TestClient) -> str:
    response = client.post("/api/ws-ticket", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    return response.json()["ticket"]


@pytest.fixture(autouse=True)
def _configured_token(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("JARVIS_API_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_websocket_rejects_invalid_ticket():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws?ticket=invalid"):
                pass

    assert exc_info.value.code == 4401


def test_websocket_reports_provider_timeout(monkeypatch):
    class EmptyRegistry:
        def __len__(self):
            return 0

        def get_tool_schemas(self):
            return []

    class FakeBrain:
        active_model = "test-model"
        registry = EmptyRegistry()
        configured = True

        @staticmethod
        def provider_candidates():
            return ["test-provider"]

        async def ask(self, *_args, **_kwargs):
            raise TimeoutError("provider timed out")
            yield  # Make this an async generator like the real brain.

    monkeypatch.setattr("app.ws.JarvisBrain", FakeBrain)

    with TestClient(app) as client:
        ticket = _issue_ticket(client)
        with client.websocket_connect(f"/ws?ticket={ticket}") as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json({"type": "chat", "message": "hello"})
            response = websocket.receive_json()

    assert response == {"type": "error", "error": "provider timed out"}


def test_websocket_cannot_self_approve_sensitive_tools(monkeypatch):
    observed = {}

    class EmptyRegistry:
        def __len__(self):
            return 0

        def get_tool_schemas(self):
            return []

    class FakeBrain:
        active_model = "test-model"
        registry = EmptyRegistry()
        configured = True

        @staticmethod
        def provider_candidates():
            return ["test-provider"]

        async def ask(self, *_args, confirm=None, auto_approve=False, **_kwargs):
            observed["confirm"] = confirm
            observed["auto_approve"] = auto_approve
            yield {"type": "done", "text": "approval remains required"}

    monkeypatch.setattr("app.ws.JarvisBrain", FakeBrain)

    with TestClient(app) as client:
        ticket = _issue_ticket(client)
        with client.websocket_connect(f"/ws?ticket={ticket}") as websocket:
            assert websocket.receive_json()["type"] == "ready"
            websocket.send_json({
                "type": "chat",
                "message": "perform a sensitive action",
                "auto_approve": True,
            })
            assert websocket.receive_json()["type"] == "done"

    assert callable(observed["confirm"])
    assert observed["auto_approve"] is False


def test_websocket_ticket_is_one_time_use():
    with TestClient(app) as client:
        ticket = _issue_ticket(client)
        with client.websocket_connect(f"/ws?ticket={ticket}") as websocket:
            assert websocket.receive_json()["type"] == "ready"

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws?ticket={ticket}"):
                pass

    assert exc_info.value.code == 4401


def test_websocket_ticket_requires_bearer_auth():
    with TestClient(app) as client:
        response = client.post("/api/ws-ticket")
    assert response.status_code == 401

