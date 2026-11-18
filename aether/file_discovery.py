"""Bounded metadata-only filename discovery and organization suggestions.

Owner-selected local roots only. No file contents, hashes, moves or uploads.
Path checks are best effort, not an OS sandbox against concurrent local changes.
"""
from __future__ import annotations

import json
import os
import stat
import time
from datetime import UTC, datetime
from pathlib import Path

MAX_ENTRIES = 2000
MAX_RESULTS = 100
MAX_DEPTH = 4
MAX_SECONDS = 3


def _link(st):
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, 'st_file_attributes', 0) & 0x400)


def _local_directory(value):
    if not isinstance(value, str) or not value or len(value) > 1024 or any(ord(c) < 32 for c in value):
        raise ValueError('Use an explicit bounded absolute local folder path.')
    if value.startswith(('\\\\', '//')) or (os.name == 'nt' and value.startswith('\\')):
        raise ValueError('Network and device paths are not supported.')
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or path == Path(path.anchor):
        raise ValueError('A local subfolder is required, not a drive/filesystem root.')
    for part in reversed([path, *path.parents]):
        st = part.lstat()
        if _link(st) or not stat.S_ISDIR(st.st_mode):
            raise ValueError('Folder components must be real directories, no links/reparse points.')
    return path


def preview(root, query='', mode='search'):
    if not isinstance(query, str) or len(query) > 100 or any(ord(c) < 32 for c in query):
        raise ValueError('Use a literal filename substring up to100 characters, no controls.')
    if mode not in ('search', 'plan'):
        raise ValueError('Mode must be search or plan.')
    try:
        roots = json.loads(os.environ.get('AETHER_FILE_ROOTS', '[]'))
    except (ValueError, TypeError) as exc:
        raise ValueError('Configure AETHER_FILE_ROOTS as a JSON list of explicit absolute local folders.') from exc
    if not isinstance(roots, list) or not 1 <= len(roots) <= 10:
        raise ValueError('File discovery is off until1-10 explicit folders are owner-configured.')
    # Match lexical normalized paths, not an unreviewed descendant or resolved link.
    if not isinstance(root, str) or not any(isinstance(r, str) and os.path.normcase(os.path.normpath(r)) == os.path.normcase(os.path.normpath(root)) for r in roots):
        raise ValueError('Exact folder is not in the owner-configured roots.')
    path = _local_directory(root)
    return {'root': str(path), 'query': query, 'mode': mode, 'limits': {'entries': MAX_ENTRIES, 'results': MAX_RESULTS, 'depth': MAX_DEPTH, 'seconds': MAX_SECONDS}, 'notice': 'Reads names, file sizes and modification dates under this exact folder. Hidden folders, links/reparse points, special files and other devices are skipped. No contents or hashes read. Plan only suggests groups, never moves/deletes/renames/opens/uploads. Names/results may reach your configured AI through the existing chat workflow.'}


def _stopped():
    from aether.security import SecurityStore
    return SecurityStore().stopped()


def _group(filename):
    suffix = Path(filename).suffix.casefold()
    for group, extensions in {
        'Documents': {'.pdf', '.txt', '.md', '.docx', '.odt', '.rtf'},
        'Spreadsheets': {'.csv', '.tsv', '.xlsx', '.ods'},
        'Presentations': {'.pptx', '.odp'},
        'Images': {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.heic', '.svg'},
        'Audio': {'.mp3', '.wav', '.m4a', '.flac', '.ogg'},
        'Video': {'.mp4', '.mkv', '.mov', '.webm'},
        'Archives': {'.zip', '.gz', '.tar', '.7z'},
    }.items():
        if suffix in extensions:
            return group
    return 'Review manually'


def discover_files(root, query='', mode='search'):
    plan = preview(root, query, mode)
    path = Path(plan['root'])
    if _stopped():
        raise RuntimeError('Emergency stop active; no inventory returned.')
    root_stat = path.lstat()
    started = time.monotonic()
    stack = [(path, 0)]
    rows = []
    scanned = skipped = 0
    reasons = set()
    aborted = False
    while stack and not aborted:
        current, depth = stack.pop()
        try:
            # Recheck lexical ancestry immediately before enumeration. Races remain.
            _local_directory(str(current))
            current_stat = current.lstat()
            if current_stat.st_dev != root_stat.st_dev:
                skipped += 1
                reasons.add('other filesystem skipped')
                continue
            with os.scandir(current) as entries:
                for entry in entries:
                    if scanned >= MAX_ENTRIES or time.monotonic() - started >= MAX_SECONDS:
                        reasons.add('entry/time limit reached')
                        aborted = True
                        break
                    if scanned % 32 == 0 and _stopped():
                        raise RuntimeError('Emergency stop active; inventory discarded.')
                    scanned += 1
                    if entry.name.startswith('.') or any(ord(c) < 32 for c in entry.name):
                        skipped += 1
                        continue
                    try:
                        metadata = entry.stat(follow_symlinks=False)
                        if _link(metadata) or metadata.st_dev != root_stat.st_dev or bool(getattr(metadata, 'st_file_attributes', 0) & 0x6):
                            skipped += 1
                            continue
                        if stat.S_ISDIR(metadata.st_mode):
                            if depth < MAX_DEPTH:
                                stack.append((Path(entry.path), depth + 1))
                            else:
                                skipped += 1
                                reasons.add('depth limit reached')
                            continue
                        if not stat.S_ISREG(metadata.st_mode):
                            skipped += 1
                            continue
                        if query.casefold() not in entry.name.casefold():
                            continue
                        row = {'relative_path': str(Path(entry.path).relative_to(path)), 'bytes': metadata.st_size, 'modified_utc': datetime.fromtimestamp(metadata.st_mtime, UTC).isoformat()}
                        if mode == 'plan':
                            row['suggested_group'] = _group(entry.name)
                        rows.append(row)
                        if len(rows) >= MAX_RESULTS:
                            reasons.add('result limit reached')
                            aborted = True
                            break
                    except (OSError, ValueError, OverflowError):
                        skipped += 1
                        reasons.add('unreadable or changed entries skipped')
        except (OSError, ValueError):
            skipped += 1
            reasons.add('unreadable or changed folders skipped')
    if _stopped():
        raise RuntimeError('Emergency stop active; inventory discarded.')
    rows.sort(key=lambda row: row['relative_path'].casefold())
    return {'root': str(path), 'query': query, 'mode': mode, 'files': rows, 'entries_examined': scanned, 'skipped_entries': skipped, 'bounded_walk_finished': not reasons, 'limits_or_errors': sorted(reasons), 'notice': 'Partial metadata snapshot, not a full disk search or verified file type. Hidden entries and links are always excluded. An empty result does not prove a file is absent. Extension-based groups are suggestions only; no folders created or files moved. Sizes/dates may change and directory iteration order decides which limited results appear. No content/duplicate check, opening, provider send or upload performed by this tool.'}


def register_file_discovery(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(name='discover_local_files', description='Search literal filenames and optionally suggest extension-based groups within one exact owner-configured local folder. Metadata only, bounded partial results, never moves/deletes/uploads. Fresh review required.', parameters={'type': 'object', 'properties': {'root': {'type': 'string', 'description': 'Exact absolute folder explicitly present in owner AETHER_FILE_ROOTS JSON list.'}, 'query': {'type': 'string', 'description': 'Literal case-insensitive filename substring, empty for all bounded files.'}, 'mode': {'type': 'string', 'enum': ['search', 'plan']}}, 'required': ['root'], 'additionalProperties': False}, handler=discover_files, confirmation_preview=preview, risk=Risk.MEDIUM, category='filesystem', requires_confirmation=True, never_auto_approve=True, allow_always=False, allow_auto_approve=False))


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description='Review-only AETHER local filename discovery')
    parser.add_argument('--root', required=True)
    parser.add_argument('--query', default='')
    parser.add_argument('--mode', choices=['search', 'plan'], default='search')
    args = parser.parse_args()
    print(json.dumps(preview(args.root, args.query, args.mode), indent=2))
    if not sys.stdin.isatty() or input('Type READ FOLDER METADATA after reviewing this exact scope: ') != 'READ FOLDER METADATA':
        raise SystemExit('Not approved. No folder inventory read.')
    print(json.dumps(discover_files(args.root, args.query, args.mode), indent=2))


if __name__ == '__main__':
    main()
