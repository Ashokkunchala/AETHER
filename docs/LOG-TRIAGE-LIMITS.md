# AETHER supplied-log pattern triage

The existing `triage_log(path, top=5)` SAFE tool reads a trusted local log copy.
`triage_text(text, top=5)` is its direct helper. Neither contacts a service,
executes commands, verifies a diagnosis, writes files or restarts anything.
Returned summaries can enter model-backed desktop tool chat; the helper itself
makes no network/model call. Use authorized, scoped local exports, not secrets.

## Evidence, not root cause

Known text signatures count memory/termination, image pulls, restart backoff,
access denial, token expiry, Terraform state locks, gateway/upstream errors,
timeouts, connection/routing errors, DNS, disk space, throttling, TLS and database
patterns. Meanings explicitly describe text matches and unverified cause/state.
Exit code 137 alone does not prove OOM: shell fatal-signal conventions and
explicit process exit values do not identify why a process terminated. Check
actual termination reasons and supporting events/metrics before diagnosing.
Even an OOMKilled text marker is supplied text, not a live verified event.

A line can match several signatures; signature counts must not be summed as
incidents. error_lines counts lines matching ERROR/FATAL/etc or any signature,
not verified failed requests. Examples/comments, negated success messages and
unrelated numeric 429 values can match. Plain HTTP 500 and many failures may be
missed. No matches does not mean healthy, available or no incident.

Raw signal examples and normalized repeated text are now omitted. Existing
example/pattern fields hold fixed omission notices; pattern_index is an input-
local rank, not a stable incident ID. Counts remain. Existing normalization
removes many numbers/IDs and truncates, so repeated groups are lossy and not
unique errors/causes. Normalization never guaranteed secret redaction. File
paths remain in tool results. No raw matching log lines are returned.

## Time and limits

Existing minute buckets deliberately remain raw wall-clock prefixes. Regex
matches YYYY-MM-DD HH:MM/T prefixes without calendar validation, timezone
normalization or clock-skew correction. Lexical first_error_minute,
last_error_minute and peak_minute are not actual incident start/end, global
chronology, MTTR or duration. Tied peaks choose first encountered; unrecognized
or missing timestamps remain unbucketed. No outage duration is calculated.

The helper accepts at most 5 MB UTF-8, uses at most the first 50000 lines and
marks line_limit_reached when more lines were supplied. top must be integer
1 through 20 in the direct helper; the legacy registry wrapper still converts
top using int(). File reads are byte-bounded, including a second cap check
while reading. Invalid UTF-8 uses replacement and can fail the decoded-byte
cap. Existing path/symlink/concurrent-rewrite behavior is not a sandbox or
stable-source guarantee; use a trusted stable local copy.

All freshness/outage/root_cause/metric_trace_correlation/incident_duration
verification flags are false. No CPU or memory usage baseline, live anomaly
or outage detection, trace correlation, incident deduplication, SLO/SLA decision,
MTTR tracking, subscription, escalation, alert or remediation occurs. Runbook
names are review pointers, not verified fixes or permission. In particular,
never force-unlock Terraform, restart production, deploy or roll back from a
signature alone. Those need scoped evidence, exact targets/effects, authority
and verified recovery under separate controls.

Existing event-ratio SLO arithmetic, supplied Deployment evidence and postmortem
formatting are separate tools. A user's report "API returns 500" is a symptom;
current authorized logs/metrics/traces, time window, scope and deployment/change
evidence must be established before likely-cause analysis. These offline helpers
do not independently gather those sources or verify a root cause.

Synthetic tests cover overlapping signals, 137 wording, omission of raw private
values, timezone/calendar limitations, no-data, caps, fixed-file/no-write behavior
and SAFE review after emergency stop. No production data or source was accessed.

Sources checked November 16, 2026:
- https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/
- https://gnu.ac.cn/software/bash/manual/html_node/Exit-Status.html (Bash manual mirror;
  primary gnu.org page could not be fetched in this check)
