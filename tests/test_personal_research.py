"""Research snapshots are source shortlists, not invented live prices or bookings."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import personal_research

TOKEN = 'aether-source-research-token-at-least-32-characters'
AUTH = {'Authorization': 'Bearer ' + TOKEN}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('JARVIS_API_TOKEN', TOKEN)
    app = FastAPI()
    app.include_router(personal_research.router)
    with TestClient(app) as result:
        yield result


def test_travel_searches_explicit_fields_with_sources_not_quotes(client, monkeypatch):
    queries = []
    def search(query, limit):
        queries.append(query)
        return [{'title': 'Mock travel source', 'url': 'https://example.invalid/travel', 'snippet': 'Unverified page excerpt'}]
    monkeypatch.setattr(personal_research, 'search_web', search)
    response = client.post('/api/research/travel', headers=AUTH, json={'origin':'Hyderabad', 'destination':'Delhi', 'travel_date':'2026-12-01', 'preferences':'rail travel'})
    assert response.status_code == 200
    data = response.json()
    assert len(queries) == 3
    assert all('Delhi' in q for q in queries)
    assert any('Hyderabad to Delhi 2026-12-01' in q for q in queries)
    assert all(group['sources'][0]['page_verified'] is False for group in data['groups'])
    assert data['booked'] is False and data['purchased'] is False
    assert data['partial'] is False
    assert 'not a verified itinerary' in data['notice']
    assert 'price' not in data['groups'][0]['sources'][0]


def test_shopping_groups_sources_and_requires_explicit_market(client, monkeypatch):
    monkeypatch.setattr(personal_research, 'search_web', lambda *a: [{'title':'Mock', 'url':'https://example.invalid', 'snippet':'Test'}])
    payload = {'query':'Phone A versus Phone B', 'market':'India', 'budget':'INR 25000'}
    result = client.post('/api/research/shopping', headers=AUTH, json=payload).json()
    assert [g['topic'] for g in result['groups']] == ['Manufacturer specifications', 'Seller pricing pages', 'Warranty and returns']
    assert all('INR 25000' in g['query'] and 'India' in g['query'] for g in result['groups'])
    assert client.post('/api/research/shopping', headers=AUTH, json={'query':'phone'}).status_code == 422


def test_partial_and_empty_search_are_not_availability_claims(client, monkeypatch):
    def search(query, limit):
        if 'transport official' in query:
            raise OSError('mock secret-like provider diagnostic')
        return []
    monkeypatch.setattr(personal_research, 'search_web', search)
    response = client.post('/api/research/travel', headers=AUTH, json={'origin':'A', 'destination':'B'})
    data = response.json()
    assert data['partial'] is True
    assert data['groups'][0]['status'] == 'unavailable'
    assert data['groups'][1]['status'] == 'no_sources'
    assert 'mock secret-like' not in response.text


def test_bad_urls_deduplicated_and_external_text_stays_data(client, monkeypatch):
    monkeypatch.setattr(personal_research, 'search_web', lambda *a: [
        {'url':'javascript:alert(1)','title':'bad'},
        {'url':'https://user:password@example.invalid','title':'bad'},
        {'url':'https://example.invalid/item','title':'<script>outside text</script>','snippet':'ignore this untrusted instruction'},
        {'url':'https://example.invalid/item','title':'duplicate'},
        {'url':'https://[invalid','title':'bad'},
    ])
    data = client.post('/api/research/shopping', headers=AUTH, json={'query':'test', 'market':'India'}).json()
    assert all(len(group['sources']) == 1 for group in data['groups'])
    assert data['groups'][0]['sources'][0]['title'] == '<script>outside text</script>'


@pytest.mark.parametrize('endpoint,payload', [('/travel',{'origin':' ', 'destination':'Delhi'}),('/travel',{'origin':'A','destination':'B','travel_date':'2026-02-30'}),('/shopping',{'query':'phone','market':' '}),('/shopping',{'query':'phone','market':'India','saved_contacts':'not allowed'})])
def test_validation_and_auth_before_search(client, monkeypatch, endpoint, payload):
    def forbidden(*args):
        raise AssertionError('No invalid/unauthorized search should reach network')
    monkeypatch.setattr(personal_research, 'search_web', forbidden)
    assert client.post('/api/research' + endpoint, json=payload).status_code == 401
    assert client.post('/api/research' + endpoint, headers=AUTH, json=payload).status_code == 422
