# AETHER CI/CD text review and execution boundaries

`review_cicd(path)` is the existing SAFE desktop tool for local Jenkinsfiles and
.github/workflows YAML text. It returns the same success/files_scanned/counts/
findings fields and rule IDs, severity, source file and line where available.
It does not parse or validate YAML/Groovy, execute a pipeline or prove security.

## What changed

- A `pull_request_target` marker reports possible privileged-context risk, not
  an unconditional claim that secrets are available. Event, checkout and code
  flow, effective token permissions, repository/organization settings, secret
  availability and protection rules are not checked.
- Mutable external `uses` refs warn for first-party actions too. The raw action
  name/ref is no longer echoed. A full lower-case 40-hex SHA text match avoids
  that warning but does not verify the origin, actual commit, immutable container
  digest, trust or safety. Local actions and many expression/unusual reference
  forms are outside this narrow regex; no warning does not mean pinned.
- A Jenkins `terraform apply -auto-approve` marker always gets a review finding.
  Any `input` substring, comment or even an input step somewhere else cannot
  prove execution-path approval or the identity/authority of its approvers.
- Credential-like, missing permissions and AWS credentials-action markers are
  pattern findings only. Presence/absence of text is not proof of a real key,
  exposure, effective token scope, credential source or OIDC trust.

Successful reviews explicitly leave workflow_schema_validated,
effective_permissions_verified, approval_gates_verified, secret_exposure_verified
and execution_security_verified false, including zero-finding reports.
Comments, strings, wrong indentation, malformed documents and unrelated stages
can match or hide signals. Reusable workflows, composite actions and Jenkins
shared libraries are not expanded. Required environment reviewers and other
live settings are not read. Findings never create an approval gate.

The existing file reader/traversal is unchanged: 512000-byte per-file cap,
at most 200 candidate paths before workflow filtering, skipped-directory rules,
UTF-8 replacement, and errors for some unreadable/oversized inputs. It is not a
symlink/concurrent-swap sandbox or complete inventory. Use trusted local copies.
Returned source paths remain visible; raw action refs and matched line contents
are omitted. Reports may be included in desktop model-backed tool chat; the
reviewer itself makes no model/provider/network call.

## Category 4D acceptance limits

This is one part of CI/CD review, not a claim of the full CI/CD blueprint.
The repository's own CI runs its tests/static checks on source commits; that
is separate from AETHER running arbitrary project tests on the user's machine.
Existing dependency-audit review summarizes a supplied export, not a live scan.
Existing Deployment status review reads a supplied snapshot, not live staging
validation or production monitoring. No Jenkinsfile/workflow generation, Docker
build, test execution, security scan, artifact publication, dev deploy, staging
validation, production watch or rollback occurs in this reviewer. The separate
[manual Python verification generator](PYTHON-VERIFICATION-PIPELINES.md) now
creates functional GitHub Actions/Jenkins test-stage text only. It does not run
project tests or implement deployment/rollback.

Those operations need separate typed parameters, reviewed repository/source and
commands, environment/credential/secret and trust boundaries, concrete scope,
result provenance, appropriate approvals and verified recovery where relevant.
A dry-run flag or human-readable plan is not a sandbox: package installs, tests,
plugins, image builds and checkout hooks can execute code and use the network.
An approval prompt existing somewhere is not enforcement. No generic shell or
AWS wrapper is accepted as a complete deployment/rollback adapter. No real
cluster, AWS account or user device was touched for this change.

Regression tests use synthetic strings/temp files only. They check first-party
refs, no raw ref/key echo, comment/unrelated marker limitations, unchanged rule
fields and SAFE review after emergency stop. They do not run Jenkins/Actions,
resolve refs, read policy settings or verify credentials.

Official sources checked November 16, 2026:
- https://docs.github.com/en/actions/reference/security/secure-use
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://www.jenkins.io/doc/pipeline/steps/pipeline-input-step/
