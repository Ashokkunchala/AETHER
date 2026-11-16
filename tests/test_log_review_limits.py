import asyncio

import pytest

from jarvis.devops.logs import MAX_LINES, triage_log, triage_text


def test_exit137_never_proves_memory_cause():
    result=triage_text('exit code 137')
    assert result['signals'][0]['signature']=='oom'
    assert 'does not establish OOM' in result['signals'][0]['meaning']
    assert not result['root_cause_verified'] and not result['outage_verified']


def test_raw_private_examples_and_normalized_patterns_omitted():
    raw='2026-11-16T10:00:00Z ERROR AccessDenied Bearer PRIVATE_TOKEN email=private@example.org'
    result=triage_text(raw+'\n'+raw)
    assert 'PRIVATE_TOKEN' not in str(result) and 'private@example.org' not in str(result)
    assert result['signals'][0]['count']==2 and result['top_repeated'][0]['count']==2
    assert 'Omitted' in result['signals'][0]['example']
    assert 'not redaction' in result['top_repeated'][0]['pattern']


def test_overlapping_signatures_not_separate_error_lines():
    result=triage_text('ERROR OOMKilled connection refused timed out')
    assert result['error_lines']==1 and sum(s['count'] for s in result['signals'])==3
    assert 'not separate incidents' in result['limits']


def test_wall_clock_buckets_not_timezone_normalized_or_durations():
    result=triage_text('2026-11-16T11:00:00+05:30 ERROR timeout\n2026-11-16T06:00:00Z ERROR timeout')
    assert result['first_error_minute']=='2026-11-16 06:00'
    assert result['peak_minute']['minute']=='2026-11-16 11:00'
    assert 'without timezone normalization' in result['limits']
    assert not result['incident_duration_verified']


def test_unvalidated_calendar_prefix_explicit_not_real_time():
    result=triage_text('2026-99-99T88:99 ERROR')
    assert result['first_error_minute']=='2026-99-99 88:99'
    assert 'calendar validation' in result['limits']


def test_signature_on_success_or_comment_still_pattern_only():
    result=triage_text('# Example: No space left on device\nINFO no 429 observed')
    assert result['error_lines']==2 and len(result['signals'])==2
    assert all('unverified' in row['meaning'] for row in result['signals'])


def test_missing_timestamp_not_assigned_or_outage_claimed():
    result=triage_text('ERROR crashed')
    assert result['error_lines']==1 and result['peak_minute'] is None
    assert not result['snapshot_freshness_verified']


def test_empty_log_is_not_healthy():
    result=triage_text('')
    assert result['success'] and result['lines_read']==0
    assert not result['outage_verified'] and not result['metric_trace_correlation_verified']


def test_line_cap_flag_versus_exact_cap():
    assert not triage_text('\n'.join(['INFO ok']*MAX_LINES))['line_limit_reached']
    result=triage_text('\n'.join(['INFO ok']*MAX_LINES+['ERROR OOMKilled']))
    assert result['line_limit_reached'] and result['error_lines']==0


@pytest.mark.parametrize('top',[0,-1,21,True,2.5,'3',None])
def test_top_bounds(top):
    with pytest.raises(ValueError):triage_text('',top)


def test_utf8_byte_cap_not_character_cap():
    with pytest.raises(ValueError):triage_text('é'*2_500_001)


def test_nontext_refused():
    with pytest.raises(ValueError):triage_text(None)


def test_file_retains_path_but_never_raw_private_text(tmp_path):
    path=tmp_path/'export.log';path.write_text('ERROR PRIVATE_VALUE OOMKilled')
    before=path.read_bytes();result=triage_log(str(path))
    assert result['file']==str(path) and path.read_bytes()==before
    assert 'PRIVATE_VALUE' not in str(result)


def test_safe_registry_available_after_stop(tmp_path,monkeypatch):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    path=tmp_path/'export.log';path.write_text('ERROR AccessDenied')
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('triage_log',{'path':str(path)}))
    assert result.ok and not result.data['root_cause_verified']
