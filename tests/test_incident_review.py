import asyncio
import json

import pytest

from aether.devops.incident_review import review_incident_evidence

SCHEMA = 'aether.incident-evidence.v1'
AS_OF = '2026-11-22T12:00:00Z'


def record(kind='log_signal', scope='api/prod', at='2026-11-22T11:30:00Z',
           summary='GET / pay 500 Internal Server Error', severity='critical'):
    return {'kind': kind, 'scope_key': scope, 'observed_at': at, 'summary': summary, 'severity': severity}


def review(evidence, **kwargs):
    return review_incident_evidence(SCHEMA, 'payments-api', evidence, AS_OF, **kwargs)


def test_timeline_sorted_and_deploy_correlation_is_not_causation():
    evidence = [record(at='2026-11-22T11:35:00Z'),
                record(kind='deploy_event', at='2026-11-22T11:20:00Z', summary='deploy 3f2a1bc to api/prod', severity='info'),
                record(kind='metric_signal', at='2026-11-22T11:36:00Z', summary='error rate 12% on api/prod', severity='warning')]
    result = review(evidence)
    assert [row['index'] for row in result['timeline']] == [1, 0, 2]
    labels = {c['label']: c for c in result['candidate_explanations']}
    assert 'recent_change_correlated' in labels
    candidate = labels['recent_change_correlated']
    assert candidate['confidence'] == 'time_correlation_only_not_causation'
    assert 1 in candidate['supporting_evidence']
    assert result['corroborated_scopes'] == ['api/prod']
    assert 'never prove causation' in result['limits']
    rendered = json.dumps(result)
    assert 'restart' in rendered and 'requires_explicit_approval' in rendered


def test_keyword_signatures_point_to_runbooks():
    result = review([record(summary='OOMKilled container api-7d9')])
    labels = {c['label'] for c in result['candidate_explanations']}
    assert 'memory_exhaustion_signal' in labels
    assert 'node-high-memory' in result['recommended_runbooks']


def test_no_candidate_is_explicit_not_silent():
    result = review([record(kind='config_note', summary='routine scaling event', severity='info')])
    assert result['candidate_explanations'][0]['label'] == 'no_candidate_from_supplied_evidence'


def test_missing_evidence_kinds_flagged():
    result = review([record(kind='endpoint_signal', summary='endpoints empty', severity='warning')])
    assert 'deploy_events' in result['missing_evidence_kinds']
    assert 'metric_signals' in result['missing_evidence_kinds']
    assert 'log_signals' in result['missing_evidence_kinds']


def test_rejects_wrong_schema_future_times_and_bad_shapes():
    with pytest.raises(ValueError):
        review_incident_evidence('v0', 'svc', [record()], AS_OF)
    with pytest.raises(ValueError):
        review([record(at='2026-11-23T00:00:00Z')])
    with pytest.raises(ValueError):
        review([record(severity='fatal')])
    with pytest.raises(ValueError):
        review([record(kind='shell_command')])
    with pytest.raises(ValueError):
        review([{**record(), 'extra': 1}])
    with pytest.raises(ValueError):
        review([])
    with pytest.raises(ValueError):
        review([record()] * 201)
    with pytest.raises(ValueError):
        review([record(summary='x' * 501)])


def test_tool_registered_and_runs_under_emergency_stop(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_incident_evidence', {
        'schema_version': SCHEMA, 'service': 'payments-api', 'evidence': [record()], 'as_of': AS_OF}))
    assert result.ok and result.data['evidence_reviewed'] == 1
