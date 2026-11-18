import asyncio

import pytest

from aether.devops.k8s import review_k8s, review_k8s_text


def message(text, rule):
    return next(row['message'] for row in review_k8s_text(text) if row['rule']==rule)


def test_loadbalancer_pattern_never_claims_public_reachability():
    text='apiVersion: v1\nkind: Service\nspec:\n  type: LoadBalancer\n'
    assert 'public reachability is not established' in message(text,'k8s-public-loadbalancer')
    # Existing line matching can miss fields; internal text isn't proof safe.
    assert review_k8s_text(text+'# internal somewhere\n')==[]


@pytest.mark.parametrize('kind',['RoleBinding','ClusterRoleBinding'])
def test_cluster_admin_name_does_not_grant_effective_cluster_scope(kind):
    text=f'apiVersion: rbac.authorization.k8s.io/v1\nkind: {kind}\nmetadata:\n  name: cluster-admin-not-a-role-reference\n'
    result=message(text,'k8s-cluster-admin-binding')
    assert 'effective privileges are not established' in result
    assert 'namespace/cluster scope' in result


def test_rbac_wildcards_different_rules_not_assumed_same_effective_permission():
    text='kind: Role\nrules:\n- verbs: ["*"]\n  resources: [pods]\n- verbs: [get]\n  resources: ["*"]\n'
    result=message(text,'k8s-wildcard-rbac')
    assert 'Rule association' in result and 'not evaluated' in result


def test_secret_text_not_claimed_committed_or_storage_unencrypted():
    text='kind: Secret\ndata:\n  private: omitted\n'
    result=message(text,'k8s-secret-in-manifest')
    assert 'Base64 is not encryption' in result
    assert 'whether this file was committed' in result


def test_image_value_and_injected_text_not_echoed():
    text='apiVersion: v1\nkind: Pod\nspec:\n  containers:\n  - image: PRIVATE_INSTRUCTION:latest\n'
    result=review_k8s_text(text)
    assert any(r['rule']=='k8s-unpinned-image' for r in result)
    assert 'PRIVATE_INSTRUCTION' not in str(result)


@pytest.mark.parametrize(('line','rule'), [('privileged: true','k8s-privileged'),('hostNetwork: true','k8s-host-network'),
    ('hostPID: true','k8s-host-pid'),('runAsUser: 0','k8s-run-as-root'),('hostPath:','k8s-hostpath'),
    ('allowPrivilegeEscalation: true','k8s-privilege-escalation')])
def test_security_context_lines_remain_pattern_findings_not_runtime(line,rule):
    value=message('kind: Pod\n  '+line+'\n',rule)
    assert 'text pattern found' in value


def test_no_findings_result_still_explicitly_unverified(tmp_path):
    path=tmp_path/'service.yaml';path.write_text('apiVersion: v1\nkind: Service\nspec:\n  type: ClusterIP\n')
    result=review_k8s(str(path))
    assert result['success'] and result['files_scanned']==1 and result['findings']==[]
    for flag in ['yaml_schema_validated','effective_rbac_verified','public_reachability_verified','runtime_security_verified']:
        assert result[flag] is False
    for caveat in ['comments','incorrect indentation','200','symlink','never secure']:
        assert caveat in result['limits']


def test_existing_response_fields_paths_and_rule_ids_remain(tmp_path):
    path=tmp_path/'pod.yaml';path.write_text('apiVersion: v1\nkind: Pod\nspec:\n  privileged: true\n')
    before=path.read_bytes();result=review_k8s(str(path))
    assert path.read_bytes()==before
    assert result['counts']['high']>=1
    finding=next(row for row in result['findings'] if row['rule']=='k8s-privileged')
    assert finding['file']==str(path) and finding['line']==4


def test_comment_match_is_only_a_pattern_not_effective_setting():
    value=message('kind: Pod\n# privileged: true\n','k8s-privileged')
    assert 'runtime privileges are not verified' in value


def test_registry_safe_after_stop_retains_name(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    path=tmp_path/'pod.yaml';path.write_text('apiVersion: v1\nkind: Pod\n')
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('review_k8s',{'path':str(path)}))
    assert result.ok and result.data['effective_rbac_verified'] is False
