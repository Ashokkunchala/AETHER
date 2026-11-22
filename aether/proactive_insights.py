"""Read-only insight helpers behind proactive alerts.

Everything here is local, bounded and recommendation-only: no cleanup, no
deletion, no process kill, no network call and no message sending. AWS cost
review is pure arithmetic over numbers the caller supplies; crash log review is
heuristic extraction over supplied text.
"""
from __future__ import annotations

import math
import os
import re
from pathlib import Path

MAX_WALK_ENTRIES = 20_000
MAX_WALK_DEPTH = 8
MAX_LOG_CHARS = 200_000
MAX_SERVICES = 100


def cpu_offenders(limit: int = 5):
    """Instantaneous top CPU processes. A sample, not proof of cause."""
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Limit must be 1-20.')
    import psutil

    # First call primes per-process counters; the 0.2s pause makes the second read meaningful.
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    psutil.cpu_percent(interval=0.2)
    ranked = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            ranked.append((proc.cpu_percent(interval=None), proc.info['pid'], (proc.info['name'] or '')[:80]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    top = sorted(ranked, reverse=True)[:limit]
    return {
        'processes': [{'name': name, 'pid': pid, 'cpu_percent': round(pct, 1)} for pct, pid, name in top],
        'notice': 'One instantaneous local sample after a 0.2s calibration; per-process percent can exceed 100 on multi-core and a brief spike is not proof of cause for the listed processes. No process was stopped or changed.',
    }


def disk_large_files(path: str, limit: int = 20):
    """Largest files under one chosen local directory. Lists only; never deletes."""
    if not isinstance(path, str) or not path or len(path) > 1000 or '\x00' in path:
        raise ValueError('Choose an existing local directory path.')
    root = Path(path).expanduser()
    if not root.is_absolute() or root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise ValueError('Choose a canonical existing local directory; no symlinks.')
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Limit must be 1-100.')
    scanned, skipped = 0, 0
    largest: list[tuple[int, str]] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        depth = len(Path(current).relative_to(root).parts)
        if depth >= MAX_WALK_DEPTH:
            dirs[:] = []
        dirs[:] = [d for d in dirs if not Path(current, d).is_symlink()]
        for name in files:
            scanned += 1
            if scanned > MAX_WALK_ENTRIES:
                break
            entry = Path(current, name)
            try:
                if entry.is_symlink():
                    skipped += 1
                    continue
                largest.append((entry.stat().st_size, str(entry)))
            except OSError:
                skipped += 1
        if scanned > MAX_WALK_ENTRIES:
            break
    largest.sort(reverse=True)
    return {
        'root': str(root),
        'entries_scanned': min(scanned, MAX_WALK_ENTRIES),
        'scan_capped': scanned > MAX_WALK_ENTRIES,
        'unreadable_skipped': skipped,
        'largest_files': [{'path': p, 'size_bytes': s} for s, p in largest[:limit]],
        'notice': 'Read-only listing of the largest files found; bounded depth, count and no symlink following. Nothing was moved, deleted or recommended for deletion: review each entry yourself before any cleanup. Large is not the same as safe to remove.',
    }


def _cost_map(value, label):
    if not isinstance(value, dict) or not 1 <= len(value) <= MAX_SERVICES:
        raise ValueError(f'{label} must be a mapping of 1-{MAX_SERVICES} service names to USD amounts.')
    result = {}
    for key, amount in value.items():
        if not isinstance(key, str) or not 1 <= len(key) <= 100:
            raise ValueError(f'{label} service names must be 1-100 characters.')
        if type(amount) not in (int, float) or not math.isfinite(amount) or not 0 <= amount <= 1e9:
            raise ValueError(f'{label} amounts must be finite USD from 0 to 1e9.')
        result[key] = float(amount)
    return result


def cost_spike_review(previous: dict, current: dict):
    """Arithmetic over caller-supplied per-service USD maps. Never calls AWS."""
    before, after = _cost_map(previous, 'previous'), _cost_map(current, 'current')
    before_total, after_total = sum(before.values()), sum(after.values())
    movers = []
    for service in sorted(set(before) | set(after)):
        delta = after.get(service, 0.0) - before.get(service, 0.0)
        movers.append({'service': service, 'previous_usd': round(before.get(service, 0.0), 4), 'current_usd': round(after.get(service, 0.0), 4), 'delta_usd': round(delta, 4)})
    movers.sort(key=lambda item: abs(item['delta_usd']), reverse=True)
    delta = after_total - before_total
    return {
        'previous_total_usd': round(before_total, 4),
        'current_total_usd': round(after_total, 4),
        'delta_usd': round(delta, 4),
        'percent_change': round(delta / before_total * 100, 2) if before_total > 0 else None,
        'top_movers': movers[:10],
        'notice': 'Arithmetic only over the numbers supplied; no AWS or network call was made and figures were not verified against any bill. A large delta names where to look, not why; percentage is empty when the previous total was zero.',
    }


_ERROR_LINE = re.compile(r'error|exception|fatal|panic|traceback|failed|segfault', re.IGNORECASE)
_CANDIDATES = (
    (re.compile(r'outofmemory|memoryerror|cannot allocate', re.IGNORECASE), 'possible memory exhaustion'),
    (re.compile(r'permission denied|access denied|eacces', re.IGNORECASE), 'possible permission problem'),
    (re.compile(r'connection refused|econnrefused|no route to host', re.IGNORECASE), 'possible refused network connection'),
    (re.compile(r'timed?\s*out|deadline exceeded', re.IGNORECASE), 'possible timeout'),
    (re.compile(r'assertion|assert', re.IGNORECASE), 'possible failed assertion'),
    (re.compile(r'segfault|segmentation fault|access violation', re.IGNORECASE), 'possible native crash'),
    (re.compile(r'no such file|filenotfound|enoent', re.IGNORECASE), 'possible missing file'),
)


def _signature(line):
    text = re.sub(r'0x[0-9a-fA-F]+|\b\d+\b', '#', line)
    text = re.sub(r'[^\w \-.:#]', ' ', text)
    return ' '.join(text.split())[:120]


def crash_log_review(text: str):
    """Heuristic extraction over supplied crash log text. Not a diagnosis."""
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_LOG_CHARS:
        raise ValueError(f'Supply log text of 1-{MAX_LOG_CHARS} characters.')
    lines = [line.strip() for line in text.splitlines() if _ERROR_LINE.search(line)]
    groups: dict[str, dict] = {}
    for line in lines[:200]:
        signature = _signature(line)
        if not signature:
            continue
        entry = groups.setdefault(signature, {'count': 0, 'example': line[:300]})
        entry['count'] += 1
    ranked = sorted(groups.values(), key=lambda item: item['count'], reverse=True)[:10]
    candidates = sorted({label for pattern, label in _CANDIDATES if pattern.search(text)})
    return {
        'log_lines': len(text.splitlines()),
        'error_like_lines': len(lines),
        'groups': ranked,
        'candidate_pointers': candidates,
        'notice': 'Heuristic keyword grouping over the supplied text only; no files, event logs or systems were read. Candidate pointers are places to start, not causes, and nothing was captured or changed on the machine.',
    }


def register_proactive_insights(registry):
    from aether.tools.registry import Risk, Tool
    definitions = [
        ('proactive_cpu_offenders', 'Instantaneous top-CPU process sample (names, PIDs, percent) to review after a high-CPU alert. A sample, not proof of cause; nothing is stopped.', cpu_offenders, Risk.SAFE,
         {'limit': {'type': 'integer'}}, []),
        ('proactive_disk_large_files', 'List the largest files under one chosen local directory after a disk alert. Read-only bounded walk; nothing is moved, deleted or recommended for deletion.', disk_large_files, Risk.SAFE,
         {'path': {'type': 'string'}, 'limit': {'type': 'integer'}}, ['path']),
        ('proactive_cost_spike_review', 'Compare caller-supplied previous/current per-service USD maps: totals, delta, percent and top movers. Pure arithmetic; never calls AWS or verifies figures.', cost_spike_review, Risk.SAFE,
         {'previous': {'type': 'object'}, 'current': {'type': 'object'}}, ['previous', 'current']),
        ('proactive_crash_log_review', 'Heuristic error-line grouping and candidate pointers over supplied crash log text. Reads no files or systems; not a diagnosis.', crash_log_review, Risk.SAFE,
         {'text': {'type': 'string'}}, ['text']),
    ]
    for name, description, handler, risk, properties, required in definitions:
        registry.register(Tool(name=name, description=description,
                               parameters={'type': 'object', 'properties': properties, 'required': required},
                               handler=handler, risk=risk, category='proactive',
                               requires_confirmation=False, never_auto_approve=False))
