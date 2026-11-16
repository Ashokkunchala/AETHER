# AETHER Windows companion agent (experimental)

This loopback-only helper reports basic platform/Python information and requests
one exact locally approved HTTPS URL open. It exposes no shell, screenshot,
terminal-output, arbitrary file, app-control or remote approval endpoint. No real
laptop/device acceptance or secure remote Android control is claimed.

## Local setup, not performed for you

Use the repository's local Python environment and install its requirements. Set
JARVIS_AGENT_TOKEN to a fresh 32+ character random secret privately in your local
environment; never paste it in chat or commit it. Set JARVIS_ALLOWED_URL_HOSTS to
exact approved hosts separated by semicolons. There is no default host allowlist,
no subdomain wildcard and no non443 port. Bind uvicorn windows_agent.agent:app
only to127.0.0.1 port8765. Do not expose the port on a LAN or forward it. Distinct
per-device pairing, TLS/authenticated remote transport and Windows acceptance
remain separate work, not supplied by this helper.

## Exact local review flow

1. GET /health is nonsensitive; GET /v1/status needs Bearer authentication.
2. POST /v1/request-url with token and {"url":"https://github.com"} creates an
   inert pending request. It returns request_id, opened:false and a120second
   lifetime. Queueing is not approval and does not open anything.
3. On the trusted laptop, in the same configured environment and an interactive
   terminal, run python -m windows_agent.local_approval review REQUEST_ID. The
   terminal shows the exact URL and the browser-cookie/network effect. Type OPEN
   to approve once, anything else to deny. Piped input is refused. Only this local
   decision changes the approval state; no HTTP endpoint does so.
4. POST /v1/open-url with token and the identical URL plus request_id. It consumes
   that exact, token-bound, unexpired approval atomically before OS invocation.
   A wrong URL/token, expired/replayed/denied request, changed host allowlist or
   local stop blocks opening. A browser failure still consumes approval. Create
   and review a new request for another attempt. Browser acceptance is not proof
   that the page loaded or was safe, and grants no downloads, commands or future
   tabs. A caller-supplied confirmed boolean is rejected, never authority.

The dashboard panel supports the same two-step request/review/execute flow. Token
is held only in page memory after Save settings; a dashboard confirmation is not
a replacement for local terminal review. CORS and the token are transport/access
checks, not user authority. Request IDs are short-lived but should not be shared.
No secret value is shown by the local review command.

## Stop and storage

python -m windows_agent.local_approval stop blocks new requests and invalidates
pending/approved requests. resume requires an interactive RESUME decision and does
not resurrect approvals. Stop cannot undo an already dispatched browser request.
There remains a small consume-to-OS-call race; this is not atomic OS cancellation.
These controls are companion-local, separate from desktop registry emergency stop.

The owner-only local database defaults to ~/.jarvis/companion-approvals.db;
JARVIS_AGENT_APPROVAL_DB can point to another canonical absolute local path in both
processes. Local OS/account, config and inherited Windows ACLs must be trusted.
This is not a sandbox against code under the same account, PTY emulation, DB edits,
network mappings, reparse-point/parent-swap races or OS compromise. POSIX new files
use0600, but Windows inherited ACLs require local review. The queue is bounded to
100unexpired requests and expired rows are purged when queueing a new request.
Exact URLs may include sensitive query strings and remain in that DB until expiry
cleanup; expiry is not secure erasure, backup/log/browser-history deletion or a
promise of privacy from the website. Raw bearer tokens are never stored there;
only their SHA256 binding is stored. An exposed token still needs rotation.

Tests use temporary databases, expiry/state and mocked webbrowser only. No
real browser was opened or laptop controlled. Pairing, remote rate limits,
end-to-end Windows acceptance and safe remote output delivery remain unbuilt.
See [Windows capability contract](../docs/WINDOWS-CAPABILITY-CONTRACT.md).

## Dedicated per-device foreground read-only protocol

A separate native Android request/result path now exists for one fixed memory
snapshot with laptop-local interactive review, requester-bound results and local
revocation/stop. It does not add HTTP execution approval, a shell or authorize LAN
exposure. See [read-only protocol and acceptance limits](../docs/ANDROID-WINDOWS-READONLY.md).

The remote-read protocol also supports owner-bound cancellation/result clearing.
It never approves or dispatches a read: pending requests cannot start, running
reads may finish but cannot publish that result, completed results are cleared.
Already returned copies are not recalled and OS cancellation is not guaranteed.
