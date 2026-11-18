# AETHER image, background reminder, deeper mentor and typed execution update

This implements source paths for the four follow-ups requested on November 17, 2026. It does not assert that every original ability is complete or that real devices/accounts were exercised. Existing phone composers, selected-text tools, mentor lessons and Windows read-only controls remain in place.

## 1. Camera and image understanding

The Android `IMAGE UNDERSTANDING / BACKGROUND REMINDER` card can select a JPEG/PNG/WebP or open a system camera handler for one thumbnail. Camera capture uses the external system handler, not continuous camera access. No CAMERA or whole-library permission is added. Selection/capture does not start analysis. The separate `Understand selected image locally` button runs bundled ML Kit image labeling and Latin-script text recognition.

Selected content streams are capped at 8 MiB regardless of declared size; bounds are checked before sampling to at most 512 pixels per side. The decoder rejects unsupported formats and extreme dimensions using the existing image policy. A rotation control allows 0/90/180/270 degrees; automatic EXIF correction is not promised. Up to eight labels above a 0.7 score threshold and 4000 recognized text characters are shown. OCR is untrusted image content, never executable instructions. The app does not route labels/text into tools or automatically upload them to a model/backend.

The models are bundled in the APK rather than dynamically downloaded at analysis time. Dependencies and selected providers have their own telemetry/network policies; selected cloud-gallery providers can fetch the chosen image. No claim of zero third-party SDK telemetry is made. No person identity, medical diagnosis, safety decision or guaranteed scene interpretation is provided. Label scores are not calibrated probabilities of truth. Latin OCR does not establish Telugu or all-script recognition. A camera thumbnail/downsample can lose fine text/details.

Closing, clearing or leaving the foreground suppresses late local image results and drops the selection. Native inference already started may finish before buffers are released. The model tasks are allowed to finish before clients/bitmaps are closed, avoiding reuse while native work is reading them. No image is saved by AETHER and no persistent URI grant is taken. The external camera app may have its own behavior. Clearing is not secure erasure or deletion from another app.

## 2. Background location reminders

The same card now offers one explicitly reviewed local background proximity reminder, separate from the existing foreground-only manual check. It stays disabled until approximate foreground location, optional `Allow all the time` background permission and notifications are granted, and the exact target/text/radius/expiry are reviewed and enabled. Permission approval alone does not schedule or read a reminder. API30/Android11+ and an available network location provider are required. No precise/GPS or background microphone permission is added.

A target latitude/longitude, radius 100-50000 m, notification text up to 200 characters and lifetime 1-168 hours are stored in app-private preferences only on explicit enable. Enabling replaces the previous single target. Android backup is disabled by the existing manifest. Coordinates/text are not uploaded by AETHER or stored as a location history. OS/provider services can use networking to obtain location.

WorkManager checks no faster than its 15-minute periodic cadence. Each check requests one approximate network fix, with a 20-second timeout and cancellation signal. Missing, stale (over 60 seconds by monotonic time), future or invalid-accuracy fixes do not trigger. A reminder triggers only if distance plus the reported accuracy fits inside the radius. A small radius with coarse location may never trigger. Expiry is checked by wall time and monotonic time with a saved boot counter; reboot invalidates the target. Missing permissions or invalid/expired state clears/disables the reminder.

Immediately before notification the worker rechecks the exact stored target and permission/expiry state under the same lock used by Disable. It consumes the stored target before notifying to prevent duplicate retries. A process crash or notification refusal can therefore lose delivery. Notifications are marked private, but someone using the unlocked device may see the text. Disable clears the target/text, cancels the scheduled work and any still-present notification; it cannot undo something already seen.

This is best-effort periodic background delivery, not an exact OS geofence. Doze, force-stop, network/provider availability, OEM restrictions, revoked grants and notification settings can delay or miss it. Closing the image panel does NOT disable a separately enabled reminder. Use the explicit Disable button. Re-enable after reboot if still wanted. Use a separate time-based reminder when missing an arrival would matter. No reliability or safety-alert guarantee is made. Distribution through Google Play would need its own background-location policy review; this source build does not establish eligibility.

## 3. Deeper mentor mode

Six new existing-registry tools provide a local adaptive scenario mode:

- `mentor_deep_catalog`: twelve scenario lessons in four tracks, each with three stages: Python concurrency/cancellation, backend transactions/concurrency, Kubernetes operations and AWS operational safety.
- `mentor_deep_start`: teaching notes, a scenario, randomized decision order, a manual lab and a two-hour local session. Two consecutive objective passes on the prerequisite unlock the next stage.
- `mentor_deep_submit`: select all appropriate decisions and provide reasoning. A single transactional claim prevents duplicate/replayed/out-of-order session answers. Feedback gives reference reasoning, missed/unsafe decisions and a self-review rubric.
- `mentor_deep_progress`: persisted weak-area counts, progression and spaced-review suggestions. Incorrect decisions reset the streak and recommend review after ten minutes; correct streaks schedule one-, three- or seven-day reviews.
- `mentor_deep_history`: latest 20 stored explanations/objective outcomes for a chosen lesson, treated as learner data rather than instructions.
- `mentor_deep_clear`: exact confirmation plus the existing high-risk confirmation boundary clears only deep-practice rows. Starter lessons remain intact; backups/secure erasure are not covered.

This is open-book objective practice, not free-text automated grading, a secure coding sandbox, certification or proof of mastery. Reference notes remain visible. Repeating known decisions can satisfy progression without genuine understanding; the UI/tool notices say so. Reasoning is stored locally for review, not judged by keyword matching or presented as an expert assessment. No lab, cloud command, calendar event or notification is executed. The twelve starter domains and existing Python AST review/project tools remain available, but this update does not claim advanced curricula for every technology.

## 4. Typed cloud execution adapters and approval gates

`aether.devops.lifecycle_runtime` adds a durable local execution protocol beyond the earlier pure design graph. It is disabled by default and is not exposed through HTTP, Android, model tools or a remote approval endpoint. The existing proposal generator remains design-only and cannot grant permission.

The production entry refuses all work unless the owner has separately approved real-target setup, a local opt-in is configured, a connection generation is supplied, the exact canonical scope digest is allowlisted and a local interactive terminal is used. An allowlist entry authorizes neither a write nor free spending. Preflight queries can access private account metadata and incur request charges; approve that access before enabling them. No real credentials or provider calls were used during development.

A pending request stores immutable scope and bounded live preflight evidence. It expires 120 seconds after preflight, checked against wall and monotonic time with a boot binding; a reboot invalidates write approval. A local TTY review displays exact scope/evidence and requires `APPROVE COST AND EFFECTS <digest prefix>`. Generic yes, piped input, caller booleans and simulation events cannot approve. Approval includes a clear warning about ongoing provider charges, outage/data-loss and the absence of an enforced dollar budget. Do not approve if the cost scope is unknown or unacceptable; arrange provider budget/limits and specific spending authority separately. No amount or price is guessed.

Execution repeats preflight, rejects drift, checks stop/revocation/generation/expiry/scope, then atomically claims once. The typed SDK driver invokes the request guard again at its write entry. There is no shell/generic CLI fallback, force variant, automatic retry or deployment broadening. The SDKs are optional `typed-live` dependencies; the app never installs them on demand. External credential-process/exec/auth-provider plugins and disabled TLS are refused rather than silently running machine commands.

Implemented SDK paths:

- EC2 start/normal stop of one exact EBS-root instance. STS account/partition/principal and region/instance/state are checked. Spot/scheduled lifecycle and unknown/enabled stop protection are refused. No force, hibernation, skip-OS-shutdown or termination. Write retries are disabled. Verification checks the exact instance's running/stopped state, not application health or proof that this request alone caused it. Costs, instance-store data loss, outage and addressing remain explicit review items.
- One Kubernetes Deployment scale through the typed Scale subresource with UID/resourceVersion and exact namespace/name. Cluster identity uses the adapter's documented `kube-system` namespace UID plus the SHA-256 of the exact CA file bytes and context. Live HPA ownership, object version and replicas are checked. HPA present/unknown, incomplete inventory or drift blocks. Server resourceVersion conflicts are not automatically retried. Desired replica count is not readiness, rollout or SLO health. Other controllers and the preflight-to-write race remain limitations; no provider transaction is claimed.
- A typed GitHub no-input dispatch/returned-run verification transport contract is implemented and tested with an injected fake. It is deliberately NOT wired to live HTTP: mutable branch/tag ref races and complete workflow/default-input/dependency-effect review remain unresolved. The production router refuses it. A caller claiming `ref_pinned=true` cannot turn on real dispatch. This is an explicit remaining implementation/review gap, not an account-approval switch or finished live CI executor.

Timeout after adapter entry leaves `outcome_unknown`, not success or definite failure. Executing the same request again is refused. Explicit read-only reconciliation can verify the same target without redispatch; an expired approval never permits another write. Stop/revoke/cancel after dispatch is a cancellation request, not proof the remote operation was killed. Completed effects are not undone. A process crash after claim also needs reconciliation. Request/stop checks cannot be atomic with external providers; a narrow check-to-provider race remains.

No real target should be enabled from an example, guess or broad request to finish development. The installed local software's approval flow is separate from the permission needed for us to operate the user's laptop/accounts. Existing generic AWS/terminal/provider tools retain their own policies and are not silently authorized or upgraded by this module.

## Verification and remaining acceptance

Python tests exercise model integration source contracts, background permission/scheduler/privacy boundaries, adaptive progression/replay/concurrency/deletion, disabled live startup, exact local approval, drift/expiry/revocation/stop, at-most-once claim, cancellation-at-write, ambiguous timeout/reconciliation, and typed EC2/Kubernetes/GitHub fake driver shapes. JVM policy tests exercise image dimensions, age/accuracy/distance and reminder expiry/reboot boundaries. Native CI must still compile models/UI and run JVM tests.

No actual camera capture, selected-image read, background location, notification, OS grant, laptop command, AWS/Kubernetes/provider mutation or spending occurred while developing/testing. Actual Android model accuracy, native layout, lifecycle/OEM permissions/background delivery and real account acceptance are unverified. Tests against fakes are not production acceptance.

Needed from the owner before effects: exact approved Windows/Android device test steps; optional background-location/notification grants and a specific reminder; and any real cloud target/account/preflight/spending/outage/data-loss scope. GitHub live dispatch additionally needs an approved implementation strategy, not merely credentials. The software does not need secret values in chat; use secure setup on the actual device/account.

## References

- Bundled image labeling: https://developers.google.com/ml-kit/vision/image-labeling/android
- Bundled Latin OCR: https://developers.google.com/ml-kit/vision/text-recognition/v2/android
- Background location permission: https://developer.android.com/develop/sensors-and-location/location/permissions/background
- Async cancellation/task groups: https://docs.python.org/3/library/asyncio-task.html
- Transaction isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- Deployment behavior: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
- EC2 states/billing: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
- Typed proposal limits and provider references: [TYPED-LIFECYCLE-DESIGN.md](TYPED-LIFECYCLE-DESIGN.md)
