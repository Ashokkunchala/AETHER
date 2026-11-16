# AETHER offline EndpointSlice evidence

`review_kubernetes_endpoints(path)` reviews an existing local
`discovery.k8s.io/v1` EndpointSlice or EndpointSliceList JSON snapshot. It also
accepts a core v1 List containing only those slices. It does not obtain an
export, read kubeconfig, contact a cluster, run a probe or make changes. This is
an evidence tool in the existing desktop DevOps registry, not a connectivity
adapter, live monitor or automatic repair workflow.

## Conditions without a healthy-backend total

For each supplied slice, the reviewer counts endpoint records by exact reported
ready/serving/terminating flag combinations. Boolean True and False, explicit
Null, and Missing stay distinct. It does not apply the defaults used by API
consumers to turn unreported values into routing eligibility.

Kubernetes documents that ready is normally a shortcut for serving and not
terminating, but publishNotReadyAddresses can force ready true. Serving and
terminating endpoints can still receive traffic in some proxy scenarios. Thus
ready true is not this tool verifying backend health or a routable destination.
A ready true record alongside serving false or terminating true gets a review
signal, not an impossible-state rejection or an outage/eligibility diagnosis.

Endpoint records can occur in multiple EndpointSlices during updates. Counts
are records, not unique network endpoints, addresses, Pods, Services or healthy
backends. No deduplication is performed. A multiple-address record still counts
as one record. A kubernetes.io/service-name label is only field presence, not
verified ownership, Service UID association, selector match or freshness.

## Input limits and output privacy

At most 2 MB UTF-8 JSON, 100 slices, 1000 endpoint records per slice and 2000
endpoint records in the entire snapshot. Duplicate namespace/name slice records
are refused. An individual endpoint needs 1-100 bounded address strings matching
the supported IPv4, IPv6 or bounded FQDN shape. This validation is not DNS,
routability, ownership or full Kubernetes API validation. Scoped IPv6 zone forms
are refused. Legacy FQDN data can be shape-reviewed but this does not establish
that a target Kubernetes version accepts or routes that addressType.

Each slice's at-most-100 port records are counted. Missing/null port values are
counted separately; supplied numeric ports need 1-65535 integers, and supplied
non-null protocols must be TCP/UDP/SCTP. Missing/null protocol is not silently
converted into a matched Service port. Port matching, targetPort names and
Service applicability are not evaluated. Empty ports/endpoints/slices do not
prove an outage, a Service without backends or complete inventory.

Malformed known condition flags, invalid shape/types, duplicate JSON keys,
non-finite JSON, oversized input and mixed resource kinds fail instead of
producing a plausible healthy result. Unknown condition fields are not
interpreted. Every slice needs explicit metadata name/namespace rather than an
assumed default namespace. Names are used only for duplicate detection.

Output slice_index is a local input position, not persistent identity. Names,
namespaces, Service label values, addresses, target references, node/topology
hints, port names/numbers and continuation values are not returned. A nonempty
metadata.continue token is flagged, not followed or exposed. No token never
proves all associated slices, namespaces, pages or contexts were supplied.
Freshness, completeness, scope, Service association, routing, connectivity and
backend health stay unverified in every output.

The input is not edited. Regular-file/symlink/junction and bounded stable-read
checks apply, not a full OS sandbox against hostile concurrent path swaps. Keep
exports in a trusted private directory. Returned counts/signals may enter
model-backed desktop chat if invoked there; the reviewer itself calls no model.
The tool is SAFE and remains available after registry stop, not a live read.

## Separate evidence needed for connectivity

Correlate slice_index with the private original. Check current context/namespace,
Service identity/UID, complete associated slices, Service type/selector/ports and
publishNotReadyAddresses through separately authorized reads. Review unique
address/port/protocol combinations and actual Pod/application readiness. Client-
side DNS, TCP and application observations, NetworkPolicy, ingress, CNI and proxy
state are separate requirements before saying a connection works or diagnosing
a cause. This parser inspects none of those sources and performs no such test.

No kubectl/Helm/SDK/network/cluster/secret call, probe, port-forward, deployment,
patch, scale, remediation or payment occurs. Service/Ingress diagnosis, Helm,
ECK, effective RBAC and upgrades remain separate work, not completed by this
EndpointSlice review. Do not use its condition counts as a healthy-backend KPI.

Tests use synthetic snapshots/temporary files: condition tuples, missing/null vs
false, ready/serving/terminating caveats, cross-slice duplicated endpoints, bounds,
address family/port shape checks, private-field omission, no writes and SAFE
registry execution after stop. No live Service, endpoint, DNS lookup, connection,
cluster, kubeconfig or kubectl command was used.

Official Kubernetes sources checked November 16, 2026:
- https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/
- https://kubernetes.io/docs/concepts/services-networking/service/
