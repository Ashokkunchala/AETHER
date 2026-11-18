"""Offline, metric/unit-preserving review of supplied Cost Explorer evidence."""
from __future__ import annotations

import json
import os
import re
import stat
from datetime import date
from decimal import Decimal, InvalidOperation

SOURCE = 'https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html'
RESULT_SOURCE = 'https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_ResultByTime.html'
COST_METRICS = {'AmortizedCost', 'BlendedCost', 'NetAmortizedCost', 'NetUnblendedCost', 'UnblendedCost'}
OTHER_METRICS = {'NormalizedUsageAmount', 'UsageQuantity'}
MAX_BYTES = 2_000_000


def _day(value):
    if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
        raise ValueError('Each cost period requires YYYY-MM-DD Start and End dates.')
    return date.fromisoformat(value)


def _metrics(value):
    if not isinstance(value, dict) or len(value) > 7:
        raise ValueError('Metrics must be an object with at most seven supported metric names.')
    result = []
    for name, item in sorted(value.items()):
        if name not in COST_METRICS | OTHER_METRICS or not isinstance(item, dict):
            raise ValueError('Unsupported cost/usage metric or invalid metric object.')
        amount, unit = item.get('Amount'), item.get('Unit')
        if not isinstance(amount, str) or len(amount) > 80 or re.fullmatch(r'-?\d+(?:\.\d+)?', amount) is None:
            raise ValueError('Metric Amount must be a bounded finite decimal string, including a possible negative credit.')
        try:
            number = Decimal(amount)
        except InvalidOperation as exc:
            raise ValueError('Invalid metric amount.') from exc
        if not number.is_finite() or not isinstance(unit, str) or re.fullmatch(r'[A-Za-z0-9_./% -]{1,40}', unit) is None:
            raise ValueError('Metric requires a finite amount and supported unit text.')
        cost = name in COST_METRICS
        result.append({'metric': name, 'reported_amount': str(number), 'reported_unit': unit,
                       'kind': 'cost' if cost else 'usage_not_money',
                       'notice': ('Reported cost metric, not a final invoice.' if cost else
                                  'Usage quantity, never money. Mixed usage units can make aggregation meaningless; scope by usage type.')})
    return result


def review_costs(document):
    if not isinstance(document, dict) or not isinstance(document.get('ResultsByTime'), list):
        raise ValueError('Supply a get-cost-and-usage JSON object with ResultsByTime.')
    periods = document['ResultsByTime']
    if len(periods) > 366:
        raise ValueError('Scope the supplied report to at most 366 periods.')
    token = document.get('NextPageToken')
    if token is not None and (not isinstance(token, str) or len(token) > 8192):
        raise ValueError('NextPageToken must be bounded text or null.')
    definitions = document.get('GroupDefinitions', [])
    if not isinstance(definitions, list) or len(definitions) > 2:
        raise ValueError('GroupDefinitions must be a list of at most two definitions.')
    for definition in definitions:
        if not isinstance(definition, dict) or not isinstance(definition.get('Type'), str) or not isinstance(definition.get('Key'), str):
            raise ValueError('Each group definition requires Type and Key text.')
    output, intervals, group_total = [], [], 0
    for period in periods:
        if not isinstance(period, dict) or not isinstance(period.get('TimePeriod'), dict):
            raise ValueError('Each period requires a TimePeriod object.')
        start, end = (_day(period['TimePeriod'].get(k)) for k in ('Start', 'End'))
        if start >= end:
            raise ValueError('Cost periods use inclusive Start and exclusive End with Start before End.')
        intervals.append((start, end))
        estimated = period.get('Estimated')
        if 'Estimated' in period and type(estimated) is not bool:
            raise ValueError('Estimated must be a boolean when supplied.')
        total_present, groups_present = 'Total' in period, 'Groups' in period
        total = _metrics(period['Total']) if total_present else []
        groups = period.get('Groups', [])
        if not isinstance(groups, list) or len(groups) > 1000:
            raise ValueError('Groups must be a list with at most 1000 groups per period.')
        group_total += len(groups)
        if group_total > 1000:
            raise ValueError('Scope the snapshot to at most 1000 groups across all periods.')
        seen, group_rows = set(), []
        for index, group in enumerate(groups):
            if not isinstance(group, dict) or not isinstance(group.get('Keys'), list):
                raise ValueError('Every group requires a Keys array.')
            keys = group['Keys']
            if not 1 <= len(keys) <= 2 or any(not isinstance(key, str) or len(key) > 1024 for key in keys):
                raise ValueError('Each group requires one or two bounded text keys.')
            if definitions and len(keys) != len(definitions):
                raise ValueError('Group key count must match the supplied definitions.')
            identity = tuple(keys)
            if identity in seen:
                raise ValueError('Duplicate group keys within a period are ambiguous.')
            seen.add(identity)
            metrics = _metrics(group.get('Metrics'))
            if not metrics:
                raise ValueError('Each supplied group requires at least one metric.')
            # Values may be tags/account identifiers or malicious text. Omit them.
            group_rows.append({'group_index': index, 'metrics': metrics})
        if not total and not groups:
            raise ValueError('Each period must contain at least one supplied total metric or group. Missing data is not zero.')
        output.append({'start_inclusive': start.isoformat(), 'end_exclusive': end.isoformat(),
                       'reported_estimated': estimated,
                       'estimate_status': 'estimated' if estimated is True else 'reported_not_estimated' if estimated is False else 'unknown',
                       'total_field_present': total_present, 'reported_totals': total,
                       'groups_field_present': groups_present, 'groups_in_snapshot': len(groups),
                       'groups': group_rows[:20], 'group_output_truncated': len(group_rows) > 20,
                       'group_identity_notice': 'Keys/definition values omitted; group indices refer only to this period in the supplied file. No service/account attribution inferred.'})
    ordered = sorted(intervals)
    if any(current[0] < previous[1] for previous, current in zip(ordered, ordered[1:])):
        raise ValueError('Duplicate or overlapping periods are ambiguous; supply one consistent scoped query result.')
    gaps = any(current[0] > previous[1] for previous, current in zip(ordered, ordered[1:]))
    return {'periods_reviewed': len(output), 'periods': output,
            'groups_in_snapshot': group_total, 'gaps_between_periods': gaps,
            'pagination_token_present': bool(token), 'group_definition_count': len(definitions),
            'inventory_completeness_verified': False, 'query_scope_verified': False,
            'snapshot_freshness_verified': False, 'amounts_independently_verified': False,
            'source': SOURCE, 'result_source': RESULT_SOURCE,
            'limits': ('Supplied cost/usage snapshot only, not a live billing report, final invoice, forecast, anomaly/root-cause analysis or savings estimate. '
                       'No sum across periods, groups, metrics or units is computed. Costs retain their separate metric/unit labels; usage quantities are never money. '
                       'Negative values are preserved, not clamped. Empty/missing totals are not zero; group amounts are not silently substituted for account totals. '
                       'A false Estimated flag is only the supplied flag, not final billing proof. Missing pagination token does not prove all pages, accounts, regions, filters or query scope. '
                       'Group keys, tag/account/service attribution and dimension attributes are omitted. Group lists above 20 are explicitly truncated; all supplied groups up to the limit are validated. '
                       'No AWS/Cost Explorer request, billed API call, SDK/CLI command, secret access, alert, change or deployment is performed.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_costs_export(path):
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json get-cost-and-usage export.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('Cost export must be regular and no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_costs(document)


def register_cost_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_cost_explorer', description='Review an existing Cost Explorer get-cost-and-usage JSON export without billed API access. Keep reported periods, cost/usage metrics, units and estimated flags separate; no final invoice, root cause, attribution or savings claim. Group keys omitted.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 JSON, max 2 MB/366 periods/1000 groups. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_costs_export, risk=Risk.SAFE, category='devops'))
