# Proactive AETHER: trigger map and boundaries

Part 8 of the AETHER spec: AETHER works without waiting for commands. This page
maps every requested trigger to what exists, what this change adds, and the
honest limits.

Standing rules: proactive means detect, record and recommend. No auto-cleanup,
no auto-delete, no auto-kill, no auto-send, no remediation. Every check is
opt-in (rules are created disabled), the inbox is local-only, and three user
switches govern noise: `proactive_set_paused` turns all resource checks off,
`proactive_quiet_hours` flags alerts raised inside a chosen window instead of
making noise, and `proactive_set_throttle` caps repeat trigger alerts per
metric. `proactive_switches` shows the current state.

## Trigger map

| Trigger | AETHER action | Status | Where |
| --- | --- | --- | --- |
| Morning | Prepare daily briefing | Exists, opt-in | `aether/briefing_schedule.py`: saved explicit schedules run from the backend scheduler tick |
| Low laptop battery | Alert you | Exists, opt-in | `proactive_configure('battery', ...)` with hysteresis; local alert inbox |
| High CPU usage | Identify the process | Added | CPU alerts now attach a bounded instantaneous top-process sample (`proactive_cpu_offenders`); a sample is labeled not proof of cause |
| Disk almost full | Find large files and recommend cleanup | Added, bounded | Disk alert exists; `proactive_disk_large_files` lists the largest files under one chosen directory, read-only. It never deletes and never recommends a specific file for deletion; review is yours |
| Failed GitHub workflow | Notify and analyze failure | Notify exists; analysis bounded | Signed webhook -> local inbox (`app/github_alerts.py`, opt-in, read-only). The signed payload carries no job logs, so root-cause analysis means pasting the run log into the existing log triage/incident reviewers; documented, not faked |
| AWS cost spike | Investigate cost increase | Added, offline | `proactive_cost_spike_review`: arithmetic over caller-supplied previous/current per-service USD (from the existing read-only Cost Explorer snapshot on approval). Never calls AWS; a delta names where to look, not why |
| Security vulnerability | Alert and recommend remediation | Exists | `aether/security_scans.py` and the dependency/config reviewers; recommendations are runbook pointers, never auto-applied |
| Missed learning session | Suggest rescheduling | Partial, documented | Mentor tracks and saved schedules exist; automatic missed-session detection is not built (needs an attendance signal), so rescheduling is one ask away, not pushed |
| Upcoming interview | Prepare revision material | Partial, documented | Mentor review tracks + work-category memories are the material; no automatic interview detection exists |
| New email | Summarize important messages | Partial, documented | Read-only Gmail access exists (docs/GMAIL-READONLY.md); proactive summarization of new mail is not built (needs a poll/push collector), ask AETHER any time |
| Important deadline | Send reminders | Exists | Reminders with due notifications on laptop and paired phone |
| Application crash | Capture logs and diagnose | Added, bounded | `proactive_crash_log_review`: heuristic error-line grouping and candidate pointers over supplied log text. It reads no files or event logs by itself and never claims a diagnosis |

## Noise and control

- Crossing-only recording with two-point hysteresis: a metric flapping around a
  threshold produces one trigger and one recovery, not a stream.
- Throttle (0-3600s) suppresses repeat trigger records per metric; recoveries
  always record so the inbox never shows a stuck alarm.
- Quiet hours flag triggered alerts as `quiet` in the inbox; nothing is hidden
  or deleted.
- Pause stops all sampling and recording; rules and history are unchanged.
- The runner samples at most once a minute and only after explicit opt-in;
  before configuration it creates no database and reads no metrics.

## Deliberately not built

- Continuous push delivery to the phone for these alerts (the inbox and the
  paired notification path are the delivery; GitHub workflow alerts arrive
  through the signed webhook only).
- Automatic missed-session/interview/email detection: each needs a collector
  signal that does not exist yet, and each is documented instead of faked.
- Any proactive mutation: cleanup, deletion, process termination, message
  sending or remediation.

## User-defined schedules, thresholds and triggers

Every threshold, schedule and trigger is user-defined; there are no hidden
watchers. Sensible defaults means: rules start disabled, battery defaults to
"below", other metrics to "at or above", and nothing samples or records until
the user opts in.

- Thresholds. Built-in metrics (cpu, memory, disk, battery) take a percentage
  the user chooses via `proactive_configure` and are sampled about once a
  minute once enabled. Any other threshold - the requested cost limit is the
  example - is a custom metric: `proactive_configure_custom` names it, sets
  the number and the direction (above/below), and
  `proactive_record_sample` evaluates the crossing the moment the user
  supplies a figure. Custom metrics are never fetched from any provider
  automatically; AWS Cost Explorer stays read-only and approval-gated, so a
  cost figure reaches AETHER only when the user (or an approved read-only
  snapshot they ran) supplies it. Crossings use the same hysteresis (2% of
  threshold), throttle, quiet-hours and pause rules as built-in metrics;
  supplied figures stay listed (bounded) via `proactive_samples`.
- Schedules. `aether/briefing_schedule.py` already stores named daily
  briefing jobs at a chosen local time and IANA timezone, with per-job
  catchup/skip policy for missed runs, dedup per day, and full run history.
  Jobs can be listed, enabled, disabled and cancelled.
- Triggers. `aether/triggers.py` stores user-defined rules: when a runtime
  event matches a chosen category (and optional action/tool), a saved
  read-only plan runs once, bounded by a per-rule cooldown (300s-86400s).
  Rules start disabled; only read-only plans can be referenced, so a trigger
  can never start a mutating or confirmation-gated action, and approvals
  never carry into a triggered run.

The detect/notify/recommend-only rule applies to all three: no schedule,
threshold or trigger can clean up, delete, kill, spend or send anything by
itself.
