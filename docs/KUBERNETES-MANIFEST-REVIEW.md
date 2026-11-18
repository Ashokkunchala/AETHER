# AETHER manifest pattern review, not an RBAC audit

The existing `review_k8s(path)` scans local YAML-looking text for selected
security, RBAC, image and workload patterns. Its tool name, finding rule IDs,
counts, file paths and line-number fields remain. Finding messages now say what
text matched instead of claiming actual public reachability, runtime privilege
or effective cluster-admin access from a line match. Raw image text no longer
appears in findings. No execution or safety policy is widened.

## What is and is not checked

This is a line-pattern scanner, not a YAML parser or API schema validator. A
match can come from a comment, string, unrelated rule, metadata name or invalid
indentation. A missing match does not prove a risky field is absent. Source
ranges/internal text can suppress the old LoadBalancer pattern without proving
a safe provider configuration. Default/inherited/admission controls, actual
container context, runtime state and effective network behavior are not read.

A LoadBalancer text match is not proof of public internet access. Provider,
controller, network and firewall context are separate requirements. Likewise,
cluster-admin text in a binding document is not proof that roleRef selects that
role or that any subject has effective cluster-wide access. RoleBinding grants
within its namespace; a ClusterRoleBinding has cluster scope. The scanner does
not resolve roleRef, subjects, roles, API groups, aggregation or rule association.
Wildcard verb/resource text can belong to different rules. Counts are findings,
not distinct vulnerabilities or effective permissions. This is not `can-i` or
an authorization simulator, and it makes no cluster call.

Secret data-field text means only that a selected pattern matched. Base64 is not
encryption, but this tool does not establish whether a file was committed,
whether data is exposed or whether the real cluster encrypts Secrets at rest.
No raw Secret value is returned by this finding. Image tag/digest presence is
not provenance, immutability, authenticity or a vulnerability scan. Resource,
probe, replica and identity text checks do not establish actual workload health
or availability. No finding never means secure, private, healthy or complete.

## Scope and file boundaries

The existing shared enumerator caps candidates at 200 without completeness
accounting. files_scanned counts files accepted by the old apiVersion/kind text
gates, not the entire repository or every document/workload. The existing 512 KB
per-file text reader and filename/directory selection behavior are unchanged.
Do not treat the cap as a full audit or the file reader as a sandbox. It does not
provide the stricter bounded no-symlink export path checks used by newer native
JSON snapshot tools. Use trusted selected files and directories; unrelated local
files, symlinks, duplicate basenames and concurrent filesystem changes need
separate handling. A change to this older enumerator is outside this slice.

File paths/line numbers remain in output and can be private. The new image-value
omission reduces raw content in model-visible findings; caller-supplied source
or other tools' outputs are separate. If invoked through model-backed desktop
chat, the result can be included in that conversation. The scanner itself calls
no model or network. Tool remains SAFE and available after registry stop.

Every successful file review now returns yaml_schema_validated=false,
effective_rbac_verified=false, public_reachability_verified=false and
runtime_security_verified=false, together with the limits. Direct
review_k8s_text callers still receive a finding list with the corrected messages;
they do not gain metadata/schema validation from that helper.

No kubeconfig, kubectl, Helm, authorization request, network probe, cluster
connection, repair, policy edit, deployment or payment occurs. Effective RBAC
review, ingress diagnosis, Helm/ECK lifecycle and upgrades remain separate work
that needs current scoped evidence and approved execution boundaries.

Tests preserve existing patterns/rules and demonstrate misleading-but-possible
matches: cluster-admin in metadata, wildcards in unrelated rules, comments and
internal text. These examples deliberately do not become effective access or
public/private verdicts. Tests also cover no-finding limits, raw image omission,
read-only behavior and SAFE registry execution after stop. No live cluster or
user manifest was used.

Official Kubernetes sources checked November 16, 2026:
- https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- https://kubernetes.io/docs/tasks/configure-pod-container/security-context/
- https://kubernetes.io/docs/concepts/configuration/secret/
- https://kubernetes.io/docs/concepts/services-networking/service/
