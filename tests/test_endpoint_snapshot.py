import asyncio
import json
import os

import pytest

from aether.devops.endpoint_snapshot import review_endpoint_slices, review_endpoint_slices_export


def endpoint(**changes):
    result={'addresses':['10.0.0.1'],'conditions':{'ready':True,'serving':True,'terminating':False}}
    result.update(changes);return result


def snapshot(**changes):
    result={'apiVersion':'discovery.k8s.io/v1','kind':'EndpointSlice','metadata':{'name':'private-slice','namespace':'private-ns','labels':{'kubernetes.io/service-name':'private-service'}},
            'addressType':'IPv4','endpoints':[endpoint()],'ports':[{'port':8080,'protocol':'TCP'}]}
    result.update(changes);return result


def first(value=None):
    return review_endpoint_slices(snapshot() if value is None else value)['slices'][0]


def test_condition_tuples_preserved_not_health_or_connectivity():
    result=review_endpoint_slices(snapshot())
    assert result['endpoint_records_in_snapshot']==1
    assert result['slices'][0]['condition_combinations']==[{'ready':'True','serving':'True','terminating':'False','record_count':1}]
    assert not result['connectivity_verified'] and not result['unique_backends_computed']
    assert not result['slices'][0]['backend_health_verified']


def test_missing_null_and_false_are_distinct_not_default_true():
    row=first(snapshot(endpoints=[endpoint(conditions={}),endpoint(conditions={'ready':None}),endpoint(conditions={'ready':False})]))
    assert {c['ready'] for c in row['condition_combinations']}=={'Missing','Null','False'}
    assert row['review_signal_record_counts']['some_condition_values_unreported_no_default_inference']==3


def test_ready_true_nonserving_or_terminating_review_not_impossible_or_eligible():
    row=first(snapshot(endpoints=[endpoint(conditions={'ready':True,'serving':False}),endpoint(conditions={'ready':True,'serving':True,'terminating':True})]))
    assert row['review_signal_record_counts']['ready_true_with_nonserving_or_terminating_flags_review']==2
    assert not row['routing_verified']


def test_multiple_slices_can_duplicate_endpoint_records_not_unique_backends():
    a=snapshot();b=snapshot(metadata={'name':'slice-two','namespace':'private-ns'})
    result=review_endpoint_slices({'apiVersion':'discovery.k8s.io/v1','kind':'EndpointSliceList','items':[a,b]})
    assert result['endpoint_records_in_snapshot']==2 and not result['unique_backends_computed']
    assert 'not unique endpoints' in result['limits']


def test_private_values_omitted_no_service_association_claim():
    result=review_endpoint_slices(snapshot(endpoints=[endpoint(targetRef={'name':'private-pod'},nodeName='private-node')],ports=[{'port':61234,'name':'private-port'}]))
    for value in ['private-slice','private-ns','private-service','10.0.0.1','private-pod','private-node','private-port','61234']:
        assert value not in json.dumps(result)
    assert result['slices'][0]['service_name_label_present']
    assert not result['slices'][0]['service_association_verified']


@pytest.mark.parametrize(('family','address'),[('IPv4','192.0.2.5'),('IPv6','2001:db8::1'),('FQDN','private.example.' )])
def test_supported_address_shapes_not_reachability(family,address):
    assert first(snapshot(addressType=family,endpoints=[endpoint(addresses=[address])]))['endpoint_records_in_slice']==1


@pytest.mark.parametrize(('family','address'),[('IPv4','::1'),('IPv6','127.0.0.1'),('IPv4','not-ip'),('IPv6','fe80::1%eth0'),('FQDN','bad name'),('FQDN','<script>')])
def test_bad_address_shape_or_family(family,address):
    with pytest.raises(ValueError):first(snapshot(addressType=family,endpoints=[endpoint(addresses=[address])]))


@pytest.mark.parametrize('change',[dict(apiVersion='v1'),dict(kind='Service'),dict(metadata=None),dict(metadata={}),
    dict(metadata={'name':'a','namespace':'n','labels':None}), dict(metadata={'name':'a','namespace':'n','labels':{'kubernetes.io/service-name':None}}),
    dict(addressType='future'),dict(addressType=[]),dict(endpoints=None),dict(endpoints=[None]),
    dict(endpoints=[endpoint(addresses=[])]),dict(endpoints=[endpoint(addresses=[True])]),
    dict(endpoints=[endpoint(conditions=None)]),dict(endpoints=[endpoint(conditions={'ready':'true'})]),
    dict(endpoints=[endpoint(conditions={'serving':1})]),dict(ports=None),dict(ports=[None]),
    dict(ports=[{'port':True}]),dict(ports=[{'port':0}]),dict(ports=[{'port':65536}]),dict(ports=[{'protocol':'ICMP'}]),
    dict(endpoints=[endpoint()]*1001),dict(ports=[{}]*101)])
def test_bad_slice(change):
    with pytest.raises(ValueError): review_endpoint_slices(snapshot(**change))


@pytest.mark.parametrize('document',[None,[],{}, {'apiVersion':'discovery.k8s.io/v1','kind':'EndpointSliceList','items':None},
    {'apiVersion':'discovery.k8s.io/v1','kind':'EndpointSliceList','items':[snapshot(),snapshot()]},
    {'apiVersion':'discovery.k8s.io/v1','kind':'EndpointSliceList','items':[snapshot()]*101},
    {'apiVersion':'v1','kind':'List','items':[{'kind':'Endpoints','apiVersion':'v1'}]},
    {'apiVersion':'v1','kind':'List','items':[],'metadata':{'continue':True}}])
def test_bad_document(document):
    with pytest.raises(ValueError): review_endpoint_slices(document)


def test_empty_omitted_ports_null_port_unknown_condition_not_zero_outage():
    value=snapshot(endpoints=[],ports=[])
    row=first(value)
    assert row['endpoint_records_in_slice']==0 and not row['routing_verified']
    del value['ports'];assert not first(value)['ports_field_present']
    value['ports']=[{'port':None},{}];assert first(value)['unspecified_port_records']==2
    assert first(snapshot(endpoints=[endpoint(conditions={'future':'PRIVATE'})]))['condition_combinations'][0]['ready']=='Missing'
    result=review_endpoint_slices({'apiVersion':'v1','kind':'List','items':[],'metadata':{'continue':'PRIVATE_TOKEN'}})
    assert result['continuation_token_present'] and not result['inventory_completeness_verified']
    assert 'PRIVATE_TOKEN' not in json.dumps(result)


def test_total_endpoint_bound_and_record_not_address_count():
    items=[snapshot(metadata={'name':f'slice-{i}','namespace':'ns'},endpoints=[endpoint()]*1000) for i in range(3)]
    document={'apiVersion':'v1','kind':'List','items':items}
    with pytest.raises(ValueError):review_endpoint_slices(document)
    document['items']=items[:2]
    assert review_endpoint_slices(document)['endpoint_records_in_snapshot']==2000
    assert first(snapshot(endpoints=[endpoint(addresses=['10.0.0.1','10.0.0.2'])]))['endpoint_records_in_slice']==1


@pytest.mark.parametrize('payload',[b'bad',b'\xff',b'{"apiVersion":"v1","apiVersion":"v1"}',b'{"x":NaN}',b'x'*2000001,b'['*2000])
def test_invalid_json(tmp_path,payload):
    path=tmp_path/'slice.json';path.write_bytes(payload)
    with pytest.raises(ValueError):review_endpoint_slices_export(str(path))


def test_no_writes_exec_or_special_files(tmp_path):
    path=tmp_path/'slice.json';marker=tmp_path/'never-created'
    text=f"__import__('pathlib').Path({str(marker)!r}).touch()"
    path.write_text(json.dumps(snapshot(endpoints=[endpoint(targetRef={'name':text})])))
    before=path.read_bytes();assert review_endpoint_slices_export(str(path))['slices_reviewed']==1
    assert path.read_bytes()==before and not marker.exists()
    link=tmp_path/'link.json';link.symlink_to(path)
    with pytest.raises(ValueError):review_endpoint_slices_export(str(link))
    if hasattr(os,'mkfifo'):
        fifo=tmp_path/'pipe.json';os.mkfifo(fifo)
        with pytest.raises(ValueError):review_endpoint_slices_export(str(fifo))


def test_registry_safe_after_stop_no_network_probe(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    path=tmp_path/'slice.json';path.write_text(json.dumps(snapshot()))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('review_kubernetes_endpoints',{'path':str(path)}))
    assert result.ok and result.data['slices_reviewed']==1
