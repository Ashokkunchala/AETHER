# AETHER installation downloads

Use a **successful current-commit Actions run**, not an older red/cancelled run. The run page lists the source commit and downloadable artifacts. GitHub artifact downloads normally require a signed-in GitHub account. No public release is created. Artifacts are retained for 14 days from each run, then must be rebuilt/downloaded from a newer successful run.

## Windows

Download `aether-windows-setup` and extract its outer GitHub ZIP. It contains:

- `AETHER-Setup.exe`: unsigned Windows console launcher with a commit-pinned, owner-reviewed setup script embedded.
- `install-aether-reviewed.ps1`: the same stamped, readable payload for inspection or a manually approved PowerShell route.
- `AETHER-Source.zip`: source/setup files for the exact run commit, not a full offline Python environment.
- `SOURCE-COMMIT.txt`, `SHA256SUMS.txt` and this guide.

The executable is a setup launcher, **not a standalone packaged AETHER app**. Windows10/11, a working Python3.11+ install and internet/package access are required. The source ZIP is also not an offline installer. Voice/API access, backend TLS and phone pairing require separate configuration and real-device checks.

1. Confirm the run succeeded and matches the commit you want. Extract the bundle into a new folder, not an old/conflicted AETHER folder. Review the script and checksums. A hash in the same unsigned ZIP checks consistency, not publisher identity; compare with the run/source you trust. The executable is unsigned, so do not bypass unexplained SmartScreen/antivirus warnings.
2. Only if you approve its described effects, open `AETHER-Setup.exe`. First it shows the exact commit and asks you to type `DOWNLOAD AETHER`. That downloads the commit into a unique new `%LOCALAPPDATA%\Programs\AETHER-...` folder. It does not overwrite the old install.
3. Review `scripts\setup-windows.ps1` in that folder. The next explicit prompt is `INSTALL REVIEWED PACKAGES`. Only your answer starts setup in the fresh folder, creates `.venv`/`.env` and downloads/installs Python packages. It does not ask for an API key, register startup, start the assistant/backend, open a firewall, pair a phone or run cloud commands. Declining leaves the downloaded source for review. Setup errors must be checked before continuing.
4. Follow [owner-run checks](OWNER-DEVICE-AND-CLOUD-SETUP.md) for temporary local tests and the reviewed launch/setup path. Do not use the older all-in-one/bootstrap startup route just because it is also present in the source. Keep your old working folder intact. Enter persistent keys only through the reviewed local secret flow, never chat/screenshots.

The signed-in CI Windows runner compiles this launcher and tests only a harmless embedded probe's extraction/exit forwarding/temp cleanup, then checks the normal clean source/package setup. It does **not** run the actual installer on your laptop or prove microphone/audio/device pairing. No installed-package state is bundled, and future package-index changes can affect installation even though the source is pinned. The built installer is not Authenticode-signed.

## Android

Download `jarvis-android-debug-apk` from the **same successful run** and extract `app-debug.apk`. The artifact keeps this legacy name; the user-facing project is AETHER. This is a debug/test APK, not a Play Store release or a signed production release with an update guarantee.

1. Transfer the extracted APK to your Android phone through a route you trust. Inspect Android's install prompts and package details. Installation is your action, not something performed remotely here.
2. Do not uninstall an existing app or erase data to force an update. If Android reports a signing/package conflict, stop and report the exact message. Existing device data/signing identity needs review first.
3. Open it after installation. The APK alone is not a private laptop connection: you still need the owner-approved same-backend HTTPS URL/trust, pairing, device token and notification/microphone permissions. See [the owner device guide](OWNER-DEVICE-AND-CLOUD-SETUP.md). Do not expose the backend publicly or bypass TLS validation to make pairing work.
4. Start with local UI/permission checks and explicit consent. Real camera recognition, microphone/voice, background notifications, private bridge and OEM behavior remain device acceptance tests; CI compilation is not proof they work on your phone.

If the same run is not fully successful, do not present its files as the current verified installers. If artifacts expired or you cannot sign into GitHub to download them, request a fresh build/delivery, not an old unverified binary. No cloud deployment, provider message, purchase, startup registration or machine/device effect is implied by downloading these files.
