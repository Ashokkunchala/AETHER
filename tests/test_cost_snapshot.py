import asyncio
import json
from datetime import date, timedelta

import pytest

from jarvis.devops.cost_snapshot import review_costs, review_costs_export


def metric(amount='12.3456789012', unit='USD'):
    return {'Amount': amount, 'Unit': unit}


def period(**kwargs):
    value = {'TimePeriod': {'Start': '2026-10-01', 'End': '2026-11-01'},
             'Estimated': False, 'Total': {'UnblendedCost': metric()}, 'Groups': []}
    value.update(kwargs)
    return value


def review(item=None, **kwargs):
    return review_costs({'ResultsByTime': [period() if item is None else item], **kwargs})


def group(keys=None, metrics=None):
    return {'Keys': ['PRIVATE_KEY'] if keys is None else keys,
            'Metrics': {'UnblendedCost': metric()} if metrics is None else metrics}


def test_native_period_totals_preserve_precision_estimate_and_exclusive_end():
    result = review()
    value = result['periods'][0]
    assert value['end_exclusive'] == '2026-11-01'
    assert value['reported_totals'][0]['reported_amount'] == '12.3456789012'
    assert value['reported_totals'][0]['reported_unit'] == 'USD'
    assert value['estimate_status'] == 'reported_not_estimated'
    assert not result['amounts_independently_verified']
    assert 'final invoice' in result['limits']
    assert 'grand_total' not in result


def test_cost_metrics_units_and_usage_never_blended():
    result = review(period(Total={'UnblendedCost': metric('-1.25'), 'BlendedCost': metric('4', 'EUR'),
                                 'UsageQuantity': metric('200', 'N/A'), 'NormalizedUsageAmount': metric('8', 'hours')}))
    rows = {r['metric']: r for r in result['periods'][0]['reported_totals']}
    assert rows['UnblendedCost']['reported_amount'] == '-1.25'
    assert rows['BlendedCost']['reported_unit'] == 'EUR'
    assert rows['UsageQuantity']['kind'] == rows['NormalizedUsageAmount']['kind'] == 'usage_not_money'
    assert 'total_amount' not in result


def test_missing_estimate_unknown_not_false():
    row = period()
    del row['Estimated']
    assert review(row)['periods'][0]['estimate_status'] == 'unknown'
    assert review(period(Estimated=True))['periods'][0]['estimate_status'] == 'estimated'


def test_groups_not_promoted_to_totals_or_attributed():
    result = review(period(Total={}, Groups=[group()]), GroupDefinitions=[{'Type': 'TAG', 'Key': 'PRIVATE_TAG'}],
                    DimensionValueAttributes=[{'Value': 'PRIVATE_ATTRIBUTE'}], NextPageToken='PRIVATE_TOKEN')
    item = result['periods'][0]
    assert item['reported_totals'] == [] and item['groups_in_snapshot'] == 1
    assert item['groups'][0]['group_index'] == 0
    for private in ['PRIVATE_KEY', 'PRIVATE_TAG', 'PRIVATE_ATTRIBUTE', 'PRIVATE_TOKEN']:
        assert private not in json.dumps(result)
    assert result['pagination_token_present'] and not result['query_scope_verified']
    assert not result['inventory_completeness_verified']


def test_duplicate_overlapping_periods_refused_and_gaps_reported():
    with pytest.raises(ValueError, match='overlapping'):
        review_costs({'ResultsByTime': [period(), period()]})
    later = period(TimePeriod={'Start': '2026-10-15', 'End': '2026-11-15'})
    with pytest.raises(ValueError):
        review_costs({'ResultsByTime': [period(), later]})
    later['TimePeriod'] = {'Start': '2026-12-01', 'End': '2027-01-01'}
    assert review_costs({'ResultsByTime': [later, period()]})['gaps_between_periods']


def test_output_truncation_explicit_but_all_groups_validated():
    rows = [group([f'key{i}']) for i in range(21)]
    result = review(period(Total={}, Groups=rows))
    assert result['periods'][0]['group_output_truncated']
    assert len(result['periods'][0]['groups']) == 20
    rows[-1]['Metrics'] = {'UnblendedCost': metric('NaN')}
    with pytest.raises(ValueError):
        review(period(Total={}, Groups=rows))


@pytest.mark.parametrize('change', [
    {'TimePeriod': None}, {'TimePeriod': {'Start': '2026-1-1', 'End': '2026-02-01'}},
    {'TimePeriod': {'Start': '2026-02-30', 'End': '2026-03-01'}},
    {'TimePeriod': {'Start': '2026-11-01', 'End': '2026-11-01'}},
    {'Estimated': 'false'}, {'Total': []}, {'Groups': None}, {'Groups': [None]},
    {'Groups': [{'Keys': [], 'Metrics': {}}]}, {'Groups': [group(['a', 'b', 'c'])]},
    {'Groups': [group([True])]}, {'Groups': [group(metrics={})]},
    {'Groups': [group(), group()]}, {'Total': {}, 'Groups': []},
])
def test_invalid_period_fields_not_success(change):
    with pytest.raises(ValueError):
        review(period(**change))


@pytest.mark.parametrize('value', [True, 12, None, 'NaN', 'Infinity', '1e9', '1.2.3', ' 3', 'x' * 81])
def test_invalid_amount_types(value):
    with pytest.raises(ValueError):
        review(period(Total={'UnblendedCost': metric(value)}))


@pytest.mark.parametrize('unit', [None, '', [], 'x' * 41, '<script>'])
def test_bad_unit_types(unit):
    with pytest.raises(ValueError):
        review(period(Total={'UnblendedCost': metric(unit=unit)}))


def test_missing_metrics_not_zero():
    row = period()
    del row['Total']
    with pytest.raises(ValueError):
        review(row)
    row['Groups'] = [group()]
    assert review(row)['periods'][0]['total_field_present'] is False
    with pytest.raises(ValueError):
        review(period(Total={'UnknownFutureMetric': metric()}))


def test_empty_result_means_supplied_empty_not_zero_invoice():
    result = review_costs({'ResultsByTime': []})
    assert result['periods_reviewed'] == 0
    assert not result['inventory_completeness_verified']


@pytest.mark.parametrize('document', [None, [], {}, {'ResultsByTime': None}, {'ResultsByTime': [None]},
    {'ResultsByTime': [period()], 'NextPageToken': 1},
    {'ResultsByTime': [period()], 'GroupDefinitions': [None]},
    {'ResultsByTime': [period()], 'GroupDefinitions': [{'Type': 'TAG'}]},
    {'ResultsByTime': [period()], 'GroupDefinitions': [{}] * 3}])
def test_bad_document(document):
    with pytest.raises(ValueError):
        review_costs(document)


def test_limits_and_group_definition_shape():
    with pytest.raises(ValueError):
        review_costs({'ResultsByTime': [period()] * 367})
    with pytest.raises(ValueError):
        review(period(Groups=[group()] * 1001))
    with pytest.raises(ValueError):
        review(period(Groups=[group(['a'])]), GroupDefinitions=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}, {'Type': 'TAG', 'Key': 'Environment'}])


def test_many_nonoverlapping_periods_and_no_implicit_sum():
    start = date(2026, 1, 1)
    periods = [period(TimePeriod={'Start': (start + timedelta(days=i)).isoformat(), 'End': (start + timedelta(days=i+1)).isoformat()}) for i in range(366)]
    result = review_costs({'ResultsByTime': periods})
    assert result['periods_reviewed'] == 366 and not result['gaps_between_periods']
    assert 'grand_total' not in result


def test_export_literal_private_values_not_executed(tmp_path):
    marker = tmp_path / 'never-created'
    text = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    path = tmp_path / 'cost.json'
    path.write_text(json.dumps({'ResultsByTime': [period(Groups=[group([text])])]}))
    before = path.read_bytes()
    result = review_costs_export(str(path))
    assert text not in json.dumps(result) and not marker.exists()
    assert path.read_bytes() == before


@pytest.mark.parametrize('payload', [b'bad-json', b'\xff', b'{"ResultsByTime":[],"ResultsByTime":[]}',
    b'{"ResultsByTime":[],"extra":NaN}', b'x' * 2000001, b'[' * 2000])
def test_bad_export(tmp_path, payload):
    path = tmp_path / 'cost.json'
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        review_costs_export(str(path))


def test_registry_does_not_call_billed_api_or_change_policy(tmp_path, monkeypatch):
    from jarvis.devops.awscli import classify
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'safety.db'))
    path = tmp_path / 'cost.json'
    path.write_text(json.dumps({'ResultsByTime': [period()]}))
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_cost_explorer', {'path': str(path)}))
    assert result.ok and result.data['periods_reviewed'] == 1
    assert classify('ce', 'get-cost-and-usage') == 'confirm'
