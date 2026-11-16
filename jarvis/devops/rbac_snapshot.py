"""Join supplied RBAC JSON objects only. No Kubernetes access/effective authorization claim."""

from __future__ import annotations

import json
import re

SOURCE = "https://kubernetes.io/docs/reference/access-authn-authz/rbac/"
_API = "rbac.authorization.k8s.io/v1"
_KINDS = {"Role", "ClusterRole", "RoleBinding", "ClusterRoleBinding"}


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("Expected JSON objects.")
    return value


def _text(value, namespace=False):
    if not isinstance(value, str) or not 1 <= len(value) <= 253:
        raise ValueError("Missing/bounded identifier required.")
    if namespace:
        if len(value) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", value):
            raise ValueError("Explicit valid namespace required; no default inferred.")
    elif value in {".", ".."} or any(c in "/%" or ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Unsupported object identifier.")
    return value


def _strings(value, empty=False, core_group=False):
    if not isinstance(value, list) or len(value) > 100 or (not value and not empty):
        raise ValueError("Expected bounded string arrays.")
    for item in value:
        if (
            not isinstance(item, str)
            or len(item) > 253
            or (not item and not core_group)
            or any(ord(c) < 32 or ord(c) == 127 for c in item)
        ):
            raise ValueError("Unsupported rule string.")
    if len(value) != len(set(value)):
        raise ValueError("Duplicate rule entries are ambiguous for this review.")
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys refused.")
        result[key] = value
    return result


def _rules(role):
    rules = role.get("rules", [])
    if not isinstance(rules, list) or len(rules) > 100:
        raise ValueError("Review at most100rules per role.")
    observations = []
    for index, raw in enumerate(rules):
        rule = _object(raw)
        verbs = _strings(rule.get("verbs"))
        urls = "nonResourceURLs" in rule
        if urls:
            _strings(rule["nonResourceURLs"])
            if role["kind"] != "ClusterRole" or any(
                k in rule for k in ["resources", "apiGroups", "resourceNames"]
            ):
                raise ValueError("Unsupported mixed/nonresource rule scope.")
            resources, groups, names = [], [], []
        else:
            resources = _strings(rule.get("resources"))
            groups = _strings(rule.get("apiGroups"), core_group=True)
            if not groups:
                raise ValueError("Explicit apiGroups required, including empty-string core group.")
            names = _strings(rule.get("resourceNames", []), empty=True)
        codes = []
        if "*" in verbs:
            codes.append("wildcard_verbs")
        if "*" in resources:
            codes.append("wildcard_resources")
        if "*" in groups:
            codes.append("wildcard_api_groups")
        if urls:
            codes.append("nonresource_rule")
        if any(v in verbs for v in ["bind", "escalate", "impersonate"]):
            codes.append("sensitive_verb_review")
        core = "" in groups or "*" in groups
        if (
            core
            and any(v in verbs for v in ["get", "list", "watch", "*"])
            and any(r in resources for r in ["secrets", "*"])
        ):
            codes.append("core_secret_read_pattern")
        if (
            core
            and any(v in verbs for v in ["create", "get", "*"])
            and any(r in resources for r in ["pods/exec", "pods/attach", "pods/*", "*"])
        ):
            codes.append("pod_exec_attach_pattern")
        observations.append(
            {
                "rule_index": index,
                "signals": codes,
                "resource_names_constraint_present": bool(names),
                "nonresource_rule": urls,
            }
        )
    return observations


def review_rbac_json(json_text: str):
    if not isinstance(json_text, str) or not json_text.strip() or len(json_text) > 524288:
        raise ValueError("Supply redacted RBAC JSON text up to524288UTF-8bytes.")
    try:
        if len(json_text.encode("utf-8")) > 524288:
            raise ValueError("Input byte limit exceeded.")
        document = json.loads(
            json_text,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON refused.")),
        )
    except (ValueError, RecursionError, OverflowError):
        raise ValueError("Malformed, duplicate-key, oversized or unsupported JSON.") from None
    doc = _object(document)
    partial = False
    if not isinstance(doc.get("kind"), str):
        raise ValueError("Explicit supported object/list kind required.")
    if doc.get("kind") in {
        "List",
        "RoleList",
        "ClusterRoleList",
        "RoleBindingList",
        "ClusterRoleBindingList",
    }:
        if doc.get("apiVersion") != ("v1" if doc["kind"] == "List" else _API):
            raise ValueError("Unsupported list API version.")
        items = doc.get("items")
        metadata = _object(doc.get("metadata", {}))
        token = metadata.get("continue", "")
        if not isinstance(token, str):
            raise ValueError("List continuation must be a string.")
        partial = bool(token)
    else:
        items = [doc]
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError("Review at most500RBAC objects.")
    roles, bindings, identities, total_rules = {}, [], set(), 0
    for index, raw in enumerate(items):
        obj = _object(raw)
        kind = obj.get("kind")
        if not isinstance(kind, str) or kind not in _KINDS or obj.get("apiVersion") != _API:
            raise ValueError(
                "Every item must be a supported RBAC v1 object, not a workload/secret."
            )
        if doc["kind"] != "List" and doc["kind"].endswith("List") and kind != doc["kind"][:-4]:
            raise ValueError("Typed list items must match its explicit kind.")
        meta = _object(obj.get("metadata"))
        name = _text(meta.get("name"))
        namespace = _text(meta.get("namespace"), True) if kind in {"Role", "RoleBinding"} else ""
        if kind in {"ClusterRole", "ClusterRoleBinding"} and meta.get("namespace") not in (
            None,
            "",
        ):
            raise ValueError("Cluster-scoped object cannot carry a namespace here.")
        identity = (kind, namespace, name)
        if identity in identities:
            raise ValueError("Duplicate object identities refused, including differing versions.")
        identities.add(identity)
        if kind in {"Role", "ClusterRole"}:
            observations = _rules(obj)
            total_rules += len(observations)
            if total_rules > 2000:
                raise ValueError("Review at most2000totalrules.")
            if "aggregationRule" in obj:
                _object(obj["aggregationRule"])
                if kind != "ClusterRole":
                    raise ValueError("Role aggregation is unsupported.")
            roles[identity] = {
                "object_index": index,
                "kind": kind,
                "aggregation_unresolved": "aggregationRule" in obj,
                "rules": observations,
                "referenced_by_bindings": 0,
            }
        else:
            ref = _object(obj.get("roleRef"))
            ref_kind = ref.get("kind")
            if ref.get("apiGroup") != "rbac.authorization.k8s.io" or ref_kind not in (
                "Role",
                "ClusterRole",
            ):
                raise ValueError("Unsupported roleRef.")
            if kind == "ClusterRoleBinding" and ref_kind != "ClusterRole":
                raise ValueError("ClusterRoleBinding must refer to ClusterRole.")
            ref_name = _text(ref.get("name"))
            subjects = obj.get("subjects", [])
            if not isinstance(subjects, list) or len(subjects) > 100:
                raise ValueError("Review at most100subjects per binding.")
            for subject in subjects:
                sub = _object(subject)
                subkind = sub.get("kind")
                _text(sub.get("name"))
                if subkind == "ServiceAccount":
                    if sub.get("apiGroup", "") != "":
                        raise ValueError("ServiceAccount subject requires core group.")
                    # Require explicit subject namespace even for RoleBinding. Never infer defaults.
                    _text(sub.get("namespace"), True)
                elif subkind in ("User", "Group"):
                    if sub.get("apiGroup") != "rbac.authorization.k8s.io" or sub.get(
                        "namespace"
                    ) not in (None, ""):
                        raise ValueError("Unsupported User/Group subject scope.")
                else:
                    raise ValueError("Unsupported subject kind.")
            bindings.append(
                {
                    "object_index": index,
                    "kind": kind,
                    "scope": "binding_namespace_only"
                    if kind == "RoleBinding"
                    else "cluster_binding",
                    "subject_count": len(subjects),
                    "_ref": (ref_kind, namespace if ref_kind == "Role" else "", ref_name),
                }
            )
    resolved = []
    for binding in bindings:
        reference = binding.pop("_ref")
        role = roles.get(reference)
        if role is not None:
            role["referenced_by_bindings"] += 1
        resolved.append(
            {
                **binding,
                "referenced_role_supplied": role is not None,
                "role_object_index": role["object_index"] if role is not None else None,
                "aggregation_unresolved": role["aggregation_unresolved"]
                if role is not None
                else None,
                "nonresource_rules_not_namespace_grants": bool(
                    role
                    and binding["kind"] == "RoleBinding"
                    and any(r["nonresource_rule"] for r in role["rules"])
                ),
            }
        )
    return {
        "object_count": len(items),
        "roles": list(roles.values()),
        "bindings": resolved,
        "partial_snapshot": partial,
        "missing_role_references": sum(not b["referenced_role_supplied"] for b in resolved),
        "effective_authorization_verified": False,
        "cluster_queried": False,
        "source": SOURCE,
        "notice": (
            "Supplied JSON structural review only, not live/current/complete Kubernetes API validation, "
            "an effective permission audit or a secure/no-access conclusion. Object/rule/subject identities "
            "are used only to join within this input; output uses zero-based object/rule indexes, not names, "
            "URLs, annotations or subject values. RoleBinding to ClusterRole remains limited to its binding "
            "namespace; ClusterRoleBinding has cluster binding scope but does not make every resource "
            "cluster-scoped. ResourceNames constraints are noted, not evaluated. A RoleBinding does not "
            "grant nonresource URL access. Aggregation, wildcards/subresources beyond selected patterns, "
            "resource discovery/scope, custom verbs, identity/groups, other bindings/authorizers, impersonation "
            "chains and admission are not evaluated. No wildcard match between unrelated rules is inferred. "
            "Missing role data is unknown, not denied access. No subjects does not prove safe. "
            "List continue marks known pagination only; no token is not proof of completeness. Input may be "
            "stale/fabricated/mixed-cluster; no provenance/timestamp/currentness check. No file read, kubeconfig, "
            "command, cluster/network/model call, change, fix or retained report is performed by this module. "
            "Caller/chat/model history may retain the supplied JSON; redact it before sharing. No signal is "
            "a confirmed exploit, and no signals means only none of these selected patterns were observed."
        ),
    }


def register_rbac_review(registry):
    from jarvis.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="review_k8s_rbac_json",
            description="Join supplied redacted RBAC v1 JSON roles/bindings structurally, distinguish binding scope and review selected rule patterns. No file/cluster access or effective-permission/security pass. Names omitted from output; supplied input can remain in chat/model history.",
            parameters={
                "type": "object",
                "properties": {"json_text": {"type": "string", "maxLength": 524288}},
                "required": ["json_text"],
                "additionalProperties": False,
            },
            handler=review_rbac_json,
            risk=Risk.SAFE,
            category="devops",
        )
    )


# A structural snapshot review never authorizes a Kubernetes operation.
