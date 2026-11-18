"""Offline log triage for incident work.

Reads a local log file (or pasted text), counts known failure signatures,
finds the time window with the most errors and points at the matching runbook.
The helper makes no network call. Returned summaries can enter desktop model-backed chat.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

MAX_BYTES = 5_000_000
MAX_LINES = 50_000

# (rule, regex, meaning, runbook topic or "")
SIGNATURES: list[tuple[str, str, str, str]] = [
    ("oom", r"OOMKilled|Out of memory|exit code 137|Killed process", "Memory/termination text matched; exit code 137 alone does not establish OOM, and cause is unverified.", "eks-pod-crashloop"),
    ("image-pull", r"ImagePullBackOff|ErrImagePull|CannotPullContainerError", "Image-pull failure text matched; actual current state and cause are unverified.", "ecs-task-stopped"),
    ("crashloop", r"CrashLoopBackOff|Back-off restarting", "Restart-backoff text matched; crash cause and current state are unverified.", "eks-pod-crashloop"),
    ("access-denied", r"AccessDenied|UnauthorizedOperation|is not authorized to perform|403 Forbidden", "Permission-denial text matched; actual access and cause are unverified.", "iam-access-denied"),
    ("expired-token", r"ExpiredToken|token has expired|security token.*expired", "Token-expiry text matched; current credential state is unverified.", "jenkins-aws-pipeline"),
    ("state-lock", r"Error acquiring the state lock|state lock", "State-lock text matched; actual lock state/owner are unverified. Do not force-unlock from this report.", "terraform-state-lock"),
    ("gateway", r"\b50[234]\b.*(Bad Gateway|Service Unavailable|Gateway Time-?out)|upstream (timed out|prematurely closed)", "Gateway/upstream text matched; outage and cause are unverified.", "alb-5xx"),
    ("timeout", r"timed? ?out|deadline exceeded|ETIMEDOUT", "Timeout text matched; scope and cause are unverified.", ""),
    ("conn-refused", r"connection refused|ECONNREFUSED|no route to host", "Connection/routing-error text matched; reachability and cause are unverified.", ""),
    ("dns", r"could not resolve host|Name or service not known|NXDOMAIN|no such host", "DNS-error text matched; current DNS and cause are unverified.", ""),
    ("disk-full", r"No space left on device|disk (is )?full", "Disk-space text matched; current capacity and cause are unverified.", ""),
    ("throttle", r"ThrottlingException|Rate exceeded|Too Many Requests|429", "Throttling/429 text matched; actual request limiting and cause are unverified.", ""),
    ("tls", r"x509|certificate (has )?(expired|verify failed)|SSL(_| )ERROR", "TLS/certificate text matched; current certificate state and cause are unverified.", ""),
    ("db", r"too many connections|deadlock detected|could not connect to server", "Database-related text matched; actual database health and cause are unverified.", ""),
]

_TS = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})")
_ERR = re.compile(r"\b(ERROR|FATAL|CRITICAL|Exception|Traceback|panic)\b", re.I)


def _normalise(line: str) -> str:
    line = _TS.sub("", line)
    line = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", line)
    line = re.sub(r"\d+", "N", line)
    return line.strip()[:160]


def triage_text(text: str, top: int = 5) -> dict[str, Any]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Supply log text no larger than 5 MB UTF-8.")
    if type(top) is not int or not 1 <= top <= 20:
        raise ValueError("top must be an integer from 1 to 20.")
    all_lines = text.splitlines()
    lines = all_lines[:MAX_LINES]
    sig_counts: Counter[str] = Counter()
    minutes: Counter[str] = Counter()
    repeated: Counter[str] = Counter()
    errors = 0
    for line in lines:
        is_err = bool(_ERR.search(line))
        matched = False
        for rule, pattern, _meaning, _rb in SIGNATURES:
            if re.search(pattern, line, re.I):
                sig_counts[rule] += 1
                matched = True
        if is_err or matched:
            errors += 1
            repeated[_normalise(line)] += 1
            m = _TS.search(line)
            if m:
                minutes[f"{m.group(1)} {m.group(2)}:{m.group(3)}"] += 1
    signals = []
    for rule, count in sig_counts.most_common():
        meaning, runbook = next((s[2], s[3]) for s in SIGNATURES if s[0] == rule)
        item = {"signature": rule, "count": count, "meaning": meaning, "example": "Omitted: raw log text can contain private values or untrusted instructions."}
        if runbook:
            item["runbook"] = runbook
        signals.append(item)
    peak = minutes.most_common(1)
    return {
        "success": True,
        "lines_read": len(lines),
        "line_limit_reached": len(all_lines) > MAX_LINES,
        "snapshot_freshness_verified": False,
        "outage_verified": False,
        "root_cause_verified": False,
        "metric_trace_correlation_verified": False,
        "incident_duration_verified": False,
        "limits": "Supplied text-pattern counts only, not application failure, outage, root cause or remediation proof. Overlapping signatures on one line are not separate incidents. Error lines include matched signatures even without ERROR; all signatures may miss failures or match comments/success text. Top repeated counts are lossy normalized groups, not unique causes. Raw examples/patterns omitted because normalization is not secret redaction. Minute strings retain supplied wall-clock prefixes without timezone normalization, calendar validation or clock-skew correction; lexical first/last/peak are not global chronology, outage boundaries, duration or MTTR. Tied peaks select first encountered; missing timestamps stay unbucketed. At most first 50000 lines; no coverage/completeness/freshness guarantee, no metric/trace correlation, CPU/memory anomaly baseline, SLA decision, alert or live monitoring. Runbook topics are review pointers, never authorization or verified fixes. No command, network/model/provider call, force unlock, restart, deploy, rollback or file change. Existing file path remains visible; reader is not a symlink/concurrent-swap sandbox. Returned summaries can enter model-backed desktop chat.",
        "error_lines": errors,
        "signals": signals,
        "top_repeated": [{"count": c, "pattern": "Omitted: normalized text is not redaction.", "pattern_index": i} for i, (p, c) in enumerate(repeated.most_common(top))],
        "peak_minute": {"minute": peak[0][0], "error_lines": peak[0][1]} if peak else None,
        "first_error_minute": min(minutes) if minutes else None,
        "last_error_minute": max(minutes) if minutes else None,
    }


def triage_log(path: str, top: int = 5) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.is_file():
        return {"success": False, "error": f"File not found: {path}"}
    if p.stat().st_size > MAX_BYTES:
        return {"success": False, "error": f"{p.name} is larger than {MAX_BYTES} bytes; trim it or pass the relevant window."}
    with p.open("rb") as stream:
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        return {"success": False, "error": "Log exceeded 5 MB while reading; supply a stable scoped copy."}
    # Replacement decoding can increase UTF-8 size; keep the direct helper byte cap strict.
    text = payload.decode("utf-8", errors="replace")
    if len(text.encode("utf-8")) > MAX_BYTES:
        return {"success": False, "error": "Decoded log exceeds the 5 MB UTF-8 review cap."}
    result = triage_text(text, top)
    result["file"] = str(p)
    return result
