import asyncio

import pytest

from aether.devops.review import review_cicd


def scan(tmp_path, text, jenkins=False):
    path=tmp_path/'Jenkinsfile' if jenkins else tmp_path/'.github'/'workflows'/'ci.yml'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text)
    return review_cicd(str(path))


@pytest.mark.parametrize('owner',['actions/checkout','actions/setup-python','vendor/private_action'])
def test_all_external_mutable_refs_warn_without_echo(tmp_path,owner):
    result=scan(tmp_path,f'on: workflow_dispatch\npermissions: {{}}\njobs:\n  run:\n    steps:\n    - uses: {owner}@PRIVATE_REF\n')
    assert {r['rule'] for r in result['findings']}=={'gha-unpinned-action'}
    assert 'PRIVATE_REF' not in str(result) and owner not in str(result)
    assert 'First-party' in result['findings'][0]['message']


@pytest.mark.parametrize('ref',['a'*40,'./local'])
def test_full_lower_hex_sha_or_local_not_flagged(tmp_path,ref):
    uses='./local' if ref=='./local' else 'actions/checkout@'+ref
    assert scan(tmp_path,'permissions: {}\n- uses: '+uses)['findings']==[]


@pytest.mark.parametrize('text',['# pull_request_target\n','on:\n  pull_request_target:\n'])
def test_privileged_event_is_pattern_not_unconditional_secret_claim(tmp_path,text):
    rows=scan(tmp_path,text)['findings']
    row=next(r for r in rows if r['rule']=='gha-pull-request-target')
    assert 'depending on configuration' in row['message']
    assert 'not verified' in row['message']


@pytest.mark.parametrize('marker',['', '// input file unrelated', 'input message: "Continue?"', 'skipDefaultCheckout() // input'])
def test_jenkins_input_substring_never_suppresses_apply_warning(tmp_path,marker):
    result=scan(tmp_path,marker+"\nsh 'terraform apply -auto-approve'",True)
    assert [r['rule'] for r in result['findings']]==['jenkins-auto-apply']
    assert 'does not establish' in result['findings'][0]['message']


def test_markers_elsewhere_are_not_proof_of_policy(tmp_path):
    result=scan(tmp_path,'# permissions: {}\n# role-to-assume\n# aws-actions/configure-aws-credentials\n')
    assert result['findings']==[]
    for key in ['workflow_schema_validated','effective_permissions_verified','approval_gates_verified','secret_exposure_verified','execution_security_verified']:
        assert result[key] is False
    for word in ['200','Comments','symlink','never secure','reusable','OIDC','raw action refs']:
        assert word in result['limits']


def test_no_permission_marker_remains_unknown_not_default_write(tmp_path):
    row=scan(tmp_path,'on: workflow_dispatch')['findings'][0]
    assert row['rule']=='gha-no-permissions' and 'not verified' in row['message']


def test_report_still_preserves_rule_severity_path_line(tmp_path):
    result=scan(tmp_path,'permissions: {}\nrun: terraform apply -auto-approve\n')
    row=result['findings'][0]
    assert (row['rule'],row['severity'],row['line'])==('gha-auto-apply','medium',2)
    assert row['file'].endswith('ci.yml') and result['success']


def test_secret_pattern_not_raw_key_echo(tmp_path):
    key='AKIA'+'A'*16
    result=scan(tmp_path,key,True)
    assert result['findings'][0]['rule']=='jenkins-hardcoded-aws'
    assert key not in str(result)


def test_registry_safe_review_after_emergency_stop(tmp_path,monkeypatch):
    from aether.tools.builtin_tools import build_registry, reset_controllers
    from aether.security import SecurityStore
    monkeypatch.setenv("AETHER_SECURITY_DB",str(tmp_path/"security.db"))
    reset_controllers(); registry=build_registry(force=True); SecurityStore().set_stop(True)
    path=tmp_path/'Jenkinsfile'; path.write_text('// no executable pipeline')
    result=asyncio.run(registry.execute('review_cicd',{'path':str(path)}))
    assert result.ok and not result.data["approval_gates_verified"]
    reset_controllers()
