"""Daily-plan generation must serialize context before calling a mocked provider."""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import life_manager


def test_daily_plan_context_is_serializable_without_real_provider(monkeypatch, tmp_path):
    token = 'mock-daily-plan-token-for-tests-only-1234567'
    monkeypatch.setenv('JARVIS_API_TOKEN', token)
    monkeypatch.setenv('JARVIS_DB_PATH', str(tmp_path / 'plan.sqlite3'))
    captured = {}
    monkeypatch.setattr(life_manager, 'configured_provider_order', lambda _: ['mock'])

    def complete(settings, providers, messages, temperature, **kwargs):
        captured['messages'] = messages
        return 'mock', '{"overview":"Review the proposed plan","schedule":[]}'

    monkeypatch.setattr(life_manager, 'complete_chat', complete)
    app = FastAPI()
    app.state.gemini_client = object()
    app.include_router(life_manager.router)
    with TestClient(app) as client:
        response = client.post('/api/life/ai-plan',
                               headers={'Authorization': f'Bearer {token}'},
                               json={'plan_date': '2026-11-16', 'timezone': 'Asia/Kolkata'})
    assert response.status_code == 200
    assert response.json()['saved'] is False
    context = json.loads(captured['messages'][-1]['content'])
    assert context['date'] == '2026-11-16'
    assert context['timezone'] == 'Asia/Kolkata'
