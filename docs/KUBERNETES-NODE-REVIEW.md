# AETHER offline Kubernetes node conditions

`review_kubernetes_nodes(path)` reviews an existing local core v1 Node or
NodeList JSON snapshot. A core v1 List containing only Nodes is also accepted.
It is available through the existing desktop DevOps evidence registry. The
reviewer does not run kubectl, contact a cluster or fetch an export. The user
selects an existing scoped JSON file. No kubeconfig/credential read is needed.

## Reported conditions, not a cluster health verdict

Ready True, False, Unknown and missing remain distinct. Reported MemoryPressure,
DiskPressure, PIDPressure and NetworkUnavailable are preserved as True, False,
Unknown or Missing. Missing pressure is never assumed False. Ready True with an
adverse condition produces a coexistence/review signal rather than hiding it.

Ready True is a reported node condition, not proof the cluster, application,
control plane, network, storage or workloads are healthy. Ready Unknown has
specific controller semantics, but this offline tool cannot establish actual
current reachability, cause, freshness or how long it has persisted. It does not
infer stale/overdue conditions from timestamps, even if timestamp fields exist.

A supplied `spec.unschedulable=true` produces a disabled-new-scheduling signal.
SchedulingDisabled in command-line presentation is not a Kubernetes API Node
condition. If supplied as a condition, it is counted as unrecognized and not
silently translated. False/missing unschedulable does not establish placement
eligibility: taints/tolerations, affinity, resources and other scheduling inputs
are not evaluated. No cordon, uncordon, drain, eviction or scale action occurs.

## Bounds and privacy

At most 2 MB UTF-8 JSON, 500 nodes and 100 condition entries per node. Node name
is required for duplicate detection but omitted from output. Row node_index is
the local input position, not a persistent identity. Duplicate node names or
condition types are refused, not merged using an assumed latest timestamp.
Unknown condition types are counted without echoing arbitrary values. Malformed
condition flags, unsupported JSON/types, duplicate JSON fields, non-finite JSON,
oversized input and mixed resource lists fail rather than producing a plausible
healthy summary. The supported name shape is bounded for duplicate detection,
not full Kubernetes API schema validation.

Missing spec/status/conditions stay missing; explicit malformed/null fields are
refused. A nonempty metadata.continue token is flagged without returning or
following it. No token never proves every cluster/context/filter/page was
supplied. Empty lists do not prove no nodes or a healthy cluster. Every report
keeps scope, completeness, freshness and cluster health unverified.

Names, addresses/provider IDs, labels, annotations, reason/message text, version
strings and continuation values are not returned. Metrics, capacity, taints,
leases, timestamps, heartbeat ages, Kubernetes compatibility and upgrades are
not parsed or evaluated. The local file is not changed. Regular-file,
symlink/junction and bounded stable-read checks apply, not a full OS sandbox
against hostile concurrent path swaps. Keep exports in a trusted directory.

If invoked in model-backed desktop chat, returned signals/counts can be included
in that conversation. The reviewer itself makes no model/provider call. It is a
SAFE evidence tool and remains available after registry stop, not a live LOW
cluster read. No kubectl/Helm/SDK/network/cluster/secret call, deployment,
remediation, upgrade, ECK action, subscription or payment occurs.

## How it fits the Kubernetes blueprint

Existing `review_kubernetes_pods` covers supplied Pod readiness, restarts,
CrashLoopBackOff, image-pull and termination signals without claiming root cause.
Existing `review_k8s` scans manifest text for selected security/RBAC patterns;
it is not a complete YAML/API/RBAC evaluator. Manual runbooks offer next checks,
not automated operations. This node addition does not create deployment,
scaling, Service/Ingress connectivity, Helm, ECK, PVC/PV, cluster log collection,
effective RBAC audits or upgrade planning adapters. Those remain separate work.
No live Kubernetes operations or hardware/provider acceptance is claimed.

Tests use synthetic snapshots and temporary files for Ready/pressure distinctions,
missing/unknown states, coexistence, cordon semantics, duplicate/invalid records,
bounds, private-value omission, no file writes and SAFE registry execution after
stop. No real node, cluster, provider, kubeconfig or kubectl invocation was used.

Official Kubernetes sources checked November 16, 2026:
- https://kubernetes.io/docs/reference/node/node-status/
- https://kubernetes.io/docs/concepts/architecture/nodes/
