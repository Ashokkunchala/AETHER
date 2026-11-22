"""Offline RDS instance snapshot triage, never monitoring or a health verdict."""
from __future__ import annotations

import json
import os
import stat
from collections import Counter

SOURCE = 'https://docs.aws.amazon.com/cli/latest/reference/rds/describe-db-instances.html'
MAX_BYTES = 2_000_000
MAX_INSTANCES = 200
KNOWN_STATES = {'available', 'backing-up', 'backtracking', 'configuring-enhanced-monitoring',
                'configuring-iam-database-auth', 'configuring-log-exports', 'converting-to-vpc',
                'creating', 'delete-precheck', 'deleting', 'failed', 'inaccessible-encryption-credentials',
                'inaccessible-encryption-credentials-recoverable', 'incompatible-network',
                'incompatible-option-group', 'incompatible-parameters', 'incompatible-restore',
                'insufficient-capacity', 'maintenance', 'modifying', 'moving-to-vpc', 'rebooting',
                'resetting-master-credentials', 'renaming', 'restore-error', 'starting',
                'stopped', 'stopping', 'storage-full', 'storage-optimization', 'upgrading'}


def _text(value, label, limit=200):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label} must be nonempty bounded text without control characters.')
    return value


def _boolean(obj, field):
    value = obj.get(field)
    if field in obj and type(value) is not bool:
        raise ValueError(f'{field} must be a boolean when supplied.')
    return value


def _count(obj, field, maximum):
    value = obj.get(field)
    if value is not None and (type(value) is not int or not 0 <= value <= maximum):
        raise ValueError(f'{field} must be an integer from 0 to {maximum} when supplied.')
    return value


def review_db_instances(document):
    if not isinstance(document, dict) or not isinstance(document.get('DBInstances'), list):
        raise ValueError('Supply an unmodified describe-db-instances JSON object with a DBInstances array.')
    instances = document['DBInstances']
    if len(instances) > MAX_INSTANCES:
        raise ValueError('Scope the supplied snapshot to at most 200 DB instances.')
    marker = document.get('Marker')
    if marker is not None and not isinstance(marker, str):
        raise ValueError('Marker must be text or null.')
    states = Counter()
    rows = []
    for position, instance in enumerate(instances):
        if not isinstance(instance, dict):
            raise ValueError('Each DB instance must be an object.')
        engine = _text(instance.get('Engine'), 'Engine', 100)
        status = _text(instance.get('DBInstanceStatus'), 'DBInstanceStatus', 100)
        state_known = status in KNOWN_STATES
        states[status if state_known else 'unrecognized'] += 1
        public = _boolean(instance, 'PubliclyAccessible')
        encrypted = _boolean(instance, 'StorageEncrypted')
        multi_az = _boolean(instance, 'MultiAZ')
        protection = _boolean(instance, 'DeletionProtection')
        retention = _count(instance, 'BackupRetentionPeriod', 35)
        storage = _count(instance, 'AllocatedStorage', 10_000_000)
        signals = []
        if not state_known:
            signals.append('unrecognized_instance_status')
        if public is True:
            signals.append('reported_publicly_accessible')
        if encrypted is False:
            signals.append('reported_unencrypted_storage')
        if retention == 0:
            signals.append('reported_backup_retention_zero')
        if protection is False:
            signals.append('reported_deletion_protection_off')
        rows.append({'instance': f'db[{position}]', 'reported_engine': engine,
                     'reported_engine_version': _text(instance['EngineVersion'], 'EngineVersion', 100) if instance.get('EngineVersion') is not None else None,
                     'reported_status': status if state_known else 'unrecognized',
                     'reported_publicly_accessible': public, 'reported_storage_encrypted': encrypted,
                     'reported_multi_az': multi_az, 'reported_deletion_protection': protection,
                     'reported_backup_retention_days': retention, 'reported_allocated_storage_gib': storage,
                     'signals': signals})
    return {'instances_reviewed': len(rows), 'by_reported_status': dict(states), 'instances': rows,
            'pagination_marker_present': bool(marker), 'inventory_completeness_verified': False,
            'snapshot_freshness_verified': False, 'account_region_scope_verified': False,
            'source': SOURCE,
            'next_checks': ['Verify the current account, region, filters, pagination and live status through an authorized read.',
                            'Review real CPU/connections/storage metrics and logs via approved CloudWatch reads before any change.'],
            'limits': ('Supplied describe-db-instances snapshot only: reported fields as supplied, not live monitoring, '
                       'performance analysis, a health verdict, cost attribution or proof a change is safe. '
                       'Unrecognized future statuses are reported, never silently mapped. '
                       'Instance identifiers, endpoints, ports, usernames, database names, ARNs, security groups, '
                       'parameter/option groups, subnet groups, KMS keys, tags and free-form values are omitted; '
                       'db[n] labels follow the supplied order. A missing Marker does not prove all pages/regions were supplied. '
                       'No AWS/SDK/CLI/network call, reboot, modify, failover, snapshot, restore, delete or credential access occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_db_instances_export(path):
    # Same no-symlink/junction path hygiene as the other snapshot exports.
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json describe-db-instances export, not a directory or special file.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('RDS export must be a regular file no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_db_instances(document)


def register_rds_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_rds_instances',
        description='Review an existing local describe-db-instances JSON snapshot: reported engine/status and public-access, encryption, backup-retention and deletion-protection signals. Offline triage only; not monitoring, a health verdict or change approval. No AWS access; identifiers and endpoints omitted.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 .json describe-db-instances export, max 2 MB/200 instances. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_db_instances_export, risk=Risk.SAFE, category='devops'))
