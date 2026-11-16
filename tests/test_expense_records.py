"""Expense corrections, bounded currency arithmetic and atomic retry claims."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import expense_records as records
from app import life_manager as life
from app.main import app

TOKEN = 'test-token-that-is-at-least-32-characters'
AUTH = {'Authorization': 'Bearer ' + TOKEN}
DATA = {'amount': 10.25, 'category': 'Food', 'note': 'Lunch', 'spent_on': '2026-11-16'}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_API_TOKEN', TOKEN)
    monkeypatch.setenv('JARVIS_DB_PATH', str(tmp_path / 'expenses.sqlite3'))
    with TestClient(app) as client:
        yield client


def save(client, data=None, key=None):
    headers = dict(AUTH)
    if key is not None:
        headers['Idempotency-Key'] = key
    return client.post('/api/life/expenses', headers=headers, json=data or DATA)


def test_existing_shape_and_local_function_stay_compatible(client):
    assert save(client).status_code == 201
    result = client.get('/api/life/expenses?month=2026-11', headers=AUTH).json()
    assert result['total'] == 10.25 and result['currency'] == 'INR'
    assert result['by_category'] == [{'category': 'Food', 'total': 10.25, 'count': 1}]
    assert len(result['items'][0]['revision']) == 64
    assert life.create_expense(life.ExpenseInput(**DATA))['amount'] == 10.25


def test_legacy_mixed_currencies_are_never_labeled_as_inr(client):
    save(client, dict(DATA, amount=0.1))
    save(client, dict(DATA, amount=0.2))
    with life._db() as db:
        db.execute("INSERT INTO life_expenses(amount,currency,category,note,spent_on,created_at) VALUES(1.23,'USD','Food','','2026-11-16','now')")
    result = client.get('/api/life/expenses', headers=AUTH).json()
    assert result['total'] == 0.3
    assert result['by_category'] == [{'category': 'Food', 'total': 0.3, 'count': 2}]
    assert result['totals_by_currency'] == [{'currency': 'INR', 'amount': '0.30', 'count': 2}, {'currency': 'USD', 'amount': '1.23', 'count': 1}]
    assert result['legacy_totals_scope'] == 'INR only'
    assert result['partial'] is False


@pytest.mark.parametrize('month', ['2026-13', '2026-00', '2026-1', 'abcd-ef', '0000-01', ''])
def test_invalid_month_is_rejected(client, month):
    assert client.get('/api/life/expenses', params={'month': month}, headers=AUTH).status_code == 422


def test_limits_and_invalid_rows_are_explicit_and_do_not_rewrite_data(client, monkeypatch):
    for i in range(5):
        save(client, dict(DATA, amount=i + 1))
    with life._db() as db:
        db.execute("INSERT INTO life_expenses(amount,currency,category,note,spent_on,created_at) VALUES(-2,'INR','bad','','2026-11-17','now')")
    monkeypatch.setattr(records, 'SCAN_LIMIT', 4)
    monkeypatch.setattr(records, 'ITEM_LIMIT', 2)
    result = client.get('/api/life/expenses', headers=AUTH).json()
    assert result['partial'] and result['items_truncated']
    assert result['invalid_records_skipped'] == 1
    assert len(result['items']) == 2
    assert result['total'] == 12
    with life._db() as db:
        assert db.execute('SELECT count(*) FROM life_expenses').fetchone()[0] == 6


def test_key_replay_and_different_payload_conflict(client):
    first = save(client, key='request-1')
    replay = save(client, key='request-1')
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert replay.headers['Idempotency-Replayed'] == 'true'
    assert first.headers['Idempotency-Replayed'] == 'false'
    assert save(client, dict(DATA, amount=12), 'request-1').status_code == 409
    assert len(client.get('/api/life/expenses', headers=AUTH).json()['items']) == 1


@pytest.mark.parametrize('key', ['', 'x' * 129, 'invalid key', 'bad/key'])
def test_bad_idempotency_key_cannot_create_a_row(client, key):
    assert save(client, key=key).status_code == 422
    assert client.get('/api/life/expenses', headers=AUTH).json()['items'] == []


def test_correct_then_replay_returns_current_record_not_stale_snapshot(client):
    first = save(client, key='edit-replay').json()
    body = dict(DATA, amount=23.45, expected_revision=first['revision'])
    updated = client.put('/api/life/expenses/' + str(first['id']), headers=AUTH, json=body)
    assert updated.status_code == 200
    assert updated.json()['created_at'] == first['created_at']
    assert updated.json()['revision'] != first['revision']
    assert client.put('/api/life/expenses/' + str(first['id']), headers=AUTH, json=body).json() == updated.json()
    assert save(client, key='edit-replay').json() == updated.json()
    stale = dict(body, amount=100)
    assert client.put('/api/life/expenses/' + str(first['id']), headers=AUTH, json=stale).status_code == 409


def test_missing_revision_missing_record_auth_and_validation(client):
    first = save(client).json()
    path = '/api/life/expenses/' + str(first['id'])
    assert client.put(path, headers=AUTH, json=DATA).status_code == 422
    assert client.put(path, json=dict(DATA, expected_revision=first['revision'])).status_code == 401
    assert client.put('/api/life/expenses/99999', headers=AUTH, json=dict(DATA, expected_revision=first['revision'])).status_code == 404
    assert save(client, dict(DATA, amount=0.001)).status_code == 422
    assert save(client, dict(DATA, spent_on='2026-02-30')).status_code == 422
    assert save(client, dict(DATA, currency='USD')).status_code == 422  # Existing create scope stays INR.


def test_legacy_foreign_currency_correction_is_explicit_no_conversion(client):
    with life._db() as db:
        db.execute("INSERT INTO life_expenses(amount,currency,category,note,spent_on,created_at) VALUES(1.23,'USD','Food','','2026-11-16','now')")
    row = client.get('/api/life/expenses', headers=AUTH).json()['items'][0]
    response = client.put('/api/life/expenses/' + str(row['id']), headers=AUTH,
                          json=dict(DATA, amount=2.34, currency='USD', expected_revision=row['revision']))
    assert response.status_code == 200 and response.json()['currency'] == 'USD'
    assert client.get('/api/life/expenses', headers=AUTH).json()['total'] == 0


def test_deleted_claim_never_revives_an_expense(client):
    first = save(client, key='delete-replay').json()
    assert client.delete('/api/life/expenses/' + str(first['id']), headers=AUTH).status_code == 204
    assert save(client, key='delete-replay').status_code == 409
    assert client.get('/api/life/expenses', headers=AUTH).json()['items'] == []


def test_concurrent_same_key_creates_once_and_credential_scopes_are_separate(client):
    # Warm up the existing schema; this test targets request-claim serialization.
    with life._db():
        pass
    item = life.ExpenseInput(**DATA)
    def create(actor='actor-one'):
        with life._db() as db:
            return records.create(db, item, life._now(), 'same-key', actor)[0]['id']
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: create(), range(8)))
    assert len(set(ids)) == 1
    assert create('actor-two') != ids[0]
    with life._db() as db:
        assert db.execute('SELECT count(*) FROM life_expenses').fetchone()[0] == 2
        columns = [row[1] for row in db.execute('PRAGMA table_info(life_expenses)')]
    assert columns == ['id', 'amount', 'currency', 'category', 'note', 'spent_on', 'created_at']


def test_insert_failure_rolls_back_both_expense_and_request_claim(client, monkeypatch):
    original = records.record
    monkeypatch.setattr(records, 'record', lambda _: (_ for _ in ()).throw(RuntimeError('injected serialization failure')))
    with pytest.raises(RuntimeError):
        with life._db() as db:
            records.create(db, life.ExpenseInput(**DATA), life._now(), 'rollback', 'actor')
    monkeypatch.setattr(records, 'record', original)
    with life._db() as db:
        assert db.execute('SELECT count(*) FROM life_expenses').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM life_expense_requests').fetchone()[0] == 0


def test_concurrent_corrections_cannot_overwrite_each_other(client):
    from fastapi import HTTPException

    first = save(client).json()
    def update(amount):
        try:
            with life._db() as db:
                records.correct(db, first['id'], life.ExpenseCorrection(**dict(DATA, amount=amount, expected_revision=first['revision'])))
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, [11.5, 12.5]))
    assert sorted(outcomes) == [200, 409]
    assert client.get('/api/life/expenses', headers=AUTH).json()['items'][0]['amount'] in (11.5, 12.5)
