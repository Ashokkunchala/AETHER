"""Offline infrastructure reviewers.

These functions only read local text. They never call AWS, never run
Terraform and never change files. Findings are heuristics meant to speed up a
human review, not a security audit.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MAX_BYTES = 512_000
MAX_FILES = 200

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _finding(severity: str, rule: str, message: str, where: str = "", line: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"severity": severity, "rule": rule, "message": message}
    if where:
        out["file"] = where
    if line:
        out["line"] = line
    return out


def _summary(findings: list[dict[str, Any]], scanned: int) -> dict[str, Any]:
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f.get("file", ""), f.get("line", 0)))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY_ORDER}
    return {"success": True, "files_scanned": scanned, "counts": counts, "findings": findings}


def _read(path: Path) -> str:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_BYTES} bytes")
    return path.read_text(encoding="utf-8", errors="replace")


def _files(root: str, patterns: tuple[str, ...]) -> list[Path]:
    base = Path(root).expanduser()
    if base.is_file():
        return [base]
    if not base.is_dir():
        raise FileNotFoundError(f"Path not found: {root}")
    skip = {".git", ".terraform", "node_modules", ".venv", "venv", "__pycache__"}
    found: list[Path] = []
    for pattern in patterns:
        for p in base.rglob(pattern):
            if p.is_file() and not (set(p.parts) & skip):
                found.append(p)
    return sorted(set(found))[:MAX_FILES]


# ----------------------------------------------------------------- IAM policy
def review_iam_policy(policy: str | dict[str, Any]) -> dict[str, Any]:
    """Review bounded supplied-policy patterns, never effective IAM permissions."""
    from jarvis.devops.iam_review import review_policy
    return review_policy(policy)


# ------------------------------------------------------------------ Terraform
_TF_RULES: list[tuple[str, str, str, str]] = [
    ("high", "tf-open-ingress", r"cidr_blocks\s*=\s*\[[^\]]*\"0\.0\.0\.0/0\"", "Security group rule open to 0.0.0.0/0; check the port is meant to be public."),
    ("high", "tf-public-s3-acl", r"acl\s*=\s*\"public-read(-write)?\"", "S3 bucket ACL grants public access."),
    ("high", "tf-hardcoded-aws-key", r"AKIA[0-9A-Z]{16}", "Looks like a hardcoded AWS access key id."),
    ("high", "tf-hardcoded-secret", r"(secret_key|password|secret)\s*=\s*\"[^\"$][^\"]{5,}\"", "Possible hardcoded secret; use a variable, Secrets Manager or SSM."),
    ("medium", "tf-storage-unencrypted", r"(storage_encrypted|encrypted)\s*=\s*false", "Encryption is explicitly disabled."),
    ("medium", "tf-rds-public", r"publicly_accessible\s*=\s*true", "RDS instance is publicly accessible."),
    ("medium", "tf-wildcard-iam", r"\"Action\"\s*:\s*\"\*\"|actions\s*=\s*\[\s*\"\*\"\s*\]", "IAM policy allows every action."),
    ("low", "tf-latest-version", r"version\s*=\s*\"(>=\s*0|latest)\"", "Provider or module version is unpinned."),
]


def review_terraform(path: str) -> dict[str, Any]:
    """Scan .tf files under a path for common risky patterns."""
    try:
        files = _files(path, ("*.tf",))
    except FileNotFoundError as exc:
        return {"success": False, "error": str(exc)}
    findings: list[dict[str, Any]] = []
    all_text = ""
    for f in files:
        try:
            text = _read(f)
        except ValueError as exc:
            findings.append(_finding("low", "file-too-large", str(exc), str(f)))
            continue
        all_text += text
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.strip().startswith(("#", "//")):
                continue
            for sev, rule, pattern, msg in _TF_RULES:
                if re.search(pattern, line):
                    findings.append(_finding(sev, rule, msg, str(f), lineno))
    if files and "backend \"" not in all_text and "cloud {" not in all_text:
        findings.append(_finding("medium", "tf-no-remote-backend", "No remote backend block found; state is local unless configured elsewhere.", str(path)))
    if files and "required_version" not in all_text:
        findings.append(_finding("low", "tf-no-required-version", "No terraform required_version constraint found.", str(path)))
    return _summary(findings, len(files))


# ------------------------------------------------------------------ Dockerfile
def review_dockerfile(path: str) -> dict[str, Any]:
    """Check Dockerfiles for common build and runtime problems."""
    try:
        files = _files(path, ("Dockerfile", "Dockerfile.*", "*.dockerfile"))
    except FileNotFoundError as exc:
        return {"success": False, "error": str(exc)}
    findings: list[dict[str, Any]] = []
    for f in files:
        text = _read(f)
        lines = text.splitlines()
        user_set = False
        has_healthcheck = False
        for n, raw in enumerate(lines, 1):
            line = raw.strip()
            up = line.upper()
            if up.startswith("FROM "):
                image = line.split()[1] if len(line.split()) > 1 else ""
                if image.lower() != "scratch" and ("@sha256:" not in image):
                    tag = image.split(":", 1)[1] if ":" in image else ""
                    if not tag or tag == "latest":
                        findings.append(_finding("medium", "docker-unpinned-base", f"Base image {image!r} has no pinned tag.", str(f), n))
            elif up.startswith("USER "):
                user_set = line.split(None, 1)[1].strip().lower() not in ("root", "0")
            elif up.startswith("HEALTHCHECK"):
                has_healthcheck = True
            elif up.startswith("ADD ") and not re.search(r"\.(tar|tgz|gz|xz|bz2)\b", line):
                findings.append(_finding("low", "docker-add-vs-copy", "Prefer COPY over ADD unless you need archive extraction.", str(f), n))
            if re.search(r"(AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|PASSWORD|API_KEY)\s*=\s*\S+", line) and up.startswith(("ENV ", "ARG ")):
                findings.append(_finding("high", "docker-secret-in-image", "Secret-like value set in ENV/ARG ends up in image layers.", str(f), n))
            if re.search(r"curl[^|]*\|\s*(sudo\s+)?(ba)?sh", line):
                findings.append(_finding("medium", "docker-curl-pipe-shell", "Piping a download into a shell is hard to verify.", str(f), n))
        if not user_set:
            findings.append(_finding("medium", "docker-runs-as-root", "No non-root USER set; the container runs as root.", str(f)))
        if not has_healthcheck:
            findings.append(_finding("low", "docker-no-healthcheck", "No HEALTHCHECK (ECS/EKS may define probes elsewhere).", str(f)))
    return _summary(findings, len(files))


# --------------------------------------------------------------- CI/CD files
def review_cicd(path: str) -> dict[str, Any]:
    """Review GitHub Actions workflows and Jenkinsfiles."""
    try:
        files = _files(path, ("*.yml", "*.yaml", "Jenkinsfile", "Jenkinsfile.*"))
    except FileNotFoundError as exc:
        return {"success": False, "error": str(exc)}
    files = [f for f in files if ".github" in f.parts and "workflows" in f.parts or f.name.startswith("Jenkinsfile")]
    findings: list[dict[str, Any]] = []
    for f in files:
        text = _read(f)
        where = str(f)
        if f.name.startswith("Jenkinsfile"):
            if re.search(r"AKIA[0-9A-Z]{16}|aws_secret_access_key", text, re.I):
                findings.append(_finding("high", "jenkins-hardcoded-aws", "AWS credential-like text pattern found; actual credential validity/exposure is not verified. Review secret handling separately.", where))
            if re.search(r"terraform\s+apply[^\n]*-auto-approve", text):
                findings.append(_finding("medium", "jenkins-auto-apply", "terraform apply -auto-approve text pattern found. A textual input substring or input step does not establish an effective approval gate or its authorized approvers.", where))
            continue
        for n, line in enumerate(text.splitlines(), 1):
            m = re.search(r"uses:\s*([\w./-]+)@([\w.-]+)", line)
            if m and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)) and not m.group(1).startswith("./"):
                findings.append(_finding("medium", "gha-unpinned-action", "uses reference is not a full lower-case 40-hex commit SHA text pattern. First-party actions are not exempt. Verify action origin and selected revision; a SHA alone does not establish trust.", where, n))
            if "pull_request_target" in line:
                findings.append(_finding("high", "gha-pull-request-target", "pull_request_target text pattern found. This event can expose privileged token/secrets depending on configuration; do not execute untrusted PR code in a privileged context. Actual event, checkout, access and code flow are not verified.", where, n))
            if re.search(r"AKIA[0-9A-Z]{16}", line):
                findings.append(_finding("high", "gha-hardcoded-aws", "AWS access-key-like text pattern found; actual credential validity/exposure is not verified.", where, n))
            if re.search(r"terraform\s+apply[^\n]*-auto-approve", line):
                findings.append(_finding("medium", "gha-auto-apply", "terraform apply -auto-approve text pattern found. Verify a separately enforced approval gate and authorized reviewers; this scan does not verify environment protection or effective execution flow.", where, n))
        if "permissions:" not in text:
            findings.append(_finding("medium", "gha-no-permissions", "No permissions text marker found. Effective token permissions depend on workflow/job settings and repository/organization/event policy; they are not verified.", where))
        if "aws-actions/configure-aws-credentials" in text and "role-to-assume" not in text:
            findings.append(_finding("medium", "gha-static-aws-keys", "AWS credentials-action text without a role-to-assume marker. Credential source, OIDC trust, role permissions and effective authentication are not verified.", where))
    result = _summary(findings, len(files))
    result.update({"workflow_schema_validated": False, "effective_permissions_verified": False,
                   "approval_gates_verified": False, "secret_exposure_verified": False,
                   "execution_security_verified": False,
                   "limits": "Text-pattern review only, never a complete security scan or proof of safety. Comments, strings, malformed YAML/Groovy, incorrect indentation and unrelated jobs/stages can match or hide patterns. No YAML/Groovy parse, expression evaluation, trigger/checkout association, reusable workflow/composite action/shared library expansion, external action trust verification or live settings check. Marker presence does not establish correct scope, approval enforcement, OIDC trust or effective token/secrets access. No findings is never secure/approved/complete. Existing reader returns at most 200 candidate files before workflow filtering; traversal/symlink/concurrent swaps are not sandboxed, and unreadable/oversized files can fail. Source paths remain in output; raw action refs and matching line contents are omitted. No Jenkins/GitHub API, build/test/scan command, artifact upload, deploy, staging check, production monitor, rollback or payment performed."})
    return result
