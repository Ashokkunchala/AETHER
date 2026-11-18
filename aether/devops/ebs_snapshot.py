"""Offline EBS attachment-state triage, never cleanup or proof of non-use."""
from __future__ import annotations

import json
import os
import re
import stat
from collections import Counter

SOURCE = 'https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-volumes.html'
DELETION_SOURCE = 'https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-volume.html'
MAX_BYTES = 2_000_000
MAX_VOLUMES = 500
STATES = {'creating', 'available', 'in-use', 'deleting', 'deleted', 'error'}
ATTACHMENT_STATES = {'attaching', 'attached', 'detaching', 'detached', 'busy'}


def _boolean(obj, field):
    value = obj.get(field)
    if field in obj and type(value) is not bool:
        raise ValueError(f'{field} must be a boolean when supplied.')
    return value


def review_volumes(document):
    if not isinstance(document, dict) or not isinstance(document.get('Volumes'), list):
        raise ValueError('Supply an unmodified describe-volumes JSON object with a Volumes array.')
    volumes = document['Volumes']
    if len(volumes) > MAX_VOLUMES:
        raise ValueError('Scope the supplied snapshot to at most 500 volumes.')
    token = document.get('NextToken')
    if token is not None and not isinstance(token, str):
        raise ValueError('NextToken must be text or null.')
    seen, rows, counts = set(), [], Counter()
    for volume in volumes:
        if not isinstance(volume, dict):
            raise ValueError('Each volume must be an object.')
        identity = volume.get('VolumeId')
        if not isinstance(identity, str) or re.fullmatch(r'vol-(?:[0-9a-f]{8}|[0-9a-f]{17})', identity) is None:
            raise ValueError('Each volume requires a supported EBS VolumeId.')
        if identity in seen:
            raise ValueError('Duplicate VolumeIds are ambiguous; supply one scoped snapshot.')
        seen.add(identity)
        state = volume.get('State')
        if not isinstance(state, str) or not state or len(state) > 50:
            raise ValueError('Each volume requires its reported State.')
        # Unknown future states must never become review candidates by omission.
        state_known = state in STATES
        size = volume.get('Size')
        if size is not None and (type(size) is not int or size < 1):
            raise ValueError('Size must be a positive integer GiB when supplied.')
        encrypted = _boolean(volume, 'Encrypted')
        multi = _boolean(volume, 'MultiAttachEnabled')
        operator = volume.get('Operator')
        managed = None
        if 'Operator' in volume:
            if not isinstance(operator, dict):
                raise ValueError('Operator must be an object.')
            managed = _boolean(operator, 'Managed')
        attachments = volume.get('Attachments')
        attachments_present = 'Attachments' in volume
        if attachments_present and (not isinstance(attachments, list) or len(attachments) > 100):
            raise ValueError('Attachments must be a list of at most 100 entries.')
        attachment_counts = Counter()
        if attachments_present:
            for attachment in attachments:
                if not isinstance(attachment, dict):
                    raise ValueError('Each attachment must be an object.')
                attachment_state = attachment.get('State')
                if not isinstance(attachment_state, str) or not attachment_state or len(attachment_state) > 50:
                    raise ValueError('Each attachment requires its reported State.')
                label = attachment_state if attachment_state in ATTACHMENT_STATES else 'unknown'
                attachment_counts[label] += 1
        signals = []
        if not state_known:
            signals.append('unrecognized_volume_state')
        if not attachments_present:
            signals.append('attachment_field_missing')
        if state == 'available' and attachments:
            signals.append('available_with_attachment_records')
        if state == 'in-use' and attachments_present and not attachments:
            signals.append('in_use_without_attachment_records')
        if 'unknown' in attachment_counts:
            signals.append('unrecognized_attachment_state')
        if managed is True:
            signals.append('service_managed_volume')
        if encrypted is False:
            signals.append('reported_unencrypted')
        candidate = state == 'available' and attachments_present and not attachments and managed is not True
        classification = ('reported_available_unattached_review_candidate' if candidate else
                          'service_managed_review_only' if managed is True else 'not_a_candidate_from_this_snapshot')
        counts[classification] += 1
        rows.append({'volume_id': identity, 'reported_state': state if state_known else 'unknown',
                     'reported_size_gib': size, 'reported_encrypted': encrypted,
                     'reported_multi_attach_enabled': multi, 'reported_service_managed': managed,
                     'attachment_records': len(attachments) if attachments_present else None,
                     'attachment_state_counts': dict(attachment_counts),
                     'classification': classification, 'signals': signals,
                     'safe_to_delete': False})
    return {'volumes_reviewed': len(rows), 'classifications': dict(counts), 'volumes': rows,
            'pagination_token_present': bool(token), 'inventory_completeness_verified': False,
            'snapshot_freshness_verified': False, 'account_region_scope_verified': False,
            'source': SOURCE, 'deletion_source': DELETION_SOURCE,
            'next_checks': ['Verify the current account, region, filters, pagination and live attachment state through an authorized read.',
                            'Confirm owner, application/recovery purpose, retention and service management before considering any change.',
                            'Independently verify backup/snapshot recoverability and obtain separate explicit change approval.'],
            'limits': ('Supplied snapshot only. Available plus an explicit empty attachment list is a human-review candidate, '
                       'not proof unused, billable waste, an orphan or safe cleanup. Missing Operator does not establish unmanaged status. '
                       'No attachment age, last use, ownership, dependency, current state, backup validity, cost/savings or security verdict is inferred. '
                       'Tags, source snapshots, KMS keys, device/instance/account identifiers and free-form values are omitted. '
                       'A missing NextToken does not prove all accounts/regions/filters/pages were supplied. '
                       'No AWS/SDK/CLI/network call, detach, delete, snapshot, restore, credential/secret access, alert or deployment occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_volumes_export(path):
    # Same no-symlink/junction path hygiene as existing local document backups.
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json describe-volumes export, not a directory or special file.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('EBS export must be a regular file no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_volumes(document)


def register_ebs_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_ebs_volumes', description='Review an existing describe-volumes JSON snapshot for reported attachment states and available/unattached human-review candidates. Offline, not proof unused/safe-to-delete, no cleanup or AWS access. Missing pagination token never proves completeness.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 .json describe-volumes export, max 2 MB/500 volumes. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_volumes_export, risk=Risk.SAFE, category='devops'))
