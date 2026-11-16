import asyncio
import hashlib
import json
import os
import struct
import warnings
import zipfile

import pytest

from jarvis.backup import create_backup, preview_backup
from jarvis.backup_verify import verify_backup


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def saved(tmp_path):
    source = tmp_path / 'lesson.md'
    source.write_text('fictional practice')
    path = tmp_path / 'backup.zip'
    preview = preview_backup([str(source)], str(path))
    created = create_backup([str(source)], str(path), preview['expected_manifest'])
    return source, path, created


def rewrite(path, change):
    with zipfile.ZipFile(path) as archive:
        files = {info.filename: archive.read(info) for info in archive.infolist()}
    change(files)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)


def manifest_change(files, change):
    manifest = json.loads(files['manifest.json'])
    change(manifest)
    files['manifest.json'] = json.dumps(manifest).encode()


def test_saved_archive_reads_back_without_source_access_or_content_echo(saved, monkeypatch):
    source, path, created = saved
    import jarvis.backup_verify as module
    seen = []
    real = module.os.open
    def watched(value, *args, **kwargs):
        seen.append(str(value))
        return real(value, *args, **kwargs)
    monkeypatch.setattr(module.os, 'open', watched)
    before = path.read_bytes()
    result = verify_backup(str(path), created['archive_sha256'])
    assert result['verified'] and result['expected_hash_matched']
    assert result['files_checked'] == 1 and result['source_bytes'] == len(b'fictional practice')
    assert result['crc_checked'] and result['manifest_hashes_matched']
    assert not result['extracted'] and not result['source_paths_opened']
    assert seen == [str(path)]
    assert 'fictional practice' not in json.dumps(result) and str(source) not in json.dumps(result)
    assert path.read_bytes() == before and source.read_text() == 'fictional practice'


def test_snapshot_survives_copy_and_source_change_without_claiming_current_source(tmp_path, saved):
    source, path, created = saved
    copied = tmp_path / 'copied.zip'
    copied.write_bytes(path.read_bytes())
    source.write_text('changed since backup')
    result = verify_backup(str(copied), created['archive_sha256'].upper())
    assert result['verified'] and 'current-source comparison' in result['notice']


def test_wrong_expected_hash_rejected_before_parsing(saved):
    _, path, _ = saved
    with pytest.raises(ValueError, match='SHA-256 does not match'):
        verify_backup(str(path), '0' * 64)


@pytest.mark.parametrize('value', ['', 'not-a-hash', None, 'a' * 63, 'g' * 64])
def test_invalid_hash(value, saved):
    with pytest.raises(ValueError):
        verify_backup(str(saved[1]), value)


@pytest.mark.parametrize('mutation', [
    lambda m: m.update(format='unknown'),
    lambda m: m.update(files=[]),
    lambda m: m.update(total_bytes=True),
    lambda m: m.update(total_bytes=999),
    lambda m: m['files'][0].update(bytes=True),
    lambda m: m['files'][0].update(bytes=-1),
    lambda m: m['files'][0].update(bytes=1000001),
    lambda m: m['files'][0].update(sha256='0' * 64),
    lambda m: m['files'][0].update(sha256='nope'),
    lambda m: m['files'][0].update(member='../outside.md'),
    lambda m: m['files'][0].update(member='files/002.md'),
    lambda m: m['files'].append(m['files'][0]),
])
def test_bad_manifest_never_reports_integrity_success(mutation, saved):
    _, path, _ = saved
    rewrite(path, lambda files: manifest_change(files, mutation))
    with pytest.raises(ValueError):
        verify_backup(str(path), sha(path))


@pytest.mark.parametrize('mutation', [
    lambda files: files.update({'files/001.md': b'changed payload'}),
    lambda files: files.pop('files/001.md'),
    lambda files: files.update({'../outside.md': b'never extract'}),
    lambda files: files.update({'extra.txt': b'not listed'}),
    lambda files: files.update({'manifest.json': b'{"format":1,"format":2}'}),
    lambda files: files.update({'manifest.json': b'[' * 2000}),
    lambda files: files.update({'manifest.json': b'x' * 256001}),
])
def test_changed_payload_missing_extra_or_bad_manifest(mutation, saved, tmp_path):
    _, path, _ = saved
    rewrite(path, mutation)
    with pytest.raises(ValueError):
        verify_backup(str(path), sha(path))
    assert not (tmp_path.parent / 'outside.md').exists()


def test_stored_source_path_is_never_opened_or_returned(saved):
    _, path, _ = saved
    value = '/never/open/PRIVATE_SENTINEL.txt'
    rewrite(path, lambda files: manifest_change(files, lambda m: m['files'][0].update(source=value)))
    result = verify_backup(str(path), sha(path))
    assert result['verified'] and value not in json.dumps(result)


def test_duplicate_member_and_symlink_members_refused(saved):
    _, path, _ = saved
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(path, 'a') as archive:
            archive.writestr('files/001.md', b'duplicate')
    with pytest.raises(ValueError, match='Duplicate'):
        verify_backup(str(path), sha(path))
    path.unlink()  # test fixture only, never a user record
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('manifest.json', '{}')
        info = zipfile.ZipInfo('files/001.md')
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, 'target')
    with pytest.raises(ValueError, match='symlinks'):
        verify_backup(str(path), sha(path))


def test_oversized_directory_checked_before_zipfile_allocation(saved, monkeypatch):
    import jarvis.backup_verify as module
    _, path, _ = saved
    raw = bytearray(path.read_bytes())
    offset = raw.rfind(b'PK\x05\x06')
    struct.pack_into('<H', raw, offset + 8, 52)
    struct.pack_into('<H', raw, offset + 10, 52)
    path.write_bytes(raw)
    monkeypatch.setattr(module.zipfile, 'ZipFile', lambda *a, **kw: pytest.fail('must reject before parsing ZIP'))
    with pytest.raises(ValueError, match='limits'):
        verify_backup(str(path), sha(path))


def test_outer_file_and_uncompressed_member_limits(saved, monkeypatch):
    import jarvis.backup_verify as module
    _, path, _ = saved
    monkeypatch.setattr(module, 'MAX_ARCHIVE_BYTES', 10)
    with pytest.raises(ValueError):
        verify_backup(str(path), sha(path))
    monkeypatch.setattr(module, 'MAX_ARCHIVE_BYTES', 20000000)
    rewrite(path, lambda files: files.update({'files/001.md': b'x' * 1000001}))
    with pytest.raises(ValueError, match='size limit'):
        verify_backup(str(path), sha(path))


def test_corrupted_compressed_payload_fails_crc_or_decompression(saved):
    _, path, _ = saved
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('files/001.md')
    raw = bytearray(path.read_bytes())
    name_len, extra_len = struct.unpack_from('<HH', raw, info.header_offset + 26)
    offset = info.header_offset + 30 + name_len + extra_len
    raw[offset] ^= 255
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        verify_backup(str(path), sha(path))


def test_truncated_appended_and_nonzip_files_refused(saved):
    _, path, _ = saved
    original = path.read_bytes()
    for raw in [b'not zip', original[:-8], original + b'extra']:
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            verify_backup(str(path), sha(path))


def test_symlink_and_fifo_outer_paths_refused(saved, tmp_path):
    _, path, created = saved
    link = tmp_path / 'link.zip'
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip('symlinks unavailable')
    with pytest.raises(ValueError, match='Symlink'):
        verify_backup(str(link), created['archive_sha256'])
    if hasattr(os, 'mkfifo'):
        pipe = tmp_path / 'pipe.zip'
        os.mkfifo(pipe)
        with pytest.raises(ValueError, match='regular'):
            verify_backup(str(pipe), '0' * 64)


def test_safe_verifier_available_after_stop_but_never_restores(saved, tmp_path, monkeypatch):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'safety.db'))
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('verify_document_backup', {'path': str(saved[1]), 'expected_archive_sha256': saved[2]['archive_sha256']}))
    assert result.ok and result.data['verified'] and not result.data['restored']


def test_encrypted_flag_and_unsupported_compression_refused(saved):
    _, path, _ = saved
    original = path.read_bytes()
    for flag_encrypted in [True, False]:
        raw = bytearray(original)
        offset = raw.find(b'PK\x01\x02')
        if flag_encrypted:
            old = struct.unpack_from('<H', raw, offset + 8)[0]
            struct.pack_into('<H', raw, offset + 8, old | 1)
        else:
            struct.pack_into('<H', raw, offset + 10, zipfile.ZIP_BZIP2)
        path.write_bytes(raw)
        with pytest.raises(ValueError, match='encrypted|compression'):
            verify_backup(str(path), sha(path))
