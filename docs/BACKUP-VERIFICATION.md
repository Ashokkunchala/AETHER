# AETHER selected-document backup verification

The existing `preview_document_backup` and confirmed `create_document_backup`
remain unchanged. A new SAFE read-only tool, `verify_document_backup`, reads a
saved archive back without extracting or restoring anything.

Use the exact archive path and `archive_sha256` from its reviewed creation
result, or a hash kept in a separately trusted record:

```text
verify_document_backup(
    path="C:\\Backups\\notes.zip",
    expected_archive_sha256="<64 hexadecimal characters>"
)
```

The hash is required. A hash supplied alongside an untrusted archive does not
prove authorship or safety. This checks byte integrity, not who made the backup.
Do not invent a hash or substitute a newly computed hash merely to clear a mismatch.

## Checks

- Regular local `.zip`, at most 20 MB. Symlink/junction paths and special files
  are refused using the existing path checks and bounded file reads.
- Stable read snapshot and full-archive SHA-256 matching the caller's expected
  value, before member decompression.
- Small ordinary single-disk, non-ZIP64 directory; at most 51 members and
  256 KB directory metadata, checked before central-entry allocation.
- Existing `aether-selected-documents-v1` manifest, numbered document members,
  no duplicate/unlisted/missing members, no directory/symlink/encrypted members,
  and only stored/deflated compression. This format identifier is preserved for
  compatibility; the display name is AETHER.
- Manifest capped at 256 KB; 1-50 files, at most 1 MB each and 10 MB total.
  Duplicate JSON fields, malformed sizes/hashes and inconsistent totals fail.
- Each document's bounded decompressed bytes, CRC, manifest size and SHA-256.
  File/header/CRC/decompression failures refuse integrity success.

Source/destination paths stored inside the manifest are data, not paths to
follow. Verification never opens those files, compares against current sources,
returns their content/paths, executes a script, invokes a shell, scans for malware,
extracts, restores, uploads, creates or overwrites anything. Moving/copying the
archive does not invalidate it if the bytes and expected hash remain unchanged.
The result describes the captured bytes; the on-disk file can change afterward.
Filesystem races/tampering are not fully prevented, so use a trusted directory.

## What success does not mean

`verified=true` means the read snapshot passed these integrity checks against
the supplied expected hash. It is not proof of encryption, application-consistent
snapshotting, recoverability, current-source equality, off-device storage,
retention, malware absence or a tested restore/disaster-recovery plan. Existing
archives are unencrypted and may contain private document content. Protect them
and their hash record. No new automated backup schedule or restore capability is
added. The existing creation approval and emergency-stop rules are retained;
this SAFE read remains available while stop blocks new writes.

Synthetic tests cover real read-back of temporary created archives, copy/source
changes, expected-hash mismatch, manifest/payload tampering, CRC corruption,
malformed/truncated/appended ZIPs, duplicate/extra/missing members, bounds,
encryption/compression flags, unsafe member names, symlink/FIFO refusal, no
source-path access and read availability after stop. No user backup was created,
read, changed, restored or deleted by this implementation work. Physical Windows
path/ACL acceptance and an actual restore exercise remain separate.

Python ZIP documentation checked November 16, 2026:
https://docs.python.org/3/library/zipfile.html
