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

Twelve starter domains have introductory material, objective checkpoints,
feedback, study plans, latest progress/weak-area summaries, mock-interview and
practice-project material, an offline Terraform lab and new daily checkpoint
history. Local examples and generated project text do not execute a lab or create
a GitHub repository. Objective choice grading is not a coding sandbox, a verified
code review, adaptive advanced curriculum, certification preparation for every
exam, or evidence of mastery. Full beginner-to-advanced coverage of every named
language/cloud/tool and secure live coding/command evaluation remain substantive
implementation work. Automatic terminal practice and proactive learning delivery
also need their own scoped execution/notification integration.

Sources: `jarvis/mentor.py`, `mentor_projects.py`, `mentor_terraform.py`,
`mentor_activity.py`; [mentor activity](MENTOR-ACTIVITY.md),
[Terraform mentor](MENTOR-TERRAFORM.md), [blueprint](ABILITIES.md).

A bounded offline [Python snippet teaching reviewer](MENTOR-PYTHON-REVIEW.md) now
checks five explicit AST patterns with source links and location-only findings.
It never imports/runs code or writes progress. Aliases/control flow and general
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
read selected image pixels or upload selected content.

A separate system specific-number picker now reads only the selected temporary
row, validates explicit international format and requires candidate review before
copying into the number field. No broad contact directory access or verified
recipient identity is implied. A separate local panel can explicitly read one
selected UTF-8 text item up to 64 KiB and find literal text within its captured
preview, with no upload or broad storage grant. Remaining implementation includes general native
contact search/export beyond system UI, scoped image
analysis, accessible-file search/organization, calendar read/edit/cancel, location
reminders, permitted wake-word lifecycle and authenticated
scoped Windows remote commands/results. Voice notes/security alerts and AWS alert sources also need end-to-end
integrations. A disabled-by-default [signed GitHub workflow report adapter](GITHUB-WORKFLOW-ALERTS.md)
now queues a narrow historical failure summary into the existing inbox with
exact repo scope and replay claims. Hosted delivery cannot reach localhost;
reviewed HTTPS/provider setup and actual Windows/Android display remain unverified. Existing Android ADB tools are
not a native remote Windows service or authorization model.

CI assembled a debug APK and ran JVM validator tests after the local action
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
or script cannot bypass policy through a file-opening label. Scoped default
document/folder-handler launch remains unimplemented; data preview/read is separate. Dedicated safe
URL/typing coverage and typed lifecycle workflows remain to build.

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
by this code. Scoped cancellation and wider commands/results remain unimplemented.
The earlier broad missing-work paragraphs remain applicable beyond this narrow
source stage; do not interpret them as denying that this one tested path exists.
