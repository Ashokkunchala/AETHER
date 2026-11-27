# Template-backed file creation

Two registry tools cover "create a file for me" requests such as "make a
Dockerfile for my app" at the same safety level as the existing file tools.

## `list_file_templates` (SAFE, files)

Lists the deterministic starter templates `create_file` can render. Current
kinds:

- `dockerfile-python` - Python app image (python:3.11-slim, port 8000, `app.py`).
- `dockerfile-node` - Node.js app image (node:20-slim, port 3000, `server.js`).
- `docker-compose` - one app service built from the local Dockerfile.
- `gitignore-python` / `gitignore-node` - standard ignore files.
- `github-actions-python` - starter CI (pip install + pytest on push/PR).

Templates are fixed local strings rendered without network, model or
environment access, so the exact bytes are reviewable in the confirmation
preview before anything is written.

## `create_file` (MEDIUM, files - fresh confirmation every time)

Parameters: `path` (required), exactly one of `kind` (a template) or
`content` (explicit text, 1-64000 characters), and `overwrite` (default
false).

Guarantees and limits:

- The confirmation preview shows the exact action (create or overwrite),
  resolved path, source (template kind or explicit content), incoming byte
  count and the first 400 characters of content. It is a snapshot;
  existence and size are re-checked when the approved write is applied.
- An existing file is never replaced unless `overwrite=true` is passed;
  without it the write is refused and the file is left untouched. Directory
  targets and protected system locations are refused.
- Never auto-approves and cannot be added to an always-allow list
  (`allow_always=False`, `allow_auto_approve=False`), matching `write_file`.
- Output is starter text: review and edit before relying on it. No format
  validation, linting, chmod or version-control step is performed, and no
  claim is made that a generated Dockerfile or CI file is correct for a
  specific project without that review.

## Typical flow

1. User: "create a Dockerfile for my Python app" ->
   `create_file(path='Dockerfile', kind='dockerfile-python')`.
2. The confirmation prompt shows the rendered starter; on approval the file
   is written; on refusal nothing happens (fail closed).
3. Arbitrary one-off text goes through `content=`; repeated shaped files go
   through templates so the model cannot improvise hidden bytes.

## Verification

Unit tests cover template listing, preview contents, the mutual-exclusion
and bounds checks, protected-location refusal (with patched prefixes),
no-overwrite-by-default on disk, verbatim explicit content, writer failure
propagation, and every template rendering non-empty. Registry integration
tests pin the MEDIUM/confirmation/preview posture and prove an unconfirmed
execute never writes while a confirmed one does. Real Windows filesystem
behaviour remains device acceptance, as with the other file tools.
