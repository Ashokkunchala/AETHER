import asyncio

import pytest

from aether.devops.telemetry_windows import compare_telemetry_windows


def metric(**kw):
    row={'scope_key':'PRIVATE_SCOPE','source_ref':'PRIVATE_SOURCE','start':'2020-01-01T00:00:00Z','end':'2020-01-01T00:01:00Z','coverage':'unknown','eligible_requests':100,'error_requests':5};row.update(kw);return row


def trace(**kw):
    row=metric();row.pop('eligible_requests');row.pop('error_requests');row.update(observed_spans=300,error_spans=10,sampling='sampled');row.update(kw);return row


def review(metrics=None,traces=None,**kw):
    params={'schema_version':'aether.telemetry-windows.v1','metric_windows':[metric()] if metrics is None else metrics,'trace_windows':[trace()] if traces is None else traces,'as_of':'2020-02-01T00:00:00Z'};params.update(kw);return compare_telemetry_windows(**params)


def test_both_counts_temporal_only_and_private_values_omitted():
    result=review();pair=result['pairs'][0]
    assert pair['temporal_comparison']=='error_counts_reported_in_both'
    assert not pair['statistical_correlation_verified'] and not pair['causal_relationship_verified']
    assert not pair['population_equivalence_verified'] and not pair['scope_equivalence_verified']
    assert 'PRIVATE_' not in str(result) and '300' in str(result)
    assert not result['outage_verified'] and not result['root_cause_verified']


def test_equivalent_offset_pairs_but_distinct_boundary_does_not():
    assert review(traces=[trace(start='2020-01-01T05:30:00+05:30',end='2020-01-01T05:31:00+05:30')])['exact_scope_window_pairs']==1
    result=review(traces=[trace(end='2020-01-01T00:02:00Z')])
    assert result['status']=='no_exact_pairs' and result['unpaired_metric_indices']==[0] and result['unpaired_trace_indices']==[0]


def test_different_scope_never_fuzzy_joined():
    assert review(traces=[trace(scope_key='other')])['exact_scope_window_pairs']==0


@pytest.mark.parametrize('errors,spans,total,expected',[(0,0,100,'no_errors_reported_in_either'),(5,0,100,'error_counts_reported_in_one_only'),(0,10,100,'error_counts_reported_in_one_only'),(0,10,0,'no_observations_in_one_or_both')])
def test_no_data_and_counts_never_health_or_causality(errors,spans,total,expected):
    result=review([metric(eligible_requests=total,error_requests=errors)],[trace(error_spans=spans)])
    assert result['pairs'][0]['temporal_comparison']==expected and not result['outage_verified']


def test_empty_signals_no_exact_pairs_not_healthy():
    result=review([],[])
    assert result['status']=='no_exact_pairs' and not result['snapshot_freshness_verified']


@pytest.mark.parametrize('changes',[{'eligible_requests':True},{'error_requests':-1},{'error_requests':101},{'eligible_requests':1.5},{'eligible_requests':10**18+1},{'coverage':'complete'},{'scope_key':' '},{'source_ref':None},{'extra':1},{'start':'bad'},{'start':'2020-01-01T00:01:00Z'},{'end':'2021-01-01T00:00:00Z'}])
def test_invalid_metric_fields_refused(changes):
    with pytest.raises(ValueError):review([metric(**changes)])


def test_missing_fields_and_trace_sampling_refused():
    row=trace();row.pop('source_ref')
    with pytest.raises(ValueError):review(traces=[row])
    with pytest.raises(ValueError):review(traces=[trace(sampling='none')])
    with pytest.raises(ValueError):review(schema_version='OTLP')


def test_duplicates_and_overlaps_rejected_but_adjacent_allowed():
    with pytest.raises(ValueError):review([metric(),metric()])
    with pytest.raises(ValueError):review(traces=[trace(),trace(start='2020-01-01T00:00:30Z',end='2020-01-01T00:02:00Z')])
    result=review([metric(),metric(start='2020-01-01T00:01:00Z',end='2020-01-01T00:02:00Z')])
    assert result['unpaired_metric_indices']==[1]


def test_partial_and_asserted_coverage_not_verified():
    result=review([metric(coverage='complete_asserted')],[trace(coverage='partial',sampling='unsampled_asserted')])
    assert result['pairs'][0]['trace_coverage_reported']=='partial'
    assert not result['inventory_completeness_verified'] and not result['source_provenance_verified']


def test_maximum_bounds_and_index_stability():
    with pytest.raises(ValueError):review([metric(scope_key=str(i)) for i in range(501)])
    result=review([metric(scope_key='other'),metric()])
    assert result['pairs'][0]['metric_index']==1


def test_no_write_or_execute(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.chdir(tmp_path)
    def fail(*a,**kw):raise AssertionError('No execution')
    monkeypatch.setattr(subprocess,'run',fail)
    assert review()['exact_scope_window_pairs']==1 and list(tmp_path.iterdir())==[]


def test_safe_registry_after_stop(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('compare_telemetry_windows',{'schema_version':'aether.telemetry-windows.v1','metric_windows':[metric()],'trace_windows':[trace()],'as_of':'2020-02-01T00:00:00Z'}))
    assert result.ok and not result.data['monitor_started']
