# AETHER categories 1-6: source status and remaining work

November 16, 2026. The ability blueprint describes intended behavior. It is not
proof that every item is implemented. Code, mocked tests, CI builds and actual
Windows/Android/provider acceptance are separate evidence levels. No deployment,
paid service, real AWS change, destructive command or provider send was performed
to develop the additions described here. Existing internal package/branch names
remain unchanged for compatibility.

## 1. Personal assistant

Implemented paths include local plans, prioritized tasks and postponement, notes,
reminders/recurrence, expense entry/correction/monthly reports, today's summary,
explicit memories, selected document previews/extractive summaries and reviewed
TXT/Markdown/DOCX downloads. The browser Life Manager and shared tool chat expose
different subsets. Configuring one interface does not enable every other one.

Google OAuth adapters implement Calendar reads and approved create/update/delete,
Gmail search/detail/AI summary and approved send. Read-only Google Contacts needs
separate opt-in. Meta's official Business Cloud API has a draft/approved-send
path, not a personal WhatsApp inbox. Expiring provider/account/credential-bound
approvals and disconnect controls exist. No real provider execution was used as
development evidence. AI summaries disclose selected content to the configured
model provider; account connection is not permission for arbitrary disclosures.

Travel/shopping forms produce grouped source shortlists, not verified inventory,
quotes, bookings or authoritative comparisons. Document operations are scoped
to configured roots, not a hardened filesystem sandbox. Scanned PDF OCR, automatic
correct-latest-resume selection and complete rich-document support are absent.
Voice/meeting notes require user-reviewed capture; this is not autonomous meeting
recording or transcription consent management. Windows/Android notification
polling exists but timing and actual delivery still require device acceptance.

Sources: `app/life_manager.py`, `personal_data.py`, `integrations.py`,
`provider_approvals.py`, `personal_contacts.py`, `personal_documents.py`,
`personal_research.py`; [integration guide](AETHER-INTEGRATIONS.md),
[personal tool chat](PERSONAL-TOOL-CHAT.md), [note capture](NOTE-CAPTURE.md).

## 2. Friend and voice

Conversation styles, English/Telugu choices, explicit memory and bounded chat
context, browser/native voice controls, interruption controls and conversational
prompts exist. Provider model availability, accent/code-switching quality,
latency, microphone/speaker routing and reconnect behavior need real acceptance.
Voice input can use external speech/model services; it is not wholly offline.
Persistent explicit memory is not perfect recall or automatic continuation of
every interrupted session. Music recommendation text is not verified playback or
control of arbitrary music applications. Always-on/background wake-word behavior
is not implemented as unrestricted Android listening. No claim of human feelings
or inferred emotional diagnosis is made.

Sources: `app/personality.py`, `app/live_voice.py`, `app/static/live_voice.js`,
`jarvis/personality_modes.py`; [voice/interface](REALTIME-VOICE-AND-INTERFACE.md),
[companion style](COMPANION-STYLE.md).

## 3. Mentor

The [four-capability follow-up](FOUR-CAPABILITIES.md) adds twelve deeper open-book
scenario lessons across four three-stage tracks, randomized multi-decision checks,
prerequisite progression, persisted weak areas/explanations and spaced-review
suggestions. Objective decision feedback is implemented, plus deterministic
free-text concept/risk/boundary phrase signals for review. This is not semantic
free-text mastery grading, an advanced curriculum for all subjects or live
coding/cloud labs.


Twelve starter domains have introductory material, objective checkpoints,
feedback, study plans, latest progress/weak-area summaries, mock-interview and
practice-project material, an offline Terraform lab and new daily checkpoint
history. Local examples and generated project text do not execute a lab or create
a GitHub repository. Objective choice grading is not a coding sandbox, a verified
code review, adaptive advanced curriculum, certification preparation for every
exam, or evidence of mastery. Full beginner-to-advanced coverage of every named
language/cloud/tool and secure live coding/command evaluation remain substantive
implementation work. A narrow reviewed one-shot deep-lesson reminder can now be
placed in the existing local backend reminder store, but automatic terminal
practice and broader proactive learning delivery still need their own scoped
execution/notification integration.

Sources: `jarvis/mentor.py`, `mentor_projects.py`, `mentor_terraform.py`,
`mentor_activity.py`; [mentor activity](MENTOR-ACTIVITY.md),
[Terraform mentor](MENTOR-TERRAFORM.md),
[review prompts](MENTOR-REVIEW-PROMPTS.md),
[shell review](MENTOR-SHELL-REVIEW.md),
[JavaScript review](MENTOR-JAVASCRIPT-REVIEW.md), [blueprint](ABILITIES.md).

A bounded [rubric-signal reviewer](MENTOR-RUBRIC-SIGNALS.md) now checks deep-mentor free-text explanations for deterministic concept/risk/boundary signals without storing standalone answers. It is not semantic grading or mastery evidence. A separate fresh-approved [review prompt](MENTOR-REVIEW-PROMPTS.md) creates one local reminder row for one exact lesson/time, without notification-delivery proof or recurrence.

A bounded offline [Python snippet teaching reviewer](MENTOR-PYTHON-REVIEW.md) now
checks five explicit AST patterns with source links and location-only findings.
It never imports/runs code or writes progress. Separate literal [shell command](MENTOR-SHELL-REVIEW.md),
[JavaScript snippet](MENTOR-JAVASCRIPT-REVIEW.md) and [TypeScript snippet](MENTOR-TYPESCRIPT-REVIEW.md)
reviewers flag five teaching patterns each without executing, type checking or
resolving the supplied text. Aliases/control flow and general
correctness/security/mastery are not evaluated; this does not close the advanced
mentor/evaluation gap above.

## 4. DevOps and SRE

Existing registry tools include guarded local command/Git/Docker/Kubernetes/AWS
wrappers and offline reviewers. A wrapper that can accept a command does not equal
a typed, validated service lifecycle adapter. User-approved exact commands,
repository trust, environment, output provenance and recovery remain necessary.
No generic wrapper authorizes deployment, destructive operations or spending.

- AWS automatic-read policy is exactly five reviewed service/operation pairs,
  not all describe/list/get calls. Offline supplied-export reviews cover EBS,
  native Cost Explorer periods, AWS Backup jobs, IAM policy patterns, security
  group ingress and Terraform plans. These do not prove live health, unused
  resources, effective permissions, restore readiness or cleanup safety. Typed
  adapters for the broader requested RDS/Lambda/CloudWatch/VPC/EKS/CloudFormation/
  Secrets Manager/Security Hub/GuardDuty lifecycle set remain incomplete. Secret
  reads and billed requests are not implicitly free or approved.
- Kubernetes supplied snapshots support pod/restart, rollout, endpoints,
  storage/node and manifest/configuration review with explicit unknown states.
  They are not continuous cluster monitoring, root-cause proof, typed Helm/ECK
  administration, approved deployment/scaling or a verified upgrade procedure.
  A [supplied RBAC JSON structural reviewer](KUBERNETES-RBAC-SNAPSHOT.md) now
  joins exact role/binding references, distinguishes namespace/cluster binding
  scope and reports selected per-rule signals without reflecting names. It
  does not establish live/effective permissions, aggregation or complete audit.
  A [Service/EndpointSlice supplied-data correlator](KUBERNETES-SERVICE-CORRELATION.md)
  now compares namespace/service label, owner UID and selected explicit port
  fields, keeping missing/default/named-target states unknown. No live
  association, connectivity or backend health is verified.
- CI/CD now has a functional manual Python verification workflow/Jenkinsfile text
  generator in addition to inert scaffold and heuristic review tools. Generation
  does not install/run tests, build Docker images, scan live dependencies, publish
  artifacts, deploy/validate staging, watch production or roll back. Those typed
  execution paths and trusted approval/recovery boundaries remain to implement.
  A separate fresh-approved [local Python test runner](PYTHON-TEST-RUNNER.md) now
  invokes fixed pytest argv in a trusted selected project using the current
  interpreter. It discards output and reports direct exit status only, not
  test counts or product readiness. It is not a sandbox or general CI executor.
  A separate fresh-approved [local Python wheel builder](PYTHON-WHEEL-BUILDER.md)
  invokes fixed build --wheel --no-isolation argv in a trusted project with a
  selected empty output folder, then hashes one bounded wheel-named file. It
  executes backend code without a sandbox. No dependency install, wheel-format/
  safety verification, publication, deployment or general CI lifecycle is added.
- The registered [typed lifecycle proposal design](TYPED-LIFECYCLE-DESIGN.md)
  validates exact EC2 start/stop, one Deployment scale or no-input GitHub workflow
  dispatch scope, returns a canonical digest and required approval/live-verification
  gates, and tests a pure no-effect state graph. Every response remains design-only,
  unverified and unauthorized. There are no effect adapters, approval receipts,
  persistent claims or live identity/cost checks in that original design module.
  The newer [disabled typed runtime](FOUR-CAPABILITIES.md) adds local TTY approval,
  durable claim/reconciliation and fake-tested EC2/Kubernetes SDK adapters. It stays
  disabled pending real-target authority/setup; GitHub's typed injected transport
  remains blocked from live HTTP until artifact/ref/effect review is solved. No
  production acceptance, dollar-budget enforcement or generic-tool retrofit is claimed.
- SRE helpers review supplied logs, telemetry windows, SLO inputs and incident
  timestamps and create postmortem drafts. They do not continuously detect live
  outages, collect/correlate arbitrary metrics/traces, prove root causes, measure
  missing incident timestamps or automatically remediate production.
- Backup creation/verification helpers are not evidence of a successful real
  restore. Dependency export review is not a live vulnerability scan.

Sources: `jarvis/devops/`, `jarvis/backup_verify.py`, tool registrations in
`jarvis/tools/builtin_tools.py`; [AWS scope](AWS-DEVOPS.md),
[CI/CD review](CICD-REVIEW.md), [pipeline generator](PYTHON-VERIFICATION-PIPELINES.md),
[telemetry contract](TELEMETRY-WINDOW-CONTRACT.md),
[backup verification](BACKUP-VERIFICATION.md).

## 5. Android

The native app has pairing/revocation, encrypted connection settings, chat,
explicit memory/reminders, opt-in WorkManager polling, user-started Live Voice,
speech fallback and settings links. New local-only actions open the system dialer,
SMS draft and calendar insert UI, selected contact/document/image pickers,
foreground plain-text clipboard controls and timestamped battery/storage/security
snapshots. An explicit foreground network-capabilities snapshot reports OS
transport and capability flags with one additional normal ACCESS_NETWORK_STATE
permission; it does not probe internet/backend reachability. They do not directly call/send/save, extract ambiguous contact numbers,
read selected image pixels or upload selected content through those older controls.

A separate system specific-number picker now reads only the selected temporary
row, validates explicit international format and requires candidate review before
copying into the number field. No broad contact directory access or verified
recipient identity is implied. A separate local panel can explicitly read one
selected UTF-8 text item up to 64 KiB and find literal text within its captured
preview, with no upload or broad storage grant.

The new [native data card](ANDROID-NATIVE-DATA.md) adds explicit read-only visible-calendar
occurrences (next seven days, first 20), per-row system calendar edit/cancel handoff,
selected-image bounded local pixel statistics, and an Android11+ one-shot approximate
foreground location/proximity-reminder check. These paths request permissions and
read only on separate explicit taps, suppress late results and have no backend/model
upload. There is no direct calendar save/delete, semantic image interpretation,
camera capture, background geofence or automatic arrival notification. Actual provider,
device, layout and permission acceptance remain unverified. Remaining implementation
includes general native contact search/export beyond system UI, semantic image
analysis, accessible-file search/organization, automatic location reminders and
permitted wake-word lifecycle. The separate Windows read path below is intentionally
one fixed action, not arbitrary remote command capability. Voice notes/security alerts and AWS alert sources also need end-to-end
integrations. A disabled-by-default [signed GitHub workflow report adapter](GITHUB-WORKFLOW-ALERTS.md)
now queues a narrow historical failure summary into the existing inbox with
exact repo scope and replay claims. Hosted delivery cannot reach localhost;
reviewed HTTPS/provider setup and actual Windows/Android display remain unverified. Existing Android ADB tools are
not a native remote Windows service or authorization model.

The [four-capability follow-up](FOUR-CAPABILITIES.md) now adds a separate native
card with bundled on-device image labels/Latin OCR, system-camera thumbnail
capture and an explicitly reviewed single-target background approximate proximity
reminder. The latter uses best-effort15-minute WorkManager checks, separate
background/notification grants, expiry/reboot/cancellation guards and no AETHER
upload. It is not an exact geofence, guaranteed arrival alert, Telugu OCR,
identity/safety assessment or all-gallery understanding. These source additions
supersede the narrow semantic-image/camera/background gaps above, not the lack
of real-device/runtime/model/notification/visual acceptance.

CI assembled a debug APK and ran JVM validator tests after the earlier local action
addition. The new card has not been run or pixel-inspected on an emulator/device.
Runtime/layout acceptance, denied/revoked permissions, OS background restrictions,
system composer outcomes and real notification delivery remain unverified. No
permission request can bypass Android platform policy.

Sources: `android/`, [phone actions](ANDROID-LOCAL-PHONE-ACTIONS.md),
[Android contract](ANDROID-CAPABILITY-CONTRACT.md).

## 6. Windows

Dashboard and local tools expose system metrics subject to hardware support.
Unsupported GPU/temperature readings stay unknown, not zero/healthy. New scoped
screenshots, exact approved-app launch, exact process stop and laptop-local URL
review are implemented with regression tests. App allowlists and URL host lists
start empty. Exact app ID/executable/hash and fresh review are needed; a PID is
not readiness. Process identity is rechecked and exit is waited for, without
name/tree/force fallback. Windows termination can lose unsaved work.

A [fresh-approved exact-name OS resolver lookup](EXACT-DNS-LOOKUP.md) now
returns bounded IPv4/IPv6 records with no application connection. Resolver
disclosure, one-outstanding-call gating and non-cancellable timeout limits are
explicit; this is not DNS authenticity or port/network health verification.

Fresh-approved bounded Windows service/startup-name and passive network-link
snapshots now exist. They do not start/stop/configure services, alter startup
entries, probe internet reachability or prove effective enabled state. A fixed fresh-approved trusted-project Python test runner is available separately;
it does not make generic command/file/Git tools typed, verified installation/update, development,
merge/conflict/PR or remote-control workflows. The older broad app/website/typing
launch path fails closed rather than bypassing the app allowlist. Legacy
default-handler open_path/open_file also fail closed for all paths so an executable
or script cannot bypass policy through a file-opening label. A separate reviewed
document/folder workflow now plans an exact digest and launches one approved
handler with one local path argument; default associations remain closed. Data
preview/read is separate. Dedicated safe URL/typing coverage and typed lifecycle
workflows remain to build.

The loopback Windows HTTP helper accepts status and narrow URL requests. It is not
a remote arbitrary shell/app/file service. Android-to-Windows scoped commands,
role/action policy, progress/output transport and cancellation of already-running
processes are substantive missing work, not solved by a caller approval boolean
or a WebSocket login. Pairing/revocation and the registry stop are useful boundaries,
not an OS sandbox or proof of remote authorization for every tool. Real laptop
hardware/foreground UI behavior and local approve/deny/replay/stop acceptance remain
unverified; development used mocked OS operations.

Sources: `jarvis/control/`, `windows_agent/`, `jarvis/tools/registry.py`,
[Windows contract](WINDOWS-CAPABILITY-CONTRACT.md),
[local inspection](WINDOWS-READONLY-INSPECTION.md),
[execution safety](EXECUTION-SAFETY.md).

## Acceptance and authority still needed

1. Windows and Android device/emulator acceptance with explicit approved local
   setup/commands, including visual inspection of the new native card. The owner
   must choose actual local executable/hash and exact host allowlists.
2. Owner-selected provider accounts/keys/OAuth consent and bounded usage approval
   for real voice/provider tests. Store secrets outside source/chat. Build success
   does not establish account access, quota, service policy or free usage.
3. Separate exact approval for deployment, paid services, real cloud changes,
   destructive operations and any external sends. No such effect is authorized
   merely by this status document.

The missing implementation above must stay open even if every acceptance item is
approved. Do not report categories 1-6 complete based on documentation, generic
shell reach or mocked regression counts.

## Integrated Android-to-Windows read-only source stage

[Foreground read-only request/result](ANDROID-WINDOWS-READONLY.md) adds one fixed
Windows memory snapshot, dedicated laptop-issued device tokens, laptop-local
interactive review, single-consume queue and requester-bound expiring results.
HTTP integration tests simulate Android protocol; native validators/source wiring
are tested separately. No real TLS/device/native-pixel acceptance is claimed.
Direct HTTPS reachability needs separate review/setup, not a port/tunnel opened
by this code. Owner-bound scoped cancellation now prevents pending reads, suppresses running
result publication or clears completed results, without promising OS termination,
undo or recall. Wider commands/results remain unimplemented.
The earlier broad missing-work paragraphs remain applicable beyond this narrow
source stage; do not interpret them as denying that this one tested path exists.

## General wellness follow-up

[General wellness support](GENERAL-WELLNESS.md) now registers a local manual
journal/planner for chosen workouts/walk/run-minute goals, meals/food notes,
activity/steps/hydration/meditation/habits and explicit-offset sleep routines.
Descriptive progress/week summaries keep unknown distinct from zero and do not
score health or infer inactivity. External NHS demonstrations are links only.
Reviewed one-shot hydration/meditation prompts reuse an already initialized local
backend reminder store; notification delivery still needs the existing opted-in
Android/private HTTPS setup and is best-effort. No sensor/wearable/medical or
personal dietary-suitability claim, media autoplay or provider/device effect is
added. This is registry functionality, not a dedicated new native wellness UI.
The older combined habit/workout weekly reviewer remains separate and unchanged.

## Security/privacy manager follow-up

[Control inventory and owner-run setup](SECURITY-PRIVACY-MANAGER.md) maps all13
requested controls to existing paths, additions and remaining gaps. New source
adds opt-in native OS credentials for integrated key lookups, an owner-configured
local four-level/exact-tool registry policy with post-review revalidation,
restricted exact file arguments, a master-only local authentication-event feed,
and owner-reviewed fixed ClamAV/pip-audit adapters. No policy or native key mode
is enabled automatically; no scanner or real key/device/provider action ran.
These are not per-device backend RBAC, universal filesystem confinement,
tamper-proof audit, pushed login alerts, a TLS bridge, security certification or
production hardening. Existing memory/stop/device/session paths stay separate
with their documented limitations.

## Rendered public browsing and custom dashboards

[Browser/dashboard workflow](BROWSER-AND-DASHBOARDS.md) adds a disabled-by-default
Playwright rendered public-page read and exact actual-link navigation with fresh
approval, exact host/public-address checks and new-context/no-login lifecycle.
This is not arbitrary click/form/account automation or an OS/network sandbox.
It also adds confirmed new local static HTML dashboards from exact supplied
metrics, nonnegative bar charts and tables; no scripts, hosting or live-data
connection. Offline Chromium integration tests and sample desktop/mobile pixel
inspection check this bounded implementation, not arbitrary website/device
compatibility or every generated dataset. Existing file/web tools remain intact.


## Local filename discovery follow-up

[Owner-selected file discovery](LOCAL-FILE-DISCOVERY.md) adds a fresh-approved,
bounded metadata-only filename search under exact configured local folders, with
optional extension-based grouping suggestions. It skips hidden entries, links/
reparse points and special files; reports limits/errors without claiming absence;
and never reads file bodies/hashes or moves, deletes, renames, opens or uploads.
This narrows the earlier accessible-file search/organization gap to one review-only
workflow, not a content index, duplicate finder, automatic organizer or sandbox.
Real laptop filesystem and provider/device acceptance remain unverified.


## Passive owner setup preflight

[Passive setup inventory](PASSIVE-SETUP-PREFLIGHT.md) now provides a separate
owner-run command that reads package metadata and configuration presence/shape
without optional SDK initialization, ADB/audio/provider/network probes or
application database writes. It omits secret values, folder paths and host names,
and distinguishes presence from runtime-tested behavior. It does not replace
device acceptance, dependency compatibility checks or existing active doctor
probes, and does not auto-install/repair anything.


## Expanded source-linked mentor scenarios

[Expanded mentor tracks](MENTOR-EXPANDED-TRACKS.md) add24 scenario lessons, bringing
the existing deeper engine to36 lessons across12 tracks. New tracks cover React
state/effects, TypeScript, CI/CD security, Terraform locking, Linux service
readiness, traces, AI tool/content safety and credential lifecycle. Existing
prerequisites, randomized objective checks, persisted weak areas, explanation
self-review and spaced-review suggestions remain. A new deterministic
`mentor_evaluate_reasoning` signal review reports expected concept coverage,
possible unsafe-choice endorsement and evidence/unknown/authority boundary
signals without storing the answer. This is not full advanced curriculum
coverage, code execution/evaluation, semantic grading, certification or
mastery assessment.


## Resumable offline evidence workflows

[Fixed offline workflow journal](OFFLINE-WORKFLOWS.md) adds owner-authored
sequences of1-10 supplied-data analyzers with exact digest/step review, atomic
single claims, restart/resume, persistent outputs and stop/cancel suppression.
Only the existing Terraform-plan, security-group, daily-cost and SLO arithmetic
reviewers are callable. No shell, live account, network, file-content input,
dynamic code, automatic next-step/retry, event trigger or deployment exists.
Failed/crashed claims block continuation rather than replaying; journals are
private local data, not encrypted or tamper-proof. This is a narrow executable
offline-plan stage, not general autonomous multi-agent effects.


## Provider-free owner console

[Local owner console](OWNER-CONSOLE.md) exposes passive setup inventory and the
new dashboard, exact-folder filename and fixed offline-workflow paths without
AI/provider access or a network listener. Interactive exact fresh approvals
reuse the existing registry/stop/policy controls; no generic command or browser
action is available. This supplies an owner-run test route, not Windows/Android
hardware, voice, remote bridge or provider acceptance.


## Resume/JD literal evidence preparation

[Literal job evidence review](JOB-EVIDENCE-REVIEW.md) adds fresh-reviewed supplied
resume/JD phrase comparison with exact context excerpts, explicit no-literal-
mention states and no ATS score, skill inference, ranking or invented experience.
A provider-free owner-console command is available; the normal AI tool workflow
can disclose supplied text to its configured provider and requires privacy
review. It does not select the latest resume, search/verify jobs, tailor factual
claims, fill forms or apply/contact anyone.


## Dedicated remote-read HTTPS source option

A [separate minimal HTTPS listener](REMOTE-READ-HTTPS.md) exposes only the existing
inert remote-read queue/status/cancel protocol, not the general Windows agent.
Its offline plan check validates an exact private IPv4/host and reviewed leaf
certificate/key; network launch needs a separate exact interactive review.
Loopback TLS/authentication/closed-surface tests pass. No LAN/public listener,
firewall, certificate trust installation or device deployment was performed.
Actual network/certificate-chain/Android trust, private reachability and owner
device acceptance remain unverified; this is not arbitrary remote commands or
production hardening.


## Reviewed document and folder opening

[Reviewed path opening](REVIEWED-PATH-OPEN.md) adds owner-configured local
handler IDs bound to exact approved applications, roots, target kinds and file
extensions. A safe planning step hashes one selected file or fingerprints one
bounded folder listing; the fresh-approved action revalidates configuration,
handler bytes and digest before starting the exact handler with one path
argument. Known executable/script/web/macro formats, network paths, links and
unapproved roots are refused. Legacy default-handler `open_path` remains closed.
This is not content-safety verification, application sandboxing, URL opening,
general typing or remote device control. Tests use fake bytes and mocked process
launch; real Windows application/UI/filesystem acceptance remains unverified.
