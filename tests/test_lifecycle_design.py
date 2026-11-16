import asyncio
import json

import pytest

from jarvis.devops.lifecycle_design import GRAPH, design_lifecycle_change, simulate_lifecycle


def ec2(operation="ec2_stop"):
    return {"operation": operation, "account_id": "123456789012", "partition": "aws", "region": "ap-south-1", "profile": "sandbox", "instance_id": "i-0123456789abcdef0", "expected_state": "running" if operation == "ec2_stop" else "stopped"}


def k8s():
    return {"operation": "k8s_scale", "context": "dev-cluster", "cluster_uid": "cluster-1", "cluster_ca_sha256": "a" * 64, "namespace": "dev", "deployment": "web", "deployment_uid": "deployment-1", "resource_version": "101", "current_replicas": 2, "target_replicas": 3, "hpa_state": "absent"}


def github():
    return {"operation": "github_dispatch", "repository_id": 1234, "owner": "example", "repository": "demo", "workflow_id": 5, "ref": "reviewed-build", "resolved_commit_sha": "b" * 40, "workflow_blob_sha": "c" * 40}


def design(data):
    return design_lifecycle_change(json.dumps(data))


@pytest.mark.parametrize("factory", [ec2, lambda: ec2("ec2_start"), k8s, github])
def test_all_operations_produce_only_unverified_nonexecutable_design(factory):
    result = design(factory())
    assert result["mode"] == "design_only"
    assert result["state"] == "draft_not_authorized"
    assert result["supplied_unverified_scope"] == factory()
    assert result["provider_calls_made"] == 0
    for key in ("execution_authorized", "effect_adapter_available", "live_state_verified", "owner_approval_recorded", "cost_verified", "external_outcome_verified"):
        assert result[key] is False
    assert len(result["proposal_sha256"]) == 64
    assert result["required_gates"] and result["operation_specific_live_checks"]
    assert result["sources"]
    assert "Existing generic tools are separate" in result["limits"]


def test_digest_stable_for_key_order_and_binds_every_target_change():
    data = k8s()
    result = design(data)
    assert design_lifecycle_change(json.dumps(dict(reversed(list(data.items())))))["proposal_sha256"] == result["proposal_sha256"]
    for key, value in {"context": "other", "cluster_uid": "cluster-2", "cluster_ca_sha256": "b" * 64, "namespace": "qa", "deployment": "other", "deployment_uid": "deployment-2", "resource_version": "102", "current_replicas": 1, "target_replicas": 4, "hpa_state": "present"}.items():
        changed = {**data, key: value}
        assert design(changed)["proposal_sha256"] != result["proposal_sha256"]


@pytest.mark.parametrize("extra", ["approved", "approval_id", "auto_approve", "executor", "command", "url", "shell", "credentials", "inputs", "force", "dry_run"])
def test_no_caller_authority_commands_or_unreviewed_flags(extra):
    for factory in (ec2, k8s, github):
        with pytest.raises(ValueError):
            design({**factory(), extra: True})


@pytest.mark.parametrize("factory", [ec2, k8s, github])
def test_every_field_required(factory):
    for key in factory():
        data = factory(); del data[key]
        with pytest.raises(ValueError):
            design(data)


@pytest.mark.parametrize("text", ["[]", "null", "true", "1", '"text"', '{"operation":"ec2_stop","operation":"ec2_start"}', '{"operation":NaN}', '{"operation":Infinity}', "{", "x" * 8193, "[" * 3000, "💡" * 3000])
def test_parser_rejects_ambiguous_hostile_data(text):
    with pytest.raises(ValueError):
        design_lifecycle_change(text)


@pytest.mark.parametrize("key,value", [("account_id", "123"), ("account_id", 123456789012), ("account_id", "１２３４５６７８９０１２"), ("instance_id", "i-*"), ("instance_id", "i-0123456789abcdef0;whoami"), ("profile", "--help"), ("region", "https://example.com"), ("expected_state", "pending"), ("partition", "other"), ("region", "cn-north-1"), ("region", "us-gov-west-1")])
def test_ec2_exact_identity_and_current_state_fields(key, value):
    with pytest.raises(ValueError):
        design({**ec2(), key: value})


def test_ec2_matching_noncommercial_partition_families_only_design():
    for partition, region in (("aws-cn", "cn-north-1"), ("aws-us-gov", "us-gov-west-1")):
        assert not design({**ec2(), "partition": partition, "region": region})["execution_authorized"]
    for operation in ("ec2_start", "ec2_stop"):
        result = design(ec2(operation))
        assert any("instance-store" in row for row in result["warnings"])
        assert any("charges" in row for row in result["warnings"])


@pytest.mark.parametrize("key,value", [("target_replicas", True), ("current_replicas", 2.0), ("target_replicas", -1), ("target_replicas", 1001), ("target_replicas", 2), ("namespace", "*"), ("namespace", "kube-system;echo"), ("deployment", "a/b"), ("resource_version", ""), ("cluster_uid", None), ("cluster_ca_sha256", "a" * 63), ("hpa_state", True), ("hpa_state", "safe")])
def test_k8s_refuses_unbound_coerced_noop_or_wildcard_scope(key, value):
    with pytest.raises(ValueError):
        design({**k8s(), key: value})


def test_scale_zero_and_hpa_unknown_are_explicit_dangers_not_approvals():
    for state in ("absent", "present", "unknown"):
        result = design({**k8s(), "target_replicas": 0, "hpa_state": state})
        assert not result["execution_authorized"]
        assert any("present or unknown blocks" in line for line in result["operation_specific_live_checks"])
        assert any("scale-to-zero" in line for line in result["operation_specific_live_checks"])


@pytest.mark.parametrize("key,value", [("repository_id", True), ("repository_id", 0), ("workflow_id", "5"), ("owner", "../other"), ("repository", "demo.git"), ("repository", "../demo"), ("ref", "a..b"), ("ref", "a//b"), ("ref", "a.lock"), ("ref", "a/.hidden"), ("ref", "a/part.lock/file"), ("ref", "a/"), ("ref", "a."), ("ref", "--flag"), ("ref", "main;whoami"), ("resolved_commit_sha", "main"), ("workflow_blob_sha", "x" * 40)])
def test_github_target_ref_and_artifact_are_closed(key, value):
    with pytest.raises(ValueError):
        design({**github(), key: value})


def test_ci_defaults_dispatch_correlation_and_ref_race_not_hidden():
    result = design(github())
    assert any("default inputs" in row for row in result["operation_specific_live_checks"])
    assert any("HTTP acceptance is not" in row for row in result["operation_specific_live_checks"])
    assert any("atomicity" in row for row in result["warnings"])
    assert "never automatically retry" in result["unknown_outcome_policy"]


def test_entire_design_graph_is_simulation_and_does_not_authorize_any_transition():
    seen = set()
    def walk(events):
        result = simulate_lifecycle(events)
        assert result["simulation_only"] and not result["execution_authorized"]
        assert not result["external_outcome_verified"] and result["dispatch_count"] == 0
        state = result["hypothetical_state"]
        if state in seen:
            return
        seen.add(state)
        for event in GRAPH.get(state, {}):
            walk([*events, event])
    walk([])
    assert {"verified", "outcome_unknown", "cancelled", "expired", "stopped", "revoked", "denied", "stale", "failed", "blocked"} <= seen


@pytest.mark.parametrize("events", [["approval_verified"], ["preflight_ok", "revalidated_and_claimed_once"], ["stop", "preflight_ok"], ["preflight_failed", "retry"], ["cancel", "approval_verified"], ["preflight_ok", "approval_verified", "revalidated_and_claimed_once", "timeout", "retry"], ["preflight_ok", "approval_verified", "revalidated_and_claimed_once", "cancel", "verified"]])
def test_no_gate_skip_terminal_resurrection_unknown_retry_or_cancel_success(events):
    with pytest.raises(ValueError):
        simulate_lifecycle(events)


def test_after_dispatch_stop_is_not_kill_and_acceptance_is_not_success():
    prefix = ["preflight_ok", "approval_verified", "revalidated_and_claimed_once"]
    assert simulate_lifecycle([*prefix, "accepted"])["hypothetical_state"] == "verification_required"
    assert simulate_lifecycle([*prefix, "stop"])["hypothetical_state"] == "cancellation_requested"
    assert simulate_lifecycle([*prefix, "cancel", "timeout"])["hypothetical_state"] == "outcome_unknown"


def test_registry_integration_invocation_is_safe_design_only(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "safety.db"))
    from jarvis.tools.builtin_tools import build_registry
    from jarvis.tools.registry import Risk
    registry = build_registry()
    tool = registry.tools["design_lifecycle_change"]
    assert tool.risk == Risk.SAFE and not tool.confirm_required
    assert tool.parameters["additionalProperties"] is False
    result = asyncio.run(registry.execute("design_lifecycle_change", {"plan_json": json.dumps(ec2())}))
    assert result.ok and not result.data["execution_authorized"]
    assert registry.tools["aws_change"].confirm_required


def test_design_has_no_effect_imports_or_generic_adapter_dispatch():
    import ast
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / "jarvis/devops/lifecycle_design.py"
    tree = ast.parse(source.read_text())
    imports = [node.module if isinstance(node, ast.ImportFrom) else alias.name for node in ast.walk(tree) if isinstance(node, (ast.ImportFrom, ast.Import)) for alias in (node.names if isinstance(node, ast.Import) else [None])]
    assert set(imports) <= {"__future__", "hashlib", "json", "re", "jarvis.tools.registry"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("open", "eval", "exec", "__import__")
