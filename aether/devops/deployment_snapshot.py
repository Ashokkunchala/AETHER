"""Offline Deployment status signals, never a rollout executor or success gate."""
from __future__ import annotations

import json
import os
import re
import stat
from collections import Counter

SOURCE = 'https://kubernetes.io/docs/concepts/workloads/controllers/deployment/'
API_SOURCE = 'https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/deployment-v1/'
MAX_BYTES = 2_000_000
COUNTERS = ('replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas', 'unavailableReplicas', 'terminatingReplicas')
CONDITIONS = ('Available', 'Progressing', 'ReplicaFailure')
REASONS = {'NewReplicaSetAvailable', 'ProgressDeadlineExceeded', 'ReplicaSetCreateError', 'FailedCreate', 'MinimumReplicasAvailable', 'MinimumReplicasUnavailable', 'DeploymentPaused', 'DeploymentResumed', 'ReplicaSetUpdated', 'NewReplicaSetCreated', 'FoundNewReplicaSet'}


def _obj(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object when supplied.')
    return value


def _integer(obj, field):
    if field not in obj:
        return None
    value = obj[field]
    if type(value) is not int or not 0 <= value <= 1_000_000_000:
        raise ValueError(f'{field} must be a bounded nonnegative integer when supplied.')
    return value


def _name(value):
    if not isinstance(value, str) or len(value) > 253 or re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?', value) is None:
        raise ValueError('Deployment metadata requires explicit bounded name and namespace identifiers.')
    return value


def review_deployments(document):
    doc = _obj(document, 'Document')
    version, kind = doc.get('apiVersion'), doc.get('kind')
    if kind == 'Deployment' and version == 'apps/v1':
        items = [doc]
    elif (kind == 'DeploymentList' and version == 'apps/v1') or (kind == 'List' and version == 'v1'):
        items = doc.get('items')
    else:
        raise ValueError('Supply apps/v1 Deployment/DeploymentList or core v1 List containing only Deployments.')
    metadata = _obj(doc.get('metadata', {}), 'Document metadata')
    token = metadata.get('continue')
    if token is not None and (not isinstance(token, str) or len(token) > 8192):
        raise ValueError('Continuation token must be bounded text or null.')
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError('Scope snapshot to at most 500 Deployment records.')
    rows, seen, counts = [], set(), Counter()
    for index, item in enumerate(items):
        item = _obj(item, 'Deployment')
        if item.get('apiVersion') != 'apps/v1' or item.get('kind') != 'Deployment':
            raise ValueError('Every list item must be an apps/v1 Deployment.')
        meta = _obj(item.get('metadata'), 'Deployment metadata')
        identity = (_name(meta.get('namespace')), _name(meta.get('name')))
        if identity in seen:
            raise ValueError('Duplicate namespace/name records are ambiguous; supply one scoped snapshot.')
        seen.add(identity)
        spec = _obj(item.get('spec', {}), 'Deployment spec')
        status = _obj(item.get('status', {}), 'Deployment status')
        generation, observed = _integer(meta, 'generation'), _integer(status, 'observedGeneration')
        generation_status = ('unknown_missing_generation' if generation is None or observed is None else
                             'controller_behind_reported_generation' if observed < generation else
                             'reported_generation_match' if observed == generation else 'observed_generation_ahead_review')
        desired = _integer(spec, 'replicas')
        paused = spec.get('paused')
        if 'paused' in spec and type(paused) is not bool:
            raise ValueError('spec.paused must be boolean when supplied.')
        replicas = {field: _integer(status, field) for field in COUNTERS}
        conditions = status.get('conditions', [])
        if not isinstance(conditions, list) or len(conditions) > 100:
            raise ValueError('conditions must be an array of at most 100 entries.')
        known, condition_types, unknown = {}, set(), 0
        for condition in conditions:
            condition = _obj(condition, 'Deployment condition')
            ctype, cstatus = condition.get('type'), condition.get('status')
            if not isinstance(ctype, str) or not ctype or len(ctype) > 100 or ctype in condition_types:
                raise ValueError('Condition types must be unique nonempty bounded strings.')
            condition_types.add(ctype)
            if cstatus not in ('True', 'False', 'Unknown'):
                raise ValueError('Condition status must be exact string True, False or Unknown.')
            reason = condition.get('reason')
            if 'reason' in condition and (not isinstance(reason, str) or not reason or len(reason) > 256):
                raise ValueError('Condition reason must be nonempty bounded text when supplied.')
            reason_label = 'Missing' if reason is None else reason if reason in REASONS else 'OtherOmitted'
            if ctype in CONDITIONS:
                known[ctype] = {'reported_status': cstatus, 'reported_reason': reason_label}
            else:
                unknown += 1
        signals = []
        if generation_status != 'reported_generation_match':
            signals.append(generation_status)
        if desired is None:
            signals.append('desired_replicas_missing_no_default_inferred')
        elif desired == 0:
            signals.append('reported_zero_desired_not_application_availability')
        if paused is True:
            signals.append('reported_paused_no_progress_deadline_inference')
        if any(value is None for value in replicas.values()):
            signals.append('some_replica_counters_missing_not_zero')
        progress = known.get('Progressing', {})
        available = known.get('Available', {})
        failure = known.get('ReplicaFailure', {})
        if progress.get('reported_status') == 'False' and progress.get('reported_reason') == 'ProgressDeadlineExceeded':
            signals.append('reported_progress_deadline_exceeded_no_automatic_rollback')
        if progress.get('reported_status') == 'True':
            signals.append('reported_progressing_true_not_completion_proof')
        if available.get('reported_status') == 'True':
            signals.append('reported_minimum_availability_not_application_health')
        elif available.get('reported_status') == 'False':
            signals.append('reported_minimum_availability_not_met')
        if failure.get('reported_status') == 'True':
            signals.append('reported_replica_failure_review')
        if desired is not None:
            if replicas['updatedReplicas'] is not None and replicas['updatedReplicas'] < desired:
                signals.append('reported_updated_below_desired')
            if replicas['availableReplicas'] is not None and replicas['availableReplicas'] < desired:
                signals.append('reported_available_below_desired')
        if unknown:
            signals.append('unrecognized_conditions_not_interpreted')
        counts[generation_status] += 1
        rows.append({'deployment_index': index, 'reported_generation': generation,
                     'reported_observed_generation': observed, 'generation_status': generation_status,
                     'reported_desired_replicas': desired, 'reported_paused': paused,
                     'reported_replica_counters': replicas,
                     'reported_conditions': {field: known.get(field, {'reported_status': 'Missing', 'reported_reason': 'Missing'}) for field in CONDITIONS},
                     'unrecognized_condition_count': unknown, 'signals': signals,
                     'rollout_complete_verified': False, 'application_health_verified': False,
                     'safe_to_deploy_or_scale': False})
    return {'deployments_reviewed': len(rows), 'generation_status_counts': dict(counts), 'deployments': rows,
            'continuation_token_present': bool(token), 'snapshot_freshness_verified': False,
            'inventory_completeness_verified': False, 'cluster_context_scope_verified': False,
            'source': SOURCE, 'api_source': API_SOURCE,
            'next_checks': ['Correlate deployment_index with the private original and verify current context/namespace, complete scope and observed generation through separately authorized reads.',
                            'Review Deployment conditions, ReplicaSets, Pods, events, probes, strategy and recent changes without treating minimum availability as application health.',
                            'Obtain separately scoped authority, exact change/reviewed manifests, impact and rollback evidence before deploying, scaling, resuming or rolling back.'],
            'limits': ('Supplied Deployment status signals only, not live rollout monitoring, successful release, application health, root cause or deployment/scale approval. '
                       'Generation match means only two supplied counters match, not freshness or completion; behind/ahead/missing generation remains explicit. '
                       'Missing replicas/counters are not defaulted to one or zero. Updated/available below desired are reported comparisons only, not failure causes. '
                       'Progressing True can mean ongoing or completed progress; Available True reports minimum availability, not all desired replicas or application success. '
                       'ProgressDeadlineExceeded does not automatically trigger Kubernetes rollback; this tool performs none. Paused state does not imply a failure or deadline calculation. '
                       'Zero desired can be intentional and never proves serving availability. Surges, terminating replicas and unavailable counts are preserved without invalid sum/equality assumptions. '
                       'No clock/timestamp/age/deadline, revision/image/strategy/selector, ReplicaSet/Pod/events, HPA, PDB, admission, capacity, compatibility, upgrade or rollback-readiness evaluation. '
                       'Names/namespaces/images/labels/annotations/selectors/messages and arbitrary reason values are omitted. Counts are records, not unique applications or completed releases. '
                       'Empty results or missing continuation never proves full inventory or no problems. No kubeconfig, kubectl/Helm/SDK/network/cluster call, deploy, scale, pause/resume, rollback, upgrade, remediation or payment occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_deployments_export(path):
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json Deployment export.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('Deployment export must be regular and no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_deployments(document)


def register_deployment_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_kubernetes_deployments', description='Review existing local apps/v1 Deployment JSON for reported generation lag, replica counters, paused and progress/availability conditions. Offline only, not rollout completion, application health, current diagnosis or permission to deploy/scale. No cluster call/change.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 JSON, max 2 MB/500 Deployments. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_deployments_export, risk=Risk.SAFE, category='devops'))
