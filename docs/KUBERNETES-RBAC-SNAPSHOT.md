# AETHER supplied Kubernetes RBAC structural review

`review_k8s_rbac_json` accepts redacted JSON text for a Role, ClusterRole,
RoleBinding, ClusterRoleBinding, or a List/typed list of these RBAC v1 objects.
It joins references within that supplied input and reviews selected rule patterns.
It does not connect a cluster, run kubectl, read kubeconfig/files, request an access
review, repair a role or change a binding. The older line-pattern `review_k8s`
manifest reviewer remains separate and unchanged.

## Associations and scope

Roles are keyed by kind, explicit namespace where applicable, and name. Duplicate
identities fail even when resource versions differ. A RoleBinding Role reference
joins only a Role with exactly the same namespace/name. A ClusterRole reference
joins the exact cluster role name. A ClusterRoleBinding cannot refer to a Role.
No namespace is inferred for Roles/RoleBindings or ServiceAccount subjects.
User/Group subjects require the RBAC API group and no namespace. Empty subjects
are counted as zero, never labelled safe.

Output uses zero-based object and rule indexes to locate the source entries.
It includes subject counts, role-reference resolution, number of supplied bindings
referencing each role, and binding scope. It deliberately omits object names,
namespaces, subjects, annotations, labels, nonresource URLs and resourceNames values.
These values are processed internally only to check structure/join references.
A missing reference is unknown data, not denied access or a broken live binding.

A RoleBinding to a ClusterRole remains limited to its binding namespace. A
ClusterRoleBinding has cluster binding scope, which does not turn every resource
into a cluster-scoped resource. Nonresource URL rules are marked separately; a
RoleBinding does not grant those URL permissions. Resource discovery/scope is not
queried. AggregationRule presence is marked unresolved; controller-synthesized
rules, selectors and cross-role aggregation are not recalculated. Supplied rules
may already include generated/stale content, so no complete permission set is claimed.

## Selected signals, not permission decisions

Each rule is considered independently. Reports identify literal wildcard verbs,
resources/API groups, nonresource rules and bind/escalate/impersonate verb-review
patterns. Core-group get/list/watch or wildcard on secrets/wildcard resources
produces a secret-read review pattern. Selected core-group get/create/wildcard
on pods/exec, pods/attach, pods/* or wildcard resources produces an exec/attach
review pattern. This is not exhaustive subresource wildcard matching or API
operation resolution, and a pattern is not a confirmed exploit.

ResourceNames constraints are noted but not evaluated. Findings from unrelated
rules are never combined into a manufactured wildcard grant. Name rebinding,
subject group membership, resource scope/custom resources, unusual/custom verbs,
other bindings, authorizers, admission policy, impersonation chains, admission-time
mutation and privilege-escalation preconditions are not computed. No signal means
only none of these patterns was observed, not least privilege, secure or no access.

## Input bounds, freshness and privacy

Input is strict UTF-8 JSON text at most 524288 bytes; duplicate keys/nonfinite values,
wrong types, malformed identifiers, unsupported objects and ambiguous duplicates
fail instead of producing a partial successful audit. The reader accepts at most
500 objects, 100 rules per role, 2000 total rules, 100 entries per rule array and
100 subjects per binding. Typed list API versions and item kinds must match.
Core rules explicitly include an empty string in apiGroups; an empty group array
is rejected. Known pagination `metadata.continue` sets partial_snapshot=true.
No continuation token is not proof that an export is complete. Empty input lists
are allowed but do not prove there are no privileges in the cluster.

This is a bounded structural subset, not full Kubernetes API schema validation;
unknown extra fields are not evaluated or reflected. Input can be stale, fabricated
or mixed from different clusters; it has no verified timestamp, account, source or
live resource version. Do not combine unrelated snapshots and infer a live grant.

The module stores no report/source and makes no model/network call, but the caller
already supplied the JSON to the assistant. It can remain in chat, configured model
context, caller logs, exports or backups. Redact private identifiers and never paste
secret objects, tokens, credentials or unrelated workload data. A returned result
does not approve a cluster command, share, role edit, deployment or paid service.

## Evidence and open acceptance

Synthetic JSON tests cover namespace joins, ClusterRole namespace versus cluster
binding scope, absent roles, subject/role structure, aggregation unknowns,
nonresource/resourceNames limits, per-rule signal associations, source-value omission,
strict malformed/duplicate input, typed lists, pagination and input/count bounds.
The existing registry and older reviewer remain available. No actual cluster,
kubeconfig, owner export or Kubernetes authorization response was inspected.
This does not complete live RBAC auditing, continuous monitoring, typed Helm/ECK
administration, deployment/scaling or the broader Kubernetes blueprint.

Official source checked November 17, 2026:

- https://kubernetes.io/docs/reference/access-authn-authz/rbac/
