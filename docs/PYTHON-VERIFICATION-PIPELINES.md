# AETHER manual Python verification templates

`generate_python_verification_pipeline` returns a Jenkinsfile or GitHub Actions
workflow as review text. Unlike the earlier inert review scaffold, it contains
real fixed checkout, virtual-environment, dependency-install and pytest steps.
The output is never written, installed or executed by the generator. Suggested
filenames end in .txt to keep them out of automatic pipeline discovery.

Only platform github_actions/jenkins and Python3.11/3.14 are accepted. There is
no caller-supplied shell/Groovy/YAML, command, URL, credential, node label or path.
The Python requirement is a target, not proof that a project's dependencies work.
The template assumes a trusted requirements-dev.txt and pytest suite. Projects
needing native audio/system libraries or services need separately reviewed setup.

## GitHub Actions

Manual workflow_dispatch only, with a required boolean defaulting false. The
verification job runs only after that input is true. It uses read-only contents
permission, no persisted checkout credential, fixed official checkout/setup-python
commit IDs, no submodules, no automatic trigger, no forced concurrent cancellation
and a15minute job timeout. Those action commits were resolved from official refs
on November16,2026, not audited for vulnerabilities or signed provenance. A skipped
job is not tests passing. workflow_dispatch discoverability also depends on the
workflow being present on the default branch and the repository's own policy.

After review, the owner can decide whether to install the text under an approved
workflow path and dispatch a trusted revision. This generator grants no authority
to do that. A workflow running arbitrary selected source can spend runner minutes,
use network and execute dependency/build/test hooks. No secrets are requested or
included; inherited runner/repository context still needs review.

## Jenkins

A declarative pipeline uses agent none and no default checkout. A15minute overall
timeout bounds local approval wait and verification. Explicit input comes before
a fixed per-version POSIX node label, then checkout scm, venv, pip and pytest.
Configure a trusted Pipeline-from-SCM job/revision with no automatic triggers,
least-privilege approvers and an isolated disposable node providing the selected
python executable. The generated node label is a required local configuration,
not an installer or inventory claim. Checkout and input/sh support depend on
installed Jenkins plugins. input is not protection from a malicious Jenkinsfile
that changes/removes the gate. The template does not provision agents or credentials.

## Limits and tests

No Docker build, integration-test environment, scanner, artifact upload, deploy,
production monitor or rollback is implemented by this template. Those remain
separate work and need project-specific source, authority, budgets and validation.
No real CI job was installed or run for generation tests. Offline tests parse
GitHub YAML, check fixed controls/commands and Jenkins brace/stage/gate structure,
reject interpolation payloads and verify no files/operations occur. This is not
Jenkins controller/plugin evaluation or an end-to-end pipeline pass. The existing
`generate_pipeline_review_scaffold` is preserved as an inert10stage checklist;
it is not silently converted into an operational deployment workflow.

Sources:
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://www.jenkins.io/doc/book/pipeline/syntax/
- https://api.github.com/repos/actions/checkout/git/ref/tags/v4
- https://api.github.com/repos/actions/setup-python/git/ref/tags/v5

## Separate local execution path

The [fresh-approved local Python test runner](PYTHON-TEST-RUNNER.md) invokes fixed
pytest argv in a selected trusted local project. It does not run the generated
pipeline, install dependencies, publish artifacts or deploy. It discards output
and reports the direct process exit code only. The generator still only returns
text; this separate action does not grant permission to execute that text.
