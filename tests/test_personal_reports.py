"""Local reports use saved records, explicit bounds and real timezone boundaries."""
import csv
import io
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import life_manager, personal_reports

TOKEN = 'aether-local-report-test-token-at-least-32-characters'
AUTH = {'Authorization': f'Bearer {TOKEN}'}


@pytest.fixture(autouse=True)
def local_db(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_DB_PATH', str(tmp_path / 'reports.sqlite3'))
    monkeypatch.setenv('JARVIS_API_TOKEN', TOKEN)


def task(title, due=None, priority=3, status='open'):
    result = life_manager.create_task(life_manager.TaskInput(title=title, due_at=due, priority=priority))
    if status != 'open':
        life_manager.update_task(result['id'], life_manager.TaskPatch(status=status))
    return result


def draft(title, start, end=None):
    return life_manager.create_event(life_manager.EventInput(title=title, starts_at=start, ends_at=end))


def expense(amount, spent_on='2026-11-16', category='Food'):
    return life_manager.create_expense(life_manager.ExpenseInput(amount=amount, spent_on=spent_on, category=category))


def test_local_midnight_in_india_not_utc_substring():
    task('Overdue', '2026-11-15T18:29:59Z')
    task('Midnight', '2026-11-15T18:30:00Z')
    task('Last second', '2026-11-16T18:29:59Z')
    task('Tomorrow', '2026-11-16T18:30:00Z')
    task('Undated')
    task('Done', '2026-11-16T01:00:00Z', status='done')
    task('In progress', '2026-11-16T03:00:00Z', status='in_progress')
    task('Postponed', '2026-11-16T04:00:00Z', status='postponed')
    result = personal_reports.today_plan('Asia/Kolkata', '2026-11-16')
    assert result['counts'] == {'overdue': 1, 'due_today': 4, 'upcoming': 1, 'undated': 1}
    assert result['tasks']['due_today'][0]['title'] == 'Midnight'
    assert result['tasks']['due_today'][0]['due_local'] == '2026-11-16T00:00:00+05:30'
    assert result['saved'] is False


@pytest.mark.parametrize('day,hours', [('2026-03-08', 23), ('2026-11-01', 25)])
def test_dst_day_length(day, hours):
    result = personal_reports.today_plan('America/New_York', day)
    delta = datetime.fromisoformat(result['day_end_utc']) - datetime.fromisoformat(result['day_start_utc'])
    assert delta.total_seconds() == hours * 3600


def test_drafts_overlapping_midnight_not_booked_events():
    draft('Overlap', '2026-11-15T18:00:00Z', '2026-11-15T19:00:00Z')
    draft('Ends at midnight', '2026-11-15T17:00:00Z', '2026-11-15T18:30:00Z')
    draft('Point at midnight', '2026-11-15T18:30:00Z')
    draft('Tomorrow', '2026-11-16T18:30:00Z')
    result = personal_reports.today_plan('Asia/Kolkata', '2026-11-16')
    assert [r['title'] for r in result['calendar_drafts']] == ['Overlap', 'Point at midnight']
    assert all(r['status'] == 'draft' for r in result['calendar_drafts'])
    assert 'unconfirmed' in result['notice']


def test_default_today_uses_requested_timezone(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=UTC):
            return cls(2026, 11, 15, 20, 0, tzinfo=UTC).astimezone(tz)
    monkeypatch.setattr(personal_reports, 'datetime', Clock)
    assert personal_reports.today_plan('Asia/Kolkata')['date'] == '2026-11-16'
    assert personal_reports.today_plan('America/Los_Angeles')['date'] == '2026-11-15'


def test_priority_order_and_display_caps():
    for i in range(52):
        task(f'Task {i}', priority=3)
    best = task('Highest', priority=1)
    result = personal_reports.today_plan('UTC', '2026-11-16')
    assert result['top_priorities'][0]['id'] == best['id']
    assert result['counts']['undated'] == 53
    assert len(result['tasks']['undated']) == 50


def test_reports_do_not_change_records():
    task('Keep me')
    expense(1.25)
    before = life_manager.list_tasks(), life_manager.list_expenses()
    personal_reports.today_plan('UTC', '2026-11-16')
    personal_reports.expense_report('2026-11-01', '2026-11-30')
    assert before == (life_manager.list_tasks(), life_manager.list_expenses())


def test_expense_decimal_totals_inclusive_range_and_currency_separation():
    expense(.1, '2026-11-01')
    expense(.2, '2026-11-30')
    expense(999, '2026-12-01')
    with life_manager._db() as db:
        db.execute("INSERT INTO life_expenses(amount,currency,category,spent_on,created_at) VALUES(1.23,'USD','Other','2026-11-16','now')")
    result = personal_reports.expense_report('2026-11-01', '2026-11-30')
    assert result['totals'] == [{'currency': 'INR', 'amount': '0.30', 'count': 2}, {'currency': 'USD', 'amount': '1.23', 'count': 1}]
    assert result['by_category'][0]['amount'] == '0.30'
    assert len(result['by_day']) == 3
    assert result['partial'] is False
    assert 'total' not in result


@pytest.mark.parametrize('start,end', [('2026-02-30','2026-03-01'), ('2026-11-2','2026-11-30'), ('2026-11-30','2026-11-01'), ('2024-01-01','2026-11-01'), ('20261101','2026-11-30')])
def test_invalid_expense_date_ranges(start, end):
    with pytest.raises(Exception) as error:
        personal_reports.expense_report(start, end)
    assert error.value.status_code == 422


@pytest.mark.parametrize('timezone,day', [('Wrong/Zone','2026-11-16'), ('../UTC','2026-11-16'), ('UTC','2026-02-30'), ('UTC','9999-12-31')])
def test_invalid_planning_parameters(timezone, day):
    with pytest.raises(Exception) as error:
        personal_reports.today_plan(timezone, day)
    assert error.value.status_code == 422


def test_explicit_partial_scan_and_invalid_legacy_records(monkeypatch):
    monkeypatch.setattr(personal_reports, 'ROW_LIMIT', 2)
    task('Invalid')
    task('Good')
    task('Not scanned')
    with life_manager._db() as db:
        db.execute("UPDATE life_tasks SET due_at='ambiguous' WHERE title='Invalid'")
    result = personal_reports.today_plan('UTC', '2026-11-16')
    assert result['partial_scan'] is True
    assert result['invalid_records_skipped'] == 1
    expense(1)
    expense(2)
    expense(3)
    result = personal_reports.expense_report('2026-11-01', '2026-11-30')
    assert result['partial'] is True
    assert result['totals'][0]['amount'] == '3.00'


def test_authenticated_routes_and_csv_formula_safety():
    expense(12.34, category='=HYPERLINK("bad")')
    app = FastAPI()
    app.include_router(life_manager.router)
    with TestClient(app) as client:
        url = '/api/life/reports/expenses?start_date=2026-11-01&end_date=2026-11-30'
        assert client.get(url).status_code == 401
        assert client.get(url, headers=AUTH).json()['totals'][0]['amount'] == '12.34'
        response = client.get(url.replace('/expenses?', '/expenses.csv?'), headers=AUTH)
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/csv')
        assert response.headers['cache-control'] == 'no-store'
        rows = list(csv.reader(io.StringIO(response.text)))
        assert rows[4][2].startswith("'=HYPERLINK")
        assert client.get('/api/life/reports/today?timezone=Bad', headers=AUTH).status_code == 422
        assert client.get('/api/life/reports/today?timezone=UTC', headers=AUTH).json()['saved'] is False


def test_ai_proposal_uses_same_local_day_drafts_without_saving(monkeypatch):
    draft('Early local meeting', '2026-11-15T19:00:00Z')
    draft('Next local day', '2026-11-16T19:00:00Z')
    captured = {}
    monkeypatch.setattr(life_manager, 'configured_provider_order', lambda _: ['mock'])
    def complete(*args, **kwargs):
        import json
        captured.update(json.loads(args[2][-1]['content']))
        return 'mock', '{"overview":"proposal"}'
    monkeypatch.setattr(life_manager, 'complete_chat', complete)
    app = FastAPI()
    app.state.gemini_client = object()
    app.include_router(life_manager.router)
    with TestClient(app) as client:
        response = client.post('/api/life/ai-plan', headers=AUTH,
                               json={'plan_date': '2026-11-16', 'timezone': 'Asia/Kolkata'})
        assert response.status_code == 200
        assert response.json()['saved'] is False
        assert [r['title'] for r in captured['calendar_drafts']] == ['Early local meeting']
        assert client.post('/api/life/ai-plan', headers=AUTH,
                           json={'plan_date': '2026-11-16', 'timezone': 'Bad'}).status_code == 422


def test_report_chat_tools_return_bounded_previews():
    from app.personal_tool_chat import build_personal_registry
    for i in range(12):
        expense(1, category=f'Category {i}')
    handler = build_personal_registry().get('report_saved_expenses').handler
    report = handler(start_date='2026-11-01', end_date='2026-11-30')
    assert len(report['by_category']) == 10
    assert report['totals'][0]['count'] == 12
    assert 'capped at 10' in report['chat_preview_notice']
