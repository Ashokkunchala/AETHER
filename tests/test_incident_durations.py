import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.devops.incident_durations import review_incident_durations

DEFINITION='Start is reported user impact; end is reported service recovery, all incidents in the supplied cohort.'
AS_OF='2020-02-01T00:00:00Z'


def row(identity='private-id',start='2020-01-01T00:00:00Z',end='2020-01-01T00:01:00Z',state='completed'):
    return {'id':identity,'state':state,'start':start,'end':end}


def review(rows,definition=DEFINITION,as_of=AS_OF):
    return review_incident_durations(rows,definition,as_of)


def test_exact_mean_median_no_private_echo():
    result=review([row(),row('second',end='2020-01-01T00:02:00Z')])
    assert result['mean_seconds']=='90' and result['median_seconds']=='90'
    assert result['total_completed_duration_microseconds']==180_000_000
    assert result['mean_exact_fraction_seconds']=={'numerator':180_000_000,'denominator':2_000_000}
    assert 'private-id' not in str(result) and DEFINITION not in str(result)
    assert not result['outage_duration_verified'] and not result['incident_tracking_started']


def test_open_excluded_no_implicit_now_end():
    result=review([row(),row('open',end=None,state='open')])
    assert result['mean_seconds']=='60' and result['open_records_excluded']==1
    assert result['incidents'][1]['duration_microseconds'] is None


@pytest.mark.parametrize('rows',[[],[row(end=None,state='open')]])
def test_no_completed_is_no_data_not_zero(rows):
    result=review(rows)
    assert result['status']=='no_completed_data' and result['mean_seconds'] is None
    assert result['median_seconds'] is None and result['mean_exact_fraction_seconds'] is None


def test_offset_normalization_and_microseconds():
    result=review([row(start='2020-01-01T05:30:00.000001+05:30',end='2020-01-01T00:00:00.000002Z')])
    assert result['mean_seconds']=='0.000001' and result['incidents'][0]['duration_microseconds']==1


def test_half_microsecond_median_and_equal_zero_boundaries():
    result=review([row(end='2020-01-01T00:00:00Z'),row('next',end='2020-01-01T00:00:00.000001Z')])
    assert result['median_seconds']=='0.0000005' and result['min_duration_microseconds']==0


def test_overlaps_allowed_but_not_total_downtime():
    result=review([row('one'),row('two')])
    assert result['completed_records']==2 and result['total_completed_duration_microseconds']==120_000_000
    assert 'not total service downtime' in result['limits']
    assert 'censoring/selection bias' in result['limits']


@pytest.mark.parametrize('change',[{'start':'bad'},{'end':None},{'state':'resolved'},{'end':'2019-01-01T00:00:00Z'},{'end':'2021-01-01T00:00:00Z'},{'id':''},{'id':' padded '},{'id':5},{'start':'2020-01-01T00:00:00'},{'start':'2020-01-01T00:00:00.1234567Z'},{'start':'2020-02-30T00:00:00Z'},{'start':'2020-01-01T00:00:60Z'},{'start':'2020-01-01T00:00:00+01:60'},{'start':'2020-01-01T00:00:00+24:00'},{'start':'2020-01-01T00:00:00-00:00'},{'unknown':1}])
def test_malformed_known_or_unknown_fields_refused(change):
    record=row();record.update(change)
    with pytest.raises(ValueError):review([record])


def test_explicit_open_end_contradiction():
    with pytest.raises(ValueError):review([row(state='open')])


def test_duplicate_ids_and_record_cap():
    with pytest.raises(ValueError):review([row(),row()])
    with pytest.raises(ValueError):review([row(str(i)) for i in range(1001)])
    assert review([row(str(i)) for i in range(1000)])['completed_records']==1000


@pytest.mark.parametrize('definition',['',True,'MTTR',None,'x'*501])
def test_explicit_definition_required(definition):
    with pytest.raises(ValueError):review([],definition)


def test_future_cutoff_and_start_after_cutoff():
    with pytest.raises(ValueError):review([],as_of=(datetime.now(UTC)+timedelta(days=1)).isoformat())
    with pytest.raises(ValueError):review([row(start='2021-01-01T00:00:00Z',end=None,state='open')])


def test_odd_median_and_repeating_fraction():
    result=review([row('one',end='2020-01-01T00:00:00.000001Z'),row('two',end='2020-01-01T00:00:00Z'),row('three',end='2020-01-01T00:00:00Z')])
    assert result['median_seconds']=='0' and result['mean_seconds'].startswith('0.000000333333')
    assert result['mean_exact_fraction_seconds']=={'numerator':1,'denominator':3_000_000}


def test_registry_safe_after_stop(tmp_path,monkeypatch):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('review_incident_durations',{'incidents':[row()],'boundary_definition':DEFINITION,'as_of':AS_OF}))
    assert result.ok and not result.data['measurement_boundaries_verified']


def test_no_tracking_files_or_execution(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.chdir(tmp_path)
    def fail(*a,**kw):raise AssertionError('No execution allowed')
    monkeypatch.setattr(subprocess,'run',fail)
    assert review([row()])['completed_records']==1
    assert list(tmp_path.iterdir())==[]
