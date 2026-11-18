"""Compare normalized supplied metric/trace windows, never infer causality."""
from __future__ import annotations

from aether.devops.incident_durations import _instant

SOURCES = ['https://opentelemetry.io/docs/concepts/signals/traces/',
           'https://opentelemetry.io/docs/concepts/signals/metrics/']


def _identifier(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 200 or value != value.strip():
        raise ValueError('scope_key and source_ref must be explicit nonblank bounded text without outer whitespace.')
    return value


def _windows(values, kind, cutoff):
    if not isinstance(values, list) or len(values) > 500:
        raise ValueError('Supply at most 500 windows per signal.')
    rows, seen = [], set()
    count_fields = ('eligible_requests', 'error_requests') if kind == 'metric' else ('observed_spans', 'error_spans')
    allowed = {'scope_key', 'source_ref', 'start', 'end', 'coverage', *count_fields}
    if kind == 'trace':
        allowed.add('sampling')
    for index, value in enumerate(values):
        if not isinstance(value, dict) or set(value) != allowed:
            raise ValueError('Supply exactly the documented normalized fields; missing/unknown fields are refused.')
        scope = _identifier(value['scope_key'])
        _identifier(value['source_ref'])
        start, end = _instant(value['start']), _instant(value['end'])
        if not start < end <= cutoff:
            raise ValueError('Window boundaries require start < end <= as_of.')
        coverage = value['coverage']
        if coverage not in ('complete_asserted', 'partial', 'unknown'):
            raise ValueError('coverage must be complete_asserted, partial or unknown.')
        if kind == 'trace' and value['sampling'] not in ('sampled', 'unsampled_asserted', 'unknown'):
            raise ValueError('sampling must be sampled, unsampled_asserted or unknown.')
        total, errors = (value[field] for field in count_fields)
        if type(total) is not int or type(errors) is not int or not 0 <= errors <= total <= 10**18:
            raise ValueError('Counts require integers 0 <= errors <= total <= 10^18.')
        key = (scope, start, end)
        if key in seen:
            raise ValueError('Duplicate scope/window per signal is ambiguous.')
        seen.add(key)
        rows.append({'key': key, 'index': index, 'coverage': coverage, 'total': total, 'errors': errors,
                     'sampling': value.get('sampling')})
    by_scope = {}
    for row in rows:
        by_scope.setdefault(row['key'][0], []).append(row)
    for scoped in by_scope.values():
        ordered = sorted(scoped, key=lambda row: row['key'][1])
        if any(b['key'][1] < a['key'][2] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Overlapping windows within one signal/scope are ambiguous; normalize first.')
    return rows


def compare_telemetry_windows(schema_version, metric_windows, trace_windows, as_of):
    if schema_version != 'aether.telemetry-windows.v1':
        raise ValueError('Use schema_version aether.telemetry-windows.v1; not raw OTLP/Prometheus/provider JSON.')
    cutoff = _instant(as_of)
    from datetime import UTC, datetime
    if cutoff > datetime.now(UTC):
        raise ValueError('as_of cannot be in the future.')
    metrics = _windows(metric_windows, 'metric', cutoff)
    traces = _windows(trace_windows, 'trace', cutoff)
    trace_by_key = {row['key']: row for row in traces}
    matches, used = [], set()
    for metric in metrics:
        trace = trace_by_key.get(metric['key'])
        if trace is None:
            continue
        used.add(trace['index'])
        signal = ('no_observations_in_one_or_both' if not metric['total'] or not trace['total'] else
                  'error_counts_reported_in_both' if metric['errors'] and trace['errors'] else
                  'error_counts_reported_in_one_only' if metric['errors'] or trace['errors'] else
                  'no_errors_reported_in_either')
        matches.append({'metric_index': metric['index'], 'trace_index': trace['index'],
                        'start_utc': metric['key'][1].isoformat(), 'end_utc': metric['key'][2].isoformat(),
                        'eligible_requests': metric['total'], 'error_requests': metric['errors'],
                        'observed_spans': trace['total'], 'error_spans': trace['errors'],
                        'metric_coverage_reported': metric['coverage'], 'trace_coverage_reported': trace['coverage'],
                        'trace_sampling_reported': trace['sampling'], 'temporal_comparison': signal,
                        'scope_equivalence_verified': False, 'population_equivalence_verified': False,
                        'statistical_correlation_verified': False, 'causal_relationship_verified': False})
    paired_metrics = {row['metric_index'] for row in matches}
    return {'schema_version': schema_version, 'as_of_utc': cutoff.isoformat(),
            'metric_windows_reviewed': len(metrics), 'trace_windows_reviewed': len(traces),
            'exact_scope_window_pairs': len(matches), 'pairs': matches,
            'unpaired_metric_indices': [r['index'] for r in metrics if r['index'] not in paired_metrics],
            'unpaired_trace_indices': [r['index'] for r in traces if r['index'] not in used],
            'status': 'supplied_exact_window_comparison' if matches else 'no_exact_pairs',
            'source_provenance_verified': False, 'snapshot_freshness_verified': False,
            'inventory_completeness_verified': False, 'outage_verified': False,
            'root_cause_verified': False, 'monitor_started': False, 'sources': SOURCES.copy(),
            'limits': ('Custom normalized schema only, not OTLP/Prometheus ingestion, source retrieval, metric/trace join or live monitoring. '
                       'scope_key equality and exactly equal UTC half-open [start,end) boundaries select pairs; source identity, query, event/error definition, units, clock accuracy, coverage and equivalent population are caller assertions, never verified. '
                       'Requests and spans differ: a request can have many spans; sampled spans and request counts are never added, divided against each other, deduplicated or equated. '
                       'Both error counts positive means supplied temporal co-occurrence only, not statistical correlation, shared request, outage, root cause or failed deployment. '
                       'No observations in either signal means no cross-signal conclusion, even if the other reports errors; no reported errors never proves healthy. '
                       'Partial/unknown coverage and sampling remain explicit; complete/unsampled are assertions, not proof. '
                       'Different scope/boundaries stay unpaired; no rebinning/interpolation, fuzzy matching, gap filling, unit conversion, cumulative counter/rate/delta reset handling or extrapolation. '
                       'No CPU/memory baseline, anomaly threshold, trace tree/status interpretation, logs, deployment attribution, SLO/SLA, alert or remediation. '
                       'Overlapping windows within signal/scope refused, not deduplicated. No source_ref/scope_key/raw attributes/spans/query/definition text echoed; input indices are local, not stable identifiers. '
                       'Counts/paired UTC windows/as_of remain in results and can enter desktop model-backed chat; parser itself makes no model/network/provider call. '
                       'No file write, subscription, credential/cluster/AWS/device access, restart, deploy, rollback or payment.')}


def register_telemetry_window_tools(registry):
    from aether.tools.registry import Risk, Tool
    common = {'scope_key': {'type': 'string', 'description': 'Caller-defined environment/service/population key, exact equality only.'},
              'source_ref': {'type': 'string', 'description': 'Private local reference to query/export evidence; never fetched.'},
              'start': {'type': 'string'}, 'end': {'type': 'string'},
              'coverage': {'type': 'string', 'enum': ['complete_asserted', 'partial', 'unknown']}}
    metric_fields = {**common, 'eligible_requests': {'type': 'integer'}, 'error_requests': {'type': 'integer'}}
    trace_fields = {**common, 'observed_spans': {'type': 'integer'}, 'error_spans': {'type': 'integer'},
                    'sampling': {'type': 'string', 'enum': ['sampled', 'unsampled_asserted', 'unknown']}}
    registry.register(Tool(
        name='compare_telemetry_windows',
        description='Compare supplied custom normalized request-metric and span-count windows for exact caller-scope/time alignment. Temporal co-occurrence only, never statistical correlation/causality/outage proof or live monitoring. No raw OTLP/provider parsing or source access.',
        parameters={'type': 'object', 'properties': {
            'schema_version': {'type': 'string', 'enum': ['aether.telemetry-windows.v1']},
            'metric_windows': {'type': 'array', 'maxItems': 500, 'items': {'type': 'object', 'properties': metric_fields, 'required': list(metric_fields), 'additionalProperties': False}, 'description': 'Exact fields scope_key,source_ref,start,end,coverage,eligible_requests,error_requests. Scoped nonoverlapping half-open windows.'},
            'trace_windows': {'type': 'array', 'maxItems': 500, 'items': {'type': 'object', 'properties': trace_fields, 'required': list(trace_fields), 'additionalProperties': False}, 'description': 'Exact fields scope_key,source_ref,start,end,coverage,sampling,observed_spans,error_spans.'},
            'as_of': {'type': 'string', 'description': 'Explicit known-offset ISO time with seconds, no later than now.'}},
            'required': ['schema_version', 'metric_windows', 'trace_windows', 'as_of'], 'additionalProperties': False},
        handler=compare_telemetry_windows, risk=Risk.SAFE, category='devops'))
