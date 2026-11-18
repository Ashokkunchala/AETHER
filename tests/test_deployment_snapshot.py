import asyncio
import json
import os

import pytest

from aether.devops.deployment_snapshot import review_deployments, review_deployments_export


def condition(kind='Progressing',status='True',reason='NewReplicaSetAvailable',**extra):
    return {'type':kind,'status':status,'reason':reason,**extra}


def deployment(**changes):
    value={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'private-app','namespace':'private-ns','generation':4},
           'spec':{'replicas':3,'paused':False},'status':{'observedGeneration':4,'replicas':3,'updatedReplicas':3,'readyReplicas':3,'availableReplicas':3,'unavailableReplicas':0,'conditions':[condition(),condition('Available','True','MinimumReplicasAvailable')]}}
    value.update(changes);return value


def row(value=None):
    return review_deployments(deployment() if value is None else value)['deployments'][0]


def test_matching_ready_counters_not_verified_release_or_health():
    value=row()
    assert value['generation_status']=='reported_generation_match'
    for flag in ['rollout_complete_verified','application_health_verified','safe_to_deploy_or_scale']:assert value[flag] is False
    assert 'reported_progressing_true_not_completion_proof' in value['signals']
    assert 'reported_minimum_availability_not_application_health' in value['signals']


@pytest.mark.parametrize(('observed','state'),[(3,'controller_behind_reported_generation'),(4,'reported_generation_match'),(5,'observed_generation_ahead_review')])
def test_generation_status(observed,state):
    item=deployment();item['status']['observedGeneration']=observed
    assert row(item)['generation_status']==state


def test_missing_counters_not_zero_and_missing_desired_not_one():
    value=row(deployment(spec={},status={}))
    assert value['reported_desired_replicas'] is None
    assert value['reported_replica_counters']['replicas'] is None
    assert value['generation_status']=='unknown_missing_generation'
    assert value['reported_conditions']['Available']['reported_status']=='Missing'


def test_paused_stall_no_automatic_rollback_or_clock_math():
    item=deployment(spec={'replicas':3,'paused':True,'progressDeadlineSeconds':1})
    item['status']['conditions']=[condition(status='False',reason='ProgressDeadlineExceeded')]
    value=row(item)
    assert 'reported_paused_no_progress_deadline_inference' in value['signals']
    assert 'reported_progress_deadline_exceeded_no_automatic_rollback' in value['signals']
    assert not value['safe_to_deploy_or_scale']


def test_updated_available_comparison_not_failure_cause_surges_allowed():
    item=deployment();item['status'].update(updatedReplicas=1,availableReplicas=2,replicas=5,terminatingReplicas=7,unavailableReplicas=8)
    value=row(item)
    assert 'reported_updated_below_desired' in value['signals']
    assert 'reported_available_below_desired' in value['signals']
    assert value['reported_replica_counters']['terminatingReplicas']==7
    assert not value['application_health_verified']


def test_zero_desired_not_service_availability():
    value=row(deployment(spec={'replicas':0}))
    assert 'reported_zero_desired_not_application_availability' in value['signals']


def test_no_private_values_or_arbitrary_reasons_echo():
    item=deployment(spec={'replicas':3,'template':{'image':'PRIVATE_IMAGE'}},metadata={'name':'private-app','namespace':'private-ns','generation':4,'annotations':{'key':'PRIVATE_VALUE'}})
    item['status']['conditions']=[condition(reason='PRIVATE_REASON',message='PRIVATE_INSTRUCTION'),condition('PRIVATE_TYPE','Unknown','PRIVATE_REASON')]
    result=review_deployments({'apiVersion':'v1','kind':'List','items':[item],'metadata':{'continue':'PRIVATE_TOKEN'}})
    for value in ['private-app','private-ns','PRIVATE_IMAGE','PRIVATE_VALUE','PRIVATE_REASON','PRIVATE_INSTRUCTION','PRIVATE_TYPE','PRIVATE_TOKEN']:assert value not in json.dumps(result)
    assert result['continuation_token_present']
    assert result['deployments'][0]['unrecognized_condition_count']==1


@pytest.mark.parametrize('change',[dict(kind='Pod'),dict(apiVersion='v1'),dict(metadata=None),dict(metadata={}),
    dict(metadata={'name':'a','namespace':'n','generation':True}),dict(metadata={'name':'a','namespace':'n','generation':-1}),
    dict(spec=None),dict(status=None),dict(spec={'replicas':None}),dict(spec={'replicas':True}),dict(spec={'paused':'false'}),
    dict(status={'replicas':-1}),dict(status={'observedGeneration':'4'}),dict(status={'conditions':None}),
    dict(status={'conditions':[None]}),dict(status={'conditions':[condition(status=True)]}),
    dict(status={'conditions':[condition(),condition()]}),dict(status={'conditions':[condition(reason=None)]}),
    dict(status={'conditions':[condition(kind=str(i)) for i in range(101)]})])
def test_bad_deployment(change):
    with pytest.raises(ValueError):review_deployments(deployment(**change))


@pytest.mark.parametrize('document',[None,[],{}, {'apiVersion':'apps/v1','kind':'DeploymentList','items':None},
    {'apiVersion':'apps/v1','kind':'DeploymentList','items':[deployment(),deployment()]},
    {'apiVersion':'apps/v1','kind':'DeploymentList','items':[deployment()]*501},
    {'apiVersion':'v1','kind':'List','items':[{'apiVersion':'v1','kind':'Pod'}]},
    {'apiVersion':'v1','kind':'List','items':[],'metadata':{'continue':True}}])
def test_bad_document(document):
    with pytest.raises(ValueError):review_deployments(document)


def test_empty_full_limit_no_scope_health_assurance():
    doc={'apiVersion':'apps/v1','kind':'DeploymentList','items':[]};result=review_deployments(doc)
    assert result['deployments_reviewed']==0 and not result['inventory_completeness_verified']
    doc['items']=[deployment(metadata={'name':f'app-{i}','namespace':'ns'}) for i in range(500)]
    assert review_deployments(doc)['deployments_reviewed']==500


@pytest.mark.parametrize('payload',[b'bad',b'\xff',b'{"kind":"a","kind":"b"}',b'{"x":NaN}',b'x'*2000001,b'['*2000])
def test_invalid_json(tmp_path,payload):
    path=tmp_path/'rollout.json';path.write_bytes(payload)
    with pytest.raises(ValueError):review_deployments_export(str(path))


def test_no_file_writes_execution_or_special_file(tmp_path):
    marker=tmp_path/'never-created';text=f"__import__('pathlib').Path({str(marker)!r}).touch()"
    item=deployment();item['status']['conditions']=[condition(message=text)]
    path=tmp_path/'rollout.json';path.write_text(json.dumps(item));before=path.read_bytes()
    assert review_deployments_export(str(path))['deployments_reviewed']==1
    assert path.read_bytes()==before and not marker.exists()
    link=tmp_path/'link.json';link.symlink_to(path)
    with pytest.raises(ValueError):review_deployments_export(str(link))
    if hasattr(os,'mkfifo'):
        fifo=tmp_path/'pipe.json';os.mkfifo(fifo)
        with pytest.raises(ValueError):review_deployments_export(str(fifo))


def test_registry_safe_stop_not_deploy_or_scale(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    path=tmp_path/'rollout.json';path.write_text(json.dumps(deployment()))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('review_kubernetes_deployments',{'path':str(path)}))
    assert result.ok and result.data['deployments_reviewed']==1
