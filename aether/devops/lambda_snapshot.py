"""Offline Lambda function snapshot triage, never troubleshooting or deprecation verdicts."""
from __future__ import annotations

import json
import os
import stat
from collections import Counter

SOURCE = 'https://docs.aws.amazon.com/cli/latest/reference/lambda/list-functions.html'
MAX_BYTES = 2_000_000
MAX_FUNCTIONS = 500
PACKAGE_TYPES = {'Zip', 'Image'}


def _text(value, label, limit=200):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label} must be nonempty bounded text without control characters.')
    return value


def _count(obj, field, maximum):
    value = obj.get(field)
    if value is not None and (type(value) is not int or not 1 <= value <= maximum):
        raise ValueError(f'{field} must be an integer from 1 to {maximum} when supplied.')
    return value


def review_lambda_functions(document):
    if not isinstance(document, dict) or not isinstance(document.get('Functions'), list):
        raise ValueError('Supply an unmodified list-functions JSON object with a Functions array.')
    functions = document['Functions']
    if len(functions) > MAX_FUNCTIONS:
        raise ValueError('Scope the supplied snapshot to at most 500 functions.')
    marker = document.get('NextMarker')
    if marker is not None and not isinstance(marker, str):
        raise ValueError('NextMarker must be text or null.')
    runtimes, packages = Counter(), Counter()
    rows = []
    for position, function in enumerate(functions):
        if not isinstance(function, dict):
            raise ValueError('Each function must be an object.')
        runtime = function.get('Runtime')
        if runtime is not None:
            runtime = _text(runtime, 'Runtime', 100)
        package = function.get('PackageType')
        if package is not None:
            package = _text(package, 'PackageType', 50)
        architectures = function.get('Architectures')
        if architectures is not None:
            if not isinstance(architectures, list) or not 1 <= len(architectures) <= 5:
                raise ValueError('Architectures must be a list of at most 5 entries.')
            architectures = [_text(item, 'Architecture', 50) for item in architectures]
        memory = _count(function, 'MemorySize', 10_240)
        timeout = _count(function, 'Timeout', 900)
        code_size = function.get('CodeSize')
        if code_size is not None and (type(code_size) is not int or code_size < 0):
            raise ValueError('CodeSize must be a nonnegative integer when supplied.')
        signals = []
        if package is not None and package not in PACKAGE_TYPES:
            signals.append('unrecognized_package_type')
        if memory is not None and memory >= 10_240:
            signals.append('reported_memory_at_maximum')
        if timeout is not None and timeout >= 900:
            signals.append('reported_timeout_at_maximum')
        runtimes[runtime or 'not_reported'] += 1
        packages[package or 'not_reported'] += 1
        rows.append({'function': f'function[{position}]', 'reported_runtime': runtime,
                     'reported_package_type': package, 'reported_architectures': architectures,
                     'reported_memory_mb': memory, 'reported_timeout_s': timeout,
                     'reported_code_size_bytes': code_size, 'signals': signals})
    return {'functions_reviewed': len(rows), 'by_reported_runtime': dict(runtimes),
            'by_reported_package_type': dict(packages), 'functions': rows,
            'pagination_marker_present': bool(marker), 'inventory_completeness_verified': False,
            'snapshot_freshness_verified': False, 'account_region_scope_verified': False,
            'source': SOURCE,
            'next_checks': ['Verify the current account, region and pagination through an authorized read.',
                            'Investigate errors via approved CloudWatch log/metric reads; this snapshot carries no invocation data.'],
            'limits': ('Supplied list-functions snapshot only: reported configuration fields as supplied, not troubleshooting, '
                       'invocation/error/latency evidence, a deprecation or end-of-life verdict, cost attribution or proof a change is safe. '
                       'No runtime support status is inferred; verify current AWS runtime deprecation dates separately. '
                       'Function names, role, handler, description, environment variables, layers, code location, versions, '
                       'aliases, VPC config, KMS keys, tags and free-form values are omitted; function[n] labels follow the supplied order. '
                       'A missing NextMarker does not prove all pages/regions were supplied. '
                       'No AWS/SDK/CLI/network call, invoke, update, publish, delete or credential access occurs.')}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON fields are not supported.')
        result[key] = value
    return result


def review_lambda_functions_export(path):
    # Same no-symlink/junction path hygiene as the other snapshot exports.
    from aether.backup import _path
    source = _path(path)
    if source.suffix.lower() != '.json' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .json list-functions export, not a directory or special file.')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('Lambda export must be a regular file no larger than 2 MB.')
        payload = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(payload) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Export changed during read or exceeded 2 MB. Supply a stable scoped copy.')
    try:
        document = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON.')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('Supply valid UTF-8 JSON without duplicate fields or non-finite values.') from exc
    return review_lambda_functions(document)


def register_lambda_tools(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='review_lambda_functions',
        description='Review an existing local list-functions JSON snapshot: reported runtime, package type, memory, timeout and code size per supplied function. Offline triage only; not troubleshooting, deprecation verdicts or invocation evidence. No AWS access; names, environment and layers omitted.',
        parameters={'type': 'object', 'properties': {'path': {'type': 'string', 'description': 'Existing regular local UTF-8 .json lambda list-functions export, max 2 MB/500 functions. No credentials.'}}, 'required': ['path'], 'additionalProperties': False},
        handler=review_lambda_functions_export, risk=Risk.SAFE, category='devops'))
