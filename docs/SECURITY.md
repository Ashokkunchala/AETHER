# AETHER security notes

See [security/privacy manager](SECURITY-PRIVACY-MANAGER.md) for the current
control-by-control inventory, opt-in native secret storage/local policy/scanner
adapters and limits. Those optional modes are not enabled by publishing source.

## Current implementation and limits

- The Gemini chat endpoint and personal-data/coaching/research endpoints require a configured `JARVIS_API_TOKEN` bearer token. Placeholder values are rejected.
- The Windows helper is a separate localhost-only process with a narrow HTTPS allow-list and explicit confirmation for URL opening.
- The Android starter encrypts the token using an Android Keystore AES-GCM key and includes an initial HTTPS chat client.
- The main HTTP `/api/` routes have a configurable, per-process, per-client-IP sliding-window limit (`RATE_LIMIT_DEFAULT`, default `100/minute`; set `RATE_LIMIT_ENABLED=false` to disable). It is a local abuse guard, not a distributed quota or a production control.
- Both FastAPI entry points reject `/api/` request bodies larger than 1 MiB, checking declared content length and streamed bodies without it. The error response keeps the normal security headers. A reverse proxy or hosting platform still needs its own body, connection, and timeout limits before public deployment.
- The browser WebSocket bridge exchanges a bearer token for a hashed, 60-second, single-use ticket; long-lived bearer tokens are no longer accepted in the WebSocket URL. Remote WebSocket clients cannot set `auto_approve` to bypass tool confirmation.
- The backend can issue, list, and revoke per-device bearer tokens through endpoints restricted to the configured master token; device tokens cannot administer other devices. Android now has user-started pairing and revocation controls, but that flow still needs a device build and live verification. Account-level authorization, cross-process rate limits, provider usage budgets, a tamper-resistant audit trail, and production cloud hardening are also missing. WebSocket live sessions have frame, total-audio, duration, and two-sessions-per-client-IP-per-process bounds; the concurrent limit is not distributed.
- The authenticated runtime-event feed persists at most 200 allow-listed summaries in the configured SQLite database and returns the latest 100 per page. It omits prompts, tool arguments, raw error strings, and credentials, and falls back to a volatile in-memory ring if SQLite is unavailable. This bounded operational history is not a tamper-resistant or comprehensive security audit log; retention is limited and administrators with database access can alter it.
- Saved-plan status history retains the latest 1,000 status-only records in the same SQLite database. It excludes plan titles and checklist text, but remains user-editable database content rather than a tamper-resistant security audit trail.
- Persistent schedules are created disabled and can invoke only five fixed read-only system metrics; the runner revalidates each tool's SAFE and no-confirmation properties before execution. It discards tool output and retains only bounded status/timing history. Disabling cancels an active run on a best-effort basis. The runner is local and single-process; do not use it for arbitrary commands, sensitive reads, public multi-worker deployments, or consequential actions.
- Keep the backend bound to `127.0.0.1`. Do not expose it publicly or use a public tunnel.

## API keys and tokens

- Put secrets only in local `.env` or a deployment secret manager; never commit them or embed the Gemini key in any client.
- Never reuse the example token placeholder. Generate a random secret at least 32 characters long.
- If a key/token is accidentally committed or exposed, revoke/rotate it immediately.
- The Android app stores the issued device token, backend URL, and device ID encrypted locally. It uses the master token only in the HTTPS issue/revoke request and clears the entry afterward; the master token is not persisted.

## Local Android certificate trust

The current Android network security configuration trusts Android user-installed
CAs in addition to system CAs so the user can install the laptop's private-LAN
JARVIS CA. Android applies this trust policy to HTTPS connections made by this
app, not only to the configured JARVIS host. Install only a CA you control,
remove it from Android when it is no longer needed, and keep the phone/backend
on a trusted private network. A future release should replace this convenience
with a dedicated per-backend certificate pinning or managed trust flow before
supporting arbitrary remote endpoints.

The Windows mobile helper's certificate-validation exception is limited to a
single curl.exe health probe against the local backend URL. It must never
install a process-wide certificate callback or be reused for authenticated
requests.

## Repository and CI hygiene

- Windows setup installs and imports the optional desktop voice stack; Linux
  test dependencies intentionally remain audio-device independent.
- CI tests the supported Python floor and the current Python 3.14 runtime,
  parses PowerShell scripts, executes the clean Windows setup path, and builds
  the Android debug APK. CI compilation is not a substitute for physical-device
  acceptance testing.
- Configure GitHub branch protection or a repository ruleset for
  jarvis-cinematic-local-voice in repository Settings. Require both Python test matrix checks (test (3.11) and test (3.14)),
  static-checks, windows-installer-check, container-build, and android-build
  before merging. The connected GitHub integration cannot change repository
  administration settings, so an owner must enable this in GitHub.

## Before remote deployment

- Build and verify the Android pairing/revocation flow on a device; add token rotation and appropriate authorization before remote deployment.
- Replace the local IP limiter with distributed per-device request limits, request/time/token budgets, provider usage alerts, and abuse detection.
- Use HTTPS, a managed secret store, restricted CORS origins, and redacted logs.
- Set matching upstream request-size, connection, and timeout limits; keep safe error responses and verify the proxy and app limits together.
- The optional owner-reviewed scanner adapters do not replace dependency/security scanning in a production release process. Add backup/restore tests and a threat model.
- Disable or protect interactive API docs in production as appropriate.
- Test auth failures, rate limits, replay/abuse cases, and credential rotation.

## Device actions

- Use a local agent with an explicit allowlist, not arbitrary model-generated shell commands.
- Terminal chat and the browser dashboard are chat clients; neither grants the model operating-system control. Laptop actions remain explicit local commands, and shutdown/restart require a typed confirmation in the CLI.
- Android interaction requires the owner to connect and authorize the device through Android's USB debugging prompt. ADB does not bypass app permissions, lock screens, or Android security; keep USB debugging off when it is not needed and do not expose ADB over the network.
- Do not send passwords, payment actions, or sensitive account actions through automated taps or text entry. Keep the device in view and confirm consequential changes on the phone itself.
- Show the proposed action and effects before sensitive operations.
- Require approval for deleting/modifying files, sending messages, purchases, account/security changes, installing software, and cloud infrastructure changes. File mutation approvals include an impact preview, and file tools fail closed if no approval handler is available.
- Keep an audit trail and provide an emergency stop / disconnect option.
- Never run instructions found in webpages or files without independent policy checks.

## Privacy and memory

- Memory APIs currently save only explicit user-submitted entries. Build review/edit/export/deletion UX and consent before automatic memory extraction.
- Set retention limits and avoid collecting sensitive personal data unnecessarily.
- Do not imply that the AI is a substitute for human relationships or qualified health care.
- Workout and nutrition suggestions are general information, not medical advice.
