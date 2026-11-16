# AETHER offline incident-duration arithmetic

`review_incident_durations(incidents, boundary_definition, as_of)` is a SAFE
planning/evidence tool for supplied incident timestamps. It returns arithmetic,
not tracked incidents or verified MTTR. It writes nothing, keeps no history,
connects to no incident system and starts no monitoring or alert.

## Define the measurement first

MTTR can mean repair, recovery, response or resolution with different boundaries.
The tool requires a 20-500-character caller-defined start/end meaning and cohort.
It does not choose or validate that meaning, call the result a standardized/DORA
metric, or infer timestamps from log buckets. Keep a consistent definition and
population outside the tool. Free-form definition text is not echoed, only its
presence and unverified status. Do not include private incident details.

Each of at most 1000 records supports only id/state/start/end. Explicit state is
completed or open. IDs must be unique nonblank strings up to 128 characters
without outer whitespace. IDs are omitted in results; input-local indices are
not persistent incident identifiers. Distinct supplied IDs do not prove distinct
real incidents. Unknown fields fail, avoiding silent acceptance of mistyped keys.

Use exact ISO date-times with T/seconds, Z or explicit known offset and at most
six fractional digits. Naive dates, leap seconds, invalid calendar/offset values,
unknown-offset -00:00, sub-microsecond precision and UTC overflow are refused.
Offsets normalize to UTC without guessing timezone/DST. A required as_of cannot
be in the future. Start <= end <= as_of for completed records. Open records
need a start <= as_of and absent/null end. A non-null end contradicts open state.
No absent end is inferred to be now, zero, or completed.

## Read the result correctly

Completed rows only contribute to total, mean, median, minimum and maximum.
Open rows are counted/excluded, not hidden, but a completed-only cohort can be
biased by unfinished long incidents and selection. No completed rows means
no data, with null mean/median/fraction, not a zero recovery time. Equal supplied
boundaries produce zero duration, not proof of instantaneous recovery.

Integer microsecond durations/totals and the mean's numerator/denominator in
seconds are exact. Decimal mean output uses 60-significant-digit arithmetic and
can be rounded for repeating fractions; the fraction remains available. Median
can be half a microsecond. No lossy float timestamp subtraction is used.

Overlaps are allowed and never merged: total_completed_duration_microseconds
sums incident durations, not unique wall-clock downtime or an availability/SLA
measure. It must not be subtracted from a reporting window to claim uptime.
Boundary/source clock accuracy/skew, coverage, cohort completeness, incident
identity/scope/impact, real outage and recovery remain unverified. The tool does
not calculate trends, percentiles, detection lag, alert effectiveness or SLOs.
No raw start/end pairs or IDs are echoed; as_of UTC and per-input durations are
returned. Tool summaries can enter model-backed desktop chat; this helper makes
no model/network/provider call itself.

No live incident/log/metric/trace retrieval, automatic anomaly/outage detection,
root-cause/remediation, database/file write, tracking subscription, production
restart, deploy, rollback or payment occurs. Existing SLO arithmetic and
postmortem formatting remain separate tools. An incident report or mean cannot
supply permission to modify production.

Synthetic tests check completed/open separation, empty cohorts, equivalent
offsets, fractional/zero durations, exact fractions, odd/even medians, duplicates,
malformed timestamps/offsets/unknown fields, future/cutoff bounds, record limits,
no file/command effects and SAFE registration after emergency stop. No real
incident or service was accessed. These checks validate arithmetic, not supplied
facts or the user's measurement policy.

Metric definitions checked November 16, 2026:
- https://www.atlassian.com/incident-management/kpis/common-metrics
