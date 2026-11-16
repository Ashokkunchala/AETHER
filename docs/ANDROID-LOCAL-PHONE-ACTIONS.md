# AETHER native local phone actions

The Android PHONE CONTROLS area now includes a collapsible LOCAL PHONE ACTIONS
card. These paths use supported system UI and explicit buttons. They do not send
selection, clipboard, phone number, SMS draft or event fields to a backend/model.
The original composer/picker/clipboard paths add no manifest permission. The
separate foreground network snapshot adds normal ACCESS_NETWORK_STATE only. No
background service, accessibility, direct-call or direct-SMS capability is added. No permission granted by a picker approves an
upload. Missing handlers and query/permission failures remain visible failures.

- Dialer: enter one exact international +number,7-15digits, then open ACTION_DIAL.
  No USSD, pause/wait, dial code, separator, recipient inference or direct call.
  The user must review and press Call in their dialer. Launch is not a call result.
- SMS: the same exact number plus an explicit nonempty draft opens ACTION_SENDTO
  smsto: with sms_body. The user reviews and sends in their SMS application. No
  direct send/inbox/receipt/role request and no delivery claim.
- Contact picker: Android's PickContact can search/select within its system UI.
  A selected contact can have multiple numbers; this implementation does not read
  the directory or infer a recipient/phone number. The user must review numbers
  in Contacts and enter the exact intended one. A full contact search/extraction
  workflow is still not implemented.
- Calendar: explicit title and ISO8601 start/end including timezone offsets open
  ACTION_INSERT on Events.CONTENT_URI. End must be later. Calendar account,
  recipients and Save remain in the calendar UI. No read/edit/cancel adapter,
  calendar permission or saved-event verification.
- Document: OpenDocument selects one accessible item and reads only its display
  name. No contents, broad inventory, persistent URI grant, move/delete/organize,
  summary or upload. SAF/provider availability and per-item access still apply.
- Image: GetContent with image/* selects an item. No pixels are read, no camera
  permission is requested, no image analysis/upload or whole-gallery search. A
  provider may offer camera/cloud routes under its own policy. Analysis needs a
  separate scoped destination and approval, not inferred from selection.
- Clipboard: explicit foreground Paste reads only plain text into a local field,
  bounded to8000characters. It does not coerce/read URI file content. Copy writes
  only that field. Android focus/privacy rules still apply. Clipboard text may
  contain secrets; it is never automatically sent. Clear fields does not clear
  the system clipboard or undo destination-app drafts, logs or backups.
- Device snapshot: battery percent/state and exposed battery-sensor temperature,
  app-data volume capacity/available bytes, keyguard credential/lock state and
  this app's microphone/notification permission status. Includes sample time.
  Unsupported/read-error values remain unknown. Volume capacity is not app/file
  inventory, battery temperature is not CPU temperature, device credential is
  not a security audit, granted mic permission is not live recording authority.
  No backend health or ongoing monitoring is claimed. A separate explicit
  [network capabilities snapshot](ANDROID-NETWORK-SNAPSHOT.md) reports OS flags
  locally without probes or identifiers.

Fields use transient Compose state, not persistent settings/chat history. They
may remain while the activity is alive; lifecycle/process death is not guaranteed
secure erasure. OS clipboard, input methods, destination apps and providers have
their own data handling. No promise is made that other software cannot see them.

Automated evidence is source-safety regression plus Kotlin validation tests for
numbers and timezone-aware event bounds. CI now runs testDebugUnitTest before
assembleDebug. Source checks are not Android runtime or visual acceptance. This
change has not been installed, screenshot-inspected or exercised on an emulator
or the owner's phone. Denied/revoked grants, missing handlers, rotation/background,
contact ambiguities, foreground clipboard behavior, system composers and actual
small-screen layout still need separately approved Android acceptance. No real
call, message, event, clipboard or user file was touched during development.

Sources checked November16,2026:
- https://developer.android.com/guide/components/intents-common
- https://developer.android.com/develop/ui/views/touch-and-input/copy-paste
- https://developer.android.com/reference/android/os/BatteryManager
- https://developer.android.com/reference/android/os/StatFs
- https://developer.android.com/reference/android/app/KeyguardManager
