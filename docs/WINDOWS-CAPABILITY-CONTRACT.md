# AETHER Windows laptop capability and remote-control contract

Checked November 16, 2026 by source review only. No real laptop, Windows service,
process, network, screenshot, terminal, installation, AWS account or production
system was queried or changed. This is a design/acceptance contract, not proof
all requested laptop abilities work. Python test hosts are not the user's laptop.

## Separate the execution surfaces

The desktop registry uses jarvis/control/laptop.py and its module adapters.
Other older controllers also exist; they are not interchangeable acceptance
paths. windows_agent/agent.py is a separate experimental loopback HTTP helper:
health, bearer-token platform/Python status, pending exact HTTPS URL requests
and laptop-locally approved single-use URL opening only. It does not expose the desktop registry, shell, screenshot, app
control, telemetry, jobs or file APIs. Native Android backend chat/pairing is a
third route and does not make the narrow helper a safe remote-control service.
Do not merge stores/authentication or expose loopback ports to claim integration.

The standing operating boundary is approved commands only for the user's
machine. No live command is authorized by this contract, a blueprint feature,
app permission, bearer token, shell classifier or confirmation boolean.

## Requested abilities versus reviewed source

| Requested ability | Existing source foundation | Acceptance gap / required boundary |
| --- | --- | --- |
| CPU/RAM/disk usage | info.py uses psutil CPU/RAM and disk space, plus summary. | Sample interval/CPU semantics and readable volume scope need verification. Disk space is not disk I/O/health; a snapshot is not ongoing monitoring. Unsupported/error remains unknown, not zero/healthy. |
| GPU usage | gpu_info invokes legacy WMIC Win32_VideoController for adapter/driver text. | Not utilization, VRAM, temperature or health. WMIC is deprecated/disabled/removed on some Windows installations; future collector should use supported CIM/vendor APIs and return explicit unavailable state. Empty list is not proof no GPU. |
| Battery/temperature | sensors_battery data if exposed, absent otherwise. | No temperature collector here. psutil sensor support varies by OS/hardware; standard Windows temperature probe often does not expose current temperature. Do not equate plugged-in with actual charging or estimate remaining time as a guarantee. No hardware driver installation assumed. |
| Running processes | List/details/top-by-memory functions. | Privilege/access-denied/exiting processes make inventory partial. Details include cmdline/executable/user and can contain secrets. Do not forward raw process details remotely by default. PID alone can be reused; bind future action to PID+creation identity+exact executable. |
| Start/stop approved apps | Exact local ID/executable/SHA256 launch allowlist, empty by default; exact PID/create_time/executable stop with exit wait. Fresh confirmation every action, legacy broad routes fail closed. | Launch PID is not app readiness; stop verifies only selected-process exit, not saved work/children/service state. Windows terminate is forceful. No default app approvals, real-device acceptance or remote adapter. Generic shell/process command primitives remain separate, not approved-app launch. Docker Desktop/Android Studio discovery/start/readiness is not verified. |
| Startup apps | Start Menu discovery includes Startup folder. | Discovery is not startup management. No reviewed typed registry/Startup/scheduled-task adapter, before/after diff, rollback or scope/owner handling. Never infer safe deletion from a shortcut. |
| Windows services | Generic shell can express Get-Service. | No typed service inspection adapter in this reviewed registry; no service mutation approval/recovery contract. Service/process security descriptors and user/UAC rights still apply. Do not elevate, bypass protected services or infer complete inventory. |
| Internet connectivity | Local/public IP, ping/netsh/socket inspection adapters exist. | Some perform real external requests/probes; not all are passive reads. Local link/IP, ICMP success and an open port do not prove internet/DNS/TLS/backend/application health. No scheduled connectivity monitor accepted. Exact targets/cadence/authorization needed before live probes. |
| Browser/repository opening | Desktop URL/app paths; narrow helper accepts credential-free HTTPS plus host allowlist. | An exact allowed host is not trust of URL content, redirects or downloads; browser launching does not prove page loaded. No credential-bearing URL or arbitrary command transport. |
| Installs/updates | Generic shell/process primitives could invoke installers. | Not a reviewed installation manager. Need exact package/publisher/version/source/hash/signature/license/cost/admin consent, effect/restart requirements and rollback. Never install/update through a generic 'approved app' name. |
| Projects/source/tests/logs/debug/docs/Git/PR | File/shell/review tools are separate foundations; offline reviewers and draft generators exist. | Exact trusted workspace/repository/branch/source baseline and edit diff matter. Tests/builds/hooks/dependencies can execute code/network even without deploy. Git commit/push/PR affect external audiences and require grounded authority; not accepted merely because shell can express them. Debug hypotheses are not root-cause proof. |
| Android-to-Windows commands | Android HTTPS pairing/chat/activity and narrow loopback helper exist. | No accepted end-to-end typed, device-bound, replay-safe remote-job protocol with local approval and cancellation. Never expose broad registry/shell as a shortcut. OS permission/authentication is not per-action authority. |
| Command monitoring/output | Orchestrator emits task start/end/retry events; shell captures bounded stdout/stderr. | Events are not a durable remote-job record. Output can include secrets. Remote screenshots or terminal output must be explicitly requested and separately scoped, not attached automatically to failures/status/alerts. No continuous screen/terminal streaming. |
| Stop long-running tasks | Emergency stop blocks new non-SAFE registry operations and rechecks after confirmation. Orchestrator avoids treating mutation timeout as stopped. | Does not guarantee cancellation of an already running subprocess/thread/child tree. Name kill isn't task cancellation. Need exact owned job/process-tree identity, stop request, deadline and observed terminal state, with 'unknown/still running' if unverifiable. No automatic force kill. |

## Material current gaps, not enforcement claims

- Screenshot hardening now requires fresh scoped confirmation in the desktop
  registry: explicit full_screen/region, exact new local PNG path and privacy/
  effect preview, no auto/always approval. Legacy direct/voice screenshot routes
  fail closed. Confirming that preview is the user's explicit single-capture
  request, not a model/caller boolean. It does not authorize upload or remote
  disclosure. Other screen/pixel/OCR/recording tools and arbitrary Python/shell
  are distinct, not covered by a screenshot-only acceptance claim.
- run_shell has explicit HIGH-risk registry confirmation, but direct shell.run
  is an execution primitive, not an authority boundary or sandbox. Its text
  classifier/dry_run do not establish safety, scope, credential or no-side-effect
  properties. Other callers/older modules need separate review.
- The helper now queues an exact URL for a trusted local interactive terminal
  decision. Its token-bound120second approval is consumed once before opening;
  caller confirmed booleans are rejected. Queueing/CORS/token possession are not
  authority. No HTTP approval endpoint exists. Local stop revokes outstanding
  requests. Keep it loopback-only; no LAN/router exposure or device-pairing claim.
- The exact app allowlist has no defaults; ID/path/hash and current executable
  bytes are rechecked. No shell/PATH/alias/URI/argument fallback exists in that
  launch route. Local config/account and executable dependencies must be trusted;
  hash matching is not signature/malware validation or an OS sandbox.
- Exact process stop rechecks PID reuse/create_time/executable and waits up to
  five seconds. A timeout remains unverified; no force escalation, recursive
  stop or authority to lose unsaved work is inferred. Protected-name lists are
  incomplete and UAC/permissions are never bypassed.

All four named hardenings have offline source/mock tests, not live Windows/device
acceptance. Details: [screenshot](SCOPED-SCREENSHOT.md),
[app launch](APP-LAUNCH-ALLOWLIST.md), [process stop](EXACT-PROCESS-STOP.md) and
[local companion review](../windows_agent/README.md). Other remaining gaps in the
matrix are not fixed by this contract. Generic commands, continuous monitors,
remote jobs/output and actual Android-to-laptop execution remain separate work.

## Required future remote-job contract

This section is a proposed non-executable contract, not a newly implemented API.

1. A paired, revocable device sends a typed operation ID from a local allowlist,
   bounded schema-valid arguments, exact target/workspace, nonce/request ID,
   issue/expiry time and requested disclosure scope. No shell strings, arbitrary
   path/application aliases, arbitrary URLs, environment secrets or model-chosen
   output destination in the remote envelope.
2. Laptop resolves/validates target identity and prepares an exact effect/impact
   preview. Sensitive operations require fresh laptop-side trusted approval
   bound to device/operation/arguments/target/request/expiry, consumed once. No
   replay, wider retry, 'always approve' inference or remote confirmed boolean.
   Queued requests recheck revocation/expiry/stop before start. Reads can still
   disclose private data; output permission is independently checked.
3. Job states distinguish proposed/awaiting approval/denied/expired/queued/
   running/stop requested/succeeded/failed/stopped/unknown. Stop requested and
   timeout are not terminal-state proof. Persist minimal redacted audit/status,
   not raw credentials/command output. Observe actual bounded result and exact
   side effect before calling success; never retry non-idempotent actions blind.
4. Only an explicit screenshot/terminal-output request for a defined job/screen
   region/window permits that disclosure. Show capture destination, private-data
   risk and retention; no surprise capture/upload/provider sends. Return minimal
   status otherwise. A local file path is not delivered output; remote transfer
   needs authenticated access and separate audience checks.
5. Cancellation targets only the owned job/process identity/tree. Distinguish
   graceful/force policy and possible data loss, require new authority for
   escalation. Verify exit, orphan children and side effects. Where unverifiable,
   say unknown/still running rather than 'stopped'. Emergency stop blocks new
   writes but must never be described as undoing completed/running work.

Required tests before activation: deny/missing/expired/replayed approval, wrong
or revoked device, argument/target swap, PID reuse, simultaneous requests,
stop during approval, disconnect/restart, process-tree timeout, missing executable,
non-admin access denied, protected services, unsaved work, output-size/redaction,
no unsolicited screen/terminal capture and correct final state. Run unit/simulation
first, then separately approved Windows/device acceptance. No such device tests
were run for this contract, and no new scheduled monitor is created.

## Sources checked

- psutil metric/platform limits: https://psutil.readthedocs.io/en/latest/
- GPU adapter class: https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-videocontroller
- Temperature probe limitations: https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-temperatureprobe
- Windows deprecations: https://learn.microsoft.com/en-us/windows/whats-new/deprecated-features
- Service rights: https://learn.microsoft.com/en-us/windows/win32/services/service-security-and-access-rights
- Process rights: https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights
