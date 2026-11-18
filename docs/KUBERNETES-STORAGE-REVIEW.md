# AETHER offline PV/PVC evidence

`review_kubernetes_storage(path)` reviews an existing local core v1
PersistentVolume or PersistentVolumeClaim JSON snapshot. It also accepts their
typed lists or a core v1 List containing only those two kinds. It does not run
an export, read kubeconfig, access a cluster or modify storage. The tool uses the
existing desktop DevOps evidence registry, not a new Kubernetes execution path.

## Phases are evidence, not operational verdicts

PV phases Pending, Available, Bound, Released and Failed are reported separately.
PVC phases Pending, Bound and Lost are reported separately. Missing remains
Missing; future phases become Unknown. A reported Lost/Failed phase is a review
signal, not this tool independently proving data loss or identifying a cause.

Bound does not prove mounted, healthy, accessible or application-consistent.
Pending is not automatically a failure: StorageClass WaitForFirstConsumer can
intentionally delay provisioning/binding until a consumer Pod exists. This
reviewer does not fetch StorageClasses or Pods and does not assert that a
particular Pending claim is explained by delayed binding. Available or Released
never means unused, disposable, safe to rebind or safe cleanup.

A PV Delete reclaim policy produces a warning because supported plugins can
remove the backing storage. Retain does not prove data recoverability or grant
permission to reuse/release it. Recycle and unknown policy values stay explicit.
There is no deletion, reclaim, provisioning, resize, binding or mount action.

## Scope and missing details

Up to 2 MB UTF-8 JSON and 500 total PV/PVC records. Every resource requires its
kind and a bounded supported name; PVC namespace is required rather than assumed
to be default. PVs are cluster-scoped. Duplicate kind/namespace/name identities
are refused. Different namespaces and the PV/PVC kind distinction are retained
for duplicate detection, not returned as private identifiers.

Missing spec/status/phase remain missing. Explicit malformed/null fields,
unsupported resource kinds, mismatched typed lists, duplicate JSON fields,
non-finite JSON and oversized snapshots fail instead of producing a plausible
healthy result. Supported identifier shapes are not full Kubernetes API schema
validation. Null optional fields are outside this supported subset; omit unused
fields in a separately reviewed snapshot instead of interpreting null as success.

StorageClassName missing and explicit empty string remain different. No default
class or valid/available class is inferred. Only field presence is reported for
PVC volumeName/PV claimRef. A claimRef object may be empty and is explicitly not
validated as a binding. No names, UIDs or bidirectional matching are correlated.
Bound without the expected reference field gets a review signal, not a diagnosis.

PVC Resizing and FileSystemResizePending conditions retain supplied exact
True/False/Unknown statuses. Other condition types are counted but not
interpreted. Duplicate condition types or malformed statuses fail. No resize
completion, current controller health, or resource allocation success is inferred.
Deletion timestamp presence is flagged without interpreting time or finalizers.

Names/namespaces, labels, annotations, CSI handles, resource/secret references,
free-form reasons/messages, timestamps, storage class values and capacity
quantities are not returned. resource_index is a local input position, not a
persistent identifier. No capacity math, access-mode/mount compatibility,
StorageClass/CSI validity, topology, recovery or upgrade assessment is made.
PV and PVC counts are records, not distinct disks or a capacity total.

A nonempty metadata.continue token is flagged but not exposed/followed. No token
or an empty list never proves complete scope or no problems. Freshness, cluster
context, completeness, binding, mounts and storage health stay unverified. Input
is not changed. Regular-file/symlink/junction/bounded stable-read checks apply,
not a full OS sandbox against hostile concurrent path swaps.

## Necessary follow-up remains separate

Correlate indices with the private source file. Verify current context/namespace,
filters, pagination and events through separately authorized reads. Review
StorageClass binding mode, CSI/controller signals, Pod placement and actual
mounts before a diagnosis. Confirm data owner, retention and tested recovery
before considering changes. Every delete/rebind/resize/provision action needs
its own reviewed authority and conditions, not this report's classification.

The SAFE reviewer stays available after registry stop. Returned signals/counts
may enter model-backed desktop chat if invoked there; the parser itself makes
no model/provider call. No kubectl/Helm/SDK/network/cluster/secret call, deployment,
alert subscription, payment or remediation occurs. This is an offline storage
foundation alongside Node/Pod evidence, not accepted Kubernetes operations.

Tests use synthetic records and temporary files: PV/PVC phases, missing/unknown,
reclaim policies, class missing/empty, namespace duplicate semantics, field-
presence-only bindings, resize flags, private-field omission, bounds, malformed
JSON, no writes and SAFE registry invocation after stop. No real storage,
mount, cluster, kubeconfig or kubectl command was used.

Official Kubernetes sources checked November 16, 2026:
- https://kubernetes.io/docs/concepts/storage/persistent-volumes/
- https://kubernetes.io/docs/reference/kubernetes-api/config-and-storage-resources/persistent-volume-claim-v1/
- https://kubernetes.io/docs/concepts/storage/storage-classes/
