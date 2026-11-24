# AETHER readiness review, November 24, 2026

## Verdict

AETHER is a personal-use release candidate, not certified production-ready.
Build and regression tests are evidence about the tested code, not proof of every
ability on a real Windows laptop, Android phone or live external service.
No deployment, real cloud operation, paid provider call or user-device installation
was performed in this review.

## Checks

- Clean Python 3.11 environment: complete backend test suite and real Chromium
  dashboard/browser tests, syntax/undefined-name lint, installable wheel build.
- Python dependency audit: no known vulnerabilities in the installed environment
  at audit time. This is not a guarantee and does not cover Android dependencies.
- Android: debug compilation, JVM unit tests, Android lint and unsigned release
  compilation. Android lint was run separately; existing CI assembles the APK.
- Safety review: existing master/device authentication, explicit sensitive-action
  approvals, bounded tool inputs, foreground microphone lifetime and HTTPS pairing.
  This was not an independent penetration test.

## Fixed in this review

- Added AETHER adaptive app icon and Talk to AETHER launcher shortcut, with visible
  quick-start controls near the top of the screen. No automatic recording.
- Added system-bar safe padding for Android edge-to-edge layouts.
- Removed silent debug-key fallback for release builds. Missing owner signing
  configuration now yields an unsigned release APK, not a false production build.
- Disabled authenticated HTTP/WebSocket redirects in chat, pairing, reminder and
  live-voice paths; validates backend URLs as HTTPS origins without embedded
  credentials, paths, queries or fragments. LAN ports remain supported.
- Fixed Android lint API/permission errors in microphone and one-shot location
  paths; retains explicit permission handling and Android 11+ location guard.
- Made the Gradle wrapper executable on Linux.

## Production acceptance still required

1. On the owner's Windows 11 laptop: clean installation, startup, microphone,
   speaker, wake phrase, interruption, recovery after network/provider failure,
   and approved local app/file/email operations. Existing tests use fixtures for
   many integrations and cannot establish live provider availability.
2. On the owner's Android 14 phone: installation/update, launch icon, long-press
   shortcut, pairing over trusted LAN HTTPS, permission denial/revocation, voice,
   backgrounding, reminders under battery optimization and offline recovery.
3. Owner-controlled persistent Android signing key, securely backed up; stable
   signing certificate for upgrades. Test APKs from different builders may have
   different debug certificates. Do not uninstall an existing app blindly.
4. Live provider keys/model access, HTTPS trust and private-network connectivity.
   The Android app is a companion, not a standalone local AI backend.
5. Before internet exposure: separate deployment/threat review, TLS/reverse-proxy
   configuration, backups and restore drill, audit retention/rotation, production
   dependency lock/rebuild policy and monitoring. Do not expose this personal
   backend publicly just because tests pass.

## Known warnings and limits

Android lint may report non-fatal dependency-update/style warnings. User-installed
CA trust is intentional for the owner's private LAN certificate, not a promise of
public-service security. Debug APKs are personal test builds, not Play Store
releases. Release signing and real-device acceptance are not solved by compilation.
Previously documented plan-only/lab/music and missing live-collector abilities
remain limits. No claim is made that all blueprint abilities are implemented.

## Install and launch

Download the test APK, verify its SHA256 using the adjacent checksum file, install
on the phone, then open AETHER from the app drawer. Pair with the running HTTPS
backend. Long-press the icon and choose Talk to AETHER; supported launchers can
place that shortcut on the home screen. Tap the in-app Talk button to start audio.
The shortcut never bypasses microphone permission or starts background listening.
