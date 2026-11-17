# AETHER: owner-run install, device checks and real-target setup

This is a manual guide, not a report that anything was installed, enabled or tested on your devices. The tested feature baseline is commit `b3a528eb38366d50f85dc015ef64d86c1543e604`, with [green build checks](https://github.com/Ashokkunchala/AETHER/actions/runs/43993786137). Native layout, camera/model accuracy, background delivery and real cloud behavior still need acceptance. Run only the steps you choose. Stop on any mismatch/error; do not improvise force/reset/uninstall commands or send secrets in chat.

## A. Android: install and test local features first

1. On your computer, open the green build above, sign in to GitHub if requested, and download the `jarvis-android-debug-apk` artifact under **Artifacts**. Extract its ZIP and confirm it contains `app-debug.apk`. This is a debug-signed test APK, not a production/store release. The artifact was available when this guide was written; retention is 14 days. Do not use an APK from a different run or unknown source.
2. Transfer the APK to your own Android phone using your chosen USB/file-transfer route. Open it on the phone. If Android asks, allow installation from that file app only for this install, then turn that permission off afterward. If it reports an incompatible signature or asks to uninstall the old app, STOP and report that screen. Uninstalling may erase app settings/reminders; no uninstall or data wipe is part of this guide.
3. Open AETHER. Leave backend URL/token empty for these local checks. No cloud/model API key is needed for bundled labels/OCR or local reminders. Keep Live Voice off. The older chat/voice functions need their own backend/provider setup and can consume paid API usage; they are not part of this test.
4. Open **IMAGE UNDERSTANDING / BACKGROUND REMINDER**. Choose a harmless photo with an obvious object and some Latin text. Selection should not run analysis. Tap **Understand selected image locally**. Expect candidate labels and OCR with uncertainty notices, not guaranteed descriptions. Try rotation if text is sideways. Do not use private documents or medical/safety images for the first test.
5. Tap **Clear image and local result**. Then try **Open system camera for one thumbnail**, capture a harmless object, and separately analyze it. A missing camera handler must show a failure, not a capture success. Start another analysis and leave the app: returning should not expose a stale analysis result. Camera/gallery apps and SDKs have their own policies; no AETHER backend upload is added.
6. For calendar acceptance, open **NATIVE CALENDAR / IMAGE / LOCATION**, request read-only calendar permission, then separately tap **Read next 7 days locally**. Check one known event's title, time, all-day/end-exclusive label and the 20-row limit. First deny permission and verify no read is claimed; grant it only if you want your visible calendars read locally. The edit button opens another app. Cancel there during this test; do not save/delete a real event unless you separately intend that exact change and its attendee effects.
7. Do not enable a background reminder until its exact target/text/radius/expiry are settled in section C. First you can deny location/notifications and verify that Enable refuses. Android11/API30+ is required for these one-shot network-location paths; older phones must show unavailable, not success.

Record: Android version/model, installed APK/run, each check's pass/fail and the exact nonsecret error text. A screenshot can help with layout, but redact calendar titles, image OCR, coordinates and tokens first. No claimed pass replaces what actually happens on the phone.

**Alternative if the artifact expired:** with Git, JDK17 and Android SDK Platform35/Build-Tools35.0.0 already installed, use the fresh source folder in section B, open its `android` folder in Android Studio, let Gradle sync/download dependencies, then **Build > Build APK(s)**. The output is `android/app/build/outputs/apk/debug/app-debug.apk`. This can download a large SDK/dependency set. Do not run mobile setup scripts merely to obtain an APK: some also change firewall/TLS/backend/device state.

## B. Windows: isolated source and local checks

Use a NEW folder, not the older working copy that previously had merge conflicts. These commands download/build/run project code locally, install Python dependencies and write a local virtual environment. They do not enable a cloud adapter, expose a network listener, install startup tasks or grant remote control. Review the commands before running them. Git and Python3.14 must already be installed; otherwise report that prerequisite rather than approving an unrelated installer automatically.

1. Open a normal, non-administrator PowerShell window in a parent folder you choose. Confirm no `AETHER-device-test` folder already exists there. Run one command at a time and stop if one fails:

```powershell
git clone --branch jarvis-cinematic-local-voice --single-branch https://github.com/Ashokkunchala/AETHER.git AETHER-device-test
Set-Location .\AETHER-device-test
git status --short
git rev-parse HEAD
```

`git status --short` should be empty. The feature baseline above must be included in the checked-out branch; newer documentation commits may make HEAD different. Do not reset, merge, rebase, clean or overwrite your old copy. If another agent/user has changed source since this guide, review that difference before running it.

2. Create a fresh local Python environment and install the repository's test dependencies (downloads from the configured package index):

```powershell
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

If `py -3.14` is unavailable or pip reports an unavailable package/build failure, stop and send the nonsecret error. Do not silently replace pinned constraints. Voice drivers, startup registration, `INSTALL-JARVIS.ps1`, `SETUP-MOBILE.bat`, firewall rules and administrator access are intentionally excluded from this minimal path.

3. Run only the targeted local tests. They execute trusted project code against temporary databases and fakes, not real AWS/Kubernetes resources or providers:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mentor_deep.py tests/test_lifecycle_runtime.py tests/test_android_advanced_companion.py -q --no-cov
```

These tests do not prove Windows hardware control or Android runtime acceptance. Report the actual pass/fail output; don't infer readiness from a previous CI count.

4. Read the deeper mentor catalog without calling a model/provider or changing cloud state:

```powershell
.\.venv\Scripts\python.exe -c "import json; from jarvis.mentor_deep import DeepMentor; print(json.dumps(DeepMentor.catalog(), indent=2))"
```

Expected: twelve scenario lessons across Python/backend/Kubernetes/AWS. The registered `mentor_deep_start`, `mentor_deep_submit`, `mentor_deep_progress` and `mentor_deep_history` paths write only local mentor practice data when used. Objective results are not free-text mastery grades.

5. Confirm typed live execution stays disabled before any credential/client access. First check the opt-in variable is absent:

```powershell
Test-Path Env:AETHER_ENABLE_TYPED_LIVE
```

Expected: `False`. If `True`, STOP and review who enabled it and which targets were intended. Do not run the next check while it is enabled. If `False`, run:

```powershell
.\.venv\Scripts\python.exe -m jarvis.devops.lifecycle_runtime status
```

Expected: a nonzero exit with **Disabled**. This is the expected safety result, not a setup failure. Do not set enable variables or run prepare/review/execute against real accounts yet.

**Remote Android-to-Windows testing is a separate checkpoint.** The RAM helper remains loopback-only on the laptop. Android requires a reviewed HTTPS443 companion origin with valid trusted TLS, per-device token and no insecure redirect/certificate bypass. The current guide does not provide a tested secure bridge to that loopback listener. Do not expose port8765/8000, open a firewall, forward ports, use HTTP or disable certificate checks to make the phone connect. Report the intended network/hostname arrangement first. Local phone features above work without this bridge. See [read-only protocol limits](ANDROID-WINDOWS-READONLY.md).

## C. Set one real background reminder after the details are confirmed

Required: exact place or coordinates, exact notification text, radius in meters (100-50000) and lifetime in hours (1-168). A place name needs resolved coordinates confirmed before enabling; do not guess a similarly named branch/building. This is a proximity reminder before expiry, not a scheduled clock-time reminder.

1. Open the advanced card. Read its best-effort notice. If missing arrival would matter, choose a separate clock-time fallback in your usual reminder app. AETHER does not automatically create that fallback.
2. Tap **Request approximate foreground permission first**, then choose the OS's approximate/location-while-using option if you consent. The app does not require precise location.
3. Tap **Review optional background location in Android Settings**. In the app's location permission page, choose **Allow all the time** only if offered and wanted. Labels vary by Android/OEM. If unavailable, stop; there is no bypass. Return to AETHER. Granting permission alone does not enable a reminder.
4. Tap **Request notification permission** and allow it if wanted. On older Android, check app notifications in Settings. If notifications/channel are disabled, delivery cannot be relied on.
5. Enter the confirmed latitude, longitude, radius, lifetime and exact text. Tap **Review background reminder (does not enable)**. Check the displayed scope. It replaces any previous single local proximity reminder. Tap **Enable this exact local background reminder** only if correct.
6. Tap **Read local enabled/expiry status** and check the actual expiration. This confirms local configuration, not future delivery. AETHER stores one target/text locally and checks best-effort every15 minutes; power/network/OEM/force-stop/permissions can delay or miss it. Approximate accuracy must fit inside the radius, so a small radius may never trigger. The worker consumes the reminder once before notifying; a crash can lose delivery. It is not an exact geofence or a safety service.
7. To stop: tap **Disable and erase background reminder**, then check status again. Closing the panel does NOT disable it. Reboot invalidates it; re-enable explicitly if still wanted. Revoking background permission also prevents future checks. Disable cannot recall a notification already seen; deletion is not secure erasure/backups.

Do not walk/drive somewhere just to test this. Use a harmless target you normally visit or your present area with a radius wide enough for approximate location, if that is the reminder you actually want. Report the actual notification/time and any miss as observations, not a guarantee.

## D. Real cloud target checklist, before setup or any provider access

Pick ONE operation first. Do not send passwords, tokens, access keys, kubeconfig content, certificates, card details or secret environment dumps. Nonsecret account/resource identifiers can be provided privately. Existing local SDK credentials are set up on your own machine through the service's supported sign-in, not pasted in chat.

| Target | Exact facts needed |
| --- | --- |
| AWS EC2 start or normal stop | Operation;12-digit account ID; partition; region; local profile label; exact instance ID; expected state (stopped for start/running for stop); EBS root; stop protection; Spot/scheduled status; instance-store/data dependencies; expected workload impact. Live checks must verify, not trust these supplied observations. |
| Kubernetes Deployment scale | Current context label; reviewed endpoint/CA identity (no secret files in chat); cluster binding (this adapter uses `kube-system` namespace UID); namespace; Deployment name/UID; fresh resourceVersion; current and desired replicas; HPA/other-controller ownership; capacity/quota/workload impact. The CA digest is SHA256 of exact CA file bytes, to be checked locally. |
| Any real operation | Account owner/authority; who/what may be affected; exact allowed action and deadline/window; cost currency and maximum incremental spend over a defined duration; how ongoing resources will be stopped/capped; acceptable outage duration; data-loss exclusions; who approves and verifies recovery. A start/stop/scale-back is not automatically safe rollback. |

The typed runtime has NO enforced dollar budget. Before enabling it, the exact cost/spend scope must be understood and approved, with suitable provider budget/limit controls or a decision not to proceed. A zero/unspecified budget does not make requests or running resources free. Timeouts can leave outcomes unknown; do not repeat writes. Reconciliation is a separate authorized read, not automatic success or automatic rollback.

This guide intentionally provides no live enable/prepare/execute command against an unspecified target. Once the checklist is grounded, the next proposal must show the exact local setup and target-bound scope for review. Connection generation, allowlist and a local TTY cost/effect approval remain required. External credential-process/exec plugins are unsupported; no shell fallback. The account/cluster read itself needs approval before preflight.

GitHub workflow dispatch remains blocked from live HTTP pending immutable-ref and complete workflow/default-input/dependency/effect review. Credentials or a broad "All" do not finish that implementation. Existing generic AWS/terminal tools are not a substitute for the typed gate.

## What to send back

1. Windows version plus whether Git/Python3.14 are installed; Android version/model; whether an older AETHER app must retain its data. For remote RAM testing, also the intended private network/HTTPS hostname setup, not secrets.
2. Reminder: exact place/text/radius/expiry. If missing it matters, the desired independent time fallback.
3. Cloud: one operation/target from the checklist, spend limit and duration, outage/data-loss limits. "Not now" is a valid choice; device/local acceptance does not require cloud setup.

Full feature limits and source references: [four-capability update](FOUR-CAPABILITIES.md). No action in this guide has been run on your devices/accounts by the assistant.
