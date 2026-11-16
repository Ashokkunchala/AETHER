"""Correlate one supplied Service with EndpointSlices; no live connectivity claim."""

from __future__ import annotations

import json
import re

from jarvis.devops.endpoint_snapshot import review_endpoint_slices

SOURCE = "https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/"
SERVICE_SOURCE = "https://kubernetes.io/docs/concepts/services-networking/service/"


def _obj(value):
    if not isinstance(value, dict):
        raise ValueError("Expected JSON objects.")
    return value


def _name(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?", value) is None
    ):
        raise ValueError("Explicit bounded supported names/namespaces required.")
    return value


def _uid(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value):
        raise ValueError("Explicit bounded UID required.")
    return value


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON keys refused.")
        obj[key] = value
    return obj


def review_service_endpoints(json_text: str):
    if not isinstance(json_text, str) or not json_text.strip() or len(json_text) > 524288:
        raise ValueError("Supply bounded redacted JSON text.")
    try:
        if len(json_text.encode("utf-8")) > 524288:
            raise ValueError("UTF-8 byte limit exceeded.")
        doc = json.loads(
            json_text,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON refused.")),
        )
    except (ValueError, RecursionError, OverflowError):
        raise ValueError("Malformed/duplicate/oversized JSON text.") from None
    doc = _obj(doc)
    service, slices = _obj(doc.get("service")), _obj(doc.get("endpoint_slices"))
    if service.get("kind") != "Service" or service.get("apiVersion") != "v1":
        raise ValueError("One core v1 Service required.")
    meta, spec = _obj(service.get("metadata")), _obj(service.get("spec"))
    name, namespace, uid = (
        _name(meta.get("name")),
        _name(meta.get("namespace")),
        _uid(meta.get("uid")),
    )
    if len(namespace) > 63 or "." in namespace:
        raise ValueError("Explicit supported namespace required.")
    service_type = spec.get("type")
    if service_type not in ("ClusterIP", "NodePort", "LoadBalancer", "ExternalName", None):
        raise ValueError("Unsupported Service type.")
    publish = spec.get("publishNotReadyAddresses")
    if publish is not None and type(publish) is not bool:
        raise ValueError("publishNotReadyAddresses must be boolean/null or missing.")
    ports = spec.get("ports", [])
    if not isinstance(ports, list) or len(ports) > 100:
        raise ValueError("Review at most100Service ports.")
    service_ports = []
    seen = set()
    for index, raw in enumerate(ports):
        port = _obj(raw)
        port_name = port.get("name", "")
        if not isinstance(port_name, str) or (
            port_name and not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", port_name)
        ):
            raise ValueError("Unsupported port name.")
        if port_name in seen:
            raise ValueError("Duplicate or multiple unnamed Service ports refused.")
        seen.add(port_name)
        number = port.get("port")
        if type(number) is not int or not 1 <= number <= 65535:
            raise ValueError("Explicit Service port integer1-65535required.")
        protocol = port.get("protocol")
        if protocol not in ("TCP", "UDP", "SCTP", None):
            raise ValueError("Unsupported protocol.")
        target = port.get("targetPort")
        if target is None:
            mode = "default_not_materialized"
        elif type(target) is int and 1 <= target <= 65535:
            mode = "numeric"
        elif (
            isinstance(target, str)
            and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,13}[a-z0-9])?", target)
            and re.search("[a-z]", target)
        ):
            mode = "named_unresolved"
        else:
            raise ValueError("Unsupported targetPort.")
        service_ports.append(
            {
                "index": index,
                "name": port_name,
                "protocol": protocol,
                "target": target,
                "mode": mode,
            }
        )
    # Existing stricter EndpointSlice record/address/condition validation, never returned raw.
    summary = review_endpoint_slices(slices)
    if slices.get("kind") == "EndpointSlice":
        items = [slices]
    else:
        items = slices["items"]
    rows = []
    for index, item in enumerate(items):
        smeta = item["metadata"]
        labels = _obj(smeta.get("labels", {}))
        label_match = (
            smeta.get("namespace") == namespace and labels.get("kubernetes.io/service-name") == name
        )
        owners = smeta.get("ownerReferences", [])
        if not isinstance(owners, list) or len(owners) > 20:
            raise ValueError("Review at most20ownerReferences per slice.")
        service_owners = []
        for owner in owners:
            owner = _obj(owner)
            if owner.get("kind") == "Service" and owner.get("apiVersion") == "v1":
                _name(owner.get("name"))
                _uid(owner.get("uid"))
                service_owners.append(owner)
        if len(service_owners) > 1:
            raise ValueError("Multiple Service owner references are ambiguous.")
        if not service_owners:
            owner_state = "absent_unknown"
        else:
            owner = service_owners[0]
            owner_state = (
                "matches_supplied_name_uid"
                if owner["name"] == name and owner["uid"] == uid and smeta["namespace"] == namespace
                else "conflicts_with_supplied_service"
            )
        slice_names = set()
        for slice_port in item.get("ports", []):
            slice_name = slice_port.get("name", "")
            if (
                not isinstance(slice_name, str)
                or (
                    slice_name
                    and not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", slice_name)
                )
                or slice_name in slice_names
            ):
                raise ValueError("Unsupported/duplicate slice port name.")
            slice_names.add(slice_name)
        associations = []
        for sp in service_ports:
            candidates = [p for p in item.get("ports", []) if p.get("name", "") == sp["name"]]
            if len(candidates) > 1:
                raise ValueError("Duplicate slice port names are ambiguous.")
            state = "not_compared_unassociated"
            if label_match:
                if not candidates:
                    state = "no_same_name_port_record"
                else:
                    candidate = candidates[0]
                    if sp["protocol"] is None or candidate.get("protocol") is None:
                        state = "protocol_unreported_unknown"
                    elif sp["protocol"] != candidate["protocol"]:
                        state = "protocol_mismatch"
                    elif candidate.get("port") is None:
                        state = "slice_port_unspecified_unknown"
                    elif sp["mode"] == "named_unresolved":
                        state = "named_target_requires_pod_resolution"
                    elif sp["mode"] == "default_not_materialized":
                        state = "target_default_not_materialized_unknown"
                    else:
                        state = (
                            "numeric_target_matches"
                            if sp["target"] == candidate["port"]
                            else "numeric_target_mismatch"
                        )
            associations.append({"service_port_index": sp["index"], "comparison": state})
        rows.append(
            {
                "slice_index": index,
                "namespace_and_service_label_match": label_match,
                "owner_reference_comparison": owner_state,
                "ports": associations,
                "reported_endpoint_records": summary["slices"][index]["endpoint_records_in_slice"],
                "reported_condition_combinations": summary["slices"][index][
                    "condition_combinations"
                ],
            }
        )
    return {
        "service_type_reported": service_type or "Unreported",
        "publish_not_ready_addresses": "True"
        if publish is True
        else "False"
        if publish is False
        else "Unreported",
        "service_ports": [
            {
                "service_port_index": p["index"],
                "target_mode": p["mode"],
                "protocol_reported": p["protocol"] or "Unreported",
            }
            for p in service_ports
        ],
        "slices": rows,
        "slice_count": len(rows),
        "matching_label_slices": sum(r["namespace_and_service_label_match"] for r in rows),
        "continuation_token_present": summary["continuation_token_present"],
        "snapshot_freshness_verified": False,
        "inventory_completeness_verified": False,
        "live_service_association_verified": False,
        "connectivity_verified": False,
        "sources": [SOURCE, SERVICE_SOURCE],
        "notice": (
            "Supplied Service/EndpointSlice field correlation only. Names/UIDs/addresses/URLs/labels/port numbers "
            "are not reflected; zero-based source indexes locate records. Label/owner UID agreement is only "
            "agreement within supplied data, not authenticated ownership, live cluster association or routing. "
            "Owner conflict is not automatically repaired or treated as proof of attack. Missing owner refs may "
            "be legitimate for manually managed slices. Service type, readiness flags and numeric target matches "
            "do not prove usable/healthy/reachable backends. publishNotReadyAddresses=true can make ready=true "
            "unhelpful as a health signal. Missing protocols/target defaults are left unknown, not inferred. "
            "Named targetPort needs Pod/container resolution not performed here. Different slices may validly "
            "have different resolved target ports. Unassociated slice condition counts are still source records, "
            "not Service backends. Counts are endpoint records, not unique addresses or connections. "
            "No selector/Pod matching, UID provenance/currentness, appProtocol, DNS, kube-proxy, ingress, "
            "NetworkPolicy, topology, traffic policy, load balancer, port reachability or network test is performed. "
            "No pagination token is not completeness proof; snapshots can be stale/fabricated/mixed-cluster. "
            "This module reads no files/kubeconfig, calls no cluster/network/model, writes no report and performs "
            "no command/fix/deployment. Supplied text can remain in caller/chat/model logs. Redact before sharing. "
            "No match or empty slices is unknown evidence, not an outage diagnosis or no-backends proof."
        ),
    }


def register_service_review(registry):
    from jarvis.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="review_k8s_service_endpoints_json",
            description="Correlate one supplied redacted Service and EndpointSlice JSON snapshot by namespace/name label and owner UID, compare selected explicit port fields, and keep live association/connectivity unknown. No file/cluster/network call or change.",
            parameters={
                "type": "object",
                "properties": {"json_text": {"type": "string", "maxLength": 524288}},
                "required": ["json_text"],
                "additionalProperties": False,
            },
            handler=review_service_endpoints,
            risk=Risk.SAFE,
            category="devops",
        )
    )


# A supplied-data comparison is never permission to probe or change a cluster.
