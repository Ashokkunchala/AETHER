"""Offline node-condition evidence, not cluster health or live diagnosis."""
from __future__ import annotations

import json
import os
import re
import stat
from collections import Counter

SOURCE = 'https://kubernetes.io/docs/reference/node/node-status/'
CONDITIONS = ('Ready', 'MemoryPressure', 'DiskPressure', 'PIDPressure', 'NetworkUnavailable')
MAX_BYTES = 2_000_000


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object when supplied.')
    return value


def review_nodes(document):
    doc = _object(document, 'Document')
    if doc.get('apiVersion') != 'v1':
        raise ValueError('Supply core Kubernetes v1 Node or NodeList JSON.')
    kind = doc.get('kind')
    meta = _object(doc.get('metadata', {}), 'Document metadata')
    token = meta.get('continue')
    if token is not None and (not isinstance(token, str) or len(token) > 8192):
        raise ValueError('List continuation token must be bounded text or null.')
    if kind == 'Node':
        items = [doc]
    elif kind in ('NodeList', 'List'):
        items = doc.get('items')
    else:
        raise ValueError('Expected Node, NodeList or a List containing only Nodes.')
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError('Scope the snapshot to an array of at most 500 nodes.')
    rows, identities, counts = [], set(), Counter()
    for index, item in enumerate(items):
        node = _object(item, 'Node')
        if node.get('apiVersion') != 'v1' or node.get('kind') != 'Node':
            raise ValueError('Every item must be a core v1 Node.')
        metadata = _object(node.get('metadata'), 'Node metadata')
        name = metadata.get('name')
        if not isinstance(name, str) or len(name) > 253 or re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?', name) is None:
            raise ValueError('Each node needs a bounded supported metadata.name for duplicate detection.')
        if name in identities:
            raise ValueError('Duplicate node names are ambiguous; supply one consistent scoped snapshot.')
        identities.add(name)
        status = _object(node.get('status', {}), 'Node status')
        spec = _object(node.get('spec', {}), 'Node spec')
        unschedulable = spec.get('unschedulable')
        if 'unschedulable' in spec and type(unschedulable) is not bool:
            raise ValueError('spec.unschedulable must be boolean when supplied.')
        conditions = status.get('conditions', [])
        if not isinstance(conditions, list) or len(conditions) > 100:
            raise ValueError('conditions must be an array of at most 100 entries.')
        known, seen, unknown = {}, set(), 0
        for condition in conditions:
            condition = _object(condition, 'Node condition')
            condition_type, value = condition.get('type'), condition.get('status')
            if not isinstance(condition_type, str) or not condition_type or len(condition_type) > 100:
                raise ValueError('Every condition requires a bounded type.')
            if condition_type in seen:
                raise ValueError('Duplicate condition types are ambiguous; no latest timestamp is inferred.')
            seen.add(condition_type)
            if value not in ('True', 'False', 'Unknown'):
                raise ValueError('Condition status must be the exact string True, False or Unknown.')
            if condition_type in CONDITIONS:
                known[condition_type] = value
            else:
                unknown += 1
        ready = known.get('Ready', 'Missing')
        classification = {'True': 'reported_ready', 'False': 'reported_not_ready',
                          'Unknown': 'reported_ready_unknown', 'Missing': 'ready_condition_missing'}[ready]
        signals = []
        if ready != 'True':
            signals.append(classification)
        for field in CONDITIONS[1:]:
            if known.get(field) == 'True':
                signals.append('reported_' + {'MemoryPressure': 'memory_pressure', 'DiskPressure': 'disk_pressure',
                               'PIDPressure': 'pid_pressure', 'NetworkUnavailable': 'network_unavailable'}[field])
        if unschedulable is True:
            signals.append('reported_unschedulable_new_scheduling_disabled')
        if unknown:
            signals.append('unrecognized_condition_types_not_interpreted')
        if ready == 'True' and any(known.get(field) == 'True' for field in CONDITIONS[1:]):
            signals.append('ready_and_adverse_conditions_coexist_review')
        counts[classification] += 1
        rows.append({'node_index': index, 'classification': classification,
                     'reported_conditions': {field: known.get(field, 'Missing') for field in CONDITIONS},
                     'missing_conditions': [field for field in CONDITIONS if field not in known],
                     'unrecognized_condition_count': unknown,
                     'conditions_field_present': 'conditions' in status,
                     'reported_unschedulable': unschedulable, 'signals': signals,
                     'scheduling_eligibility_verified': False, 'node_health_verified': False})
    return {'node_records_reviewed': len(rows), 'classifications': dict(counts), 'nodes': rows,
            'continuation_token_present': bool(token), 'snapshot_freshness_verified': False,
            'inventory_completeness_verified': False, 'cluster_identity_scope_verified': False,
            'cluster_health_verified': False, 'source': SOURCE,
            'next_checks': ['Correlate node_index with the private supplied file; verify current cluster/context, scope and pagination through a separately authorized read.',
                            'Review live node conditions, events, kubelet/network reachability and resource pressure before attributing a cause.',
                            'Evaluate workload placement, taints/tolerations, capacity, control plane and application signals separately before calling a cluster healthy or planning a change.'],
            'limits': ('Supplied Node condition snapshot only, not live cluster health, diagnosis, root cause or scheduling assurance. '
                       'Ready True is only a reported condition, not proof workloads, control plane, storage, networking or cluster are healthy. '
                       'Ready False, Unknown and missing remain distinct; absent pressure fields are missing, never assumed False. '
                       'spec.unschedulable True reports disabled new scheduling, not an API SchedulingDisabled condition; False/missing does not prove a pod can schedule. '
                       'Unknown condition types are counted but not interpreted. Timestamps, age/staleness, leases, metrics, capacity, taints, versions, upgrades and workload placement are not evaluated. '
                       'Names, labels, annotations, addresses/provider IDs, messages/reasons, versions and continuation values are omitted. Node indices are local input positions, not persistent identities. '
                       'An empty list or missing continuation token does not prove complete inventory or a healthy cluster. '
                       'No kubectl/Helm/SDK/network/cluster call, secret access, cordon/drain, scaling, deployment, remediation, upgrade or payment occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_nodes_export(path):
    from jarvis.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json Node/NodeList export.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('Node export must be regular and no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_nodes(document)


def register_node_tools(registry):
    from jarvis.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_kubernetes_nodes', description='Review a supplied local core v1 Node/NodeList JSON snapshot for reported Ready, pressure, network and unschedulable signals. Offline only, not cluster health, current diagnosis, root cause or scheduling proof. No cluster call/change.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 JSON, max 2 MB/500 nodes. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_nodes_export, risk=Risk.SAFE, category='devops'))
