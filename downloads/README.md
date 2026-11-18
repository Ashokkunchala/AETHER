# AETHER direct setup files

Built from source commit `8931de221b4ed30dfcf2e16005c4d2f37cf593fc`.
Verified successful build: https://github.com/Ashokkunchala/AETHER/actions/runs/44254259588

- `AETHER-Setup.exe`: unsigned Windows setup launcher, not an offline/standalone assistant. Requires Windows10/11, Python3.11+ and internet. Inspect the included PowerShell payload and checksums before running. It asks separately to download the exact source and install packages into a NEW folder. No old installation overwrite, startup registration, provider launch or phone effects.
- `AETHER-Android.apk`: debug/test Android APK. Installing/updating is an owner action. Do not uninstall/erase an existing app to force a signature-conflicting update. Secure same-backend HTTPS, pairing and reviewed permissions still need setup and actual device acceptance.
- `install-aether-reviewed.ps1`: the readable Windows payload embedded in the executable.
- `SHA256SUMS.txt` and `SOURCE-COMMIT.txt`: exact binary integrity/source references. These are not a code signature or safety guarantee.

Download an individual file with GitHub's Download raw file button, not the webpage saved as HTML. The repository has the files directly; no Actions artifact ZIP is required. Use the raw links supplied with the completion report.

No public Release was created. These files have the SAME visibility as this repository. No user device was installed, started, paired or changed by publishing them. Do not bypass unexplained antivirus/SmartScreen/TLS warnings. This is tested source/build output, not proof all AETHER abilities work on your devices.

This batch includes custom static dashboards and optional approval-gated public rendered reads. Browser use remains off by default and needs separate reviewed Playwright/Chromium installation plus exact-host opt-in. It does not add logged-in browser actions. See [browser/dashboard guide](../docs/BROWSER-AND-DASHBOARDS.md).

Also includes owner-configured filename discovery and extension-based grouping suggestions. Metadata only, no file bodies, moves, deletes or uploads. Fresh review required; see [local file guide](../docs/LOCAL-FILE-DISCOVERY.md).

This consolidated source also includes passive package/configuration inventory,36 source-linked mentor scenario lessons and one-reviewed-step-at-a-time offline evidence workflows. These are not device acceptance, full courses, live cloud or unrestricted autonomous execution. Guides: [preflight](../docs/PASSIVE-SETUP-PREFLIGHT.md), [mentor](../docs/MENTOR-EXPANDED-TRACKS.md), [offline workflows](../docs/OFFLINE-WORKFLOWS.md).

A provider-free interactive local console is now included for reviewing preflight, dashboard, filename and offline workflow actions without starting a backend/model. No generic shell or live browser in that console: [owner console guide](../docs/OWNER-CONSOLE.md).

Also includes literal supplied resume/JD evidence navigation, exact context and explicit no-score/no-inference limits. No latest-resume selection or application/contact: [job evidence guide](../docs/JOB-EVIDENCE-REVIEW.md).

Includes a separately reviewed dedicated remote-read HTTPS source option and offline TLS/target validation. No network deployment or phone trust/acceptance: [HTTPS guide](../docs/REMOTE-READ-HTTPS.md).

This batch adds reviewed local document/folder opening through exact approved handlers. Fresh owner review is required, network/linked/protected paths and executable-like targets stay refused, and no default association, upload or extra arguments are used. See [reviewed path opening](../docs/REVIEWED-PATH-OPEN.md).

This batch adds deterministic mentor free-text rubric signals for reviewed reasoning submissions. They report concept, evidence, uncertainty and unsafe-endorsement signals only; they do not claim semantic grading, mastery, certification, code execution or lab evidence. See [mentor rubric signals](../docs/MENTOR-RUBRIC-SIGNALS.md).

This batch also adds fresh-approved one-shot deep-mentor review reminders in the existing local backend reminder store. They are not sent notifications, calendar events, recurrence, automatic practice or mastery evidence; existing notification workers need the same backend plus their separate token/TLS/permission setup. See [review prompts](../docs/MENTOR-REVIEW-PROMPTS.md).

This batch adds literal shell teaching review for one redacted command. It reports only five fixed patterns outside single quotes, with no execution, URL contact, path/variable resolution, approval, sandboxing, or security/correctness/mastery claim: [shell review](../docs/MENTOR-SHELL-REVIEW.md).

This batch adds literal JavaScript teaching review for one redacted snippet. It reports only five fixed markers outside comments and quoted/template strings, with no execution, fixes, progress writes, or security/correctness/mastery claim: [JavaScript review](../docs/MENTOR-JAVASCRIPT-REVIEW.md).

This batch adds literal TypeScript teaching review for one redacted snippet. It reports only five fixed patterns, with no compiler/type-checking, execution, fixes, progress writes, or security/correctness/mastery claim: [TypeScript review](../docs/MENTOR-TYPESCRIPT-REVIEW.md).

This batch adds literal HTML teaching review for one redacted snippet. It reports only five fixed tags/attribute patterns, with no rendering, validation, sanitization, execution, fixes, progress writes, or security/correctness/mastery claim: [HTML review](../docs/MENTOR-HTML-REVIEW.md).

This batch adds measured provider health summaries from bounded local runtime events, available through an authenticated endpoint and SAFE tool. No provider, network, quota or billing API is contacted; the summary does not route traffic, estimate cost or prove future availability: [provider health guide](../docs/PROVIDER-HEALTH.md).

Full owner-run guide: [installation downloads](../docs/INSTALLABLE-FILES.md).
