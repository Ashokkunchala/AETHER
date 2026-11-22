# AETHER CI/CD and SRE foundations

This maps the requested CI/CD professional and incident-management (SRE)
abilities to what exists. Everything is read-only, plan-only or offline by
default. Every publish, deploy, restart, rollback or paid/billed call requires
explicit run-time approval; nothing here executes on its own. See
[local execution safety](EXECUTION-SAFETY.md) and the
[AWS read policy](AWS-DEVOPS.md).

## CI/CD professional

| Ability | What exists today | Boundary |
| --- | --- | --- |
| Generate Jenkinsfiles | `generate_pipeline_review_scaffold` scaffolds and `generate_python_verification_pipeline` text (pinned action SHAs, no execution) | Generated text is a draft to review, never written to a repo or run |
| Create GitHub Actions workflows | Same templates plus `review_cicd` for existing workflows | No workflow is committed or enabled automatically |
| Build Docker images | `review_dockerfile` for Dockerfiles; builds run only through the approved-command path | No image is built, tagged or pushed without per-command approval |
| Run unit and integration tests | `run_python_tests`: one freshly approved fixed pytest command in an explicit trusted project | Executes project code; no sandbox, install, retry or auto-approve |
| Perform security scans | `review_dependency_audit`, `review_cicd`, `review_k8s`, `review_iam_policy` | Heuristic pattern reviews, not vulnerability feeds; no finding does not mean safe |
| Publish artifacts | `ci-publish-checklist` runbook; publishing stays an approval-gated command | Never published automatically; verify digests afterwards |
| Deploy to development environments | `design_lifecycle_change` typed proposals (design-only) and the guarded shell | No real deployment without explicit approval at run time |
| Validate staging deployments | `review_kubernetes_deployments` on a supplied deployment snapshot | Supplied evidence only; not a live gate |
| Monitor production deployments | `review_kubernetes_deployments`, `review_kubernetes_endpoints`, `review_k8s_service_endpoints_json` on supplied snapshots | Snapshot triage, not a monitoring service |
| Roll back failed deployments after approval | `deploy-rollback-decision` runbook plus approval-gated commands | Rollback is a change: exact command shown, explicit approval first |

## Incident management (SRE)

| Ability | What exists today | Boundary |
| --- | --- | --- |
| Detect application failures | `triage_log` on authorized local log windows | Known local patterns only; a match is a signal, not a verified root cause |
| Identify abnormal CPU/memory | `review_kubernetes_nodes` on supplied node snapshots; `node-high-memory` runbook | Supplied snapshots; not live metrics or a culprit verdict |
| Analyze logs | `triage_log` | Select and redact logs before model-backed use |
| Correlate metrics and traces | `compare_telemetry_windows` on caller-normalized windows | Correlation never proves causality |
| Detect service outages | `review_kubernetes_endpoints`, `review_k8s_service_endpoints_json` on supplied snapshots | No live connectivity claim |
| Investigate failed deployments | `review_deployment_status` plus runbooks | Supplied snapshots only |
| Identify potential root causes | `review_incident_evidence`: timeline, corroborated scopes, correlation-only candidates | Candidates are pointers for a human, never a diagnosis |
| Generate incident reports | `review_incident_evidence` incident summary draft (missing fields flagged) | Caller-supplied claims, not verified |
| Suggest remediation | Runbooks plus remediation options, each marked approval-required | No restart, rollback, scale or deploy is performed |
| Track MTTR | `review_incident_durations` arithmetic on supplied incident boundaries | Caller-defined boundaries; not tracking or monitoring |
| Monitor SLOs and SLAs | `review_slo_budget` event-ratio arithmetic | Not a live monitor or SLA decision |
| Create postmortem reports | `draft_postmortem` with missing sections flagged | Caller facts formatted, not independently verified |

## Example: "production API is returning 500 errors, investigate"

1. Triage an authorized, redacted log window with `triage_log` and note the
   peak error minute.
2. Normalize the evidence (log signals, metric windows, the deploy event,
   endpoint state) into `aether.incident-evidence.v1` records and run
   `review_incident_evidence` for a timeline, corroborated scopes and
   correlation-only candidates (for example, a deploy that preceded the first
   error by minutes).
3. Read the recommended runbooks (`api-5xx-investigation`,
   `deploy-rollback-decision`) and collect any missing evidence kinds the
   review flags.
4. Present findings with their evidence, then recommend a fix. Any restart or
   rollback is an approval-gated change, never automatic.

## Standing limits

No APM, monitoring provider, cluster, CI system or production environment is
connected by default. Live reads go through the guarded AWS/k8s/shell paths
with their own approval rules. Nothing in this document is an SLA commitment,
an on-call rotation, paging, auto-remediation or a sandbox. Never expose this
local prototype directly to the public internet.
