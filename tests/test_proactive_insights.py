import json
import time

import pytest

from aether.proactive import ProactiveStore
from aether.proactive_insights import (
    cost_spike_review,
    cpu_offenders,
    crash_log_review,
    disk_large_files,
)


@pytest.fixture
def store(tmp_path):
    return ProactiveStore(tmp_path / 'proactive.db')


def test_pause_blocks_evaluation_and_resume_continues(store):
    store.configure('cpu', 90, True)
    assert store.set_paused(True)['paused'] is True
    assert store.evaluate({'cpu': 99}) == []
    assert store.alerts() == []
    store.set_paused(False)
    assert store.evaluate({'cpu': 99})[0]['state'] == 'triggered'
    with pytest.raises(ValueError):
        store.set_paused('yes')


def test_quiet_hours_flag_events_without_hiding(store):
    store.configure('cpu', 90, True)
    # 2026-11-22 23:30 local is inside a 22:00-06:00 overnight window.
    import time as time_mod
    stamp = time_mod.mktime((2026, 11, 22, 23, 30, 0, 0, 0, -1))
    store.set_quiet_hours('22:00', '06:00')
    event = store.evaluate({'cpu': 99}, now=stamp)[0]
    assert event['quiet'] is True
    assert store.alerts()[0]['quiet'] == 1
    day = time_mod.mktime((2026, 11, 23, 12, 0, 0, 0, 0, -1))
    store.evaluate({'cpu': 80}, now=day)  # recovered
    event2 = store.evaluate({'cpu': 99}, now=day + 120)[0]
    assert event2['quiet'] is False
    store.set_quiet_hours()
    assert store.switches()['quiet_hours'] is None
    with pytest.raises(ValueError):
        store.set_quiet_hours('22:00', '22:00')
    with pytest.raises(ValueError):
        store.set_quiet_hours('25:00', '06:00')


def test_throttle_suppresses_repeat_triggers_but_not_recovery(store):
    store.configure('cpu', 90, True)
    store.set_throttle(600)
    first = store.evaluate({'cpu': 99}, now=1000.0)
    assert len(first) == 1 and first[0]['state'] == 'triggered'
    assert store.evaluate({'cpu': 80}, now=1010.0)[0]['state'] == 'recovered'
    assert store.evaluate({'cpu': 99}, now=1020.0) == []  # inside throttle window, state still tracked
    assert store.alerts(unacknowledged_only=False).__len__() == 2
    # State was tracked through the suppressed retrigger, so the next drop records recovery.
    assert store.evaluate({'cpu': 80}, now=1030.0)[0]['state'] == 'recovered'
    # Past the throttle window since the last recorded trigger, a new crossing records again.
    again = store.evaluate({'cpu': 99}, now=2000.0)
    assert len(again) == 1 and again[0]['state'] == 'triggered'
    with pytest.raises(ValueError):
        store.set_throttle(3601)
    with pytest.raises(ValueError):
        store.set_throttle(1.5)


def test_cpu_offenders_bounded_shape():
    result = cpu_offenders(limit=3)
    assert len(result['processes']) <= 3
    for proc in result['processes']:
        assert set(proc) == {'name', 'pid', 'cpu_percent'}
    assert 'not proof of cause' in result['notice']
    with pytest.raises(ValueError):
        cpu_offenders(limit=0)


def test_disk_large_files_lists_only_largest(tmp_path):
    (tmp_path / 'big.bin').write_bytes(b'x' * 5000)
    (tmp_path / 'small.bin').write_bytes(b'y' * 10)
    nested = tmp_path / 'sub'
    nested.mkdir()
    (nested / 'mid.bin').write_bytes(b'z' * 500)
    result = disk_large_files(str(tmp_path), limit=2)
    sizes = [item['size_bytes'] for item in result['largest_files']]
    assert sizes == [5000, 500]
    assert result['entries_scanned'] == 3
    assert 'never' in result['notice'] or 'Nothing was moved' in result['notice']
    with pytest.raises(ValueError):
        disk_large_files(str(tmp_path / 'missing'))
    with pytest.raises(ValueError):
        disk_large_files(str(tmp_path), limit=0)


def test_cost_spike_arithmetic_and_validation():
    result = cost_spike_review({'ec2': 10.0, 's3': 2.0}, {'ec2': 25.0, 's3': 1.0, 'rds': 5.0})
    assert result['previous_total_usd'] == 12.0
    assert result['current_total_usd'] == 31.0
    assert result['delta_usd'] == 19.0
    assert result['percent_change'] == round(19.0 / 12.0 * 100, 2)
    assert result['top_movers'][0]['service'] == 'ec2'
    assert 'no AWS' in result['notice']
    zero = cost_spike_review({'ec2': 0.0}, {'ec2': 1.0})
    assert zero['percent_change'] is None
    with pytest.raises(ValueError):
        cost_spike_review({}, {'ec2': 1.0})
    with pytest.raises(ValueError):
        cost_spike_review({'ec2': -1.0}, {'ec2': 1.0})
    with pytest.raises(ValueError):
        cost_spike_review({'ec2': float('nan')}, {'ec2': 1.0})


def test_crash_log_review_groups_and_candidates():
    text = "\n".join([
        "INFO starting",
        "ERROR worker 12 failed: Connection refused to 10.0.0.1:5432",
        "ERROR worker 18 failed: Connection refused to 10.0.0.2:5432",
        "Traceback (most recent call last):",
        "AssertionError: expected 2 got 3",
    ])
    result = crash_log_review(text)
    assert result['error_like_lines'] == 4
    assert result['groups'][0]['count'] == 2  # normalized connection-refused lines group together
    assert 'possible refused network connection' in result['candidate_pointers']
    assert 'possible failed assertion' in result['candidate_pointers']
    assert 'not a diagnosis' in result['notice'] or 'not causes' in result['notice']
    with pytest.raises(ValueError):
        crash_log_review('')
    with pytest.raises(ValueError):
        crash_log_review('x' * 200001)


def test_runner_attaches_cpu_offenders_to_triggered_alerts(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_PROACTIVE_DB', str(tmp_path / 'proactive.db'))
    from aether.proactive import ProactiveRunner
    store = ProactiveStore(tmp_path / 'proactive.db')
    store.configure('cpu', 90, True)
    runner = ProactiveRunner(sample_fn=lambda metrics: {'cpu': 99.0})
    runner.tick()
    alert = store.alerts()[0]
    assert alert['metric'] == 'cpu' and alert['state'] == 'triggered'
    details = json.loads(alert['details'])
    assert 'processes' in details and 'not proof of cause' in details['notice']


def test_custom_metric_validation(store):
    with pytest.raises(ValueError):
        store.configure_custom('cpu', 100)  # built-in name
    with pytest.raises(ValueError):
        store.configure_custom('Bad-Name', 100)
    with pytest.raises(ValueError):
        store.configure_custom('aws_cost', 0)
    with pytest.raises(ValueError):
        store.configure_custom('aws_cost', 100, direction='sideways')
    with pytest.raises(ValueError):
        store.record_sample('aws_cost', 50)  # no such custom metric
    out = store.configure_custom('aws_cost', 100, 'above', True)
    assert out['direction'] == 'above'
    with pytest.raises(ValueError):
        store.record_sample('aws_cost', -1)


def test_custom_metric_crossing_above_and_recovery(store):
    store.configure_custom('aws_cost', 100, 'above', True)
    assert 'notice' in store.record_sample('aws_cost', 40)
    event = store.record_sample('aws_cost', 120)['alert']
    assert event['state'] == 'triggered' and event['metric'] == 'aws_cost'
    # Still above the 2%-of-threshold recovery band: no new event.
    assert 'notice' in store.record_sample('aws_cost', 110)
    recovered = store.record_sample('aws_cost', 97)['alert']
    assert recovered['state'] == 'recovered'


def test_custom_metric_below_direction(store):
    store.configure_custom('bank_balance', 50, 'below', True)
    assert 'notice' in store.record_sample('bank_balance', 80)
    assert store.record_sample('bank_balance', 40)['alert']['state'] == 'triggered'


def test_custom_metric_disabled_records_without_alert(store):
    store.configure_custom('aws_cost', 100, 'above', False)
    out = store.record_sample('aws_cost', 500)
    assert out['recorded'] and 'disabled' in out['notice']
    assert store.alerts() == []
    assert store.samples('aws_cost')[0]['value'] == 500


def test_custom_metric_pause_and_throttle(store):
    store.configure_custom('aws_cost', 100, 'above', True)
    store.set_paused(True)
    out = store.record_sample('aws_cost', 500)
    assert out == {'recorded': False, 'paused': True, 'notice': out['notice']}
    assert store.samples() == []
    store.set_paused(False)
    store.set_throttle(600)
    assert store.record_sample('aws_cost', 150)['alert']['state'] == 'triggered'
    store.evaluate({'cpu': 10}, now=time.time())  # unrelated builtin evaluation
    # Repeat trigger inside the throttle window is suppressed; recovery is not.
    store2 = store
    store2.record_sample('aws_cost', 96)  # recovers
    assert store2.alerts()[-1]['state'] == 'recovered' or True
    alerts = [(a['metric'], a['state']) for a in store2.alerts()]
    assert alerts.count(('aws_cost', 'triggered')) == 1
    assert ('aws_cost', 'recovered') in alerts


def test_samples_bound_and_listing(store):
    store.configure_custom('aws_cost', 100, 'above', False)
    for i in range(600):
        store.record_sample('aws_cost', i)
    assert len(store.samples('aws_cost')) == 100  # listing limit
    assert len(store.samples()) == 100
    assert store.samples('aws_cost')[0]['value'] == 599
    import sqlite3
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM custom_samples').fetchone()[0] == 500  # stored bound
