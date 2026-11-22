import asyncio
import json

import pytest

from aether.devops.rds_snapshot import review_db_instances, review_db_instances_export


def instance(**changes):
    item = {'DBInstanceIdentifier': 'private-name', 'Engine': 'postgres', 'EngineVersion': '15.4',
            'DBInstanceStatus': 'available', 'PubliclyAccessible': False, 'StorageEncrypted': True,
            'MultiAZ': True, 'DeletionProtection': True, 'BackupRetentionPeriod': 7, 'AllocatedStorage': 100,
            'Endpoint': {'Address': 'private.host', 'Port': 5432}, 'MasterUsername': 'private-user',
            'DBName': 'private-db', 'DBInstanceArn': 'arn:aws:rds:private'}
    item.update(changes)
    return item


def review(item=None, **changes):
    document = {'DBInstances': [instance() if item is None else item]}
    document.update(changes)
    return review_db_instances(document)


def test_reports_fields_and_omits_identifiers():
    result = review()
    row = result['instances'][0]
    assert row['reported_engine'] == 'postgres' and row['reported_status'] == 'available'
    assert row['reported_multi_az'] is True and row['signals'] == []
    assert result['by_reported_status'] == {'available': 1}
    rendered = json.dumps(result)
    for private in ('private-name', 'private.host', 'private-user', 'private-db', 'arn:aws:rds:private'):
        assert private not in rendered
    assert result['inventory_completeness_verified'] is False
    assert 'not live monitoring' in result['limits']


def test_risk_signals_from_reported_fields():
    result = review(instance(PubliclyAccessible=True, StorageEncrypted=False,
                             BackupRetentionPeriod=0, DeletionProtection=False))
    signals = result['instances'][0]['signals']
    assert 'reported_publicly_accessible' in signals
    assert 'reported_unencrypted_storage' in signals
    assert 'reported_backup_retention_zero' in signals
    assert 'reported_deletion_protection_off' in signals


def test_unrecognized_status_reported_not_mapped():
    result = review(instance(DBInstanceStatus='future-state'))
    row = result['instances'][0]
    assert row['reported_status'] == 'unrecognized'
    assert 'unrecognized_instance_status' in row['signals']
    assert result['by_reported_status'] == {'unrecognized': 1}


def test_rejects_bad_shapes_and_unbounded_input():
    with pytest.raises(ValueError):
        review_db_instances({'DBInstances': 'nope'})
    with pytest.raises(ValueError):
        review(instance(BackupRetentionPeriod=36))
    with pytest.raises(ValueError):
        review(instance(PubliclyAccessible='yes'))
    with pytest.raises(ValueError):
        review_db_instances({'DBInstances': [instance()] * 201})


def test_export_hygiene_and_registry_under_stop(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        review_db_instances_export(str(tmp_path))
    path = tmp_path / 'rds.json'
    path.write_text(json.dumps({'DBInstances': [instance()]}))
    assert review_db_instances_export(str(path))['instances_reviewed'] == 1
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_rds_instances', {'path': str(path)}))
    assert result.ok and result.data['instances_reviewed'] == 1
