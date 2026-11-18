# AETHER feature status matrix

Reconciled against the implemented source on November 16, 2026. The blueprint
is a target, not a completion checklist. See [category status](CATEGORY-STATUS.md)
for the remaining implementation work in categories 1-6.

Status meanings: **implemented** means code exists; **CI verified** means automated checks passed for a repository revision; **device verification pending** means it still needs a real local/device test. No item should be treated as production-ready solely because code exists.

| Capability | Status | Details |
|---|---|---|
| Gemini chat backend | Implemented with browser streaming and stop control; live-key test pending | API key remains server-side; JSON and SSE chat endpoints require configured bearer token |
| Voice-first browser interface | Initial implementation | Assistant orb, visible ready/listening/thinking/speaking states, responsive layout, transcript-first capture, stop listening and stop speaking controls |
| Terminal microphone input | Implemented as explicit one-utterance capture; device test pending | Click MIC to capture a single utterance, transcribe it with Google Speech Recognition (`en-IN`), and submit it to the Gemini tool loop. Audio is sent to the speech service; this is not offline transcription or an always-on wake-word listener. Install `SpeechRecognition[audio]` and a working microphone/PyAudio device. |
| Browser speech input | Implemented where supported; device test pending | User-initiated only; browser permission required; transcript is displayed for review before sending |
| Browser text-to-speech | Implemented where supported; device test pending | Uses OS/browser voices, not Gemini-generated audio; playback can be interrupted |
| Full-duplex real-time voice | Implemented in browser; end-to-end verification pending | Gemini Live client is served from `/static`; AudioWorklet capture produces bounded 40 ms PCM blocks, transcript captions are displayed, and transient socket failures retry at most twice with a visible cancel control. The server enforces one-time tickets, per-frame/session audio budgets, a 10-minute cap, and a two-session per-client-IP concurrent limit. Provider account usage budgets and current browser/device tests remain pending |
| Adaptive assistant personality | Implemented | Friendly, witty, calm, motivational and technical modes in system instructions |
| Indian English / Telugu | Implemented; quality test pending | Auto, English, Telugu choices; actual speech voice depends on browser/OS |
| Conversation context | Implemented | Up to 20 previous messages per request; not stored server-side |
| Responsive Command Center dashboard | Initial implementation; host/device test pending | `/dashboard` displays authenticated live CPU, RAM, disk, battery, process memory, aggregate network throughput, HTTP polling latency, provider request/turn durations, and tool lifecycle summaries. Runtime history persists up to 200 allow-listed summaries in SQLite and omits prompts, tool arguments, raw errors, and credentials; it is bounded operational telemetry, not a security audit log. If SQLite is unavailable the feed falls back to a process-local ring. `/api/provider/health` and the SAFE `provider_health_summary` tool aggregate only recorded provider attempts, measured latency and latest retained results; no live provider, quota or billing call is made. The dashboard AI providers panel renders the same recorded-only summary on demand. Works in desktop and mobile browsers; it is not yet a native Android dashboard. |
| Browser chat UI | Implemented | Includes session-only token entry, memory/reminder/workout forms, research and coaching panels |
| Explicit persistent memory | Implemented | SQLite API plus browser review/edit/delete/export controls; explicitly saved memories are bounded and included in chat context as untrusted profile data |
| Reminders | Partially implemented | SQLite create/list/complete/delete and due polling; daily/weekly/monthly recurrence advances on completion; experimental Windows toast and opt-in Android WorkManager polling; Android delivery is best-effort (15-minute minimum interval) and device verification is pending |
| Saved user plans | Initial implementation | Authenticated SQLite API and browser UI support user-authored checklist steps, optional target date, planned/in-progress/completed/cancelled status, deletion, status history, and export. The latest 1,000 plan-status events persist without titles or step text. A target date creates a linked one-time reminder returned by the existing due-reminders endpoint; configured notification workers deliver it best-effort. Plans never execute tools. |
| Scheduled system checks | Partial; local single-process scheduler | SQLite schedules repeat every 5 minutes to 7 days and start disabled. Enabling runs only `system_status`, `cpu_usage`, `memory_usage`, `disk_usage`, or `battery_status`, after rechecking the tool registry's SAFE/no-confirmation policy. Results are discarded; status/timing history is retained. Browser controls can disable/cancel a running job or delete a schedule. Requires the backend process to stay running; no distributed coordination or arbitrary scheduled actions. |
| Live web research | Initial implementation | Authenticated DuckDuckGo HTML adapter returns source links/snippets; not full browser automation |
| Native Android app | Initial implementation; Android CI build/JVM tests passed; device and current local-actions layout verification pending | Kotlin/Compose, HTTPS health check, master-token-backed per-device pairing and confirmed revocation, Keystore-encrypted device token/backend URL/device ID, authenticated chat and personal-data APIs, user-started full-duplex Live Voice, tap-to-speak fallback, spoken replies, explicit memory review/save/delete, recurring reminders, and opt-in WorkManager notifications |
| Windows companion agent | Restricted initial implementation | Loopback authenticated status and exact allow-listed HTTPS URL opening. URL requests require a one-time laptop-local interactive review, not caller boolean approval; no remote arbitrary shell/app/file endpoint |
| Laptop/Android tool core | Broad implementation, safety/device tests still needed | Typed risk-graded tool registry; risky actions must remain confirmation-gated |
| Task orchestration | Partially implemented; resumable multi-step execution pending | The shared tool registry has a dependency-aware task runner; AI-issued independent read-only calls run with a concurrency cap of three, state-changing actions run serially, and tasks emit lifecycle events with cancellation. Explicit plans can request up to two transient retries for read-only tools; model-generated batches currently request no retries. Sanitized lifecycle history persists in SQLite. Saved plans remain checklists; scheduled execution currently supports only the fixed read-only system metrics above. Resumable multi-step plans and arbitrary event-triggered tool actions are not implemented. |
| Visible website launch and direct app typing | Legacy broad launch paths now fail closed | Exact approved-app launch is separate; the older website/app-and-type helpers cannot bypass that policy. A dedicated scoped URL/typing path and Windows acceptance remain |
| YouTube search and playback | Not started / partial research adapter only | Needs browser search/selection and playback verification; public web search alone does not prove playback |
| Local file and app operations | Initial implementation; Windows verification pending | Listing/search and exact locally allow-listed app launch exist; legacy default-handler file/folder launch now fails closed to prevent executable/script bypass; write/copy/move/rename/delete/organize tools require point-of-action confirmation with impact previews. Previews include affected item/byte estimates and destination conflicts; organize shows proposed moves. Estimates are bounded and can become stale. Delete fails safely if Recycle Bin support is unavailable. Windows results and permissions still need review |
| Gmail, Google Calendar and opt-in Google Contacts | Implemented adapters; live account acceptance pending | Official OAuth integration supports Gmail search/detail/AI summary and approved send, Calendar read and approved create/update/delete, and separate read-only Contacts opt-in. Provider/account-bound, expiring single-claim approvals. One Google credential slot, not multi-account routing; no blanket Google Workspace/share support |
| WhatsApp messaging | Official Business Cloud API draft/approval adapter; live account acceptance pending | Requires configured Meta business sender and policy-compliant recipients. No personal WhatsApp inbox/Web scraping. No message was sent during development |
| Install/uninstall and system maintenance | Partial, guarded shell only | Needs official package-manager integration, preview/approval flow, rollback notes and administrator elevation safeguards |
| Warnings and proactive notifications | Partial; dashboard threshold alerts implemented | The dashboard can monitor CPU/RAM/disk thresholds while open after explicit opt-in, persist threshold values locally, and show crossing alerts in-page. OS notifications require a separate permission click; no background monitoring is performed. Cross-device warnings, alert history, network thresholds, and physical-browser verification remain pending |
| Music search and playback | Not started end-to-end | Requires authorized service/browser integration and playback confirmation; singing/generated music depends on configured capabilities |
| Debugging and self-development | Partial foundation | Coding/research tools and roadmap exist; require sandboxed branch-based changes, regression tests and approval before merge/deploy |
| Brainstorming and conversational reflection | Partially implemented | Chat personality supports conversation; distinguish generated suggestions from facts and never invent lived experiences |
| Workout tracking | Implemented | SQLite activity log with list/delete |
| Workout/nutrition coaching | Implemented; live-key test pending | Authenticated Gemini endpoints with general-information safeguards |
| Secure cloud deployment | Not ready | Backend supports admin-issued per-device tokens and revocation, with Android pairing/device controls implemented but not device-verified; local per-process IP throttling exists, while distributed quotas, audit/monitoring and production hardening remain |
| Proactive daily routines | Partial | Recurring reminders and authenticated Windows/Android notification polling exist. Delivery is best-effort and needs device acceptance; no general always-on event/action platform |
| Continuous improvement loop | Designed, not autonomous | Roadmap defines feedback, tests, review and release; no self-modifying code/deployment is enabled |

See [NEXT-MILESTONES.md](NEXT-MILESTONES.md), [REALTIME-VOICE-AND-INTERFACE.md](REALTIME-VOICE-AND-INTERFACE.md) and [VERIFICATION-CHECKLIST.md](VERIFICATION-CHECKLIST.md) for remaining acceptance criteria.

## New narrow execution and review paths

- Scoped screenshot: explicit rectangle and fresh confirmation, new local PNG only. No automatic upload or whole-screen fallback.
- Approved app launch: empty-by-default exact ID/executable/hash policy, no arguments, URI, shell or elevation fallback. PID is not readiness.
- Process stop: exact PID/create-time/executable, fresh approval, bounded exit check, no name/tree/escalation fallback. Windows termination can lose unsaved work.
- Windows service/startup-name and passive network-link inventories: bounded fresh-approved snapshots with unknown/partial states, no service/startup/network changes. Link-up is not internet verification.
- Manual Python verification pipeline generator: real GitHub Actions/Jenkins test-stage text. Does not write/run/install/deploy; see [pipeline guide](PYTHON-VERIFICATION-PIPELINES.md).
- Native Android local actions: dial/SMS/calendar system composers, selected-item pickers, foreground clipboard and device snapshot. These are not direct sends, saved-event verification, image analysis, broad file management or remote laptop control. See [phone actions](ANDROID-LOCAL-PHONE-ACTIONS.md).

- Native Android foreground network snapshot: explicit local OS capabilities only, one additional normal ACCESS_NETWORK_STATE declaration; no identifier read, probe or backend-health claim. Runtime/layout acceptance remains unverified. See [network snapshot](ANDROID-NETWORK-SNAPSHOT.md).

- Local Python test execution: fresh-approved fixed pytest argv, canonical project/tests selection, current interpreter, reduced environment and direct-process timeout. No install, output log, verified count, sandbox or readiness claim. See [test runner](PYTHON-TEST-RUNNER.md).

- Optional GitHub workflow failure reports: disabled-by-default HMAC/repository-scoped inbound webhook with replay-safe local inbox enqueue. No API/log/model/remediation call or verified device display. Localhost reachability needs separately approved architecture/setup. See [workflow alerts](GITHUB-WORKFLOW-ALERTS.md).

### Bounded Python mentor snippet review

`mentor_review_python` provides five explicit AST teaching checks on supplied
redacted text, without execution, imports, file access or progress writes. It is
not a correctness/security/mastery pass and does not resolve aliases/data flow.
See [Python review scope and evidence](MENTOR-PYTHON-REVIEW.md).

### Bounded JavaScript mentor snippet review

`mentor_review_javascript` provides five literal teaching checks on supplied
redacted text, without execution, file/network access or progress writes. It is
not a parser, correctness/security/mastery pass or complete JavaScript/TypeScript
review. See [JavaScript review scope and evidence](MENTOR-JAVASCRIPT-REVIEW.md).

### Bounded TypeScript mentor snippet review

`mentor_review_typescript` provides five literal teaching checks on supplied
redacted text, without execution, type checking, file/network access or progress
writes. It is not a parser, compiler, correctness/security/mastery pass or
complete TypeScript/JavaScript review. See [TypeScript review scope and evidence](MENTOR-TYPESCRIPT-REVIEW.md).

### Bounded HTML mentor snippet review

`mentor_review_html` provides five literal teaching checks on supplied redacted
markup, without rendering, validation, browser/file/network access or progress
writes. It is not a sanitizer, correctness/security/mastery pass or complete
HTML/browser review. See [HTML review scope and evidence](MENTOR-HTML-REVIEW.md).

### Trusted-project local Python wheel build

`build_python_wheel` adds a fixed fresh-reviewed no-isolation wheel-build command
and bounded output hashing. It runs arbitrary trusted backend code, not a sandbox,
and does not install dependencies, publish, deploy or certify the resulting file.
See [wheel builder boundaries and evidence](PYTHON-WHEEL-BUILDER.md).

### Supplied Kubernetes RBAC structure

`review_k8s_rbac_json` joins bounded supplied RBAC v1 JSON roles/bindings by exact
namespace/kind/name, reports selected per-rule patterns with source indexes and
keeps effective permissions/live cluster state unknown. No cluster call/change.
See [RBAC structural scope and evidence](KUBERNETES-RBAC-SNAPSHOT.md).

### Supplied Service and EndpointSlice field correlation

`review_k8s_service_endpoints_json` compares one supplied Service with bounded
EndpointSlices by namespace/label/owner UID and explicit port fields, with source
indexes and unknowns instead of live routing/health claims. No cluster/network call.
See [Service correlation scope](KUBERNETES-SERVICE-CORRELATION.md).

### Exact-name OS DNS lookup

`lookup_dns_name` requires fresh review for one absolute lowercase ASCII dotted
name, returns bounded OS IPv4/IPv6 records, and opens no application connection.
Timeout stops waiting, not OS cancellation; one outstanding call gates later
requests. No DNS authenticity/connectivity/health pass.
See [DNS scope and privacy](EXACT-DNS-LOOKUP.md).
