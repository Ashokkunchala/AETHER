# AETHER reviewed document and folder opening

This adds a narrow local alternative to the closed legacy `open_path` route. It
lets the owner configure a reviewed file/folder handler, review the exact current
target, then launch one already approved handler executable with that one local
path as its only argument. It does not use Windows default associations, a shell,
PATH search, URI, shortcut or script.

No handler, root, document, folder or application is approved by default. No real
owner file or application was opened while developing this source.

## Local owner setup

The existing approved-app allowlist remains the source for the handler program.
Example shape only, not an approved path or hash:

```json
{"version":1,"apps":{"viewer":{"executable":"C:\\Approved\\viewer.exe","sha256":"reviewed-64-lowercase-hex"}}}
```

A second owner-managed file, default `~/.jarvis/reviewed_open.json` or the path
in `JARVIS_REVIEWED_OPEN_FILE`, binds a handler ID to that approved app and exact
local roots:

```json
{"version":1,"handlers":{"documents":{"app":"viewer","roots":["C:\\Users\\Owner\\Documents"],"targets":["file","folder"],"extensions":[".txt",".pdf"]}}}
```

The reviewed-open file must be canonical, non-symlink UTF-8 JSON no larger than
64 KB. Duplicate keys, unknown fields, network-style paths, missing roots and
unknown approved-app IDs fail. A handler can allow `file`, `folder`, or both.
File handlers require an explicit lower-case extension list. Known executable,
script, shortcut, web and macro-capable formats are refused even if listed.

## Review and launch flow

1. `plan_reviewed_open(handler_id, path)` reads the local configuration and
   selected target. For a file up to 512 MiB it returns a SHA-256 content
   digest. For a folder with at most 1,000 immediate entries it returns a
   SHA-256 fingerprint of the bounded immediate listing. It launches nothing.
2. The owner or trusted local caller passes the returned handler ID, target
   kind and digest, plus the exact approved handler app/path/hash, to
   `open_reviewed_path`.
3. The registry shows a fresh preview and cannot use auto, always or caller
   supplied approval. Emergency stop and owner policy are checked before and
   after the review.
4. Immediately before launch, the handler configuration, approved executable
   bytes and target digest are validated again. A changed file, folder listing,
   handler mapping, executable, root or configuration fails closed.
5. The exact handler executable is started with `[handler, path]`,
   `shell=False`, and the handler directory as its working directory.

A returned PID means only that a process-start request was accepted. It does not
prove the application opened the item, became ready, rendered content, stayed
running or avoided its own network/account behavior.

## Boundaries

- Hash or listing review identifies the target at recheck time. It is not
  malware scanning, macro safety, content understanding or publisher/signature
  verification.
- The handler application can read the target and can have side effects of its
  own. Choose and hash it through the existing approved-app setup.
- This is not an OS sandbox. Host compromise, mapped drives, hostile path races
  after launch, handler DLL/config changes and child processes remain outside
  this control.
- Legacy `open_path` and `open_file` remain closed. This workflow does not
  restore default-handler launch, arbitrary file opening, general typing, URL
  opening, remote file transfer or Android-to-Windows commands.
- In hardened owner-policy mode, the exact document target and handler
  executable path must both be covered by explicit policy roots. Non-path
  identity and digest arguments are accepted only for these two reviewed-open
  tools.
- Local tests use disposable files, fake executable bytes and mocked `Popen`.
  They do not establish real Windows UI, application, filesystem-race or device
  acceptance.
