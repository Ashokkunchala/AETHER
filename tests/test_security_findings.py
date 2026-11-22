import asyncio
import json

import pytest

from aether.devops.security_findings import (
    review_guardduty_findings,
    review_guardduty_findings_export,
    review_security_hub_findings,
    review_security_hub_findings_export,
)


def hub_finding(**changes):
    item = {'Types': ['Software and Configuration Checks/Industry and Regulatory Standards/PCI'],
            'Severity': {'Label': 'HIGH'}, 'Workflow': {'Status': 'NEW'}, 'RecordState': 'ACTIVE',
            'Compliance': {'Status': 'FAILED'}, 'Id': 'private-finding-id', 'AwsAccountId': '111122223333',
            'Title': 'private title', 'Description': 'private description',
            'Resources': [{'Type': 'AwsEc2Instance', 'Id': 'i-private'}]}
    item.update(changes)
    return item


def hub_review(item=None, **changes):
    document = {'Findings': [hub_finding() if item is None else item]}
    document.update(changes)
    return review_security_hub_findings(document)


def test_hub_counts_reported_labels_and_omits_private_fields():
    result = hub_review()
    assert result['by_reported_severity'] == {'HIGH': 1}
    assert result['by_reported_workflow_status'] == {'NEW': 1}
    assert result['by_reported_record_state'] == {'ACTIVE': 1}
    assert result['by_reported_compliance_status'] == {'FAILED': 1}
    row = result['findings'][0]
    assert row['reported_severity'] == 'HIGH' and row['signals'] == []
    rendered = json.dumps(result)
    for private in ('private-finding-id', '111122223333', 'private title', 'private description', 'i-private'):
        assert private not in rendered
    assert result['coverage_verified'] is False and result['snapshot_freshness_verified'] is False
    assert 'never means secure' in result['limits']


def test_hub_unrecognized_values_are_reported_not_mapped():
    result = hub_review(hub_finding(Severity={'Label': 'FUTURE'}, Workflow={'Status': 'FUTURE'}))
    row = result['findings'][0]
    assert row['reported_severity'] == 'unrecognized'
    assert row['reported_workflow_status'] == 'unrecognized'
    assert 'unrecognized_severity_label' in row['signals'] and 'unrecognized_workflow_status' in row['signals']


def test_hub_requires_findings_array_and_bounded_types():
    with pytest.raises(ValueError):
        review_security_hub_findings({'Findings': 'not-a-list'})
    with pytest.raises(ValueError):
        hub_review(hub_finding(Types=[]))
    with pytest.raises(ValueError):
        hub_review(hub_finding(Types=['x' * 201]))
    with pytest.raises(ValueError):
        hub_review(hub_finding(Severity={'Label': None}))
    with pytest.raises(ValueError):
        review_security_hub_findings({'Findings': [hub_finding()] * 501})


def gd_finding(**changes):
    item = {'Type': 'UnauthorizedAccess:EC2/MaliciousIPCaller.Custom', 'Severity': 7.5,
            'Resource': {'ResourceType': 'Instance', 'InstanceDetails': {'InstanceId': 'i-private'}},
            'Id': 'private-id', 'AccountId': '111122223333', 'Title': 'private', 'Arn': 'arn:aws:guardduty:private'}
    item.update(changes)
    return item


def test_guardduty_bands_severities_and_omits_identifiers():
    result = review_guardduty_findings({'Findings': [gd_finding(), gd_finding(Severity=2.0), gd_finding(Severity=4.0)]})
    assert result['by_severity_band'] == {'high': 1, 'low': 1, 'medium': 1}
    assert result['by_reported_type'] == {'UnauthorizedAccess:EC2/MaliciousIPCaller.Custom': 3}
    assert result['findings'][0]['reported_resource_type'] == 'Instance'
    rendered = json.dumps(result)
    for private in ('private-id', '111122223333', 'i-private', 'arn:aws:guardduty:private'):
        assert private not in rendered
    assert result['coverage_verified'] is False
    assert 'zero findings never means safe' in result['limits']


def test_guardduty_rejects_out_of_range_severity_and_bad_shapes():
    with pytest.raises(ValueError):
        review_guardduty_findings({'Findings': [gd_finding(Severity=11)]})
    with pytest.raises(ValueError):
        review_guardduty_findings({'Findings': [gd_finding(Severity=True)]})
    with pytest.raises(ValueError):
        review_guardduty_findings({'Findings': [gd_finding(Type='')]})


def test_exports_reject_directories_and_duplicate_fields(tmp_path):
    with pytest.raises(ValueError):
        review_security_hub_findings_export(str(tmp_path))
    path = tmp_path / 'findings.json'
    path.write_text(json.dumps({'Findings': [gd_finding()]}))
    assert review_guardduty_findings_export(str(path))['findings_reviewed'] == 1
    path.write_text('{"Findings": [], "Findings": []}')
    with pytest.raises(ValueError):
        review_guardduty_findings_export(str(path))
    hub = tmp_path / 'hub.json'
    hub.write_text(json.dumps({'Findings': [hub_finding()]}))
    assert review_security_hub_findings_export(str(hub))['findings_reviewed'] == 1


def test_tools_registered_and_run_under_emergency_stop(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    path = tmp_path / 'findings.json'
    path.write_text(json.dumps({'Findings': [hub_finding()]}))
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_security_hub_findings', {'path': str(path)}))
    assert result.ok and result.data['findings_reviewed'] == 1
