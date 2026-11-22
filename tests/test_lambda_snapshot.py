import asyncio
import json

import pytest

from aether.devops.lambda_snapshot import review_lambda_functions, review_lambda_functions_export


def function(**changes):
    item = {'FunctionName': 'private-name', 'Runtime': 'python3.12', 'PackageType': 'Zip',
            'Architectures': ['x86_64'], 'MemorySize': 256, 'Timeout': 30, 'CodeSize': 1024,
            'Role': 'arn:aws:iam::private', 'Environment': {'Variables': {'SECRET': 'private-value'}},
            'Layers': [{'Arn': 'arn:aws:lambda:private-layer'}]}
    item.update(changes)
    return item


def review(item=None, **changes):
    document = {'Functions': [function() if item is None else item]}
    document.update(changes)
    return review_lambda_functions(document)


def test_reports_configuration_and_omits_sensitive_fields():
    result = review()
    row = result['functions'][0]
    assert row['reported_runtime'] == 'python3.12' and row['reported_memory_mb'] == 256
    assert row['signals'] == []
    assert result['by_reported_runtime'] == {'python3.12': 1}
    rendered = json.dumps(result)
    for private in ('private-name', 'private-value', 'arn:aws:iam::private', 'arn:aws:lambda:private-layer'):
        assert private not in rendered
    assert result['inventory_completeness_verified'] is False
    assert 'deprecation' in result['limits']


def test_maximum_memory_and_timeout_are_signals_not_verdicts():
    result = review(function(MemorySize=10240, Timeout=900))
    signals = result['functions'][0]['signals']
    assert 'reported_memory_at_maximum' in signals and 'reported_timeout_at_maximum' in signals


def test_unrecognized_package_type_reported_not_mapped():
    result = review(function(PackageType='Future'))
    row = result['functions'][0]
    assert row['reported_package_type'] == 'Future'
    assert 'unrecognized_package_type' in row['signals']


def test_rejects_bad_shapes_and_unbounded_input():
    with pytest.raises(ValueError):
        review_lambda_functions({'Functions': 'nope'})
    with pytest.raises(ValueError):
        review(function(MemorySize=0))
    with pytest.raises(ValueError):
        review(function(Timeout=901))
    with pytest.raises(ValueError):
        review(function(Architectures=[]))
    with pytest.raises(ValueError):
        review_lambda_functions({'Functions': [function()] * 501})


def test_export_hygiene_and_registry_under_stop(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        review_lambda_functions_export(str(tmp_path))
    path = tmp_path / 'lambda.json'
    path.write_text(json.dumps({'Functions': [function()]}))
    assert review_lambda_functions_export(str(path))['functions_reviewed'] == 1
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_lambda_functions', {'path': str(path)}))
    assert result.ok and result.data['functions_reviewed'] == 1
