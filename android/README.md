# AETHER for Android

Native Kotlin + Jetpack Compose app with the cinematic command-centre look: deep
navy panels, cyan accents and the glowing AI Core orb. It talks to your own
AETHER backend over HTTPS on your private network.

## What the app does

- Cinematic command centre: animated AI Core orb (offline / idle / listening /
  working states), dark navy panels, cyan status lights.
- Secure connect: HTTPS health check to a user-configured backend; cleartext
  HTTP is disabled.
- Device pairing: the backend master token is sent once (never stored) to issue
  a per-device token; the issued token, backend URL and device ID are encrypted
  with Android Keystore AES-GCM. Paired devices can be revoked after an explicit
  confirmation; "Forget device token" clears this phone only.
- Chat with short conversation history: text input plus tap-to-speak speech
  recognition (transcript shown for review before sending) and spoken replies
  through the phone's installed text-to-speech voice.
- Personality modes: Assistant, Friend, Teacher, Storyteller and Doctor chips
  send the mode with each chat request, matching the web command centre. Doctor
  mode gives general health information only and is not medical advice.
- Quick actions: one-tap prompt chips (system status, story, song, AWS lesson,
  today's reminders) that fill the message box for review before sending.
- Activity & approvals feed: polls the backend's bounded runtime event feed and
  shows what AETHER is doing. Confirmations for sensitive or irreversible
  actions stay on your laptop; the phone feed is read-only on purpose.
- Live Voice: user-started full-duplex Gemini Live audio over the
  authenticated, short-lived-ticket WebSocket bridge, with visible start,
  interrupt and stop controls. The microphone runs only while the app is visible.
- Reminders: create, list, complete and recurring reminders through the
  backend; opt-in WorkManager reminder polling with Android notifications
  (best-effort, may be delayed at least 15 minutes; not an alarm service).
  Due reminders carry a "Talk now" action that opens the app with one explicit
  Live Voice offer; the microphone still starts only from your in-app tap.
  See docs/ANDROID.md for the full ability map and limits.
- Explicit memories: save, review and delete only the facts you choose.
- Phone controls: quick links to Android device, Wi-Fi, Bluetooth and AETHER
  app-permission settings; supported voice transcripts open the matching system
  screen only after you tap "Run recognized phone command".
- Language: reply language cycles through adaptive/auto, Indian English and
  Telugu.

No hardcoded secrets, no analytics, no third-party tracking, no cloud spend.

## Build the APK

Everything needed is in this directory: the Gradle wrapper (`gradlew`,
`gradlew.bat`, `gradle/wrapper/gradle-wrapper.jar`,
`gradle/wrapper/gradle-wrapper.properties`) and pinned dependency versions in
`app/build.gradle.kts`. You do not need to install Gradle yourself.

Requirements:

- JDK 17 (Android Studio bundles one, or install any OpenJDK 17).
- Android SDK with Platform 35 and Build-Tools 35.0.0. The easiest way to get
  both is Android Studio (Settings > SDK Manager). Tell Gradle where the SDK is
  with the `ANDROID_HOME` environment variable or a `local.properties` file
  containing `sdk.dir=/path/to/Android/Sdk` (never commit `local.properties`).

Option 0a - one double-click from the repository root (recommended on Windows):

```bat
SETUP-MOBILE.bat      :: install + build APK + firewall + start HTTPS backend
START-MOBILE.bat      :: start the HTTPS backend again later
```

`SETUP-MOBILE.bat` runs `scripts/setup-mobile.ps1`: it installs the Python
environment if needed, mints the LAN HTTPS certificate, builds (and with the
prompted `y` installs) `app-debug.apk`, opens the firewall port, prints the
phone-side steps, then starts the backend.

Option 0b - one script from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-android.ps1            # check JDK/SDK, build app-debug.apk
.\scripts\setup-android.ps1 -Install   # also install on a USB-connected device
```

The script verifies JDK 17+, locates the Android SDK (`ANDROID_HOME`,
`ANDROID_SDK_ROOT`, `%LOCALAPPDATA%\Android\Sdk`, or an existing
`local.properties`), installs `platforms;android-35` and
`build-tools;35.0.0` through `sdkmanager` when they are missing, writes
`local.properties`, builds the debug APK with the checked-in wrapper, and with
`-Install` pushes it to the first connected device over adb. Use `-SkipBuild`
to run only the prerequisite checks and `-Reinstall` (with `-Install`) to
uninstall the existing app first.

Option 1 - Android Studio (recommended):

1. Install Android Studio, then open this `android/` directory as a project.
2. Let Gradle sync finish (it downloads Gradle 8.9 and the dependencies once).
3. Build > Build App Bundle(s)/APK(s) > Build APK(s). The APK lands at
   `app/build/outputs/apk/debug/app-debug.apk`.
4. With your phone connected by USB with USB debugging on, use Run to install
   it directly.

Option 2 - command line:

```sh
cd android
./gradlew assembleDebug        # Windows: gradlew.bat assembleDebug
```

The APK is written to `app/build/outputs/apk/debug/app-debug.apk`. Copy it to
your phone and tap it to install (allow installs from this source when
Android asks), or install over USB with `adb install app/build/outputs/apk/debug/app-debug.apk`.

GitHub Actions also builds the debug APK on every push to this branch (the
`android-build` job in `.github/workflows/tests.yml`) and uploads it as the
`aether-android-debug-apk` artifact. A CI build proves the code compiles; it
does not prove the app runs on your phone or that your backend is reachable.

## Optional release signing

`assembleRelease` produces an unsigned APK when no release key is configured.
It never silently uses the debug key. Debug APKs are for local testing only.
To sign release builds with your own key, create `android/keystore.properties` (gitignored, along with
`*.keystore`/`*.jks`):

```properties
storeFile=/absolute/path/to/release.keystore
storePassword=your-store-password
keyAlias=your-key-alias
keyPassword=your-key-password
```

Generate a keystore once with:

```sh
keytool -genkey -v -keystore release.keystore -alias aether -keyalg RSA -keysize 2048 -validity 10000
```

Then `gradlew.bat assembleRelease` signs with it. Never commit the keystore,
the properties file, or either password. There is still no Play Store
publishing setup; release builds are for sideloading.

## Network security config (how HTTPS to your laptop works)

`app/src/main/res/xml/network_security_config.xml` is wired into the manifest
(`android:networkSecurityConfig`, with `android:usesCleartextTraffic="false"`)
and enforces two rules:

1. **Cleartext HTTP is disabled everywhere.** The bearer/device token is only
   ever sent over TLS; a plain `http://` backend URL is rejected outright.
2. **User-installed CA certificates are trusted** (in addition to the system
   store) so the laptop backend can use a private self-signed CA. Install only
   a CA you control (`data/tls/aether-ca.crt` → Settings > Security >
   Encryption & credentials > Install a certificate > CA certificate). Android
   applies this trust to HTTPS requests made by this app generally, not only
   to your configured AETHER host. Remove the user CA when you no longer need
   it. This is a documented convenience trade-off; do not use this prototype
   with untrusted networks or arbitrary remote backends.

Because the file is a normal `res/xml` resource it is compiled into the APK
(`res/xml/network_security_config.xml`) and its resource id is referenced from
the merged manifest - rebuild with `.\scripts\setup-android.ps1` after editing
it.

Verify the phone can actually reach a TLS backend from Windows before you walk
away from the laptop:

```powershell
.\scripts\https-smoke-test.ps1
```

## Connect your phone safely

1. Start the backend with `aether serve` on a machine reachable by the phone
   over a private network or a secured HTTPS host.
2. The app accepts only an `https://` endpoint. `http://127.0.0.1:8000` on the
   phone points to the phone itself, not your laptop. For plain-HTTP testing on
   a LAN, put a local HTTPS proxy in front of the backend - never send the
   bearer token over plain HTTP.
3. For a per-device credential, enter a descriptive device name and the
   backend's master `AETHER_API_TOKEN` in the pairing section, then tap
   **Pair device**. The issued per-device token is encrypted with Android
   Keystore. Manual token entry remains available for backends without the
   device-management endpoints.
4. Tap **Connect securely**, pick a personality mode, then type or speak.
5. Tap **Speak to AETHER** for one-utterance speech recognition; the transcript
   is displayed for review before sending. Speech recognition may rely on the
   Android speech service and its availability/network behavior.
6. Tap **Start Live Voice** for full-duplex audio. Live audio is sent to the
   configured Gemini service.
7. To receive due reminders, tap **Enable Android notifications** and grant
   notification permission. WorkManager checks about every 15 minutes when
   network access is available; this is not an exact alarm.
8. To revoke this paired device, re-enter the backend master token, tap
   **Revoke paired device**, and confirm. **Forget device token** clears local
   credentials only; it does not revoke the backend credential.

## Android capability and permission contract

See [the checked capability contract](../docs/ANDROID-CAPABILITY-CONTRACT.md) for
implemented versus planned features, supported APIs, OS/store limits and device
acceptance gaps. No universal app control, always-on mic or all-data access is
claimed. Permission to use Android data is not permission to upload it or run
a laptop command.

## Honest limitations

- The debug APK here is built from source on your machine or CI. Release
  signing is optional via `keystore.properties` (see above); there is no Play
  Store or other distribution pipeline yet.
- Android 14 restricts starting microphone foreground services from boot;
  launch AETHER yourself and tap Speak or Start Live Voice to use the
  microphone. There is no always-on listening.
- Telugu voice quality depends on the system language data installed on the
  phone.
- Pairing uses the shared master token to issue a per-device token. Token
  rotation, device-flow verification and production authorization remain
  required before any cloud deployment; keep the backend local/private until
  then.
- Memory add/list/delete UI exists; workout tracking and general background data
  sync are not implemented. Backend/laptop command approvals remain separate.
  Generic chat/activity display is not acceptance of arbitrary remote app control.

## Explicit local phone actions

See [local phone actions](../docs/ANDROID-LOCAL-PHONE-ACTIONS.md) for the new
optional card: system dial/SMS/calendar composers, selected contact/item UI,
foreground plain clipboard controls and limited local device snapshots. No direct
call/send/save, data upload or new broad permission. Build/source/JVM tests do not
replace pending emulator/device and visual acceptance.

## Image understanding and background proximity update

See [four-capability follow-up](../docs/FOUR-CAPABILITIES.md) for bundled image
labels/Latin OCR, system camera thumbnail handling, optional background/notification
grants, a single-target best-effort15-minute local proximity worker, expiry and
Disable behavior. No AETHER image/location upload. Models and runtime/native pixels,
OEM permissions and actual background delivery still need device acceptance.

## Direct Android launcher (0.3.0)

Install the debug APK for personal testing, then tap the AETHER icon in your
app drawer. Long-press it for **Talk to AETHER**; supported launchers let you drag
that shortcut onto the home screen. It opens visible voice controls near the top
of the app. Tap Talk to AETHER to grant microphone permission and start audio.
Opening the icon or shortcut never starts the microphone automatically.

This is an app launcher entry, not an Android HOME replacement. The laptop
backend must still be running, trusted by the phone, and paired. No permission,
provider key or working network connection is supplied by the APK itself.

The debug APK is signed with the build machine's test key. If an older install
uses another key, Android rejects the update. Do not uninstall without first
noting your pairing/recovery details; uninstalling removes local settings.
Production distribution needs an owner-controlled stable signing key and device
acceptance. See ../docs/PRODUCTION-READINESS.md.
