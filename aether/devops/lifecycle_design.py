"""Typed lifecycle proposal design. No credentials, approvals, files or effect adapters.

Input values describe desired scope, not verified accounts, current state or authority.
The pure simulator tests the proposed protocol only. It cannot produce an approval
receipt or dispatch to existing generic AWS, shell, kubectl or provider paths.
"""
from __future__ import annotations

import hashlib
import json
import re

SOURCES = {
    "ec2": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html",
    "ec2_billing": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html",
    "scale": "https://kubernetes.io/docs/reference/kubectl/generated/kubectl_scale/",
    "dispatch": "https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28",
}
GATES = (
    "verify_active_requester_device_credential_and_account_connection_generation",
    "resolve_live_identity_target_artifact_and_required_permissions",
    "collect_fresh_current_state_and_conflict_preconditions",
    "review_cost_data_loss_outage_external_audience_and_undo_limits",
    "obtain_explicit_owner_approval_of_exact_immutable_scope_and_cost_limits",
    "revalidate_scope_expiry_revocation_stop_and_live_preconditions_at_dispatch",
    "atomically_claim_once_then_enter_one_typed_adapter_without_shell_fallback",
    "verify_external_outcome_with_same_identity_target_and_evidence",
)
# Only a design graph. Each event is a hypothetical label, never evidence of permission.
GRAPH = {
    "draft": {"preflight_ok": "approval_required", "preflight_failed": "blocked", "cancel": "cancelled", "stop": "stopped", "revoke": "revoked", "expire": "expired"},
    "approval_required": {"approval_verified": "revalidation_required", "deny": "denied", "cancel": "cancelled", "expire": "expired", "stop": "stopped", "revoke": "revoked"},
    "revalidation_required": {"revalidated_and_claimed_once": "dispatching", "drift": "stale", "cancel": "cancelled", "expire": "expired", "stop": "stopped", "revoke": "revoked"},
    "dispatching": {"accepted": "verification_required", "definite_rejection": "failed", "timeout": "outcome_unknown", "cancel": "cancellation_requested", "stop": "cancellation_requested", "revoke": "cancellation_requested"},
    "cancellation_requested": {"effect_confirmed": "verification_required", "no_effect_confirmed": "cancelled", "timeout": "outcome_unknown"},
    "verification_required": {"verified": "verified", "contradiction": "failed", "timeout": "outcome_unknown", "cancel": "cancellation_requested", "stop": "cancellation_requested", "revoke": "cancellation_requested"},
}


def simulate_lifecycle(events: list[str]) -> dict:
    """Finite protocol simulation. Deliberately no persistence, authority or dispatcher."""
    if type(events) is not list or len(events) > 12:
        raise ValueError("Use at most 12 hypothetical events.")
    state = "draft"
    trace = [state]
    for event in events:
        if type(event) is not str or event not in GRAPH.get(state, {}):
            raise ValueError("Unsupported lifecycle transition; no retry or terminal-state resurrection.")
        state = GRAPH[state][event]
        trace.append(state)
    return {"simulation_only": True, "hypothetical_state": state, "hypothetical_trace": trace,
            "execution_authorized": False, "external_outcome_verified": False, "dispatch_count": 0}


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate keys refused.")
        value[key] = item
    return value


def _text(data, key, pattern, limit=256):
    value = data[key]
    if type(value) is not str or not 1 <= len(value) <= limit or re.fullmatch(pattern, value, flags=re.ASCII) is None:
        raise ValueError("Unsupported exact target field: " + key)
    return value


def _integer(data, key, low, high):
    value = data[key]
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Bounded integer required: " + key)
    return value


def design_lifecycle_change(plan_json: str) -> dict:
    if type(plan_json) is not str or not plan_json.strip() or len(plan_json.encode("utf-8")) > 8192:
        raise ValueError("Supply one bounded 8 KiB typed proposal JSON object, no credentials.")
    try:
        data = json.loads(plan_json, object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON refused.")))
    except (ValueError, RecursionError, OverflowError):
        raise ValueError("Malformed/duplicate/nonfinite JSON refused.") from None
    if type(data) is not dict or type(data.get("operation")) is not str:
        raise ValueError("One typed operation object required.")
    operation = data["operation"]
    fields = {
        "ec2_start": {"account_id", "partition", "region", "profile", "instance_id", "expected_state"},
        "ec2_stop": {"account_id", "partition", "region", "profile", "instance_id", "expected_state"},
        "k8s_scale": {"context", "cluster_uid", "cluster_ca_sha256", "namespace", "deployment", "deployment_uid", "resource_version", "current_replicas", "target_replicas", "hpa_state"},
        "github_dispatch": {"repository_id", "owner", "repository", "workflow_id", "ref", "resolved_commit_sha", "workflow_blob_sha"},
    }
    if operation not in fields or set(data) != fields[operation] | {"operation"}:
        raise ValueError("Unsupported operation or missing/extra fields. No raw commands, URLs, inputs, caller approval or wildcard targets.")
    live_checks = []
    warnings = []
    if operation.startswith("ec2_"):
        _text(data, "account_id", r"[0-9]{12}", 12)
        partition = _text(data, "partition", r"aws(?:-cn|-us-gov)?", 10)
        region = _text(data, "region", r"[a-z]{2}(?:-[a-z]+){1,3}-[1-9][0-9]?", 32)
        if (partition == "aws-cn") != region.startswith("cn-") or (partition == "aws-us-gov") != region.startswith("us-gov-"):
            raise ValueError("Partition and region family mismatch.")
        _text(data, "profile", r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}", 64)
        _text(data, "instance_id", r"i-[0-9a-f]{17}", 19)
        expected = "stopped" if operation == "ec2_start" else "running"
        if data["expected_state"] != expected:
            raise ValueError("Unsupported/no-op current state for this proposed operation.")
        live_checks = ["STS account and partition, configured profile identity and region match exact supplied scope",
                       "EC2 instance state and EBS root support; reject instance-store-root or transient states",
                       "Instance-store data dependency, attached storage, addressing, stop protection and workload impact",
                       "Explicit owner-approved cost ceiling and outage/data-loss scope; current billing not guessed"]
        warnings = ["Start may incur instance and other charges; stopped instances can still incur storage/address charges.",
                    "Stop can erase instance-store data and RAM; start/stop is not a safe automatic rollback.",
                    "A public address or host may change. No force, skip-OS-shutdown, hibernation or termination variant is designed."]
    elif operation == "k8s_scale":
        _text(data, "context", r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}", 128)
        for key in ("cluster_uid", "deployment_uid"):
            _text(data, key, r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", 128)
        _text(data, "cluster_ca_sha256", r"[0-9a-f]{64}", 64)
        for key in ("namespace", "deployment"):
            _text(data, key, r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", 63)
        _text(data, "resource_version", r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", 128)
        current = _integer(data, "current_replicas", 0, 1000)
        desired = _integer(data, "target_replicas", 0, 1000)
        if current == desired:
            raise ValueError("No-op scale refused; refresh the desired scope.")
        if data["hpa_state"] not in ("absent", "present", "unknown"):
            raise ValueError("Supply explicit HPA observation state.")
        live_checks = ["Verify context resolves to exact cluster identity/CA and authorized namespace",
                       "Fresh deployment UID, resourceVersion and current replicas must match the preconditions",
                       "Live HPA/other-controller ownership must be absent; present or unknown blocks this design",
                       "Review capacity/quota, affected workloads and cost/outage effects including scale-to-zero",
                       "Use server-checked concurrency preconditions; drift requires a fresh plan and fresh approval"]
        warnings = ["Desired replicas are not ready/available replicas, application health or SLO success.",
                    "Controllers can race or reverse a manual scale. A stale count/version must not be silently retried.",
                    "Scaling back requires a new exact proposal/approval; it is not an automatic rollback."]
    else:
        _integer(data, "repository_id", 1, 2**63 - 1)
        _integer(data, "workflow_id", 1, 2**63 - 1)
        _text(data, "owner", r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", 39)
        name = _text(data, "repository", r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", 100)
        if name.endswith(".git"):
            raise ValueError("Supply repository name without .git suffix.")
        ref = _text(data, "ref", r"[A-Za-z0-9][A-Za-z0-9_./-]{0,127}", 128)
        if ".." in ref or "//" in ref or ref.endswith(("/", ".", ".lock")) or any(part.startswith(".") or part.endswith(".lock") for part in ref.split("/")):
            raise ValueError("Unsupported branch/tag ref.")
        for key in ("resolved_commit_sha", "workflow_blob_sha"):
            _text(data, key, r"(?:[0-9a-f]{40}|[0-9a-f]{64})", 64)
        live_checks = ["Verify authenticated repository numeric ID/owner/name and workflow numeric ID/blob",
                       "Verify workflow_dispatch on default branch and selected ref; pin and recheck selected commit",
                       "Resolve branch/tag ambiguity and refuse ref drift; API dispatch ref is not itself a commit lock",
                       "Review all workflow/default inputs, reusable workflows, actions, scripts, permissions, secrets and environments",
                       "Require a reviewed no-input workflow for this version; omitted inputs can still apply unsafe defaults",
                       "Approve runner minutes/artifact cost ceiling and any deployment/provider/notification effects separately",
                       "Correlate returned provider run identity; HTTP acceptance is not workflow success"]
        warnings = ["CI workflows execute code and may deploy, spend, publish or send messages. A no-input dispatch is not inherently safe.",
                    "No ref-to-submit atomicity is promised; mutable ref support stays blocked until a reviewed strategy exists.",
                    "Unknown dispatch outcome must be reconciled against runs before any new request; no blind retry."]
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": 1, "mode": "design_only", "operation": operation,
        "supplied_unverified_scope": data,
        "proposal_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "state": "draft_not_authorized", "execution_authorized": False,
        "effect_adapter_available": False, "provider_calls_made": 0,
        "live_state_verified": False, "owner_approval_recorded": False,
        "cost_verified": False, "external_outcome_verified": False,
        "suggested_approval_ttl_seconds": 120,
        "required_gates": list(GATES), "operation_specific_live_checks": live_checks,
        "approval_binding_requirements": ["requester credential hash/device and live revocation status",
            "account/connection generation and exact target identities", "immutable canonical scope digest and artifact revision",
            "fresh preflight evidence digest and bounded approval expiry", "exact cost/credit, data-loss, outage and external-audience scope"],
        "unknown_outcome_policy": "Reconcile live external state, never automatically retry or mark successful.",
        "cancel_policy": "Before claim: suppress dispatch. After dispatch: cancellation requested only, verify externally; no undo/recall claim.",
        "warnings": warnings,
        "design_graph": {state: dict(events) for state, events in GRAPH.items()},
        "sources": [SOURCES[key] for key in (("ec2", "ec2_billing") if operation.startswith("ec2_") else ("scale",) if operation == "k8s_scale" else ("dispatch",))],
        "limits": "No executable adapter, approval receipt or shell fallback. Existing generic tools are separate and not upgraded by this proposal. Supplied observations and hashes do not authenticate accounts, authority, freshness or provenance.",
    }


def register_lifecycle_design(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name="design_lifecycle_change",
        description="Build one strict design-only EC2 start/stop, Kubernetes deployment scale or GitHub no-input workflow-dispatch proposal and required approval gates. No live preflight, approval recording, credential read, execution or shell. Supplied scope remains unverified.",
        parameters={"type": "object", "properties": {"plan_json": {"type": "string", "description": "One exact typed JSON object, max8KiB; operation ec2_start/ec2_stop/k8s_scale/github_dispatch. See lifecycle design guide for required fields. No credentials, arbitrary commands or caller approval booleans."}}, "required": ["plan_json"], "additionalProperties": False},
        handler=design_lifecycle_change, risk=Risk.SAFE, category="devops",
    ))
