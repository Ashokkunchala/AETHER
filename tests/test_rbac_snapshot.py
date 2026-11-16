import asyncio
import copy
import json

import pytest

from jarvis.devops.rbac_snapshot import review_rbac_json

API = "rbac.authorization.k8s.io/v1"


def role(name="reader", namespace="dev", kind="Role", rules=None):
    return {
        "apiVersion": API,
        "kind": kind,
        "metadata": {"name": name, **({"namespace": namespace} if kind == "Role" else {})},
        "rules": rules
        if rules is not None
        else [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]}],
    }


def binding(
    name="reader-binding", namespace="dev", kind="RoleBinding", refkind="Role", refname="reader"
):
    return {
        "apiVersion": API,
        "kind": kind,
        "metadata": {"name": name, **({"namespace": namespace} if kind == "RoleBinding" else {})},
        "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": refkind, "name": refname},
        "subjects": [{"kind": "ServiceAccount", "name": "worker", "namespace": "dev"}],
    }


def review(items, metadata=None):
    return review_rbac_json(
        json.dumps({"apiVersion": "v1", "kind": "List", "metadata": metadata or {}, "items": items})
    )


def test_exact_namespace_join_not_same_name_elsewhere():
    result = review([role(namespace="other"), binding(), role()])
    assert result["bindings"][0]["role_object_index"] == 2
    assert result["roles"][0]["referenced_by_bindings"] == 0
    assert result["roles"][1]["referenced_by_bindings"] == 1
    assert result["bindings"][0]["scope"] == "binding_namespace_only"
    assert not result["effective_authorization_verified"] and not result["cluster_queried"]


def test_clusterrole_binding_stays_namespace_limited_and_clusterbinding_separate():
    result = review(
        [
            role(kind="ClusterRole"),
            binding(refkind="ClusterRole"),
            binding(kind="ClusterRoleBinding", refkind="ClusterRole", name="cluster"),
        ]
    )
    assert result["bindings"][0]["scope"] == "binding_namespace_only"
    assert result["bindings"][1]["scope"] == "cluster_binding"
    assert result["roles"][0]["referenced_by_bindings"] == 2


def test_missing_role_and_pagination_stay_unknown():
    result = review([binding()], {"continue": "PRIVATE_TOKEN"})
    assert result["partial_snapshot"] and result["missing_role_references"] == 1
    assert result["bindings"][0]["role_object_index"] is None
    assert "PRIVATE_TOKEN" not in str(result)
    assert "unknown, not denied" in result["notice"]


def test_same_rule_association_not_cross_rule_wildcard_inference():
    rules = [
        {"apiGroups": [""], "resources": ["secrets"], "verbs": ["create"]},
        {"apiGroups": ["other"], "resources": ["secrets"], "verbs": ["get"]},
        {"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]},
    ]
    result = review([role(rules=rules)])
    assert all("core_secret_read_pattern" not in r["signals"] for r in result["roles"][0]["rules"])


@pytest.mark.parametrize(
    ("rule", "code"),
    [
        ({"apiGroups": [""], "resources": ["pods"], "verbs": ["*"]}, "wildcard_verbs"),
        ({"apiGroups": [""], "resources": ["*"], "verbs": ["get"]}, "wildcard_resources"),
        ({"apiGroups": ["*"], "resources": ["pods"], "verbs": ["get"]}, "wildcard_api_groups"),
        (
            {"apiGroups": [""], "resources": ["secrets"], "verbs": ["watch"]},
            "core_secret_read_pattern",
        ),
        (
            {"apiGroups": [""], "resources": ["pods/exec"], "verbs": ["create"]},
            "pod_exec_attach_pattern",
        ),
        (
            {"apiGroups": [""], "resources": ["pods/attach"], "verbs": ["get"]},
            "pod_exec_attach_pattern",
        ),
        (
            {
                "apiGroups": ["rbac.authorization.k8s.io"],
                "resources": ["roles"],
                "verbs": ["escalate"],
            },
            "sensitive_verb_review",
        ),
    ],
)
def test_patterns(rule, code):
    assert code in review([role(rules=[rule])])["roles"][0]["rules"][0]["signals"]


def test_nonresource_rules_never_namespace_grant_and_aggregation_not_resolved():
    r = role(kind="ClusterRole", rules=[{"nonResourceURLs": ["/healthz"], "verbs": ["get"]}])
    r["aggregationRule"] = {"clusterRoleSelectors": [{"matchLabels": {"example": "value"}}]}
    result = review([r, binding(refkind="ClusterRole")])
    assert result["roles"][0]["aggregation_unresolved"]
    assert result["bindings"][0]["aggregation_unresolved"]
    assert result["bindings"][0]["nonresource_rules_not_namespace_grants"]
    assert "nonresource_rule" in result["roles"][0]["rules"][0]["signals"]


def test_resource_names_constraints_not_evaluated_or_reflected():
    r = role(
        rules=[
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "verbs": ["get"],
                "resourceNames": ["PRIVATE_RESOURCE"],
            }
        ]
    )
    r["metadata"]["annotations"] = {"instruction": "UNIQUE_PRIVATE_SENTINEL"}
    b = binding()
    b["subjects"][0]["name"] = "PRIVATE_SUBJECT"
    result = review([r, b])
    encoded = json.dumps(result)
    assert result["roles"][0]["rules"][0]["resource_names_constraint_present"]
    for text in [
        "PRIVATE_RESOURCE",
        "UNIQUE_PRIVATE_SENTINEL",
        "PRIVATE_SUBJECT",
        "reader-binding",
    ]:
        assert text not in encoded


@pytest.mark.parametrize("kind", ["Role", "ClusterRole", "RoleBinding", "ClusterRoleBinding"])
def test_single_object_supported(kind):
    obj = (
        role(kind=kind)
        if "Binding" not in kind
        else binding(kind=kind, refkind="ClusterRole" if kind == "ClusterRoleBinding" else "Role")
    )
    assert review_rbac_json(json.dumps(obj))["object_count"] == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        1,
        True,
        "",
        "[]",
        "null",
        '{"kind":[]}',
        '{"kind":"Role","kind":"List"}',
        '{"kind":"List","apiVersion":"v1","items":[],"x":NaN}',
        "\ud800",
        "x" * 524289,
    ],
)
def test_bad_text_or_json(value):
    with pytest.raises(ValueError):
        review_rbac_json(value)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(kind="Secret"),
        lambda r: r.update(apiVersion="v1"),
        lambda r: r["metadata"].pop("namespace"),
        lambda r: r["metadata"].update(namespace="UPPER"),
        lambda r: r["metadata"].update(name="../bad"),
        lambda r: r.update(rules={}),
        lambda r: r.update(rules=[{"resources": ["pods"], "verbs": ["get"]}]),
        lambda r: r.update(rules=[{"apiGroups": [], "resources": ["pods"], "verbs": ["get"]}]),
        lambda r: r.update(rules=[{"apiGroups": [""], "resources": [""], "verbs": ["get"]}]),
        lambda r: r.update(rules=[{"apiGroups": [""], "resources": ["pods"], "verbs": []}]),
        lambda r: r.update(
            rules=[{"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "get"]}]
        ),
        lambda r: r.update(
            rules=[
                {"apiGroups": [""], "resources": ["pods"], "verbs": ["get"], "resourceNames": [""]}
            ]
        ),
        lambda r: r.update(rules=[{"nonResourceURLs": ["/"], "verbs": ["get"]}]),
        lambda r: r.update(aggregationRule={}),
    ],
)
def test_invalid_roles_not_partial_pass(change):
    obj = role()
    change(obj)
    with pytest.raises(ValueError):
        review([obj])


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b["roleRef"].update(kind="Secret"),
        lambda b: b["roleRef"].update(apiGroup="core"),
        lambda b: b.update(kind="ClusterRoleBinding", metadata={"name": "binding"}),
        lambda b: b["subjects"][0].pop("namespace"),
        lambda b: b["subjects"][0].update(apiGroup="other"),
        lambda b: b["subjects"][0].update(kind="Other"),
        lambda b: b.update(subjects={}),
        lambda b: b.update(
            subjects=[
                {
                    "kind": "User",
                    "name": "person",
                    "apiGroup": "rbac.authorization.k8s.io",
                    "namespace": "dev",
                }
            ]
        ),
        lambda b: b.update(subjects=[{"kind": "Group", "name": "group"}]),
    ],
)
def test_invalid_bindings_not_reported_as_access(change):
    obj = binding()
    change(obj)
    with pytest.raises(ValueError):
        review([obj])


def test_user_group_and_empty_subjects_no_identity_or_safety_assumption():
    obj = binding()
    obj["subjects"] = [
        {"kind": "User", "name": "private@example.test", "apiGroup": "rbac.authorization.k8s.io"},
        {"kind": "Group", "name": "system:authenticated", "apiGroup": "rbac.authorization.k8s.io"},
    ]
    result = review([obj])
    assert result["bindings"][0]["subject_count"] == 2
    assert "private@example" not in str(result) and "system:authenticated" not in str(result)
    obj["subjects"] = []
    assert review([obj])["bindings"][0]["subject_count"] == 0


def test_duplicates_limits_and_continuation_type():
    with pytest.raises(ValueError):
        review([role(), copy.deepcopy(role())])
    with pytest.raises(ValueError):
        review([binding()] * 501)
    with pytest.raises(ValueError):
        review([], {"continue": True})
    with pytest.raises(ValueError):
        review([role(rules=[{"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]}] * 101)])
    obj = binding()
    obj["subjects"] *= 101
    with pytest.raises(ValueError):
        review([obj])
    with pytest.raises(ValueError):
        review(
            [
                role(
                    name="r" + str(i),
                    rules=[{"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]}] * 100,
                )
                for i in range(21)
            ]
        )


def test_cluster_namespace_and_mixed_resource_rules_refused():
    obj = role(kind="ClusterRole")
    obj["metadata"]["namespace"] = "dev"
    with pytest.raises(ValueError):
        review([obj])
    obj = role(
        kind="ClusterRole",
        rules=[{"nonResourceURLs": ["/"], "verbs": ["get"], "resources": ["pods"]}],
    )
    with pytest.raises(ValueError):
        review([obj])


def test_registry_preserves_old_heuristic_and_has_no_cluster_execution(tmp_path, monkeypatch):
    from jarvis.tools.builtin_tools import build_registry

    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    assert "review_k8s" in registry.tools
    data = json.dumps(role())
    result = asyncio.run(registry.execute("review_k8s_rbac_json", {"json_text": data}))
    assert result.ok and result.data["object_count"] == 1 and not result.data["cluster_queried"]


def test_typed_list_version_and_item_kind_checked():
    assert (
        review_rbac_json(json.dumps({"apiVersion": API, "kind": "RoleList", "items": [role()]}))[
            "object_count"
        ]
        == 1
    )
    for value in [
        {"apiVersion": [], "kind": "List", "items": []},
        {"apiVersion": "v1", "kind": "RoleList", "items": [role()]},
        {"apiVersion": API, "kind": "RoleList", "items": [binding()]},
    ]:
        with pytest.raises(ValueError):
            review_rbac_json(json.dumps(value))
