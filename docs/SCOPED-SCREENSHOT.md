# AETHER explicit scoped screenshot request

The desktop `screenshot` tool now requires explicit scope (`full_screen` or
`region`) and an exact absolute new local .png path. No implicit full-screen
fallback, default output path or partial region is accepted. Full-screen means
all monitors. A region requires integer left/top/width/height with bounded
coordinates, positive dimensions and at most 40 million pixels.

Before any capture, the trusted confirmation UI receives exact scope/region,
destination, one-capture effect, no-upload statement and a private-data warning.
Confirming that exact preview is the user's explicit request for this capture
now. A model/caller `confirmed` boolean is not accepted as authorization. Denial,
missing confirmation, invalid preview or emergency stop means no capture. Every
capture requires a new single-use local approval record bound by the existing
registry to tool/arguments/task/expiry; no auto/always approval. Stop is rechecked
after confirmation and arguments cannot change during the wait.

This uses the registry's trusted confirmation callback boundary, not text-based
inference that the user said screenshot. A callback implemented by an untrusted
caller or arbitrary Python execution is outside this boundary; this is not a
sandbox against code running with the user's own OS account.

The parent directory must exist, be canonical and not resolve through a symlink;
UNC/network-style paths and alternate streams are refused. Existing destination
files/symlinks are refused; the output uses exclusive creation to prevent an
existing/newly inserted destination from being overwritten. No directories are
created. Mapped network drives, hostile concurrent parent swaps, hard-link/ACL
attacks and OS account compromise are not sandboxed. No redaction guarantee is
made. If a local disk write fails after capture, a partial new file may remain;
no retry or cleanup is automatic. No capture occurs just to prepare a preview.

Legacy screen.screenshot, legacy SystemController screenshot, direct unified
laptop screenshot keyword and legacy voice take_screenshot now fail closed with
instructions to use the scoped registry. The internal capture primitive is not
a public permission boundary and must never be separately exposed as an API.
The narrow Windows HTTP helper exposes no screenshot route.

Success returns only the local path, scope and unshared/unuploaded/unredacted
flags. It does not transmit bytes or grant remote disclosure. A screenshot may
contain credentials/messages/other people's data; any later upload/send/model
analysis requires its own audience/data authority. A local path is not delivery.
No proactive screen capture, background stream or failure-attachment feature is
added. Terminal output is not returned by this operation.

This change covers the named screenshot path, not separate pixel/OCR/recording,
Android/ADB, arbitrary shell/Python or every old input-automation surface. Those
must not be represented as acceptable alternate remote capture routes. The
remaining app-launch/process-stop/HTTP-approval gaps are separate hardenings.

Tests mock capture and use synthetic bytes only. They cover missing/denied/
auto approval, exact preview, frozen arguments, repeat fresh prompts, stop during
approval, malformed/implicit scope, paths/symlinks/overwrite and legacy denials.
No actual screenshot, screen state, Windows laptop or device was accessed. This
is code-level boundary validation, not hardware/real UI acceptance.
