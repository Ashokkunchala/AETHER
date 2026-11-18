# AETHER supplied Service and EndpointSlice correlation

`review_k8s_service_endpoints_json` joins one supplied redacted core v1 Service
with a discovery.k8s.io/v1 EndpointSlice/EndpointSliceList or core v1 List. Input is
one JSON object with `service` and `endpoint_slices` fields. The reader extends
the earlier EndpointSlice-only conditions reviewer without changing that tool.

It reads no files/kubeconfig and performs no kubectl, API, model, network probe,
cluster fix or deployment. A match means supplied fields agree, not live verified
association, effective routing, public reachability or backend/application health.

## What it correlates

The Service requires explicit namespace/name/UID. A slice matches the Service-name
label only when both its namespace and kubernetes.io/service-name label match the
supplied Service. Owner references are checked independently against the supplied
Service namespace/name/UID and marked matching, conflicting or absent/unknown.
Missing owner references can be legitimate for manually managed slices; a conflict
is not automatically an attack or permission to fix anything. Fabricated/mixed or
stale JSON can contain matching fields, so no live provenance/currentness is claimed.

For each Service port, the reader compares the same slice port name, or the empty
name for a single unnamed port. Duplicate Service/slice port names are rejected.
Explicit protocols must match before numeric targetPort comparison. Missing/null
protocol, missing/null slice port and an unmaterialized Service targetPort default
remain unknown rather than silently inferred. Named targetPort remains unresolved
because no Pod/container port lookup occurs. Different slices can validly have
different resolved numeric target ports for a named target. A numeric match alone
is not a connection test or an explanation of a failed connection.

Port comparisons are not performed for a namespace/label-unassociated slice.
Their supplied condition/record counts still appear with that unassociated state;
they are not automatically counted as the chosen Service's backends. Output gives
Service-port and slice indexes, comparison states, endpoint-record counts and
ready/serving/terminating combinations, not names, UIDs, label values, addresses,
URLs, annotations or numeric ports. Counts are source records, not unique
addresses, Pods, connections or deduplicated backends.

Service publishNotReadyAddresses is reported as True/False/Unreported, with the
warning that true can make ready=true unsuitable as a health signal. Service type
is a reported fixed vocabulary, not public/private routing assurance. No selector/
Pod matching, appProtocol, DNS, kube-proxy, ingress, NetworkPolicy, traffic policy,
topology, load balancer, external IP, authentication or port reachability is tested.

## Input, privacy and limits

Strict JSON text is limited to 524288 UTF-8 bytes, with duplicate keys, nonfinite
numbers, malformed supported fields and ambiguous duplicates rejected. The chosen
Service has at most 100 ports, slices at most 20 owner references each. Existing
EndpointSlice validation caps 100 slices, 1000 endpoint records per slice, 2000 records
in total, 100 addresses per record and 100 ports per slice, and validates address
shapes/explicit condition types without reflecting their values. These are a
structural subset, not complete Kubernetes API schema validation.

Known pagination sets continuation_token_present. No token or an empty slice list
is not proof of complete inventory, an outage, or no backends. Service or endpoint
snapshots can be from different moments/clusters; no source/account/timestamp is
verified. Input source values are not returned by this module, but they were
already supplied to the assistant and may remain in chat/model context, caller
logs, exports and backups. Redact before sharing. Never paste secrets or credentials.
No report is retained by this module and no returned state authorizes a command.

## Evidence and remaining work

Synthetic tests cover same-namespace label/owner correlation, missing/conflicting
owners, explicit port match/mismatch/unknowns, named targets, readiness reporting,
pagination, unassociated slices, duplicate/size/type limits, source-value omission
and existing-registry preservation. No real cluster, network path, owner export,
kubeconfig or device was used. This does not complete live Service diagnostics,
continuous health monitoring, ingress analysis, Helm/ECK or deployment/scaling.

Official sources checked November 17, 2026:

- https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/
- https://kubernetes.io/docs/concepts/services-networking/service/
