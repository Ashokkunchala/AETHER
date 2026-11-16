# AETHER Android companion: capability and permission contract

Source review and Android documentation checked November 16, 2026. This is an
offline design/acceptance contract, not device testing, Play approval or delivery
of all requested abilities. No device was connected, installed, controlled or
queried. Android runtime, API target, manufacturer, installed handlers/services,
user grants and distribution policies all affect availability.

## Local phone actions addendum

The new [local phone actions](ANDROID-LOCAL-PHONE-ACTIONS.md) card adds explicit
ACTION_DIAL, SMS ACTION_SENDTO and calendar ACTION_INSERT composers, a system
contact picker without number extraction, a separate [specific-number picker](ANDROID-SELECTED-PHONE-NUMBER.md)
with selected-row-only access and explicit candidate review, selected document display metadata,
and a separate [explicit selected UTF-8 text preview/find](ANDROID-SELECTED-TEXT.md),
image selection without analysis/upload, plain-text foreground clipboard buttons,
and battery/app-volume/keyguard/own-permission snapshots. These composer/picker
paths add no new manifest grant. The separate [foreground network snapshot](ANDROID-NETWORK-SNAPSHOT.md)
adds the normal ACCESS_NETWORK_STATE permission and a local-only capabilities
button. No background service, direct call/send/save, broad file/contact read, remote command
or provider disclosure is added. Source/JVM/build tests are distinct from missing
Android runtime and visual acceptance. The capability matrix below records the
original reviewed baseline; this addendum supersedes its "not implemented" cells
only for the narrow routes just named. It does not turn selection into analysis,
verified person/phone identity, file organization or confirmed communication delivery.

## Original reviewed source baseline

The native app has minSdk 26, targetSdk/compileSdk 35. The manifest declares
only INTERNET, RECORD_AUDIO and POST_NOTIFICATIONS and one launcher activity
at the original baseline. The network-snapshot addendum adds ACCESS_NETWORK_STATE;
current source checks cover those four declarations.
No foreground microphone service, boot receiver, accessibility service,
notification listener, default-assistant implementation, SMS/call-log/contact/
calendar/location/storage/camera permission is declared. Permission declaration
is not proof of an actual runtime grant.

Implemented source paths, not real-device acceptance:

- Typed HTTPS backend chat; user-started system speech recognition displays a
  transcript for review before Send. Recognition availability/network/privacy
  depends on the Android speech service.
- User-started visible Live Voice uses AudioRecord/AudioTrack and an HTTPS/WSS
  backend ticket. Lifecycle ON_STOP/disposal stops its controller. No always-on
  wake word or background mic. Audio goes to the configured backend/provider;
  it is not promised on-device/offline. Permission denial leaves typed chat.
- Explicit buttons/recognized commands open device/Wi-Fi/Bluetooth/app settings.
  Opening settings is not changing those settings or controlling other apps.
- Opt-in notifications use the backend due-reminder and integration-notification
  inbox, permission/channel checks, network-constrained 15-minute WorkManager
  periodic work and an ordinary tap-to-open-activity PendingIntent. Delivery is
  best-effort, can be delayed/missed and is not an exact alarm or immediate alert.
  A notification does not start voice recording. Source-specific GitHub/AWS/
  laptop alerts require their own configured upstream and authority; an inbox
  poll alone proves none are connected.
- Backend pairing/per-device encrypted credential, chat/activity display,
  reminders and memory UI are present. The old README sentence saying memory
  editing is absent is stale: source has add/list/delete memory requests.
  This does not imply full sync, context parity or access to every desktop tool.

Source files: android/app/src/main/AndroidManifest.xml, app/build.gradle.kts and
src/main/java/com/ashok/jarvis/{MainActivity,LiveVoiceController,ReminderWorker,
TokenVault}.kt under android/app. Internal package/credential names are retained.

## Requested ability, safe route, current gap

| Ability | Supported design route and limits | Current native-app state |
| --- | --- | --- |
| Wake word/background voice | Ordinary mic grant is not blanket background permission. Android 12+ foreground-service starts and Android 14+ while-in-use mic checks constrain starts; a correctly declared microphone foreground service needs its own permissions/type and visible ongoing use. Notification interaction can qualify for a documented exception, not silent boot listening. User-selected VoiceInteractionService/default assistant is a separate role with device/hardware/policy limits, not a universal hotword entitlement. | Visible sessions only; no service/role/hotword engine. |
| Voice conversation from notification | Prefer user tap opening visible activity, then explicit mic action. Any background service implementation needs exact API/lifecycle review, notification and revocation testing. | Tap opens app only. |
| Calls | ACTION_DIAL opens a reviewed number; user taps Call. Direct ACTION_CALL requires CALL_PHONE/runtime permission and separate exact-call approval, with device/SIM/handler limits. | No dial/call flow. No call-log access. |
| SMS | ACTION_SENDTO with smsto: opens a recipient/body draft; user sends. Composer launch is not delivery. Direct SMS/reading/history requires applicable permissions and platform/role/carrier restrictions. Google Play separately restricts SMS/Call Log permissions to permitted core uses/roles or approved exceptions; runtime yes alone does not satisfy store policy. | No compose/send/inbox route. Never infer role/Play eligibility. |
| Contacts | User contact picker for selected data first; broader directory query only if needed with explicit READ_CONTACTS permission and scoped query. Resolve exact person/number before calling/messaging. | Not implemented. |
| Camera/gallery analysis | Delegate capture to camera handler and use content URIs; photo picker grants selected media without broad media permission. Direct camera capture needs CAMERA and lifecycle controls. User selection is access to that item, not approval to upload it to a model/backend. Show destination/data disclosure separately. | No picker/capture/upload/analysis flow. No whole-gallery search. |
| Files search/organize | Storage Access Framework for selected documents/tree and granted operations; app-owned files otherwise. Android 11+ restrictions exclude other apps' private data and certain roots/Download-tree/Android data/obb. Persist only eligible explicit URI grants. Moving/deleting needs exact-item review and authority. | No native file picker/organizer. No all-files access. |
| Calendar | ACTION_INSERT presents a reviewed event to calendar UI without broad calendar access. Direct read/edit/delete requires provider permissions and exact account/calendar/time/audience authority; returning from UI is not saved-event proof. | Not implemented. Backend reminders are not Android calendar events. |
| Location reminders | Fine/background permissions as required, disclosure and scoped geofence setup. Google Play background-location rules also apply. Geofences can arrive late or fail with stale location/network/power restrictions; offer a time-based fallback for consequential reminders. | No location permission/geofence implementation. |
| Launch apps | Supported exported activities/intents/deep links only; missing handler/refusal is normal. Android package visibility limits inventory queries. Use narrow queries if needed, never QUERY_ALL_PACKAGES by default. Opening app is not permission to inspect its data or automate UI. | Settings destinations only, not generic launcher. |
| Clipboard | Explicit user copy/paste with foreground focus. Android 10+ limits reads to focused app/default IME; do not claim continuous background clipboard access. Never auto-send clipboard secrets. | No clipboard helper. |
| Battery/storage/network | BatteryManager, StatFs on accessible volume and ConnectivityManager can report scoped values; unknown/unavailable must stay unknown. Network state query needs ACCESS_NETWORK_STATE. Storage capacity is not file inventory or all-app storage. Connectivity is not internet/backend reachability. | No native status dashboard. |
| Wi-Fi/security status | Open settings and show app's own permission/channel status. Ordinary API35 app cannot silently toggle Wi-Fi using deprecated setWifiEnabled; privileged/device-owner exemptions are not assumed. No full-device malware/security audit or other apps' permission control. | Settings buttons only. |
| Laptop command/results | Existing secure backend route is a foundation. Explicit pairing, device revocation, per-command allowlist, exact target/arguments, replay/expiry/stop controls and laptop-side approval must govern execution. Phone authentication/mic permission never approves a shell/DevOps action. | Chat/activity/pairing exist; not accepted as arbitrary remote-control interface. |
| Voice notes, approved Windows app control, CPU/RAM/disk | User-selected recording/upload destination and separate authenticated typed laptop adapters with source/as-of, allowed app operations and result verification. No arbitrary remote shell. | Not implemented end-to-end in native app. Desktop/ADB modules are separate, not phone feature proof. |
| Security/GitHub failure/AWS cost/learning alerts | Typed upstream sources, account scope, freshness, cadence, cost/privacy/notification permission and clear failure/deadline behavior. Credential and source authorization remain separate. Reminders may carry learning notes but are not an adaptive curriculum. | Generic backend notification/reminder transport only, not verified feeds. |

## Security and acceptance gates

Do not use accessibility, ADB/root, device-owner status, overlays, hidden APIs,
notification access or broad file access to bypass Android restrictions. ADB
helpers elsewhere in the repository are not normal-app capabilities or accepted
native integration. Accessibility cannot be a general security bypass; Google
Play requires narrow APIs where available, disclosure/consent and eligible use.
No accessibility permission/service is added by this contract.

Keep operating-system permission, user approval of a particular communication/
file upload/change and laptop-side command authority separate. A normal app
cannot freely read all device data, control every app, change system permissions,
read SMS/call logs or silently run privileged operations. User refusal/revocation
must stop the affected path without falling back to a broader access route.

Future feature acceptance requires unit tests plus emulator/device checks across
supported versions: deny/revoke/one-time permissions; activity stop/process death;
locked screen; missing handlers/roles/services; offline backend/token revocation;
notification channel/Doze delays; selected-URI revocation; correct account/time/
recipient; no secrets in logs; no replay or approval bypass. No such device tests
were run for this documentation-only contract. Source regression tests do not
prove an APK works or that merged dependencies never add permissions.

## Observed sources

- Foreground/while-in-use starts: https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- Microphone service type: https://developer.android.com/develop/background-work/services/fgs/service-types
- Assistant role service: https://developer.android.com/reference/android/service/voice/VoiceInteractionService
- Dial/SMS/calendar/capture intents: https://developer.android.com/guide/components/intents-common
- Narrow permissions/pickers: https://developer.android.com/privacy-and-security/minimize-permission-requests
- Photo picker: https://developer.android.com/training/data-storage/shared/photopicker
- Scoped documents: https://developer.android.com/training/data-storage/shared/documents-files
- Clipboard: https://developer.android.com/about/versions/10/privacy/changes
- Geofences: https://developer.android.com/develop/sensors-and-location/location/geofencing
- Package visibility: https://developer.android.com/training/package-visibility
- Wi-Fi controls: https://developer.android.com/reference/android/net/wifi/WifiManager
- Battery: https://developer.android.com/training/monitoring-device-state/battery-monitoring
- Storage: https://developer.android.com/reference/android/os/StatFs
- Network: https://developer.android.com/reference/android/net/ConnectivityManager
- Work scheduling: https://developer.android.com/reference/androidx/work/PeriodicWorkRequest
- Notification permission: https://developer.android.com/develop/ui/views/notifications/notification-permission
- Play SMS/Call Log policy: https://support.google.com/googleplay/android-developer/answer/10208820
- Play sensitive APIs/accessibility policy: https://support.google.com/googleplay/android-developer/answer/9888170

Play's SMS/Call Log page also announces a January 27, 2027 account-verification
change. It is future policy at this check, not an already-effective Android API
change. Recheck current policy/target requirements before distribution; this
contract does not make API35 a claim of present/future Play submission compliance.
