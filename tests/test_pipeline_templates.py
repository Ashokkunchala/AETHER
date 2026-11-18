import asyncio

import pytest
import yaml

from aether.devops.pipeline_templates import STAGES, generate_pipeline_scaffold


@pytest.mark.parametrize('platform',['jenkins','github_actions'])
def test_preview_only_no_acceptance_or_action_claim(platform):
    result=generate_pipeline_scaffold(platform)
    for flag in ['files_written','executed','installed','tests_run','image_built','scan_performed','artifact_published','deployment_performed','monitor_started','rollback_performed','approval_granted','workflow_schema_validated']:
        assert result[flag] is False
    assert result['stage_count']==10
    assert result['suggested_review_filename'].endswith('.txt')
    assert result['scaffold_text'].count('NOT IMPLEMENTED')==10
    assert 'not an enforced gate' in result['limits']


@pytest.mark.parametrize('value',['github','GitHub','Jenkins','',None,{},[],"jenkins';sh 'touch /tmp/no'"])
def test_no_arbitrary_template_input(value):
    with pytest.raises(ValueError):generate_pipeline_scaffold(value)


def test_github_yaml_disabled_and_no_actions_credentials_or_checkout():
    text=generate_pipeline_scaffold('github_actions')['scaffold_text']
    # PyYAML YAML1.1 parses on as True; this is test structure only, not GitHub validation.
    doc=yaml.safe_load(text)
    assert doc.get('on',doc.get(True))=={'workflow_dispatch':None}
    assert doc['permissions']=={}
    job=doc['jobs']['review_scaffold']
    assert job['if']=='${{ false }}' and job['timeout-minutes']==5
    assert len(job['steps'])==10
    for step in job['steps']:
        assert set(step)=={'name','run'} and step['run'].startswith('echo "REVIEW ONLY.')
    assert 'uses:' not in text and '${{ secrets' not in text


def test_jenkins_has_no_node_agent_checkout_shell_or_build_steps():
    text=generate_pipeline_scaffold('jenkins')['scaffold_text']
    assert 'agent none' in text and 'skipDefaultCheckout(true)' in text
    assert 'disableConcurrentBuilds()' in text
    for line in text.splitlines():
        assert not line.lstrip().startswith(('sh ','bat ','powershell ','node(','checkout ','build ','input ','post {'))
    assert text.count("        echo 'REVIEW ONLY.")==10
    assert text.count('{')==text.count('}')


@pytest.mark.parametrize('platform',['github_actions','jenkins'])
def test_deterministic_output_and_no_files_or_execution(tmp_path,monkeypatch,platform):
    monkeypatch.chdir(tmp_path)
    import subprocess
    def fail(*a,**kw):raise AssertionError('Must never execute')
    monkeypatch.setattr(subprocess,'run',fail)
    first=generate_pipeline_scaffold(platform);second=generate_pipeline_scaffold(platform)
    assert first==second and list(tmp_path.iterdir())==[]
    first['sources'].clear()
    assert len(generate_pipeline_scaffold(platform)['sources'])==2


@pytest.mark.parametrize('platform',['github_actions','jenkins'])
def test_fixed_stage_coverage_not_actual_implementation(platform):
    text=generate_pipeline_scaffold(platform)['scaffold_text']
    for title,description in STAGES:
        assert title+' - NOT IMPLEMENTED' in text and description in text
    assert 'never automatic' in text


def test_registry_is_safe_and_available_after_stop(tmp_path,monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB',str(tmp_path/'security.db'))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('generate_pipeline_review_scaffold',{'platform':'jenkins'}))
    assert result.ok and not result.data['executed']
    assert not registry.get('generate_pipeline_review_scaffold').confirm_required
