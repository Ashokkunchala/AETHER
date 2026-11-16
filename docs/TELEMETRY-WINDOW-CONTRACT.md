# AETHER metric/trace window comparison contract v1

`compare_telemetry_windows(schema_version, metric_windows, trace_windows, as_of)`
is a SAFE offline comparison of supplied normalized counts. It is not a raw
OpenTelemetry/OTLP/Prometheus/provider parser, trace join, statistical-correlation
engine or live incident investigator. It retrieves no source and runs nothing.

Use schema_version `aether.telemetry-windows.v1`. This custom schema is not an
OpenTelemetry standard. Manually prepare authorized scoped summaries first.
Each metric window has exactly:

```json
{
  "scope_key": "reviewed-env-service-and-population-key",
  "source_ref": "private-reference-to-query-or-export",
  "start": "2020-01-01T00:00:00Z",
  "end": "2020-01-01T00:01:00Z",
  "coverage": "unknown",
  "eligible_requests": 100,
  "error_requests": 5
}
```

Each trace window has exactly scope_key, source_ref, start, end, coverage,
sampling, observed_spans and error_spans. For example observed_spans=300,
error_spans=10,sampling="sampled" describes observed span counts, not requests.
Coverage is complete_asserted/partial/unknown. Sampling is
sampled/unsampled_asserted/unknown. Complete/unsampled values are caller claims,
not verified coverage. No values are inferred from absent fields.

Counts are bounded integers, not booleans/floats, with
0 <= errors <= total <= 10^18. Unknown/missing fields fail. Up to 500 windows per
signal, nonblank bounded scope/source references, strict known-offset ISO
start/end/as_of with seconds and up to six fractional digits. Boundaries use
half-open [start,end), start < end <= as_of, and as_of no later than now. The
incident-duration parser supplies the strict calendar/offset checks; unknown
-00:00 and naive/sub-microsecond/leap-second values are refused.

## Pairing is a caller assertion, not a diagnosis

The tool pairs only exactly equal scope_key and UTC-normalized start/end.
Different boundaries/scopes stay unpaired with input indices. No fuzzy match,
rebinning, interpolation, gap fill, default values or population alignment.
Duplicate or overlapping windows within one signal/scope fail instead of
silently double counting. Adjacent windows or distinct scopes are allowed.
No aggregate across windows, scopes or signals is calculated.

Choose scope_key only after reviewing environment/service/population and
measurement definitions yourself. Equal strings do not prove equivalent scope,
request/error semantics, clocks or source provenance. Keep private source_ref
records with exact query, event/error definition, clock/skew notes, coverage,
sampling, measurement unit and source timestamp. The tool checks only nonblank
source_ref presence; it does not retrieve or authenticate the reference.

Both positive error counts mean supplied temporal co-occurrence only. They do
not establish statistical correlation, shared request/trace, application outage,
failed deployment, root cause or remediation. If either total is zero, the
comparison says no observations in one or both, never cross-signal agreement.
No reported errors does not mean healthy. Partial/unknown coverage and sampling
remain explicit. A request can produce many spans, and sampling changes what is
observed. Requests/spans are never divided against each other, equated, added or
extrapolated to the full population. No latency/CPU/memory anomaly baseline,
counter reset/rate/delta handling, trace tree or span-status parsing occurs.

Results retain input-local indices, paired UTC boundaries/as_of and counts;
private scope/source strings and raw attributes/spans/query/definition text are
omitted. These counts/windows can enter desktop model-backed tool chat. The
helper itself makes no model/provider/network call. No file, credential, source,
cluster, AWS account or user device is accessed or changed. No monitor, alert,
restart, deploy, rollback, remediation, payment or persistent tracking occurs.
All source/freshness/completeness/scope/population/statistical/causal/outage/root-
cause verification stays false. Existing incident/SLO/log tools remain distinct.

Synthetic tests cover exact/offset-equivalent pairs, mismatches, no data,
positive/zero counts, privacy omission, partial/asserted coverage, malformed/
missing/unknown fields, limits, duplicates/overlaps, input-local pairing, no
writes/commands and SAFE registration after stop. They test this custom contract,
not vendor export compatibility or true production correlation.

Signal concepts checked November 16, 2026:
- https://opentelemetry.io/docs/concepts/signals/traces/
- https://opentelemetry.io/docs/concepts/signals/metrics/
