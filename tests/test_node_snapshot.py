import asyncio
import json
import os

import pytest

from jarvis.devops.node_snapshot import CONDITIONS, review_nodes, review_nodes_export


def condition(kind='Ready', status='True', **extra):
    return {'type': kind, 'status': status, **extra}


def node(**changes):
    result = {'apiVersion': 'v1', 'kind': 'Node', 'metadata': {'name': 'private-node'},
              'spec': {}, 'status': {'conditions': [condition()]}}
    result.update(changes)
    return result


def first(item=None):
    return review_nodes(node() if item is None else item)['nodes'][0]


@pytest.mark.parametrize(('value','classification'), [('True','reported_ready'), ('False','reported_not_ready'), ('Unknown','reported_ready_unknown')])
def test_ready_true_false_unknown_distinct_not_health(value, classification):
    row = first(node(status={'conditions': [condition(status=value)]}))
    assert row['classification'] == classification
    assert not row['node_health_verified'] and not row['scheduling_eligibility_verified']
    assert 'MemoryPressure' in row['missing_conditions']


def test_missing_never_false_or_healthy():
    row = first(node(status={}))
    assert row['classification'] == 'ready_condition_missing'
    assert row['reported_conditions'] == dict.fromkeys(CONDITIONS, 'Missing')
    assert not row['conditions_field_present']
    assert first(node(status={'conditions': []}))['conditions_field_present']


@pytest.mark.parametrize(('kind','signal'), [('MemoryPressure','memory_pressure'), ('DiskPressure','disk_pressure'),
    ('PIDPressure','pid_pressure'), ('NetworkUnavailable','network_unavailable')])
def test_adverse_signal_not_hidden_by_ready_true(kind, signal):
    row = first(node(status={'conditions': [condition(), condition(kind)]}))
    assert 'reported_'+signal in row['signals']
    assert 'ready_and_adverse_conditions_coexist_review' in row['signals']


@pytest.mark.parametrize('value', ['False', 'Unknown'])
def test_pressure_false_unknown_preserved_without_asserted_pressure(value):
    row = first(node(status={'conditions': [condition('DiskPressure', value)]}))
    assert row['reported_conditions']['DiskPressure'] == value
    assert 'reported_disk_pressure' not in row['signals']


def test_cordon_is_spec_field_not_condition_and_no_scheduling_promise():
    row = first(node(spec={'unschedulable': True}))
    assert row['reported_unschedulable'] is True
    assert 'reported_unschedulable_new_scheduling_disabled' in row['signals']
    assert first()['reported_unschedulable'] is None
    assert first(node(spec={'unschedulable': False}))['reported_unschedulable'] is False
    row = first(node(status={'conditions': [condition('SchedulingDisabled')]}))
    assert row['unrecognized_condition_count'] == 1 and row['classification'] == 'ready_condition_missing'


def test_no_names_messages_labels_addresses_tokens_or_times_echo():
    item = node(metadata={'name': 'private-node', 'labels': {'private-label':'PRIVATE_VALUE'}},
                status={'addresses': [{'address':'PRIVATE_IP'}], 'conditions': [condition(message='PRIVATE_MESSAGE', reason='PRIVATE_REASON', lastHeartbeatTime='PRIVATE_DATE')]},
                spec={'providerID':'PRIVATE_PROVIDER'})
    result = review_nodes({'apiVersion':'v1','kind':'NodeList','items':[item], 'metadata':{'continue':'PRIVATE_TOKEN'}})
    text = json.dumps(result)
    for value in ['private-node','private-label','PRIVATE_VALUE','PRIVATE_IP','PRIVATE_MESSAGE','PRIVATE_REASON','PRIVATE_DATE','PRIVATE_PROVIDER','PRIVATE_TOKEN']:
        assert value not in text
    assert result['continuation_token_present'] and not result['snapshot_freshness_verified']


@pytest.mark.parametrize('change', [dict(apiVersion='v2'), dict(kind='Pod'), dict(metadata=None), dict(metadata={}),
    dict(metadata={'name': 'bad name'}), dict(metadata={'name': 'a'*254}), dict(spec=None), dict(status=None),
    dict(spec={'unschedulable': 'false'}), dict(spec={'unschedulable': None}), dict(status={'conditions':None}),
    dict(status={'conditions':[None]}), dict(status={'conditions':[{}]}),
    dict(status={'conditions':[condition(status=True)]}), dict(status={'conditions':[condition(status='true')]}),
    dict(status={'conditions':[condition(status=None)]}), dict(status={'conditions':[condition(),condition()]}),
    dict(status={'conditions':[condition('future'),condition('future')]}), dict(status={'conditions':[condition('x'*101)]}),
    dict(status={'conditions':[condition(str(i)) for i in range(101)]})])
def test_invalid_node(change):
    with pytest.raises(ValueError):
        review_nodes(node(**change))


@pytest.mark.parametrize('document', [None, [], {}, {'apiVersion':'v1','kind':'NodeList','items':None},
    {'apiVersion':'v1','kind':'NodeList','items':[node(),node()]},
    {'apiVersion':'v1','kind':'NodeList','items':[node()]*501},
    {'apiVersion':'v1','kind':'List','items':[{'apiVersion':'v1','kind':'Pod'}]},
    {'apiVersion':'v1','kind':'NodeList','items':[], 'metadata':{'continue':True}}])
def test_bad_document(document):
    with pytest.raises(ValueError):
        review_nodes(document)


def test_empty_does_not_mean_cluster_healthy_and_500_nodes():
    document = {'apiVersion':'v1','kind':'NodeList','items':[]}
    result = review_nodes(document)
    assert result['node_records_reviewed'] == 0
    assert not result['cluster_health_verified'] and not result['inventory_completeness_verified']
    document['kind'] = 'List'
    document['items'] = [node(metadata={'name':f'node-{i}'}) for i in range(500)]
    assert review_nodes(document)['node_records_reviewed'] == 500


@pytest.mark.parametrize('payload', [b'bad', b'\xff', b'{"apiVersion":"v1","apiVersion":"v1"}', b'{"v":NaN}', b'x'*2000001, b'['*2000])
def test_bad_json(tmp_path, payload):
    path = tmp_path / 'node.json';path.write_bytes(payload)
    with pytest.raises(ValueError):
        review_nodes_export(str(path))


def test_no_file_mutation_code_execution_or_special_files(tmp_path):
    marker = tmp_path / 'never-created'
    path = tmp_path / 'node.json'
    text = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    path.write_text(json.dumps(node(status={'conditions':[condition(message=text)]})))
    before = path.read_bytes()
    assert review_nodes_export(str(path))['node_records_reviewed'] == 1
    assert path.read_bytes() == before and not marker.exists()
    link = tmp_path / 'link.json';link.symlink_to(path)
    with pytest.raises(ValueError): review_nodes_export(str(link))
    if hasattr(os, 'mkfifo'):
        fifo=tmp_path/'pipe.json';os.mkfifo(fifo)
        with pytest.raises(ValueError): review_nodes_export(str(fifo))


def test_registry_safe_stop_no_cluster_command(tmp_path, monkeypatch):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'safety.db'))
    path=tmp_path/'node.json';path.write_text(json.dumps(node()))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('review_kubernetes_nodes',{'path':str(path)}))
    assert result.ok and result.data['node_records_reviewed']==1
