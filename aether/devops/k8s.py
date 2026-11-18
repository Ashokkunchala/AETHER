"""Offline Kubernetes manifest reviewer.

Reads local YAML text only. No cluster calls, no kubectl, no file changes.
It uses line patterns instead of a YAML parser so it works with no extra
dependency; findings are heuristics for a human review, not a security audit.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aether.devops.review import _files, _finding, _read, _summary

WORKLOADS = ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob", "Pod", "ReplicaSet")


def _documents(text: str) -> list[tuple[int, str]]:
    """Split a multi-document YAML file into (first_line_number, text) pairs."""
    docs: list[tuple[int, str]] = []
    start = 1
    buf: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip() == "---":
            if buf:
                docs.append((start, "\n".join(buf)))
            start, buf = n + 1, []
        else:
            buf.append(line)
    if buf:
        docs.append((start, "\n".join(buf)))
    return docs


def _line_of(doc: str, start: int, pattern: str) -> int | None:
    for i, line in enumerate(doc.splitlines()):
        if re.search(pattern, line):
            return start + i
    return None


def review_k8s_text(text: str, where: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for start, doc in _documents(text):
        kind_m = re.search(r"^kind:\s*(\w+)", doc, re.M)
        if not kind_m:
            continue
        kind = kind_m.group(1)
        if kind == "Service" and re.search(r"^\s*type:\s*LoadBalancer", doc, re.M):
            if not re.search(r"loadBalancerSourceRanges|internal", doc):
                findings.append(_finding("medium", "k8s-public-loadbalancer", "LoadBalancer text pattern without recognized source-range/internal text. Review provider/network configuration; public reachability is not established.", where, _line_of(doc, start, r"LoadBalancer")))
        if kind == "Secret" and re.search(r"^data:\s*$", doc, re.M):
            findings.append(_finding("medium", "k8s-secret-in-manifest", "Secret data field text pattern found. Base64 is not encryption; actual storage encryption, exposure and whether this file was committed are not evaluated.", where, _line_of(doc, start, r"^kind:")))
        if kind in ("ClusterRoleBinding", "RoleBinding") and re.search(r"name:\s*cluster-admin", doc):
            findings.append(_finding("high", "k8s-cluster-admin-binding", "Binding document contains cluster-admin name text. Verify roleRef, subjects and namespace/cluster scope; effective privileges are not established.", where, _line_of(doc, start, r"cluster-admin")))
        if kind in ("ClusterRole", "Role") and re.search(r"verbs:\s*\[?\s*['\"]?\*", doc) and re.search(r"resources:\s*\[?\s*['\"]?\*", doc):
            findings.append(_finding("high", "k8s-wildcard-rbac", "Role document contains wildcard verb/resource text. Rule association, API groups, scope, binding and effective permissions are not evaluated.", where, _line_of(doc, start, r"verbs:")))
        if kind not in WORKLOADS:
            continue
        checks = [
            (r"privileged:\s*true", "high", "k8s-privileged", "privileged true text pattern found. Review the actual container/security context and platform; runtime privileges are not verified."),
            (r"hostNetwork:\s*true", "high", "k8s-host-network", "hostNetwork true text pattern found. Verify actual pod placement/context; network isolation and reachability are not evaluated."),
            (r"hostPID:\s*true", "high", "k8s-host-pid", "hostPID true text pattern found. Verify actual pod context and process isolation; runtime access is not evaluated."),
            (r"allowPrivilegeEscalation:\s*true", "medium", "k8s-privilege-escalation", "allowPrivilegeEscalation true text pattern found. Review actual container context; runtime behavior is not verified."),
            (r"runAsUser:\s*0\b", "medium", "k8s-run-as-root", "runAsUser zero text pattern found. Actual container UID, overrides and runtime state are not verified."),
            (r"hostPath:", "medium", "k8s-hostpath", "hostPath text pattern found. Review source path, mount permissions and actual workload; effective host access is not evaluated."),
        ]
        for pattern, sev, rule, msg in checks:
            if re.search(pattern, doc):
                findings.append(_finding(sev, rule, msg, where, _line_of(doc, start, pattern)))
        for m in re.finditer(r"^\s*-?\s*image:\s*['\"]?([^\s'\"]+)", doc, re.M):
            image = m.group(1)
            if "@sha256:" in image:
                continue
            last = image.rsplit("/", 1)[-1]
            tag = last.split(":", 1)[1] if ":" in last else ""
            if not tag or tag == "latest":
                findings.append(_finding("medium", "k8s-unpinned-image", "Image text appears untagged or tagged latest. Value omitted; a tag/digest is not proof of immutability, provenance or security.", where, _line_of(doc, start, re.escape(image))))
        if "resources:" not in doc:
            findings.append(_finding("medium", "k8s-no-resources", "No resources text pattern found in this workload document. Per-container values, defaults, admission and capacity are not evaluated.", where, _line_of(doc, start, r"^kind:")))
        elif "limits:" not in doc:
            findings.append(_finding("low", "k8s-no-limits", "resources text is present but no limits text found. Actual per-container requests/limits and defaults are not verified.", where, _line_of(doc, start, r"resources:")))
        if kind != "Job" and kind != "CronJob" and kind != "Pod":
            if "readinessProbe" not in doc:
                findings.append(_finding("low", "k8s-no-readiness", "No readinessProbe text found in this workload document. Actual readiness, traffic routing and alternative readiness gates are not verified.", where, _line_of(doc, start, r"^kind:")))
            if "livenessProbe" not in doc:
                findings.append(_finding("low", "k8s-no-liveness", "No livenessProbe text found in this workload document. This does not prove a hung container exists or that no other restart mechanism applies.", where, _line_of(doc, start, r"^kind:")))
        if kind == "Deployment" and re.search(r"replicas:\s*1\s*$", doc, re.M):
            findings.append(_finding("low", "k8s-single-replica", "replicas one text pattern found. Actual replicas, disruption controls, other workloads and availability during drains are not verified.", where, _line_of(doc, start, r"replicas:")))
        if "runAsNonRoot" not in doc and "runAsUser" not in doc:
            findings.append(_finding("low", "k8s-no-security-context", "No runAsNonRoot/runAsUser text found in this document. Inherited/default/admission/runtime identity controls are not evaluated.", where, _line_of(doc, start, r"^kind:")))
    return findings


def review_k8s(path: str) -> dict[str, Any]:
    """Review Kubernetes YAML manifests under a local path."""
    try:
        files = _files(path, ("*.yml", "*.yaml"))
    except FileNotFoundError as exc:
        return {"success": False, "error": str(exc)}
    findings: list[dict[str, Any]] = []
    scanned = 0
    for f in files:
        if ".github" in Path(f).parts:
            continue
        try:
            text = _read(f)
        except ValueError as exc:
            findings.append(_finding("low", "k8s-file-too-large", str(exc), str(f)))
            continue
        if not re.search(r"^apiVersion:", text, re.M) or not re.search(r"^kind:", text, re.M):
            continue
        scanned += 1
        findings.extend(review_k8s_text(text, str(f)))
    result: dict[str, Any] = _summary(findings, scanned)
    result.update({'yaml_schema_validated': False, 'effective_rbac_verified': False,
                   'public_reachability_verified': False, 'runtime_security_verified': False,
                   'limits': ('Local line-pattern review only, not a YAML parser, Kubernetes API validation, effective RBAC audit or runtime security test. '
                              'Matches may be comments, strings, unrelated rules/fields or incorrect indentation; absent matches do not prove an unsafe field is absent or a control is safe. '
                              'RoleBinding namespace scope differs from ClusterRoleBinding cluster scope; roleRef/subjects/roles/API groups are not resolved. '
                              'LoadBalancer text does not prove public internet reachability; provider/controller/firewall/network context is not read. '
                              'No finding means only no selected pattern was found, never secure, private, healthy or complete. '
                              'The shared file enumerator caps candidate files at 200 without completeness accounting; files_scanned is not a complete repository audit. '
                              'File paths/line numbers remain in results and may be private. Existing path traversal/symlink handling is not a sandbox; use trusted selected files. '
                              'Image values are omitted, but source files/caller context are separate. No kubeconfig, cluster/network/model call or code execution, repair or deployment occurs.'),
                   'sources': ['https://kubernetes.io/docs/reference/access-authn-authz/rbac/',
                               'https://kubernetes.io/docs/tasks/configure-pod-container/security-context/',
                               'https://kubernetes.io/docs/concepts/configuration/secret/',
                               'https://kubernetes.io/docs/concepts/services-networking/service/']})
    return result
