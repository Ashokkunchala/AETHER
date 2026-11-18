"""Offline AWS Backup job-state triage, never proof of recoverability."""
from __future__ import annotations

import json
import os
import re
import stat
from collections import Counter

SOURCE = 'https://docs.aws.amazon.com/cli/latest/reference/backup/list-backup-jobs.html'
MONITOR_SOURCE = 'https://docs.aws.amazon.com/aws-backup/latest/devguide/monitoring.html'
STATES = {'CREATED', 'PENDING', 'RUNNING', 'ABORTING', 'ABORTED', 'COMPLETED', 'FAILED', 'EXPIRED', 'PARTIAL'}
MAX_BYTES = 2_000_000


def _text(value, field, limit):
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError(f'{field} must be nonempty bounded text when supplied.')
    return value


def review_backup_jobs(document):
    if not isinstance(document, dict) or not isinstance(document.get('BackupJobs'), list):
        raise ValueError('Supply an AWS Backup list-backup-jobs JSON object with BackupJobs.')
    jobs = document['BackupJobs']
    if len(jobs) > 500:
        raise ValueError('Scope the supplied snapshot to at most 500 backup job records.')
    token = document.get('NextToken')
    if token is not None and (not isinstance(token, str) or len(token) > 8192):
        raise ValueError('NextToken must be bounded text or null.')
    rows, ids, counts, states = [], set(), Counter(), Counter()
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise ValueError('Each backup job must be an object.')
        identity = _text(job.get('BackupJobId'), 'BackupJobId', 200)
        if identity in ids:
            raise ValueError('Duplicate BackupJobId records are ambiguous; supply one scoped snapshot.')
        ids.add(identity)
        state = _text(job.get('State'), 'State', 80)
        state_label = state if state in STATES else 'UNKNOWN'
        category = job.get('MessageCategory')
        if 'MessageCategory' in job:
            _text(category, 'MessageCategory', 200)
        category_label = ('missing' if category is None else 'reported_success' if category == 'SUCCESS' else 'reported_non_success')
        parent = job.get('IsParent')
        if 'IsParent' in job and type(parent) is not bool:
            raise ValueError('IsParent must be a boolean when supplied.')
        parent_ref = job.get('ParentJobId')
        if 'ParentJobId' in job:
            _text(parent_ref, 'ParentJobId', 200)
        resource_type = job.get('ResourceType')
        if 'ResourceType' in job and (not isinstance(resource_type, str) or re.fullmatch(r'[A-Za-z0-9_.-]{1,50}', resource_type) is None):
            raise ValueError('ResourceType must be bounded identifier text when supplied.')
        signals = []
        if state == 'COMPLETED':
            classification = ('reported_completed_with_issues' if category_label == 'reported_non_success' else
                              'reported_completed_success_category' if category_label == 'reported_success' else
                              'reported_completed_category_unknown')
        elif state in {'FAILED', 'ABORTED', 'EXPIRED', 'PARTIAL'}:
            classification = 'reported_failure_or_incomplete_review'
        elif state in STATES:
            classification = 'reported_pending_or_in_progress'
        else:
            classification = 'unknown_state_review'
            signals.append('unrecognized_state')
        if state != 'COMPLETED' and category == 'SUCCESS':
            signals.append('success_category_does_not_override_noncompleted_state')
        if parent is True:
            signals.append('parent_composite_job_child_outcomes_not_verified')
        if parent_ref is not None:
            signals.append('child_job_parent_outcome_not_verified')
        if parent is True and parent_ref is not None:
            signals.append('both_parent_and_child_indicators_require_review')
        if parent_ref == identity:
            signals.append('self_parent_identifier_requires_review')
        counts[classification] += 1
        states[state_label] += 1
        # Arbitrary job IDs, vaults, resource labels, timestamps and messages are
        # not returned. Row indices are for human correlation in the local file.
        rows.append({'job_index': index, 'reported_state': state_label,
                     'message_category_status': category_label,
                     'reported_is_parent': parent, 'parent_reference_present': parent_ref is not None,
                     'resource_type_present': resource_type is not None,
                     'classification': classification, 'signals': signals,
                     'recoverability_verified': False})
    return {'job_records_reviewed': len(rows), 'reported_state_counts': dict(states),
            'classifications': dict(counts), 'jobs': rows,
            'pagination_token_present': bool(token), 'snapshot_freshness_verified': False,
            'inventory_completeness_verified': False, 'account_region_filter_scope_verified': False,
            'resource_coverage_verified': False, 'restore_test_verified': False,
            'source': SOURCE, 'monitoring_source': MONITOR_SOURCE,
            'next_checks': ['Correlate job_index to the supplied local file and inspect current status through separately authorized AWS reads.',
                            'Verify account, region, query filters, pagination and parent/child jobs before assessing job outcomes.',
                            'Check intended resource coverage, recovery-point availability/retention, permissions and separate restore-test evidence before relying on recovery.'],
            'limits': ('Supplied job-record snapshot only, not live monitoring, protected-resource coverage, backup integrity or restore readiness. '
                       'COMPLETED plus a non-SUCCESS MessageCategory is reported completed with issues; a missing category remains unknown. '
                       'Even COMPLETED with SUCCESS does not verify a usable recovery point or tested restore. Unknown states remain review-only. '
                       'Counts describe job records, not distinct resources or successful backups: parent/composite and child records can overlap. '
                       'No age, stuck-job, overdue-job, latest-backup, RPO/RTO, schedule or duration inference; timestamps are not evaluated. '
                       'Job/resource/account/vault/role/key identifiers, names, free-form messages, categories and size totals are omitted. '
                       'Missing NextToken never proves all pages/accounts/regions/filters are covered; empty jobs do not prove no backups are needed. '
                       'No AWS/SDK/CLI/network call, credential read, subscription, alert, retry, cancel, backup, copy, restore, deletion, payment or deployment occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_backup_jobs_export(path):
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json list-backup-jobs export.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('AWS Backup export must be regular and no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_backup_jobs(document)


def register_aws_backup_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_aws_backup_jobs', description='Review an existing local AWS Backup list-backup-jobs JSON snapshot. Reported job-state triage only, not live monitoring, backup coverage, freshness, integrity or restore readiness. No AWS calls/actions; private identifiers and messages omitted.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 JSON, max 2 MB/500 job records. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_backup_jobs_export, risk=Risk.SAFE, category='devops'))
