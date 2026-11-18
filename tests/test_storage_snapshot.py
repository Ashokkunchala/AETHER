import asyncio
import json
import os

import pytest

from aether.devops.storage_snapshot import PV, PVC, review_storage, review_storage_export


def resource(kind=PVC, **changes):
    result={'apiVersion':'v1','kind':kind,'metadata':{'name':'private-resource'},'spec':{},'status':{'phase':'Bound'}}
    if kind==PVC: result['metadata']['namespace']='private-namespace'
    result.update(changes)
    return result


def row(value=None):
    return review_storage(resource() if value is None else value)['resources'][0]


@pytest.mark.parametrize(('kind','phase'), [(PV,'Pending'),(PV,'Available'),(PV,'Bound'),(PV,'Released'),(PV,'Failed'),(PVC,'Pending'),(PVC,'Bound'),(PVC,'Lost')])
def test_phases_reported_without_health_cleanup_or_mount_claim(kind,phase):
    item=row(resource(kind,status={'phase':phase}))
    assert item['reported_phase']==phase
    assert not any(item[key] for key in ['safe_to_delete','binding_verified','mounted_verified','storage_health_verified'])


def test_unknown_missing_and_null_phase_distinct():
    assert row(resource(status={}))['reported_phase']=='Missing'
    assert row(resource(status={'phase':'FuturePhase'}))['reported_phase']=='Unknown'
    with pytest.raises(ValueError): row(resource(status={'phase':None}))


def test_delete_reclaim_warning_not_deletion_or_retention_assurance():
    item=row(resource(PV,spec={'persistentVolumeReclaimPolicy':'Delete'}))
    assert 'reported_delete_reclaim_can_remove_backing_storage' in item['signals']
    for value in ['Retain','Recycle','future']:
        item=row(resource(PV,spec={'persistentVolumeReclaimPolicy':value}))
        assert item['reported_reclaim_policy']==('Unknown' if value=='future' else value)
        assert item['safe_to_delete'] is False


def test_missing_empty_named_storage_class_stay_distinct():
    assert row()['reported_storage_class_status']=='missing'
    assert row(resource(spec={'storageClassName':''}))['reported_storage_class_status']=='explicit_empty'
    assert row(resource(spec={'storageClassName':'private-class'}))['reported_storage_class_status']=='named_value_omitted'


def test_binding_reference_only_field_presence_not_matching_or_proof():
    assert 'reported_bound_without_volume_name' in row()['signals']
    assert row(resource(spec={'volumeName':'private-pv'}))['binding_reference_field_present']
    assert row(resource(PV,spec={'claimRef':{}}))['binding_reference_field_present']
    assert not row(resource(PV,spec={'claimRef':{}}))['binding_verified']


def test_private_content_omitted_and_deletion_only_presence():
    item=resource(PV,metadata={'name':'private-resource','labels':{'a':'PRIVATE_LABEL'},'deletionTimestamp':'PRIVATE_DATE'},
                  spec={'claimRef':{'name':'PRIVATE_CLAIM'},'csi':{'volumeHandle':'PRIVATE_HANDLE'},'capacity':{'storage':'PRIVATE_CAPACITY'}},
                  status={'phase':'Released','message':'PRIVATE_MESSAGE'})
    result=review_storage({'apiVersion':'v1','kind':'List','items':[item], 'metadata':{'continue':'PRIVATE_TOKEN'}})
    text=json.dumps(result)
    for value in ['private-resource','PRIVATE_LABEL','PRIVATE_DATE','PRIVATE_CLAIM','PRIVATE_HANDLE','PRIVATE_CAPACITY','PRIVATE_MESSAGE','PRIVATE_TOKEN']:
        assert value not in text
    assert result['continuation_token_present']
    assert 'deletion_timestamp_present_no_age_or_finalizer_inference' in result['resources'][0]['signals']


def test_resize_conditions_no_success_or_unknown_type_inference():
    item=row(resource(status={'phase':'Bound','conditions':[{'type':'Resizing','status':'True'}, {'type':'FileSystemResizePending','status':'Unknown'}, {'type':'PRIVATE_FUTURE','status':'True'}]}))
    assert item['pvc_condition_records']==3
    assert len(item['reported_resize_conditions'])==2
    assert 'PRIVATE_FUTURE' not in json.dumps(item)
    assert 'unrecognized_pvc_conditions_not_interpreted' in item['signals']


def test_pvc_namespaces_distinguish_duplicate_keys_and_kinds():
    first=resource();second=resource(metadata={'name':'private-resource','namespace':'other'})
    result=review_storage({'apiVersion':'v1','kind':'List','items':[first,second,resource(PV)]})
    assert result['storage_records_reviewed']==3
    assert 'distinct disks' in result['limits']
    assert 'private-namespace' not in json.dumps(result)


@pytest.mark.parametrize('change',[dict(kind='Pod'),dict(apiVersion='v2'),dict(metadata=None),dict(metadata={}),
    dict(metadata={'name':'a','namespace':''}),dict(metadata={'name':'bad name','namespace':'ns'}),
    dict(status=None),dict(spec=None),dict(status={'phase':1}),dict(spec={'volumeName':''}),
    dict(spec={'storageClassName':None}),dict(status={'conditions':None}),dict(status={'conditions':[None]}),
    dict(status={'conditions':[{'type':'Resizing','status':True}]}),dict(status={'conditions':[{'type':'Resizing','status':'true'}]}),
    dict(status={'conditions':[{'type':'x','status':'True'}]*2}),dict(status={'conditions':[{'type':str(i),'status':'True'} for i in range(101)]}),
    dict(metadata={'name':'a','namespace':'ns','deletionTimestamp':None})])
def test_bad_resources(change):
    with pytest.raises(ValueError): review_storage(resource(**change))


@pytest.mark.parametrize('document',[None,[],{}, {'apiVersion':'v1','kind':'List','items':None},
    {'apiVersion':'v1','kind':'List','items':[resource(),resource()]},
    {'apiVersion':'v1','kind':'List','items':[resource()]*501},
    {'apiVersion':'v1','kind':PV+'List','items':[resource()]},
    {'apiVersion':'v1','kind':PVC+'List','items':[resource(PV)]},
    {'apiVersion':'v1','kind':'List','items':[],'metadata':{'continue':True}}])
def test_bad_documents(document):
    with pytest.raises(ValueError): review_storage(document)


def test_pv_namespace_and_claim_reference_type_refused():
    with pytest.raises(ValueError): review_storage(resource(PV,metadata={'name':'a','namespace':'ns'}))
    with pytest.raises(ValueError): review_storage(resource(PV,spec={'claimRef':None}))


def test_empty_is_not_healthy_full_limit_and_typed_lists():
    for kind in [PV+'List',PVC+'List','List']:
        result=review_storage({'apiVersion':'v1','kind':kind,'items':[]})
        assert result['storage_records_reviewed']==0
        assert not result['inventory_completeness_verified'] and not result['snapshot_freshness_verified']
    items=[resource(metadata={'name':f'pvc-{i}','namespace':'ns'}) for i in range(500)]
    assert review_storage({'apiVersion':'v1','kind':PVC+'List','items':items})['storage_records_reviewed']==500


@pytest.mark.parametrize('payload',[b'bad',b'\xff',b'{"apiVersion":"v1","apiVersion":"v1"}',b'{"x":Infinity}',b'x'*2000001,b'['*2000])
def test_invalid_json(tmp_path,payload):
    path=tmp_path/'storage.json';path.write_bytes(payload)
    with pytest.raises(ValueError): review_storage_export(str(path))


def test_regular_file_only_no_writes_or_execution(tmp_path):
    path=tmp_path/'storage.json';marker=tmp_path/'never-created'
    text=f"__import__('pathlib').Path({str(marker)!r}).touch()"
    path.write_text(json.dumps(resource(status={'phase':'Pending','message':text})))
    before=path.read_bytes();result=review_storage_export(str(path))
    assert result['storage_records_reviewed']==1 and path.read_bytes()==before and not marker.exists()
    link=tmp_path/'link.json';link.symlink_to(path)
    with pytest.raises(ValueError): review_storage_export(str(link))
    if hasattr(os,'mkfifo'):
        fifo=tmp_path/'pipe.json';os.mkfifo(fifo)
        with pytest.raises(ValueError): review_storage_export(str(fifo))


def test_registry_safe_after_stop_no_cluster_change(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    path=tmp_path/'storage.json';path.write_text(json.dumps(resource()))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('review_kubernetes_storage',{'path':str(path)}))
    assert result.ok and result.data['storage_records_reviewed']==1
