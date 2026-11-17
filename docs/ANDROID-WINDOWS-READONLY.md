# AETHER foreground Android-to-Windows read-only request/result

This source slice joins a native Android foreground card, dedicated per-device
Windows companion authentication, a bounded queue, laptop-local interactive review,
a fixed read-only memory collector and requester-bound result retrieval. It is not
remote shell control, backend chat/tool dispatch, general registry reach, a network
deployment or proof of actual phone/laptop acceptance.

## The single allowed operation

Only `memory_snapshot` exists. No arguments, command string, tool name, file path,
app name, URL to open or caller approval boolean is accepted. It reads Windows
psutil total/available RAM bytes and reported used percentage. No user/machine name,
process, address, directory, clipboard, screenshot, secret or free-form output is
included. Both the collector and returned result use a closed numeric schema.
A memory reading is not a full system/CPU/health diagnosis. The wrapper never
invokes a shell, subprocess, generic registry or fallback action.

## Source protocol and local-only authority

1. On the trusted laptop, the separately approved interactive local command
   `python -m windows_agent.remote_read pair` asks for PAIR and issues one opaque
   device ID and a fresh dedicated token, displayed once in that terminal. Enter
   the token privately in the intended phone, never chat/source/logs. The companion
   stores only its SHA256 hash. Existing backend/master or legacy agent tokens do
   not authenticate this new protocol. Pairing is local-only; no HTTP route issues
   tokens. This does not automatically establish HTTPS or phone network access.
2. The foreground phone card accepts a reviewed HTTPS companion origin on 443 only,
   no path/query/fragment/user info, and a dedicated token. Fields are transient,
   not saved to settings, backend chat or TokenVault. Closing/clearing removes local
   state but is not server cancellation, token revocation, log deletion or secure
   erasure. Android IME/OS/screenshots/process memory are separate. Do not use a
   credential that has appeared in chat. The app has no certificate/hostname
   bypass and follows no redirects. New pairing/token entry is separate from the
   app's existing backend pairing, which remains unchanged.
3. One explicit phone button POSTs `/v1/remote-read/requests` with exactly
   `{"action":"memory_snapshot"}`. Queueing is inert. A fresh opaque request ID
   is returned with pending_local_review and executed=false. A lost response may
   still leave a request pending; no automatic retry occurs. Do not retry blindly.
4. On the trusted laptop, run the separately approved local command
   `python -m windows_agent.remote_read review REQUEST_ID`. It refuses piped input,
   displays exact request ID, requesting opaque device ID, fixed action/output
   fields and disclosure risk. Only typing SHARE MEMORY approves this one read and
   release to that paired device. Anything else denies. TTY checks are not a
   boundary against same-account code/PTY emulation or a compromised laptop.
5. Review checks token-device revocation, local stop, exact request/device/action,
   pending state and 120 second request expiry. An atomic SQLite transition consumes
   the request before collecting. Concurrent/duplicate/expired/denied/revoked
   reviews cannot collect again. Collector failure is consumed, with fixed failed
   state and no raw exception/result. There is no HTTP approval/execute/review
   endpoint. Same-account code can call internal functions; the local OS/account
   must remain trusted. There is a small transaction-to-read race, not atomic OS
   cancellation. This fixed read is not a job/process sandbox.
6. The same device can explicitly GET `/v1/remote-read/requests/REQUEST_ID` once
   per button press to check state/result. No automatic/background polling exists.
   Another device, invalid/legacy token, local stop or revoked device is refused.
   A completed result is available for 120 seconds after collection; phone display
   can remain a stale copy until cleared. The server returns captured_at_unix,
   result TTL and device_display_verified=false, not a read receipt. Results are
   not automatically forwarded to backend chat/model services or other devices.

A denied request does not execute. Request/result expiry prevents access but is
not secure erasure. Completed/denied/request rows are only purged opportunistically
on new queueing after applicable expiry; backing DB files, memory, logs, backups,
phone display and screenshots remain separate. The DB is the existing local
companion approval DB, default ~/.jarvis/companion-approvals.db or configured
canonical JARVIS_AGENT_APPROVAL_DB. Existing local path/Windows ACL trust limits
apply; this is not protection against same-account DB edits, reparse/parent swaps
or OS compromise. No real ACL/device acceptance has been performed.

## Revocation, stop and boundedness

The separately approved local interactive command
`python -m windows_agent.remote_read revoke DEVICE_ID` requires REVOKE. It blocks
that token and clears its queued/result data. Device records remain as revoked
hashes; no remote token administration route is added. The existing local
`python -m windows_agent.local_approval stop` also blocks this protocol and
invalidates remote-read requests/results. Resume never resurrects old approvals.
Revocation/stop during a read suppresses result publication; it cannot undo the
read or recall a result already obtained by the phone. Clear-local-fields does
not cancel the server request. A separate explicit owner-bound cancellation button
POSTs `/v1/remote-read/requests/REQUEST_ID/cancel` with an empty JSON object. It can
only prevent/suppress/clear this request, never approve or dispatch an operation.
Pending requests become cancelled_before_read and cannot pass later local review.
A running read becomes cancelled_result_suppressed: it may already have read RAM,
but its eventual result cannot be published back to this request. Completed
results become result_cleared; stored result text is set NULL, but already returned
copies cannot be recalled. Duplicate cancels are idempotent. Other device tokens,
revoked tokens, extra caller fields and wrong request IDs cannot cancel it.
Cancellation remains available to the authenticated owner while local stop is on;
it cannot resume work. Revoked devices stay refused. A cancellation response lost
in transit is not confirmed cancellation; the phone says so and never auto-retries.
No UI claim implies that an already-running OS operation was terminated. Ordinary
SQLite updates are not secure erasure of DB pages/WAL/backups or remote copies.

At most 50 device records, 100 unexpired request/result rows and 5 pending/running
requests per device are accepted. Capacity fails closed. This is bounded queue
storage, not distributed denial-of-service/rate-limit protection. JSON action
schema forbids extra fields. IDs and tokens have strict shape/length. The app
bounds successful response reads to 8192 bytes, uses 8 second connect/read timeouts,
drops late UI results after clear/edit/collapse and never retries itself. A
cancelled UI coroutine need not stop OS/TLS I/O or the server request. No ongoing
monitor or background wake is created.

## Reachability and acceptance remain separate

The existing helper must remain loopback-only until a separately approved reviewed
HTTPS architecture makes it reachable from the chosen phone. This change does not
open a LAN port, add a tunnel, configure TLS, install certificates, weaken Android
network policy, deploy or spend. Plain HTTP and alternate ports are refused by the
new card even when a development environment uses them. The existing companion's
other endpoints are not thereby approved for exposure. Review firewall/routing,
authentication, CORS/rate limits, TLS termination and all exposed endpoints before
any network change. CORS is not native-app authentication or execution permission.

Tests exercise request creation through the real HTTP app, inert pending state,
interactive/local review, fixed collector, requester-bound HTTP result, deny/replay/
expiry/concurrency/revocation/stop/capacity/cancel-clear failures and closed result disclosure.
Android JVM tests cover pure origin/ID/token/result validators; cancellation race
tests exercise pending-prevention, running-suppression, completed-result clearing,
owner binding, duplicate cancellation and stop/revocation without resurrection; source tests cover
foreground wiring, fixed action/no redirects/no approval route/no fallback. The
HTTP integration client simulates Android's protocol, not Android runtime or real
TLS transport. No phone, emulator, laptop command, real metric collection, remote
network, provider send or account was used. Native card pixels, real TLS, device
latency, keyboard/privacy/rotation/cancellation and Windows runtime remain
unverified. CI compilation is not device/UI acceptance. This is not full remote
Windows control or completion of categories 1-6.


## Separate dedicated HTTPS source option

[Dedicated HTTPS listener](REMOTE-READ-HTTPS.md) now provides a separate closed
queue/status/cancel app and offline certificate/target validator. It never
exposes/proxies the general agent or approves/executes a remote read. Only
ephemeral loopback TLS fixtures have been exercised. Owner-approved network
launch, reviewed certificate-chain/phone trust and actual private-network/device
acceptance remain separate and unverified. Existing helper loopback defaults
and Android TLS/443 restrictions are unchanged. Do not run network exposure
merely because this source option exists.
