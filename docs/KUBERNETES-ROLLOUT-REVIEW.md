# AETHER offline Deployment status evidence

`review_kubernetes_deployments(path)` reviews an existing local apps/v1
Deployment or DeploymentList JSON snapshot, or a core v1 List containing only
Deployments. It does not create, deploy, patch, scale, pause/resume or roll back
anything. No kubeconfig, kubectl, Helm, SDK, network or cluster call occurs.
This SAFE desktop DevOps evidence tool stays available after registry stop.

## Keep reported status separate from acceptance

The reviewer compares metadata.generation with status.observedGeneration only
when both are supplied. Behind, match, ahead/review and missing are distinct.
A match proves only that the two supplied counters match, not freshness or
rollout completion. All conditions/counters can be old or fabricated.

Desired spec.replicas and supplied status replica counters are preserved. Missing
values remain unknown, not an inferred default of one or zero. Explicit zero
can be intentional and is not proof an application is serving traffic. Updated
or available counters below supplied desired replicas produce comparison signals,
not failure diagnoses. No sum/equality checks falsely reject surge/terminating
replicas or treat counters as an application count.

Available=True reports minimum availability, not every desired replica ready or
application health. Progressing=True can describe ongoing or completed progress;
reason NewReplicaSetAvailable remains reported evidence, not independently
verified success. Progressing=False with ProgressDeadlineExceeded is a review
signal; Kubernetes reports a stalled condition and does not automatically roll
back. This tool performs no rollback. A paused deployment gets a paused signal,
not a deadline or stalled-state inference. Timestamps, age and deadlines are not
computed, even if relevant fields are present in the input.

Known Available/Progressing/ReplicaFailure condition types retain exact
True/False/Unknown statuses and selected recognized reasons. Other reason values
are marked OtherOmitted; future types are counted but not interpreted. Missing
conditions stay Missing. Duplicate types are refused instead of choosing one by
an assumed latest timestamp. Reported replica failure and minimum-availability-
not-met remain signals, not root-cause claims.

Every row marks rollout_complete_verified=false, application_health_verified=false
and safe_to_deploy_or_scale=false. There is no green release gate or permission
created by this report. Inspect current ReplicaSets, Pods, events, probes,
strategy, recent changes and actual application checks separately. Scope current
context/namespace and complete inventory before relying on any conclusion.

## Input bounds, privacy and limits

At most 2 MB UTF-8 JSON and 500 Deployments, each with explicit bounded name and
namespace for duplicate detection. Duplicate namespace/name records, malformed
known fields, null/noninteger/negative counters, nonboolean paused, duplicate JSON
keys, non-finite JSON and mixed resource lists fail rather than producing a
plausible complete result. Each supplied integer is bounded at one billion.
Missing spec/status are accepted as missing; explicit malformed/null objects are
refused. Conditions are limited to 100 per Deployment. This is a supported
snapshot subset, not full Kubernetes API schema validation.

Names/namespaces, images, labels, annotations, selectors, messages and arbitrary
reason values are not returned. deployment_index is a local input position, not
a persistent identity. No revision/image/strategy/selector, HPA, PDB, admission,
capacity, compatibility, upgrade or rollback-readiness evaluation is performed.
Counts describe supplied Deployment records, not distinct applications/releases.

A nonempty metadata.continue is flagged but not exposed/followed. No token or an
empty list never proves complete scope or no problems. Snapshot freshness,
completeness and cluster scope remain unverified. The file is not changed.
Regular-file/symlink/junction and bounded stable-read checks apply, not an OS
sandbox against hostile concurrent path swaps. Use a trusted local export.
Returned signals/counts can enter model-backed desktop chat if invoked there;
the parser itself makes no model/provider call.

Real deploy/scale/resume/rollback/upgrade needs separately reviewed manifests,
exact context/namespace/targets, expected effect/impact, charges where applicable,
current evidence, approval and verified recovery route. A generic wrapper or
this snapshot does not settle those requirements. No deploy, scale, pause,
resume, rollback, upgrade, repair, alert subscription or payment is performed.
Helm/ECK lifecycle and upgrade planning remain separate work.

Tests use synthetic snapshots and temporary files: generation lag/ahead/missing,
replica counters/surges/zero desired, paused/deadline flags, conditions, private
omission, input bounds/malformed records and SAFE registry behavior after stop.
No live Deployment, ReplicaSet, Pod, application, kubeconfig or command was used.

Official Kubernetes sources checked November 16, 2026:
- https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/deployment-v1/
