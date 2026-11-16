"""Offline arithmetic for supplied incident boundaries, never tracking/monitoring."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, localcontext

SOURCE = 'https://www.atlassian.com/incident-management/kpis/common-metrics'
_TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})')


def _instant(value):
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        raise ValueError('Use ISO date-time with seconds and explicit Z/offset, at most six fractional digits.')
    # Offset component ranges are checked separately: fromisoformat normalizes +01:60.
    if value.endswith('-00:00'):
        raise ValueError('Unknown-local-offset -00:00 is not accepted; supply a known offset.')
    if value[-1] != 'Z' and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError('Invalid UTC offset.')
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise ValueError('Invalid calendar time or UTC conversion overflow.') from exc


def review_incident_durations(incidents, boundary_definition, as_of):
    if not isinstance(boundary_definition, str) or not 20 <= len(boundary_definition.strip()) <= 500:
        raise ValueError('Explicitly define what start/end mean for this cohort, in 20-500 characters.')
    cutoff = _instant(as_of)
    if cutoff > datetime.now(UTC):
        raise ValueError('as_of must not be in the future.')
    if not isinstance(incidents, list) or len(incidents) > 1000:
        raise ValueError('Supply at most 1000 incident records.')
    seen, rows, durations = set(), [], []
    for index, incident in enumerate(incidents):
        if not isinstance(incident, dict) or set(incident) - {'id', 'state', 'start', 'end'}:
            raise ValueError('Each record supports only id, state, start and end.')
        identity, state = incident.get('id'), incident.get('state')
        if not isinstance(identity, str) or not 1 <= len(identity.strip()) <= 128 or identity != identity.strip() or identity in seen:
            raise ValueError('Incident IDs must be unique nonblank bounded strings without outer whitespace.')
        seen.add(identity)
        if state not in ('completed', 'open'):
            raise ValueError('Every record requires explicit state completed or open.')
        start = _instant(incident.get('start'))
        if start > cutoff:
            raise ValueError('Incident starts must be no later than as_of.')
        microseconds = None
        if state == 'completed':
            end = _instant(incident.get('end'))
            if end < start or end > cutoff:
                raise ValueError('Completed boundaries require start <= end <= as_of.')
            delta = end - start
            microseconds = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
            durations.append(microseconds)
        elif incident.get('end') is not None:
            raise ValueError('Open incidents must not have a completed end time.')
        rows.append({'incident_index': index, 'reported_state': state,
                     'duration_microseconds': microseconds,
                     'included_in_completed_mean': state == 'completed'})
    ordered = sorted(durations)
    total, count = sum(durations), len(durations)
    with localcontext() as ctx:
        ctx.prec = 60
        mean = format(Decimal(total) / count / 1_000_000, 'f') if count else None
        median = (Decimal(ordered[count//2]) if count % 2 else
                  Decimal(ordered[count//2-1] + ordered[count//2]) / 2) if count else None
        median_seconds = format(median / 1_000_000, 'f') if median is not None else None
    return {'records_reviewed': len(rows), 'completed_records': count, 'open_records_excluded': len(rows)-count,
            'status': 'completed_records_only' if count else 'no_completed_data',
            'boundary_definition_asserted': True, 'boundary_definition_verified': False,
            'boundary_definition_text_omitted': True, 'as_of_utc': cutoff.isoformat(),
            'total_completed_duration_microseconds': total,
            'mean_seconds': mean, 'median_seconds': median_seconds,
            'mean_exact_fraction_seconds': {'numerator': total, 'denominator': count*1_000_000} if count else None,
            'min_duration_microseconds': min(durations) if count else None,
            'max_duration_microseconds': max(durations) if count else None,
            'incidents': rows, 'source': SOURCE,
            'inventory_completeness_verified': False, 'measurement_boundaries_verified': False,
            'outage_duration_verified': False, 'incident_tracking_started': False,
            'limits': ('Arithmetic over supplied completed start/end pairs only. Caller must define identical start/end semantics and cohort; the free-form definition is not validated or echoed. '
                       'MTTR may mean repair/recovery/response/resolution; this tool labels only generic completed durations, not a standardized/DORA metric. '
                       'Open incidents are counted/excluded, never zero or completed; completed-only mean is subject to censoring/selection bias. '
                       'Distinct IDs need not be distinct real incidents; overlaps are allowed and not merged. Sum is incident-duration sum, not total service downtime or uptime/SLA. '
                       'No full reporting-window coverage, source clock accuracy/skew, event identity, impact, scope, freshness, causality, detection lag or recovery verification. '
                       'Zero duration is supplied equal boundaries, not instantaneous recovery proof. No completed rows means no data, not zero mean. '
                       'UTC normalization handles supplied offsets only, no inferred timezone/DST or leap-second support. Max six fractional digits avoids silent precision loss. '
                       'Integer microsecond totals and mean fraction are exact; mean decimal is rounded to 60 significant-digit arithmetic where needed. '
                       'IDs and raw boundary-definition text omitted; input-local indices are not persistent incident IDs. '
                       'No persistence/tracking/history, trend/percentile, alert, live logs/metrics/traces, root-cause/remediation, provider/network/model call, file write or production action.')}


def register_incident_duration_tools(registry):
    from jarvis.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_incident_durations',
        description='Offline duration arithmetic from supplied completed/open incident boundaries and explicit boundary definition/as-of time. Completed-only mean/median, open excluded. No tracking, outage verification, monitoring or production action. IDs/definition text omitted.',
        parameters={'type': 'object', 'properties': {
            'incidents': {'type': 'array', 'maxItems': 1000, 'items': {'type': 'object', 'properties': {'id': {'type': 'string'}, 'state': {'type': 'string', 'enum': ['open', 'completed']}, 'start': {'type': 'string'}, 'end': {'type': ['string', 'null']}}, 'required': ['id', 'state', 'start'], 'additionalProperties': False}},
            'boundary_definition': {'type': 'string', 'minLength': 20, 'maxLength': 500, 'description': 'Define identical start/end meaning and cohort, not private context.'},
            'as_of': {'type': 'string', 'description': 'Explicit ISO time with seconds and Z/offset, no later than now.'}},
            'required': ['incidents', 'boundary_definition', 'as_of'], 'additionalProperties': False},
        handler=review_incident_durations, risk=Risk.SAFE, category='devops'))
