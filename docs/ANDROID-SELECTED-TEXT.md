# AETHER Android selected local text preview and find

LOCAL PHONE ACTIONS includes a separate selected-text panel. It uses Android's
system document picker for one text/plain or text/markdown document, then waits
for an explicit "Read selected text locally" button. A content URI and matching
reported MIME are required. No broad storage, directory-tree grant, persistent
URI permission or new manifest permission is requested. Picker selection alone
never uploads, executes, copies or sends a document to chat/a model.

The provider may download a remote document and use data even though AETHER makes
no network request here. Choose a trusted item appropriate to display locally.
A provider's MIME/name is not verified identity, safe-file certification, latest
version or proof that it is not a secret. Reading/displaying private text is an
explicit user action. No scan of other documents, file move/delete/rename,
organization, OCR, PDF/DOCX parsing, image analysis or automatic summary is added.

Reading runs on an I/O dispatcher, requests at most 65536 bytes plus one detection
byte, and refuses oversize input rather than displaying a silently partial file.
Strict UTF-8 decoding rejects malformed bytes. A leading UTF-8 BOM is removed;
CRLF/CR newlines become LF, and selected control/bidi-format characters are
replaced with U+FFFD with a visible replacement count. This is not exact byte
reproduction, full Unicode spoof detection or an encoding detector. HTML/Markdown
content is plain Compose Text, never rendered as markup or followed as instructions.
The preview has a bounded-height scroll area. Empty text is explicitly identified.

The optional local find uses literal case-insensitive substring matching on the
captured normalized preview, returning one-based matching line numbers, first 100
with a truncation flag. It is not regex or semantic search, not a device-wide file
search, and not current-source revalidation. A zero is no match in that captured
preview only. Cross-line queries do not match. Query is bounded to 200 characters.

Clear/cancel/new selection discards displayed text and blocks late results from
appearing; a generation check prevents an older read from changing a newer read's
busy state. Provider I/O cancellation is not guaranteed: blocked third-party
provider operations may finish later and use resources. There is no hard provider
wall-clock timeout. Streams are closed when reading exits. The text stays in
transient Compose state, not saved settings/chat; collapse/activity destruction
can discard the panel. This is not secure erasure of memory, keyboard state,
screenshots, OS/provider logs or backups. Do not display credentials or secrets.

Pure JVM tests cover bounds, malformed UTF-8, BOM/newlines/control replacement,
empty text and literal search/truncation. Source tests check explicit read, I/O
scope and no upload/automatic launch. No emulator or phone was run or pixel-
inspected for this feature. Grant revocation, system providers, remote-provider
latency, rotation/cancel behavior, actual small-screen scrolling and permission
failures still require runtime and visual acceptance. A CI compile/JVM test pass
is not device behavior or visual-readiness evidence.

Official source checked November 16, 2026:
- https://developer.android.com/training/data-storage/shared/documents-files
