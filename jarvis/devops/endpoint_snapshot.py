"""Offline EndpointSlice condition records, never routing/health assurance."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import stat
from collections import Counter

SOURCE = 'https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/'
SERVICE_SOURCE = 'https://kubernetes.io/docs/concepts/services-networking/service/'
MAX_BYTES = 2_000_000
FIELDS = ('ready', 'serving', 'terminating')


def _obj(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object when supplied.')
    return value


def _name(value, label):
    if not isinstance(value, str) or len(value) > 253 or re.fullmatch(r'[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?', value) is None:
        raise ValueError(f'{label} requires a bounded supported identifier.')
    return value


def _flag(conditions, field):
    if field not in conditions:
        return 'Missing'
    value = conditions[field]
    if value is None:
        return 'Null'
    if type(value) is not bool:
        raise ValueError('Endpoint conditions must be boolean, null or missing, not string flags.')
    return 'True' if value else 'False'


def review_endpoint_slices(document):
    doc = _obj(document, 'Document')
    version, kind = doc.get('apiVersion'), doc.get('kind')
    if kind == 'EndpointSlice' and version == 'discovery.k8s.io/v1':
        items = [doc]
    elif (kind == 'EndpointSliceList' and version == 'discovery.k8s.io/v1') or (kind == 'List' and version == 'v1'):
        items = doc.get('items')
    else:
        raise ValueError('Supply discovery.k8s.io/v1 EndpointSlice/EndpointSliceList or core v1 List containing only those slices.')
    metadata = _obj(doc.get('metadata', {}), 'Document metadata')
    token = metadata.get('continue')
    if token is not None and (not isinstance(token, str) or len(token) > 8192):
        raise ValueError('Continuation token must be bounded text or null.')
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError('Scope snapshot to at most 100 EndpointSlices.')
    seen, rows, all_records = set(), [], 0
    for index, item in enumerate(items):
        item = _obj(item, 'EndpointSlice')
        if item.get('apiVersion') != 'discovery.k8s.io/v1' or item.get('kind') != 'EndpointSlice':
            raise ValueError('Every item must be a discovery.k8s.io/v1 EndpointSlice.')
        meta = _obj(item.get('metadata'), 'Slice metadata')
        identity = (_name(meta.get('namespace'), 'namespace'), _name(meta.get('name'), 'name'))
        if identity in seen:
            raise ValueError('Duplicate slice namespace/name is ambiguous; supply one scoped snapshot.')
        seen.add(identity)
        labels = _obj(meta.get('labels', {}), 'Slice labels')
        service_label = labels.get('kubernetes.io/service-name')
        if 'kubernetes.io/service-name' in labels:
            _name(service_label, 'Service-name label')
        address_type = item.get('addressType')
        if not isinstance(address_type, str) or address_type not in {'IPv4', 'IPv6', 'FQDN'}:
            raise ValueError('Supported addressType is IPv4, IPv6 or FQDN.')
        endpoints = item.get('endpoints')
        if not isinstance(endpoints, list) or len(endpoints) > 1000:
            raise ValueError('Each slice needs an endpoints array of at most 1000 records.')
        all_records += len(endpoints)
        if all_records > 2000:
            raise ValueError('Scope snapshot to at most 2000 endpoint records across slices.')
        combos, signals = Counter(), Counter()
        for endpoint in endpoints:
            endpoint = _obj(endpoint, 'Endpoint record')
            addresses = endpoint.get('addresses')
            if not isinstance(addresses, list) or not 1 <= len(addresses) <= 100:
                raise ValueError('Each endpoint needs 1-100 bounded address strings.')
            for address in addresses:
                if not isinstance(address, str) or len(address) > 253:
                    raise ValueError('Address must be bounded text.')
                try:
                    if address_type in ('IPv4', 'IPv6'):
                        parsed = ipaddress.ip_address(address)
                        if parsed.version != (4 if address_type == 'IPv4' else 6) or '%' in address:
                            raise ValueError('Address family mismatch.')
                    elif re.fullmatch(r'[A-Za-z0-9](?:[-A-Za-z0-9.]*[A-Za-z0-9])?\.?', address) is None:
                        raise ValueError('Unsupported FQDN address.')
                except ValueError as exc:
                    raise ValueError('Address shape/family does not match the supported addressType; values omitted.') from exc
            conditions = _obj(endpoint.get('conditions', {}), 'Endpoint conditions')
            ready, serving, terminating = (_flag(conditions, field) for field in FIELDS)
            combos[(ready, serving, terminating)] += 1
            if ready == 'True' and (serving == 'False' or terminating == 'True'):
                signals['ready_true_with_nonserving_or_terminating_flags_review'] += 1
            if any(value in {'Missing', 'Null'} for value in (ready, serving, terminating)):
                signals['some_condition_values_unreported_no_default_inference'] += 1
        ports = item.get('ports', [])
        if not isinstance(ports, list) or len(ports) > 100:
            raise ValueError('Slice ports must be an array of at most 100 records.')
        unspecified_ports = 0
        for port in ports:
            port = _obj(port, 'Slice port')
            number = port.get('port')
            if number is None:
                unspecified_ports += 1
            elif type(number) is not int or not 1 <= number <= 65535:
                raise ValueError('A supplied port number must be integer 1-65535 or null.')
            protocol = port.get('protocol')
            if protocol is not None and (not isinstance(protocol, str) or protocol not in {'TCP', 'UDP', 'SCTP'}):
                raise ValueError('Unsupported protocol; no silent protocol/port match is inferred.')
        rows.append({'slice_index': index, 'reported_address_type': address_type,
                     'service_name_label_present': service_label is not None,
                     'endpoint_records_in_slice': len(endpoints),
                     'condition_combinations': [dict(zip(FIELDS, flags), record_count=count) for flags, count in sorted(combos.items())],
                     'review_signal_record_counts': dict(signals), 'ports_field_present': 'ports' in item,
                     'port_records': len(ports), 'unspecified_port_records': unspecified_ports,
                     'service_association_verified': False, 'routing_verified': False, 'backend_health_verified': False})
    return {'slices_reviewed': len(rows), 'endpoint_records_in_snapshot': all_records, 'slices': rows,
            'continuation_token_present': bool(token), 'snapshot_freshness_verified': False,
            'inventory_completeness_verified': False, 'cluster_context_scope_verified': False,
            'unique_backends_computed': False, 'connectivity_verified': False,
            'source': SOURCE, 'service_source': SERVICE_SOURCE,
            'next_checks': ['Correlate slice_index with the private source; verify current context, namespace, Service identity/UID and complete associated slice inventory through separately authorized reads.',
                            'Review Service publishNotReadyAddresses, type/selector/ports, endpoint conditions, unique address/port/protocol combinations and workload readiness separately.',
                            'Use separately authorized client-side DNS/TCP/application evidence plus NetworkPolicy, proxy/CNI, ingress and network context before claiming connectivity or a cause.'],
            'limits': ('Supplied EndpointSlice record conditions only, not live Service connectivity, routing, healthy-backend counts or root cause. '
                       'Missing and null flags remain unreported values; API consumer default behavior is not simulated. '
                       'ready True is not verified serving/health: publishNotReadyAddresses can force it True. Serving+terminating endpoints may still receive traffic in some proxy scenarios. '
                       'Endpoints may occur in multiple slices. Counts are records, not unique endpoints, IP addresses, Pods, Services or healthy backends; no deduplication or traffic-routing eligibility is computed. '
                       'A Service label is not verified ownership or Service association. No Service object, selector, targetPort, publishNotReadyAddresses, NetworkPolicy, DNS, ingress, CNI or proxy state is evaluated. '
                       'Address/port shape validation does not prove valid API objects, routability, matching ports, unique listeners, ownership or reachability. FQDN handling is bounded text validation, not DNS resolution. '
                       'Names/namespaces/labels/addresses/target references, port names/numbers, topology/hints, messages and continuation tokens are omitted. '
                       'Empty endpoints/ports/slices or missing continuation never proves outage, no matching backends or complete inventory; other slices/scopes/Service types may apply. '
                       'No kubeconfig, kubectl/Helm/SDK/network/cluster call, probe, port-forward, deployment, patch, scale, remediation or payment occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_endpoint_slices_export(path):
    from jarvis.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json EndpointSlice export.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('EndpointSlice export must be regular and no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_endpoint_slices(document)


def register_endpoint_tools(registry):
    from jarvis.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_kubernetes_endpoints', description='Review existing local discovery.k8s.io/v1 EndpointSlice JSON condition-record combinations. Offline evidence only, not Service routing/connectivity, unique or healthy-backend counts or root cause. No cluster call/probe/change.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 JSON, max 2 MB/100 slices/2000 endpoint records. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_endpoint_slices_export, risk=Risk.SAFE, category='devops'))
