"""Offline triage of supplied Security Hub / GuardDuty findings, never remediation."""
from __future__ import annotations

import json
import os
import stat
from collections import Counter

SECURITYHUB_SOURCE = 'https://docs.aws.amazon.com/cli/latest/reference/securityhub/get-findings.html'
GUARDDUTY_SOURCE = 'https://docs.aws.amazon.com/cli/latest/reference/guardduty/get-findings.html'
GUARDDUTY_SEVERITY_SOURCE = 'https://docs.aws.amazon.com/guardduty/latest/ug/guardduty_findings.html#guardduty_findings-severity'
MAX_BYTES = 2_000_000
MAX_FINDINGS = 500
SEVERITY_LABELS = {'INFORMATIONAL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}
WORKFLOW_STATES = {'NEW', 'NOTIFIED', 'SUPPRESSED', 'RESOLVED'}
RECORD_STATES = {'ACTIVE', 'ARCHIVED'}
COMPLIANCE_STATES = {'PASSED', 'WARNING', 'FAILED', 'NOT_AVAILABLE'}


def _text(value, label, limit=300):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label} must be nonempty bounded text without control characters.')
    return value


def _types(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 25:
        raise ValueError('Each finding requires 1-25 Types entries.')
    return [_text(item, 'Finding type', 200) for item in value]


def _optional_label(container, field, known, label):
    if field not in container or container[field] is None:
        return None
    value = _text(container[field], label, 100)
    return value if value in known else 'unrecognized'


def review_security_hub_findings(document):
    if not isinstance(document, dict) or not isinstance(document.get('Findings'), list):
        raise ValueError('Supply an unmodified securityhub get-findings JSON object with a Findings array.')
    findings = document['Findings']
    if len(findings) > MAX_FINDINGS:
        raise ValueError('Scope the supplied snapshot to at most 500 findings.')
    token = document.get('NextToken')
    if token is not None and not isinstance(token, str):
        raise ValueError('NextToken must be text or null.')
    severities, workflows, records, compliance = Counter(), Counter(), Counter(), Counter()
    rows = []
    for position, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError('Each finding must be an object.')
        types = _types(finding.get('Types'))
        severity = finding.get('Severity')
        if not isinstance(severity, dict):
            raise ValueError('Each finding requires its Severity object.')
        label = _optional_label(severity, 'Label', SEVERITY_LABELS, 'Severity.Label')
        if label is None:
            raise ValueError('Each finding requires its reported Severity.Label.')
        workflow = _optional_label(finding.get('Workflow') if isinstance(finding.get('Workflow'), dict) else {},
                                   'Status', WORKFLOW_STATES, 'Workflow.Status')
        record = _optional_label(finding, 'RecordState', RECORD_STATES, 'RecordState')
        comp = _optional_label(finding.get('Compliance') if isinstance(finding.get('Compliance'), dict) else {},
                               'Status', COMPLIANCE_STATES, 'Compliance.Status')
        severities[label] += 1
        workflows[workflow or 'not_reported'] += 1
        records[record or 'not_reported'] += 1
        compliance[comp or 'not_reported'] += 1
        signals = []
        if severity.get('Label') not in SEVERITY_LABELS:
            signals.append('unrecognized_severity_label')
        if workflow == 'unrecognized':
            signals.append('unrecognized_workflow_status')
        if record == 'unrecognized':
            signals.append('unrecognized_record_state')
        rows.append({'finding': f'finding[{position}]', 'types': types, 'reported_severity': label,
                     'reported_workflow_status': workflow, 'reported_record_state': record,
                     'reported_compliance_status': comp, 'signals': signals})
    return {'findings_reviewed': len(rows), 'by_reported_severity': dict(severities),
            'by_reported_workflow_status': dict(workflows), 'by_reported_record_state': dict(records),
            'by_reported_compliance_status': dict(compliance), 'findings': rows,
            'pagination_token_present': bool(token), 'coverage_verified': False,
            'snapshot_freshness_verified': False, 'source': SECURITYHUB_SOURCE,
            'next_checks': ['Verify the current account, region, active filters and pagination through an authorized read.',
                            'Confirm each finding against its owning service before accepting any status as resolved.'],
            'limits': ('Supplied get-findings snapshot only: reported severity/workflow/record/compliance fields as supplied, '
                       'not a current security posture, full coverage, exploitability or a verified root cause. '
                       'Unrecognized future values are reported, never silently mapped. Severity labels are the provider claim, '
                       'not an independent risk rating; a low label or zero findings never means secure. '
                       'Finding Ids, account, product/generator identifiers, titles, descriptions, resources, '
                       'remediation text, timestamps and free-form fields are omitted. '
                       'No AWS/SDK/CLI/network call, workflow status change, suppression, archive, insight or remediation occurs.')}


def _severity_band(value):
    # Documented GuardDuty bands: 0.1-3.9 Low, 4.0-6.9 Medium, 7.0-8.9 High.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10:
        raise ValueError('GuardDuty Severity must be a number from 0 to 10 as supplied.')
    if value < 4:
        return 'low'
    if value < 7:
        return 'medium'
    return 'high'


def review_guardduty_findings(document):
    if not isinstance(document, dict) or not isinstance(document.get('Findings'), list):
        raise ValueError('Supply an unmodified guardduty get-findings JSON object with a Findings array.')
    findings = document['Findings']
    if len(findings) > MAX_FINDINGS:
        raise ValueError('Scope the supplied snapshot to at most 500 findings.')
    bands, type_counts, resource_types = Counter(), Counter(), Counter()
    rows = []
    for position, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError('Each finding must be an object.')
        kind = _text(finding.get('Type'), 'Finding Type', 300)
        band = _severity_band(finding.get('Severity'))
        resource = finding.get('Resource')
        resource_type = None
        if resource is not None:
            if not isinstance(resource, dict):
                raise ValueError('Resource must be an object when supplied.')
            if 'ResourceType' in resource:
                resource_type = _text(resource['ResourceType'], 'ResourceType', 100)
        bands[band] += 1
        type_counts[kind] += 1
        resource_types[resource_type or 'not_reported'] += 1
        rows.append({'finding': f'finding[{position}]', 'reported_type': kind,
                     'reported_severity': finding.get('Severity'), 'severity_band': band,
                     'reported_resource_type': resource_type})
    return {'findings_reviewed': len(rows), 'by_severity_band': dict(bands),
            'by_reported_type': dict(type_counts), 'by_reported_resource_type': dict(resource_types),
            'findings': rows, 'coverage_verified': False, 'snapshot_freshness_verified': False,
            'source': GUARDDUTY_SOURCE, 'severity_band_source': GUARDDUTY_SEVERITY_SOURCE,
            'next_checks': ['Verify the detector, region, finding criteria and pagination through an authorized read.',
                            'Investigate each finding type against the affected workload before accepting or archiving it.'],
            'limits': ('Supplied get-findings snapshot only: reported type and numeric severity as supplied, banded by the '
                       'documented low/medium/high ranges, not a current threat posture, coverage, exploitability or a verified incident. '
                       'A low band or zero findings never means safe. Finding Ids, account, ARN, title, description, '
                       'resource identifiers, service/action details, confidence and timestamps are omitted. '
                       'No AWS/SDK/CLI/network call, archive, suppression, detector change or remediation occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def _read_export(path, label):
    # Same no-symlink/junction path hygiene as the other snapshot exports.
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError(f'Choose a regular local .json {label} export, not a directory or special file.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError(f'{label} export must be a regular file no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        return json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc


def review_security_hub_findings_export(path):
    return review_security_hub_findings(_read_export(path, 'securityhub get-findings'))


def review_guardduty_findings_export(path):
    return review_guardduty_findings(_read_export(path, 'guardduty get-findings'))


def register_security_findings_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_security_hub_findings',
        description='Review an existing local securityhub get-findings JSON snapshot: reported severity/workflow/record/compliance tallies per supplied finding. Offline triage only; not posture, coverage or remediation. No AWS access; identifiers and descriptions omitted.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 .json securityhub get-findings export, max 2 MB/500 findings. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_security_hub_findings_export, risk=Risk.SAFE, category='devops'))
    registry.register(Tool(
        name='review_guardduty_findings',
        description='Review an existing local guardduty get-findings JSON snapshot: reported types and numeric severities banded by the documented ranges. Offline triage only; not threat posture or a verified incident. No AWS access; identifiers and descriptions omitted.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 .json guardduty get-findings export, max 2 MB/500 findings. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_guardduty_findings_export, risk=Risk.SAFE, category='devops'))
