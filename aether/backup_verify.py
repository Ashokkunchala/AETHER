"""Read-back verification of bounded selected-document ZIPs. Never extracts."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import struct
import zipfile
import zlib

from aether.backup import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES, _path
from aether.memory.doc_memory import INDEXABLE_SUFFIXES

MAX_ARCHIVE_BYTES = 20_000_000
MAX_MANIFEST_BYTES = 256_000
MAX_DIRECTORY_BYTES = 256_000


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate manifest fields are not supported.')
        result[key] = value
    return result


def _directory_bounds(raw):
    # Restrict our small non-ZIP64 format before ZipFile allocates central entries.
    # EOCD: signature, disk, directory disk, entries on disk, all entries,
    # central-directory bytes, directory offset, comment bytes.
    offset = raw.rfind(b'PK\x05\x06', max(0, len(raw) - 65557))
    if offset < 0 or offset + 22 > len(raw):
        raise ValueError('Missing or incomplete ZIP directory.')
    _, disk, directory_disk, count_disk, count, size, start, comment = struct.unpack_from('<4s4H2LH', raw, offset)
    if disk != 0 or directory_disk != 0 or count != count_disk:
        raise ValueError('Multi-disk ZIPs are not supported.')
    if not 2 <= count <= MAX_FILES + 1 or size > MAX_DIRECTORY_BYTES:
        raise ValueError('ZIP directory exceeds the supported member or metadata limits.')
    if start + size != offset or offset + 22 + comment != len(raw):
        raise ValueError('Only complete ordinary non-ZIP64 archives without appended data are supported.')
    return count


def _read_member(archive, info, limit):
    if info.file_size > limit:
        raise ValueError('Uncompressed member exceeds the supported size limit.')
    with archive.open(info) as stream:
        payload = stream.read(limit + 1)
        # Reaching EOF lets zipfile check headers/CRC. Never extract to disk.
        if len(payload) > limit or stream.read(1):
            raise ValueError('Uncompressed member exceeds the supported size limit.')
    if len(payload) != info.file_size or (zlib.crc32(payload) & 0xffffffff) != info.CRC:
        raise ValueError('Member size or CRC mismatch.')
    return payload


def verify_backup(path, expected_archive_sha256):
    if not isinstance(expected_archive_sha256, str) or re.fullmatch(r'[0-9a-fA-F]{64}', expected_archive_sha256) is None:
        raise ValueError('Provide the expected archive SHA-256 from the reviewed creation result or a separately trusted record.')
    source = _path(path)
    if source.suffix.lower() != '.zip' or not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('Choose a regular local .zip file, not a directory or special file.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(source, flags)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_ARCHIVE_BYTES:
            raise ValueError('Archive must be a regular file no larger than 20 MB.')
        raw = stream.read(MAX_ARCHIVE_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > MAX_ARCHIVE_BYTES or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Archive changed while reading or exceeded the size limit. Verify a stable copy.')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_archive_sha256.lower():
        raise ValueError('Archive SHA-256 does not match the supplied expected hash. No integrity success is claimed.')
    count = _directory_bounds(raw)
    try:
        with zipfile.ZipFile(io.BytesIO(raw), 'r') as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) != count or len(set(names)) != len(names) or names.count('manifest.json') != 1:
                raise ValueError('Duplicate, missing or inconsistent ZIP members.')
            for info in infos:
                if info.is_dir() or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError('Directories, encrypted members and symlinks are not supported.')
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError('Unsupported ZIP compression method.')
            manifest_info = archive.getinfo('manifest.json')
            try:
                manifest = json.loads(_read_member(archive, manifest_info, MAX_MANIFEST_BYTES), object_pairs_hook=_unique,
                                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite manifest value.')))
            except (UnicodeError, RecursionError, ValueError) as exc:
                raise ValueError('Malformed or oversized backup manifest.') from exc
            if not isinstance(manifest, dict) or manifest.get('format') != 'aether-selected-documents-v1':
                raise ValueError('Not a supported selected-document backup format.')
            records = manifest.get('files')
            if not isinstance(records, list) or not 1 <= len(records) <= MAX_FILES:
                raise ValueError('Manifest requires 1-50 document records.')
            expected_names, total = {'manifest.json'}, 0
            suffixes = INDEXABLE_SUFFIXES | {'.pdf', '.docx', '.xlsx', '.pptx'}
            for index, record in enumerate(records, 1):
                if not isinstance(record, dict):
                    raise ValueError('Malformed manifest record.')
                member, size, file_hash = (record.get(k) for k in ('member', 'bytes', 'sha256'))
                if not isinstance(member, str) or re.fullmatch(r'files/[0-9]{3}\.[a-z0-9]+', member) is None:
                    raise ValueError('Unsupported or unsafe member name.')
                suffix = '.' + member.rsplit('.', 1)[1]
                if suffix not in suffixes or member != f'files/{index:03}{suffix}':
                    raise ValueError('Member does not match the numbered document format.')
                if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
                    raise ValueError('Invalid manifest file size.')
                if not isinstance(file_hash, str) or re.fullmatch(r'[0-9a-f]{64}', file_hash) is None:
                    raise ValueError('Invalid manifest file hash.')
                if member in expected_names or member not in names:
                    raise ValueError('Duplicate or missing manifest file member.')
                expected_names.add(member)
                total += size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError('Backup exceeds the 10 MB document total limit.')
                payload = _read_member(archive, archive.getinfo(member), MAX_FILE_BYTES)
                if len(payload) != size or hashlib.sha256(payload).hexdigest() != file_hash:
                    raise ValueError('Document bytes do not match their manifest hash or size.')
            if set(names) != expected_names or type(manifest.get('total_bytes')) is not int or manifest['total_bytes'] != total:
                raise ValueError('Extra members or inconsistent manifest total.')
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError) as exc:
        raise ValueError('ZIP integrity verification failed. No file was extracted or restored.') from exc
    return {'verified': True, 'scope': 'Archive byte snapshot integrity only',
            'archive_sha256': digest, 'expected_hash_matched': True,
            'files_checked': len(records), 'source_bytes': total, 'archive_bytes': len(raw),
            'crc_checked': True, 'manifest_hashes_matched': True,
            'extracted': False, 'restored': False, 'source_paths_opened': False,
            'notice': ('Read-only verification of the captured bytes against the supplied expected hash and internal manifest. '
                       'The hash must come from a separately trusted record; a hash supplied with an untrusted archive proves no authorship. '
                       'Stored source/destination paths are data and were not opened. No content or source paths returned. '
                       'Not malware scanning, encryption, current-source comparison, application consistency, restore testing or disaster recovery. '
                       'The on-disk file can change after this read; filesystem tampering is not fully prevented. No upload or extraction occurred.')}


def register_backup_verifier(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='verify_document_backup', description='Read back a selected-document ZIP against its separately trusted expected SHA-256, bounded member CRCs and manifest hashes. No extraction, restore, upload, source-path access or writes. Does not establish authorship or disaster recovery.',
        parameters={'type': 'object', 'properties': {
            'path': {'type': 'string', 'description': 'Existing regular selected-document .zip file, at most 20 MB, trusted local directory.'},
            'expected_archive_sha256': {'type': 'string', 'description': '64 hexadecimal characters from the reviewed creation result or separately trusted record, not just the same untrusted source.'}},
            'required': ['path', 'expected_archive_sha256'], 'additionalProperties': False},
        handler=verify_backup, risk=Risk.SAFE, category='files'))
