"""Generate opt-in Python verification pipeline text, never install or execute it."""
from __future__ import annotations

CHECKOUT_SHA='11d5960a326750d5838078e36cf38b85af677262'
PYTHON_SHA='a26af69be951a213d495a4c3e4e4022e16d87065'
SOURCES=[
    'https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax',
    'https://www.jenkins.io/doc/book/pipeline/syntax/',
    'https://api.github.com/repos/actions/checkout/git/ref/tags/v4',
    'https://api.github.com/repos/actions/setup-python/git/ref/tags/v5',
]


def generate_python_verification_pipeline(platform,python_version='3.11'):
    """Fixed commands/paths only. Caller strings cannot become shell/YAML/Groovy."""
    if platform not in ('github_actions','jenkins'):raise ValueError('Choose exactly github_actions or jenkins.')
    if python_version not in ('3.11','3.14'):raise ValueError('Choose supported Python3.11 or3.14.')
    if platform=='github_actions':
        text=f'''# AETHER Python verification template. Review trusted source and costs before installation.
# Manual dispatch only. Not a deployment pipeline; installing this file does not run it.
name: AETHER manual Python verification
on:
  workflow_dispatch:
    inputs:
      reviewed_source_and_costs:
        description: 'I reviewed the selected branch, dependency execution and runner/network costs'
        type: boolean
        required: true
        default: false
permissions:
  contents: read
concurrency:
  group: aether-python-verification-${{{{ github.ref }}}}
  cancel-in-progress: false
jobs:
  verify:
    if: ${{{{ inputs.reviewed_source_and_costs == true }}}}
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Check out selected trusted revision
        uses: actions/checkout@{CHECKOUT_SHA}
        with:
          persist-credentials: false
          submodules: false
      - name: Set up Python
        uses: actions/setup-python@{PYTHON_SHA}
        with:
          python-version: '{python_version}'
      - name: Create isolated environment
        run: python -m venv .aether-ci-venv
      - name: Install reviewed dependencies
        run: .aether-ci-venv/bin/python -m pip install --disable-pip-version-check -r requirements-dev.txt
      - name: Run unit tests
        run: .aether-ci-venv/bin/python -m pytest -q
'''
        filename='aether-python-verification.yml.txt'
    else:
        text=f'''// AETHER Python verification template. Review trusted SCM, node and costs first.
// Configure a Pipeline-from-SCM job with a trusted immutable revision, no automatic triggers.
// Requires input, checkout/scm and sh support; node label aether-python-{python_version} must exist.
// The label must provide python{python_version} and an isolated disposable POSIX workspace.
pipeline {{
  agent none
  options {{
    skipDefaultCheckout(true)
    disableConcurrentBuilds()
    timeout(time: 15, unit: 'MINUTES')
  }}
  stages {{
    stage('Review source and costs') {{
      steps {{
        input message: 'Run Python verification for this trusted SCM revision? Dependencies/tests execute code and may use network/runner resources.', ok: 'Run reviewed verification'
      }}
    }}
    stage('Verify Python') {{
      agent {{ label 'aether-python-{python_version}' }}
      steps {{
        checkout scm
        sh 'python{python_version} -m venv .aether-ci-venv'
        sh '.aether-ci-venv/bin/python -m pip install --disable-pip-version-check -r requirements-dev.txt'
        sh '.aether-ci-venv/bin/python -m pytest -q'
      }}
    }}
  }}
}}
'''
        filename='AETHER-Jenkinsfile.python-verification.txt'
    return {'platform':platform,'python_version':python_version,'pipeline_text':text,
            'suggested_review_filename':filename,'output_kind':'manual_python_verification_template',
            'files_written':False,'installed':False,'executed':False,'tests_run':False,
            'deployment_performed':False,'artifact_published':False,'approval_granted':False,
            'pipeline_runtime_verified':False,'sources':SOURCES.copy(),
            'limits':'Functional fixed checkout/venv/dependency-install/pytest steps for review, not inert echo stages. Generated text is not installed or executed. Manual gate is not verified owner authority or a sandbox. SCM/requirements/build hooks/tests/actions/plugins can execute arbitrary code and use network. Review the exact trusted revision, dependencies, isolation, runner costs, credentials and permissions before installing or dispatching. No Docker build, integration environment, security scan, artifact publishing, deployment, monitoring or rollback is supplied. Requirements file must exist; native dependencies/project compatibility may need separately reviewed setup. GitHub fixed action commits were checked against their official refs on2026-11-16, not a vulnerability/signature audit. Jenkins plugins/node/scm and both actual CI runtimes remain unverified. Jenkins administrators must restrict who can approve and which SCM revision is trusted; input alone cannot defend a malicious Jenkinsfile. No secrets are requested or embedded.'}


def register_verification_pipeline_tool(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='generate_python_verification_pipeline',
        description='Generate manual opt-in Python3.11/3.14 Jenkins or GitHub Actions verification template text: checkout, venv, reviewed dependency install and pytest. Fixed commands, no writes/execution/deploy/approval. Runtime compatibility remains unverified. Review source and resource costs before activation.',
        parameters={'type':'object','properties':{'platform':{'type':'string','enum':['github_actions','jenkins']},'python_version':{'type':'string','enum':['3.11','3.14']}},'required':['platform'],'additionalProperties':False},
        handler=generate_python_verification_pipeline,risk=Risk.SAFE,category='devops'))
