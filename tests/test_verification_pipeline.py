"""Generated pipeline text is inspected, never activated on CI/OS/provider."""
import pytest
import yaml

from jarvis.devops.verification_pipeline import (
    CHECKOUT_SHA,
    PYTHON_SHA,
    generate_python_verification_pipeline,
)
from jarvis.tools.builtin_tools import build_registry


@pytest.mark.parametrize('version',['3.11','3.14'])
def test_github_fixed_manual_gate_and_real_steps(version):
    result=generate_python_verification_pipeline('github_actions',version)
    # BaseLoader preserves the YAML1.2 workflow key 'on' (YAML1.1 treats it as bool).
    doc=yaml.load(result['pipeline_text'],Loader=yaml.BaseLoader)
    assert set(doc['on'])=={'workflow_dispatch'}
    gate=doc['on']['workflow_dispatch']['inputs']['reviewed_source_and_costs']
    assert gate['default']=='false' and gate['type']=='boolean'
    job=doc['jobs']['verify'];assert job['timeout-minutes']=='15'
    assert job['if']=='${{ inputs.reviewed_source_and_costs == true }}'
    steps=job['steps']
    assert steps[0]['uses']=='actions/checkout@'+CHECKOUT_SHA
    assert steps[0]['with']['persist-credentials']=='false'
    assert steps[1]['uses']=='actions/setup-python@'+PYTHON_SHA
    assert steps[1]['with']['python-version']==version
    assert steps[-1]['run']=='.aether-ci-venv/bin/python -m pytest -q'
    assert doc['permissions']=={'contents':'read'}
    assert not any(result[k] for k in ['files_written','installed','executed','tests_run','deployment_performed','artifact_published','approval_granted','pipeline_runtime_verified'])


@pytest.mark.parametrize('version',['3.11','3.14'])
def test_jenkins_gate_before_executor_and_fixed_commands(version):
    text=generate_python_verification_pipeline('jenkins',version)['pipeline_text']
    assert text.index('input message:')<text.index("agent { label")
    assert 'agent none' in text and 'skipDefaultCheckout(true)' in text
    assert "label 'aether-python-"+version+"'" in text
    assert "sh 'python"+version+' -m venv .aether-ci-venv' in text
    assert "sh '.aether-ci-venv/bin/python -m pytest -q'" in text
    assert 'checkout scm' in text and 'triggers {' not in text
    assert text.count('{')==text.count('}')


@pytest.mark.parametrize('platform,version', [('gitlab','3.11'),('github_actions','3.12'),('jenkins','3.11;rm -rf /'),('jenkins',"3.11'\nsh 'evil"),('github_actions',None),(None,'3.11')])
def test_no_arbitrary_platform_version_interpolation(platform,version):
    with pytest.raises(ValueError):generate_python_verification_pipeline(platform,version)


def test_output_is_review_text_never_auto_discovered_and_no_operations(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    for platform in ['github_actions','jenkins']:
        result=generate_python_verification_pipeline(platform)
        assert result['suggested_review_filename'].endswith('.txt')
        text=result['pipeline_text']
        for command in ['docker build','kubectl ','terraform apply','curl ','aws ','upload-artifact@']:
            assert command not in text
    assert list(tmp_path.iterdir())==[]


def test_new_registry_tool_and_old_scaffold_preserved():
    registry=build_registry(force=True)
    for name in ['generate_python_verification_pipeline','generate_pipeline_review_scaffold']:
        assert registry.get(name).risk.value==0
    assert 'NOT IMPLEMENTED' in registry.get('generate_pipeline_review_scaffold').handler('jenkins')['scaffold_text']
