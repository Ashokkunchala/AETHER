"""Owner-run local setup for the disabled typed live lifecycle. No provider access.

This wizard only writes a local opt-in file holding a fresh connection generation
and one exact allowlisted scope digest, plus the reviewed plan JSON. It never
enables, approves, executes or tests any live provider call, and it never reads
credentials. The owner still runs prepare/review/execute on a trusted local
terminal and uses their own already-configured AWS profile or kubeconfig.
Real targets can cost money, interrupt service or lose data; the typed runtime
re-asks for an exact typed approval with a 120 second expiry before any write.
"""
from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path

from aether.devops.lifecycle_design import design_lifecycle_change

OPERATIONS = ("ec2_start", "ec2_stop", "k8s_scale")

HELPERS = {
    "account_id": "aws sts get-caller-identity --profile YOURPROFILE --query Account --output text",
    "region": "aws configure get region --profile YOURPROFILE",
    "instance_id": "aws ec2 describe-instances --profile YOURPROFILE --query 'Reservations[].Instances[].{id:InstanceId,state:State.Name,root:RootDeviceType}' --output table",
    "context": "kubectl config current-context",
    "cluster_uid": "kubectl get namespace kube-system -o jsonpath='{.metadata.uid}'",
    "cluster_ca_sha256": "sha256sum the exact CA file your context uses (see: kubectl config view --raw -o jsonpath='{.clusters[?(@.name==\"CLUSTER\")].cluster.certificate-authority}')",
    "deployment_uid": "kubectl get deployment NAME -n NAMESPACE -o jsonpath='{.metadata.uid}'",
    "resource_version": "kubectl get deployment NAME -n NAMESPACE -o jsonpath='{.metadata.resourceVersion}'",
    "current_replicas": "kubectl get deployment NAME -n NAMESPACE -o jsonpath='{.spec.replicas}'",
    "hpa_state": "kubectl get hpa -n NAMESPACE (absent/present/unknown)",
}

EC2_FIELDS = ("account_id", "partition", "region", "profile", "instance_id")
K8S_FIELDS = ("context", "cluster_uid", "cluster_ca_sha256", "namespace", "deployment",
              "deployment_uid", "resource_version", "current_replicas", "target_replicas", "hpa_state")


def setup_dir() -> Path:
    raw = os.environ.get("AETHER_LIVE_SETUP_DIR") or str(Path.home() / ".aether")
    path = Path(raw).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Absolute local nonsymlink setup directory required.")
    return path


def collect_plan(operation: str, answers: dict) -> dict:
    """Build one exact typed plan from supplied answers; no live lookups or defaults."""
    if operation not in OPERATIONS:
        raise ValueError("Choose one exact operation: " + ", ".join(OPERATIONS) + ". GitHub dispatch stays disabled by design.")
    if not isinstance(answers, dict):
        raise ValueError("Exact field answers required.")
    if operation.startswith("ec2_"):
        unknown = set(answers) - set(EC2_FIELDS)
        if unknown:
            raise ValueError("Unsupported fields: " + ",".join(sorted(unknown)))
        plan = {key: answers.get(key, "") for key in EC2_FIELDS}
        plan["expected_state"] = "stopped" if operation == "ec2_start" else "running"
    else:
        unknown = set(answers) - set(K8S_FIELDS)
        if unknown:
            raise ValueError("Unsupported fields: " + ",".join(sorted(unknown)))
        plan = {key: answers.get(key, "") for key in K8S_FIELDS}
        for key in ("current_replicas", "target_replicas"):
            value = plan[key]
            if isinstance(value, str) and value.isdigit():
                plan[key] = int(value)
    plan = {"operation": operation, **plan}
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    proposal = design_lifecycle_change(canonical)  # validates every exact field
    return {"plan": plan, "plan_json": canonical, "digest": proposal["proposal_sha256"],
            "warnings": proposal["warnings"], "live_checks": proposal["operation_specific_live_checks"]}


def write_opt_in(directory: Path, generation: str, digest_value: str, plan_json: str, replace: bool = False) -> dict:
    """Write the local opt-in env file and reviewed plan. Owner-only permissions."""
    if not isinstance(generation, str) or not generation or len(generation) > 128:
        raise ValueError("Fresh connection generation required.")
    if not isinstance(digest_value, str) or len(digest_value) != 64 or any(c not in "0123456789abcdef" for c in digest_value):
        raise ValueError("Exact canonical scope digest required.")
    if not isinstance(plan_json, str) or not plan_json.strip() or len(plan_json.encode()) > 8192:
        raise ValueError("Bounded reviewed plan JSON required, no credentials.")
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        directory.chmod(0o700)
    env_path = directory / "typed-live.env"
    plan_path = directory / "typed-live-plan.json"
    for path in (env_path, plan_path):
        if path.is_symlink():
            raise ValueError("Refusing to write through a symlink: " + path.name)
        if path.exists() and not replace:
            raise ValueError(path.name + " already exists; review it or rerun with replace confirmed. Nothing overwritten.")
    env_text = (
        "# AETHER typed live opt-in, written by `aether setup-live-cloud`.\n"
        "# Local to this machine and user. Delete this file or run the revoke step to disable.\n"
        "# This file alone changes nothing in any cloud account.\n"
        "AETHER_ENABLE_TYPED_LIVE=I_REVIEWED_REAL_TARGETS\n"
        "AETHER_TYPED_CONNECTION_GENERATION=" + generation + "\n"
        "AETHER_TYPED_ALLOWED_SCOPE_SHA256=" + digest_value + "\n"
    )
    for path, text in ((env_path, env_text), (plan_path, plan_json + "\n")):
        fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        if os.name == "posix":
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode != 0o600:
                raise ValueError("Owner-only file permissions required on " + path.name)
    return {"env_file": str(env_path), "plan_file": str(plan_path), "generation": generation, "digest": digest_value}


def next_steps(env_path: str, plan_path: str) -> list:
    return [
        "1. Load the opt-in for one terminal only:",
        "   POSIX:   set -a; . \"" + env_path + "\"; set +a",
        "   PowerShell: Get-Content \"" + env_path + "\" | Where-Object {$_ -match '^AETHER_'} | ForEach-Object {$k,$v=$_ -split '=',2; [Environment]::SetEnvironmentVariable($k,$v,'Process')}",
        "2. Prepare (reads live preflight evidence; provider read charges may apply):",
        "   python -m aether.devops.lifecycle_runtime prepare \"$(cat '" + plan_path + "')\"",
        "3. Review the exact scope and evidence, then approve in the same terminal:",
        "   python -m aether.devops.lifecycle_runtime review <request_id>",
        "4. Execute once:",
        "   python -m aether.devops.lifecycle_runtime execute <request_id>",
        "5. Check the outcome (never blindly retry):",
        "   python -m aether.devops.lifecycle_runtime status <request_id>",
        "To disable: delete " + env_path + " and run: python -m aether.devops.lifecycle_runtime revoke",
    ]


def setup_live_cloud(ask, confirm) -> dict:
    """Interactive owner wizard. ask/confirm are injected so tests never touch a TTY."""
    if ask is None or confirm is None:
        raise ValueError("Interactive local terminal callbacks required.")
    if not confirm(
        "This writes a LOCAL opt-in for one exact real cloud target (EC2 start/stop or one "
        "Kubernetes Deployment scale). Nothing is enabled, approved or executed by this wizard. "
        "Real targets can cost money, interrupt service or lose data. Continue?"
    ):
        return {"completed": False, "reason": "owner_declined"}
    choice = ask("Operation [1=ec2_start 2=ec2_stop 3=k8s_scale]: ").strip()
    operation = {"1": "ec2_start", "2": "ec2_stop", "3": "k8s_scale"}.get(choice, "")
    if operation not in OPERATIONS:
        raise ValueError("Choose 1, 2 or 3. GitHub workflow dispatch stays disabled by design.")
    fields = EC2_FIELDS if operation.startswith("ec2_") else K8S_FIELDS
    answers = {}
    for field in fields:
        helper = HELPERS.get(field)
        if helper:
            ask("Find this value with: " + helper + "  (press Enter to continue)")
        answers[field] = ask(field + ": ").strip()
    built = collect_plan(operation, answers)
    for warning in built["warnings"]:
        ask("Warning: " + warning + "  (press Enter)")
    phrase = "I REVIEWED REAL TARGETS AND COSTS"
    if ask("Scope digest " + built["digest"][:16] + "... Type " + phrase + " to write the local opt-in: ") != phrase:
        return {"completed": False, "reason": "phrase_not_confirmed"}
    directory = setup_dir()
    replace = (directory / "typed-live.env").exists()
    if replace and not confirm("An existing typed-live.env will be replaced (old generation/digest stop working). Replace it?"):
        return {"completed": False, "reason": "replace_declined"}
    written = write_opt_in(directory, secrets.token_hex(16), built["digest"], built["plan_json"], replace=replace)
    return {"completed": True, "operation": operation, "digest": built["digest"],
            "env_file": written["env_file"], "plan_file": written["plan_file"],
            "steps": next_steps(written["env_file"], written["plan_file"])}
