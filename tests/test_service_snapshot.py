import asyncio
import json

import pytest

from aether.devops.service_snapshot import review_service_endpoints


def sample():
    return {
        "service": {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "svc", "namespace": "dev", "uid": "uid-1"},
            "spec": {
                "type": "ClusterIP",
                "ports": [{"name": "web", "port": 80, "targetPort": 8080, "protocol": "TCP"}],
            },
        },
        "endpoint_slices": {
            "apiVersion": "discovery.k8s.io/v1",
            "kind": "EndpointSliceList",
            "items": [
                {
                    "apiVersion": "discovery.k8s.io/v1",
                    "kind": "EndpointSlice",
                    "metadata": {
                        "name": "slice",
                        "namespace": "dev",
                        "labels": {"kubernetes.io/service-name": "svc"},
                        "ownerReferences": [
                            {"apiVersion": "v1", "kind": "Service", "name": "svc", "uid": "uid-1"}
                        ],
                    },
                    "addressType": "IPv4",
                    "endpoints": [{"addresses": ["192.0.2.1"], "conditions": {"ready": True}}],
                    "ports": [{"name": "web", "port": 8080, "protocol": "TCP"}],
                }
            ],
        },
    }


def review(data):
    return review_service_endpoints(json.dumps(data))


def test_label_owner_and_numeric_port_agreement_not_live_proof():
    result = review(sample())
    row = result["slices"][0]
    assert row["namespace_and_service_label_match"]
    assert row["owner_reference_comparison"] == "matches_supplied_name_uid"
    assert row["ports"][0]["comparison"] == "numeric_target_matches"
    assert not result["live_service_association_verified"] and not result["connectivity_verified"]
    assert (
        not result["snapshot_freshness_verified"] and not result["inventory_completeness_verified"]
    )
    for value in ["192.0.2.1", "uid-1", "8080", '"svc"', '"dev"', '"web"']:
        assert value not in json.dumps(result)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            lambda d: d["service"]["spec"]["ports"][0].update(targetPort=8081),
            "numeric_target_mismatch",
        ),
        (
            lambda d: d["service"]["spec"]["ports"][0].update(targetPort="http"),
            "named_target_requires_pod_resolution",
        ),
        (
            lambda d: d["service"]["spec"]["ports"][0].pop("targetPort"),
            "target_default_not_materialized_unknown",
        ),
        (lambda d: d["service"]["spec"]["ports"][0].pop("protocol"), "protocol_unreported_unknown"),
        (
            lambda d: d["endpoint_slices"]["items"][0]["ports"][0].pop("protocol"),
            "protocol_unreported_unknown",
        ),
        (
            lambda d: d["endpoint_slices"]["items"][0]["ports"][0].update(protocol="UDP"),
            "protocol_mismatch",
        ),
        (
            lambda d: d["endpoint_slices"]["items"][0]["ports"][0].update(port=None),
            "slice_port_unspecified_unknown",
        ),
        (
            lambda d: d["endpoint_slices"]["items"][0]["ports"][0].update(name="other"),
            "no_same_name_port_record",
        ),
        (
            lambda d: d["endpoint_slices"]["items"][0]["metadata"].update(namespace="other"),
            "not_compared_unassociated",
        ),
    ],
)
def test_port_unknowns_mismatch_and_no_cross_namespace_comparison(change, expected):
    data = sample()
    change(data)
    assert review(data)["slices"][0]["ports"][0]["comparison"] == expected


def test_owners_missing_conflict_and_label_disagreement_separate():
    data = sample()
    sl = data["endpoint_slices"]["items"][0]
    sl["metadata"]["ownerReferences"][0]["uid"] = "different"
    result = review(data)["slices"][0]
    assert (
        result["namespace_and_service_label_match"]
        and result["owner_reference_comparison"] == "conflicts_with_supplied_service"
    )
    sl["metadata"].pop("ownerReferences")
    assert review(data)["slices"][0]["owner_reference_comparison"] == "absent_unknown"
    sl["metadata"]["labels"]["kubernetes.io/service-name"] = "different"
    assert review(data)["matching_label_slices"] == 0


def test_pagination_publish_readiness_and_empty_slices_stay_unknown():
    data = sample()
    data["service"]["spec"]["publishNotReadyAddresses"] = True
    data["endpoint_slices"]["metadata"] = {"continue": "PRIVATE_TOKEN"}
    result = review(data)
    assert result["continuation_token_present"] and result["publish_not_ready_addresses"] == "True"
    assert "PRIVATE_TOKEN" not in str(result)
    assert result["slices"][0]["reported_condition_combinations"][0]["ready"] == "True"
    data["endpoint_slices"]["items"] = []
    assert review(data)["matching_label_slices"] == 0 and not review(data)["connectivity_verified"]


def test_single_slice_unnamed_port_and_source_omission():
    data = sample()
    data["endpoint_slices"] = data["endpoint_slices"]["items"][0]
    data["service"]["spec"]["ports"][0].pop("name")
    data["endpoint_slices"]["ports"][0].pop("name")
    data["service"]["metadata"]["annotations"] = {"instruction": "PRIVATE_INSTRUCTION"}
    assert review(data)["slices"][0]["ports"][0]["comparison"] == "numeric_target_matches"
    assert "PRIVATE_INSTRUCTION" not in str(review(data))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["service"].update(kind="Secret"),
        lambda d: d["service"].update(apiVersion="other"),
        lambda d: d["service"]["metadata"].pop("uid"),
        lambda d: d["service"]["metadata"].update(uid="bad/uid"),
        lambda d: d["service"]["metadata"].update(namespace="bad.ns"),
        lambda d: d["service"]["metadata"].update(name="BAD"),
        lambda d: d["service"]["spec"].update(type="Other"),
        lambda d: d["service"]["spec"].update(publishNotReadyAddresses="true"),
        lambda d: d["service"]["spec"].update(ports={}),
        lambda d: d["service"]["spec"]["ports"][0].update(port=True),
        lambda d: d["service"]["spec"]["ports"][0].update(port=0),
        lambda d: d["service"]["spec"]["ports"][0].update(targetPort=True),
        lambda d: d["service"]["spec"]["ports"][0].update(targetPort="123"),
        lambda d: d["service"]["spec"]["ports"][0].update(protocol="OTHER"),
        lambda d: d["service"]["spec"]["ports"][0].update(name=[]),
        lambda d: d["endpoint_slices"]["items"][0]["metadata"].update(ownerReferences={}),
        lambda d: d["endpoint_slices"]["items"][0]["metadata"]["ownerReferences"][0].pop("uid"),
        lambda d: d["endpoint_slices"]["items"][0]["ports"][0].update(name=[]),
        lambda d: d["endpoint_slices"]["items"][0]["ports"][0].update(protocol="OTHER"),
        lambda d: d["endpoint_slices"]["items"][0]["endpoints"][0]["conditions"].update(
            ready="True"
        ),
        lambda d: d["endpoint_slices"]["items"][0]["endpoints"][0].update(
            addresses=["bad-address"]
        ),
    ],
)
def test_malformed_fields_fail_not_partial_healthy(change):
    data = sample()
    change(data)
    with pytest.raises(ValueError):
        review(data)


@pytest.mark.parametrize(
    "value",
    [None, True, {}, "", "[]", "null", '{"x":1,"x":2}', '{"x":NaN}', "x" * 524289, "\ud800"],
)
def test_bad_json(value):
    with pytest.raises(ValueError):
        review_service_endpoints(value)


def test_duplicate_and_count_limits():
    data = sample()
    data["service"]["spec"]["ports"] *= 2
    with pytest.raises(ValueError):
        review(data)
    data = sample()
    data["endpoint_slices"]["items"][0]["ports"] *= 2
    with pytest.raises(ValueError):
        review(data)
    data = sample()
    data["endpoint_slices"]["items"][0]["metadata"]["ownerReferences"] *= 2
    with pytest.raises(ValueError):
        review(data)
    data = sample()
    data["service"]["spec"]["ports"] *= 101
    with pytest.raises(ValueError):
        review(data)
    data = sample()
    data["endpoint_slices"]["items"][0]["metadata"]["ownerReferences"] *= 21
    with pytest.raises(ValueError):
        review(data)


def test_registry_keeps_existing_snapshot_reviewers(tmp_path, monkeypatch):
    from aether.tools.builtin_tools import build_registry

    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    assert "review_k8s_rbac_json" in registry.tools and "review_k8s" in registry.tools
    result = asyncio.run(
        registry.execute("review_k8s_service_endpoints_json", {"json_text": json.dumps(sample())})
    )
    assert (
        result.ok
        and result.data["matching_label_slices"] == 1
        and not result.data["connectivity_verified"]
    )
