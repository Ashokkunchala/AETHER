"""Offline correlation of supplied incident evidence, never live investigation or action.

Accepts caller-normalized evidence records (schema aether.incident-evidence.v1),
produces a deterministic timeline, corroboration groups and correlation-only
candidate explanations. No restarts, rollbacks, deployments, provider calls or
root-cause verdicts: every remediation stays approval-gated at run time.
"""
from __future__ import annotations

from datetime import timedelta

from aether.devops.incident_durations import _instant

SCHEMA = 'aether.incident-evidence.v1'
SOURCES = ['https://sre.google/sre-book/managing-incidents/',
           'https://sre.google/workbook/incident-response/']
MAX_ITEMS = 200
MAX_SUMMARY = 500
KINDS = {'log_signal', 'metric_signal', 'deploy_event', 'endpoint_signal', 'config_note'}
SEVERITIES = {'info', 'warning', 'critical'}
CORRELATION_WINDOW = timedelta(minutes=30)

# Conservative keyword -> candidate label mappings. A match is a pointer for a
# human to verify, never a diagnosis.
SIGNATURES = [
    (('oomkilled', 'out of memory', 'oom '), 'memory_exhaustion_signal', 'node-high-memory'),
    (('connection refused', 'connection reset', 'no route to host', 'dns'), 'dependency_connectivity_signal', 'alb-5xx'),
    (('accessdenied', 'access denied', 'unauthorizedoperation', 'expiredtoken'), 'permissions_or_credentials_signal', 'iam-access-denied'),
    (('imagepull', 'errimagepull', 'cannotpullcontainer'), 'image_pull_signal', 'eks-pod-crashloop'),
    (('crashloop', 'restart'), 'workload_restart_signal', 'eks-pod-crashloop'),
    (('state lock', 'statelock'), 'terraform_state_lock_signal', 'terraform-state-lock'),
]
ERROR_WORDS = ('500', '502', '503', '504', '5xx', 'error', 'exception', 'traceback', 'failed', 'timeout')


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 and c not in '\n' for c in value):
        raise ValueError(f'{label} must be nonempty bounded text of at most {limit} characters without controls.')
    return value.strip()


def review_incident_evidence(schema_version, service, evidence, as_of):
    if schema_version != SCHEMA:
        raise ValueError(f'Use schema_version {SCHEMA}; not raw provider, log or metric exports.')
    service = _text(service, 'service', 120)
    cutoff = _instant(as_of)
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_ITEMS:
        raise ValueError(f'Supply 1-{MAX_ITEMS} normalized evidence records.')
    rows = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or set(item) != {'kind', 'scope_key', 'observed_at', 'summary', 'severity'}:
            raise ValueError('Each record supports exactly kind, scope_key, observed_at, summary and severity.')
        kind = item['kind']
        if kind not in KINDS:
            raise ValueError(f'kind must be one of {sorted(KINDS)}.')
        severity = item['severity']
        if severity not in SEVERITIES:
            raise ValueError(f'severity must be one of {sorted(SEVERITIES)}.')
        scope = _text(item['scope_key'], 'scope_key', 200)
        summary = _text(item['summary'], 'summary', MAX_SUMMARY)
        observed = _instant(item['observed_at'])
        if observed > cutoff:
            raise ValueError('observed_at must not be after as_of.')
        rows.append({'index': index, 'kind': kind, 'scope_key': scope, 'observed_at': observed,
                     'severity': severity, 'summary': summary})
    ordered = sorted(rows, key=lambda row: (row['observed_at'], row['index']))
    timeline = [{'index': row['index'], 'kind': row['kind'], 'scope_key': row['scope_key'],
                 'observed_at_utc': row['observed_at'].isoformat(), 'severity': row['severity'],
                 'summary': row['summary']} for row in ordered]

    # Corroboration: scopes observed through more than one kind of signal.
    kinds_by_scope = {}
    for row in rows:
        kinds_by_scope.setdefault(row['scope_key'], set()).add(row['kind'])
    corroborated = sorted(scope for scope, kinds in kinds_by_scope.items() if len(kinds) >= 2)

    # Candidate explanations: keyword signatures plus deploy/error time correlation.
    candidates = []
    seen_labels = set()
    for row in ordered:
        lowered = row['summary'].lower()
        for words, label, runbook in SIGNATURES:
            if label not in seen_labels and any(word in lowered for word in words):
                seen_labels.add(label)
                candidates.append({'label': label, 'confidence': 'keyword_match_only',
                                   'supporting_evidence': [row['index']], 'runbook': runbook})
    deploys = [row for row in ordered if row['kind'] == 'deploy_event']
    errors = [row for row in ordered if row['severity'] == 'critical' or
              (row['kind'] in ('log_signal', 'metric_signal', 'endpoint_signal') and
               any(word in row['summary'].lower() for word in ERROR_WORDS))]
    for deploy in deploys:
        correlated = [row for row in errors
                      if row['scope_key'] == deploy['scope_key'] and
                      deploy['observed_at'] <= row['observed_at'] <= deploy['observed_at'] + CORRELATION_WINDOW]
        if correlated and 'recent_change_correlated' not in seen_labels:
            seen_labels.add('recent_change_correlated')
            candidates.append({'label': 'recent_change_correlated',
                               'confidence': 'time_correlation_only_not_causation',
                               'supporting_evidence': [deploy['index']] + [row['index'] for row in correlated[:5]],
                               'runbook': 'deploy-rollback-decision'})
    if not candidates:
        candidates.append({'label': 'no_candidate_from_supplied_evidence', 'confidence': 'none',
                           'supporting_evidence': [], 'runbook': 'api-5xx-investigation'})

    impact_items = [row for row in ordered if row['severity'] == 'critical']
    missing = []
    if not deploys:
        missing.append('deploy_events')
    if not any(row['kind'] == 'metric_signal' for row in rows):
        missing.append('metric_signals')
    if not any(row['kind'] == 'log_signal' for row in rows):
        missing.append('log_signals')
    return {'service': service, 'evidence_reviewed': len(rows), 'timeline': timeline,
            'corroborated_scopes': corroborated, 'candidate_explanations': candidates,
            'critical_records': len(impact_items), 'missing_evidence_kinds': missing,
            'incident_summary_draft': {
                'status': '_Not provided - fill in before sharing._',
                'impact': f'{len(impact_items)} critical supplied record(s) for {service}; real user impact unverified.',
                'timeline_items': len(timeline),
                'next_update': '_Not provided - fill in before sharing._'},
            'remediation_options': [{'action': 'Roll back a correlated change', 'requires_explicit_approval': True},
                                    {'action': 'Restart or scale the affected workload', 'requires_explicit_approval': True},
                                    {'action': 'Collect more evidence first (logs, metrics, endpoints)', 'requires_explicit_approval': False}],
            'recommended_runbooks': sorted({c['runbook'] for c in candidates if c.get('runbook')}),
            'sources': SOURCES,
            'limits': ('Caller-normalized supplied evidence only, normalized by the caller from authorized sources. '
                       'Timeline order and time correlation never prove causation; keyword matches are pointers, not diagnoses. '
                       'No live logs, metrics, traces, endpoints, deployments or production systems were inspected. '
                       'Evidence completeness, freshness, sampling, redaction and authorization are the caller’s responsibility. '
                       'No restart, rollback, scale, deploy, page, ticket or notification is performed or scheduled; '
                       'every remediation option requires explicit run-time approval. '
                       'Summaries are echoed as supplied; do not include secrets, tokens or personal data in evidence records.')}


def register_incident_review_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_incident_evidence',
        description=('Correlate caller-normalized incident evidence (schema aether.incident-evidence.v1: log/metric/deploy/endpoint '
                     'records) into a timeline, corroborated scopes and correlation-only candidate explanations with runbook pointers. '
                     'Offline; no live investigation, no root-cause verdict, no restarts or rollbacks.'),
        parameters={'type': 'object',
                    'properties': {
                        'schema_version': {'type': 'string', 'description': 'Must be aether.incident-evidence.v1.'},
                        'service': {'type': 'string', 'description': 'Service name, at most 120 characters.'},
                        'evidence': {'type': 'array', 'description': '1-200 records with exactly kind, scope_key, observed_at (ISO with offset), summary, severity.'},
                        'as_of': {'type': 'string', 'description': 'ISO date-time cutoff; evidence must not be newer.'}},
                    'required': ['schema_version', 'service', 'evidence', 'as_of'], 'additionalProperties': False},
        handler=review_incident_evidence, risk=Risk.SAFE, category='devops'))
