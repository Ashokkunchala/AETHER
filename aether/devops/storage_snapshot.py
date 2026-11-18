"""Offline PV/PVC phase evidence, never storage health or cleanup authority."""
from __future__ import annotations

import json
import os
import re
import stat
from collections import Counter

SOURCE = 'https://kubernetes.io/docs/concepts/storage/persistent-volumes/'
PVC_SOURCE = 'https://kubernetes.io/docs/reference/kubernetes-api/config-and-storage-resources/persistent-volume-claim-v1/'
CLASS_SOURCE = 'https://kubernetes.io/docs/concepts/storage/storage-classes/'
PV = 'PersistentVolume'
PVC = 'PersistentVolumeClaim'
PHASES = {PV: {'Pending', 'Available', 'Bound', 'Released', 'Failed'}, PVC: {'Pending', 'Bound', 'Lost'}}
MAX_BYTES = 2_000_000


def _obj(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object when supplied.')
    return value


def _text(value, label, empty=False):
    if not isinstance(value, str) or len(value) > 253 or (not value and not empty) or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label} must be bounded text when supplied.')
    return value


def _name(value, label):
    value = _text(value, label)
    if re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?', value) is None:
        raise ValueError(f'{label} must be a supported identifier.')
    return value


def review_storage(document):
    doc = _obj(document, 'Document')
    if doc.get('apiVersion') != 'v1':
        raise ValueError('Supply core v1 PV/PVC JSON, a typed list or a List containing only PV/PVC objects.')
    kind = doc.get('kind')
    if not isinstance(kind, str) or kind not in {PV, PVC, PV+'List', PVC+'List', 'List'}:
        raise ValueError('Expected PersistentVolume, PersistentVolumeClaim, their typed lists or core v1 List.')
    meta = _obj(doc.get('metadata', {}), 'Document metadata')
    token = meta.get('continue')
    if token is not None and (not isinstance(token, str) or len(token) > 8192):
        raise ValueError('Continuation token must be bounded text or null.')
    items = [doc] if kind in (PV, PVC) else doc.get('items')
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError('Scope the supplied snapshot to at most 500 PV/PVC records.')
    rows, identities, counts = [], set(), Counter()
    for index, item in enumerate(items):
        obj = _obj(item, 'Storage object')
        resource_kind = obj.get('kind')
        if obj.get('apiVersion') != 'v1' or not isinstance(resource_kind, str) or resource_kind not in (PV, PVC):
            raise ValueError('Every item must be a core v1 PersistentVolume or PersistentVolumeClaim.')
        if kind in (PV+'List', PVC+'List') and resource_kind != kind[:-4]:
            raise ValueError('Typed list items must match its resource kind.')
        metadata = _obj(obj.get('metadata'), 'Resource metadata')
        name = _name(metadata.get('name'), 'metadata.name')
        namespace = metadata.get('namespace', '')
        if resource_kind == PVC:
            namespace = _name(namespace, 'PVC metadata.namespace')
        elif namespace != '':
            raise ValueError('PV is cluster-scoped; do not supply a namespace.')
        identity = (resource_kind, namespace, name)
        if identity in identities:
            raise ValueError('Duplicate kind/namespace/name records are ambiguous; supply one scoped snapshot.')
        identities.add(identity)
        deletion = 'deletionTimestamp' in metadata
        if deletion:
            _text(metadata['deletionTimestamp'], 'deletionTimestamp')
        status = _obj(obj.get('status', {}), 'Resource status')
        spec = _obj(obj.get('spec', {}), 'Resource spec')
        raw_phase = status.get('phase')
        if 'phase' in status:
            _text(raw_phase, 'phase')
        phase = 'Missing' if raw_phase is None else raw_phase if raw_phase in PHASES[resource_kind] else 'Unknown'
        signals = []
        if phase != 'Bound':
            signals.append('reported_'+phase.lower()+'_phase_review')
        if deletion:
            signals.append('deletion_timestamp_present_no_age_or_finalizer_inference')
        class_status = 'missing'
        if 'storageClassName' in spec:
            value = _text(spec['storageClassName'], 'storageClassName', empty=True)
            class_status = 'explicit_empty' if value == '' else 'named_value_omitted'
        reclaim = None
        target_present = None
        conditions_output, condition_count = [], 0
        if resource_kind == PV:
            if 'persistentVolumeReclaimPolicy' in spec:
                raw_reclaim = _text(spec['persistentVolumeReclaimPolicy'], 'persistentVolumeReclaimPolicy')
                reclaim = raw_reclaim if raw_reclaim in {'Retain', 'Delete', 'Recycle'} else 'Unknown'
                if reclaim == 'Delete':
                    signals.append('reported_delete_reclaim_can_remove_backing_storage')
                elif reclaim == 'Recycle':
                    signals.append('reported_recycle_policy_requires_compatibility_review')
                elif reclaim == 'Unknown':
                    signals.append('unrecognized_reclaim_policy')
            target_present = 'claimRef' in spec
            if target_present:
                _obj(spec['claimRef'], 'claimRef')
            if phase == 'Bound' and not target_present:
                signals.append('reported_bound_without_claim_reference')
        else:
            target_present = 'volumeName' in spec
            if target_present:
                _name(spec['volumeName'], 'volumeName')
            if phase == 'Bound' and not target_present:
                signals.append('reported_bound_without_volume_name')
            conditions = status.get('conditions', [])
            if not isinstance(conditions, list) or len(conditions) > 100:
                raise ValueError('PVC conditions must be an array of at most 100 entries.')
            seen = set()
            for condition in conditions:
                condition = _obj(condition, 'PVC condition')
                ctype = _text(condition.get('type'), 'condition type')
                cstatus = condition.get('status')
                if ctype in seen or cstatus not in ('True', 'False', 'Unknown'):
                    raise ValueError('PVC condition types must be unique and statuses exact True/False/Unknown strings.')
                seen.add(ctype)
                condition_count += 1
                if ctype in {'Resizing', 'FileSystemResizePending'}:
                    conditions_output.append({'type': ctype, 'reported_status': cstatus})
            if condition_count > len(conditions_output):
                signals.append('unrecognized_pvc_conditions_not_interpreted')
        counts[resource_kind+':'+phase] += 1
        rows.append({'resource_index': index, 'kind': resource_kind, 'reported_phase': phase,
                     'reported_storage_class_status': class_status, 'reported_reclaim_policy': reclaim,
                     'binding_reference_field_present': target_present,
                     'reported_resize_conditions': conditions_output, 'pvc_condition_records': condition_count,
                     'signals': signals, 'safe_to_delete': False, 'binding_verified': False,
                     'mounted_verified': False, 'storage_health_verified': False})
    return {'storage_records_reviewed': len(rows), 'kind_phase_counts': dict(counts), 'resources': rows,
            'continuation_token_present': bool(token), 'snapshot_freshness_verified': False,
            'inventory_completeness_verified': False, 'cluster_context_scope_verified': False,
            'source': SOURCE, 'pvc_source': PVC_SOURCE, 'storage_class_source': CLASS_SOURCE,
            'next_checks': ['Correlate resource_index with the private source file; verify current context/namespace, scope and pagination through a separately authorized read.',
                            'Review PVC/PV events, StorageClass binding mode, CSI/controller status, topology, pod scheduling and mounts before attributing a cause.',
                            'Verify ownership, data retention and tested recovery separately; obtain explicit approval before any delete/rebind/resize/provision action.'],
            'limits': ('Supplied PV/PVC phase evidence only, not live storage monitoring, root cause, mount health, data durability or cleanup approval. '
                       'Bound is not proof mounted or healthy. Pending is not automatically failure: WaitForFirstConsumer or other legitimate binding constraints may apply, but StorageClass/pods are not inspected. '
                       'Lost/Failed are reported phase signals, not independent proof of data loss or a diagnosis. Available/Released are never safe-to-delete verdicts. '
                       'Delete reclaim policy can remove backing storage for supported plugins; Retain does not prove recoverability or authorize release/reuse. '
                       'Binding-reference field presence is not matching or bidirectional binding proof, and empty claimRef objects are not validated as bindings. '
                       'Missing storageClassName and explicit empty differ; no default class is inferred. Names/namespaces/labels/annotations, CSI handles, reasons/messages, timestamps, capacities and secret references are omitted. '
                       'No PV/PVC cross-correlation, capacity/quantity arithmetic, access-mode compatibility, finalizer/age, CSI health, resize success, StorageClass validity, recovery or upgrade assessment. '
                       'Counts describe supplied records; PV and PVC entries can describe the same storage and must not be summed as distinct disks. Empty results or missing continuation never prove complete scope or no problems. '
                       'No kubectl/Helm/SDK/network/cluster or secret call, delete, rebind, resize, provision, mount, deployment, payment or remediation occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_storage_export(path):
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json PV/PVC export.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('Storage export must be regular and no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_storage(document)


def register_storage_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_kubernetes_storage', description='Review a supplied local core v1 PV/PVC JSON snapshot for reported phases, reclaim-policy and resize-condition evidence. Offline only, not mount/storage health, binding verification, root cause or cleanup authority. No cluster action.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 JSON, max 2 MB/500 PV/PVC records. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_storage_export, risk=Risk.SAFE, category='devops'))
