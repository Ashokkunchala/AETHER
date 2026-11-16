"""Return inert pipeline review scaffolds, without writing or executing files."""
from __future__ import annotations

STAGES = (
    ('Source', 'Verify repository, immutable revision and trusted checkout before executing any source.'),
    ('Unit tests', 'Review exact unit-test command, dependencies and isolation; no tests run in this scaffold.'),
    ('Integration tests', 'Use isolated approved fixtures; no real service or production credentials.'),
    ('Image build', 'Review Dockerfile, context, base digest and build secrets; do not infer a build is safe.'),
    ('Security scan', 'Review scanner/version, database freshness, scope and exceptions; no findings is not proof secure.'),
    ('Artifact', 'Bind checks to immutable digest, provenance and exact registry; upload requires separate authority.'),
    ('Development', 'Review exact environment, change, impact, authority and verified recovery route.'),
    ('Staging', 'Verify deployed digest, readiness and application checks separately; minimum availability is not success.'),
    ('Production monitor', 'Define authorized source, freshness, scope, duration, thresholds and escalation.'),
    ('Rollback', 'Require separate approval of exact target/revision, impact and recovery verification; never automatic.'),
)
SOURCES = ['https://www.jenkins.io/doc/book/pipeline/syntax/',
           'https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax']


def generate_pipeline_scaffold(platform):
    """A scaffold is deliberately not an operational CI/deployment implementation."""
    if platform not in ('github_actions', 'jenkins'):
        raise ValueError('Choose exactly github_actions or jenkins.')
    if platform == 'github_actions':
        lines = ['# AETHER REVIEW SCAFFOLD - no source checkout or operational commands.',
                 '# Job is disabled. Removing the guard can consume runner minutes.',
                 '# Do not install/activate without separate review and approval.',
                 'name: AETHER review scaffold', 'on:', '  workflow_dispatch:',
                 'permissions: {}', 'jobs:', '  review_scaffold:',
                 '    if: ${{ false }}', '    runs-on: ubuntu-latest',
                 '    timeout-minutes: 5', '    steps:']
        for title, text in STAGES:
            lines += [f'      - name: {title} - NOT IMPLEMENTED',
                      f'        run: echo "REVIEW ONLY. {text}"']
        suggested = 'aether-review-workflow.yml.txt'
    else:
        lines = ['// AETHER REVIEW SCAFFOLD - no source checkout or operational commands.',
                 '// No executor/node requested. Do not install/activate without separate review.',
                 'pipeline {', '  agent none', '  options {',
                 '    skipDefaultCheckout(true)', '    disableConcurrentBuilds()',
                 '  }', '  stages {']
        for title, text in STAGES:
            lines += [f"    stage('{title} - NOT IMPLEMENTED') {{", '      steps {',
                      f"        echo 'REVIEW ONLY. {text}'", '      }', '    }']
        lines += ['  }', '}']
        suggested = 'AETHER-Jenkinsfile.review.txt'
    return {'platform': platform, 'scaffold_text': '\n'.join(lines)+'\n',
            'suggested_review_filename': suggested, 'stage_count': len(STAGES),
            'output_kind': 'inert_review_scaffold_not_operational_pipeline',
            'files_written': False, 'executed': False, 'installed': False,
            'tests_run': False, 'image_built': False, 'scan_performed': False,
            'artifact_published': False, 'deployment_performed': False,
            'monitor_started': False, 'rollback_performed': False,
            'approval_granted': False, 'workflow_schema_validated': False,
            'sources': SOURCES.copy(),
            'limits': ('Fixed text preview only, not a tested Jenkinsfile/GitHub workflow or a complete CI/CD implementation. '
                       'All stages are NOT IMPLEMENTED and emit review text only; no checkout, installs, tests, Docker, scanners, upload or deploy commands are generated. '
                       'GitHub job-level false guard disables runner work; do not interpret a skipped/green run as tests passing. Removing it can consume runner minutes. '
                       'Jenkins agent none and skipDefaultCheckout avoid requesting a node/checkout in this scaffold; installing it still evaluates Pipeline code on a controller. '
                       'No source/project/command/action version/plugin/schema/credential/environment/protection/policy compatibility is verified. '
                       'An echo mentioning approval is not an enforced gate. No automatic rollback, provider/model/network call, write, execution, monitoring, upload or payment. '
                       'Review plain text outside auto-discovered paths. Activation, project-specific commands, credentials, charges and deployment/rollback each need separately grounded authority and controls.')}


def register_pipeline_tools(registry):
    from jarvis.tools.registry import Risk, Tool
    registry.register(Tool(
        name='generate_pipeline_review_scaffold',
        description='Return inert fixed Jenkins or GitHub Actions review text with NOT IMPLEMENTED stages. No files written, checkout, tests, build, security scan, artifact upload, deployment, monitor or rollback. Not operational pipeline generation or approval.',
        parameters={'type': 'object', 'properties': {'platform': {'type': 'string', 'enum': ['github_actions', 'jenkins']}}, 'required': ['platform'], 'additionalProperties': False},
        handler=generate_pipeline_scaffold, risk=Risk.SAFE, category='devops'))
