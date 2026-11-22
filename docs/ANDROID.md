# AETHER Android companion: ability map

How the requested Android abilities map to the app today. The app uses only
supported Android APIs with explicit runtime permissions; it never bypasses
Android security, requests accessibility services, reads other apps' data or
runs the microphone in the background. See [android/README.md](../android/README.md)
for setup and [local execution safety](EXECUTION-SAFETY.md) for the laptop side.

## Base abilities

| Ability | What exists today | Boundary |
| --- | --- | --- |
| Voice assistant | Tap-to-speak with transcript review before sending; spoken replies via the installed TTS voice; Live Voice over the authenticated bridge | Microphone runs only while the app is visible and user-started |
| Wake word | On-device wake-phrase controller with explicit listening states | Only where Android permits foreground microphone use; no always-on background listener |
| Notifications | Opt-in WorkManager reminder polling and the backend notification inbox, posted as private-visibility notifications | Best-effort, may be delayed at least 15 minutes; not an alarm service |
| Calls | Exact international-number validation, then the number is opened in the system dialer for review | The app never places the call; the user confirms in the dialer |
| SMS | Draft text validated and opened in the system SMS composer | The app never sends SMS itself |
| Contacts | System contact picker; the chosen contact is used for the dialer/SMS composers | No contact database read, sync or upload |
| Camera | User-captured thumbnail or user-selected image, analyzed on explicit tap; on-device models by default, optional consented cloud vision | No full camera/library permission requested; selection cleared when the app stops |
| Gallery | Same user-selected image flow | No background photo access |
| Files | System document picker for one accessible document at a time | No broad storage permission or file indexing |
| Calendar | Read-only local calendar window after explicit permission; new events and edits open in the system calendar for review | The system calendar owns save/delete and attendee notifications |
| Location reminders | Approximate foreground location with strict freshness/accuracy bounds; opt-in background reminder after separate review | No stored last-known fallback; background location only after explicit separate permission |
| App launching | Recognized commands open matching system screens after the user taps "Run recognized phone command" | Arbitrary app control stays on the laptop-side ADB bridge with its own approvals |
| Clipboard | Explicit local read into a field; explicit copy back | Marked as possibly private; never sent automatically |
| Battery | On-tap battery, volume and lock status read | Snapshot only, no continuous monitoring |
| Storage | On-tap storage usage read (StatFs) | Snapshot only |
| Network | Wi-Fi/connectivity snapshot card | Snapshot only, no VPN or traffic inspection |
| Security status | Permission settings shortcuts and local device status reads | Shows status only; cannot change device policy |
| Laptop connection | HTTPS pairing with per-device Keystore-encrypted tokens; chat, activity feed, remote memory read | The phone feed is read-only on purpose; sensitive confirmations stay on the laptop |

## Advanced abilities

| Ability | What exists today | Boundary |
| --- | --- | --- |
| Start a voice conversation from a notification | Due-reminder notifications carry a "Talk now" action that opens the app with one explicit Live Voice offer | The microphone still starts only from the in-app tap; the notification never starts audio |
| Send voice notes to your laptop | Not built | Live Voice audio goes to the configured voice backend, not stored as notes; no upload endpoint exists yet |
| Receive laptop security alerts | The backend notification inbox is polled and posted to the phone | Only alerts the backend already produces; not a new detector |
| Control approved Windows applications from your phone | Not built, by design | Phone actions stay read-only; approvals stay on the laptop |
| View laptop CPU/RAM/disk | Remote memory read: queued on the laptop, reviewed in the trusted laptop terminal, read once from the phone | Laptop-local approval every time; no polling or phone-side approval |
| Trigger approved DevOps scripts remotely | Not built, by design | Same remote-read pattern would be required with laptop-local per-command approval; phone cannot run laptop commands today |
| GitHub Actions failure notifications | Not built | Needs a backend collector; the phone inbox would display them once the backend produces them |
| AWS cost alerts | Not built | Same: needs a backend collector (Cost Explorer is billed per request); the inbox would display them |
| Daily learning reminders | Recurring reminders through the backend, posted as notifications | Best-effort delivery as above |

## Standing limits

Normal apps cannot control every application or read all device data, and this
app does not try: no accessibility service, no device admin, no background
microphone, no SMS/call-log access, no contact sync. Every "send", "call" and
"save" completes in the destination system app under the user's finger. The
backend master token is never stored on the phone; per-device tokens live in
Android Keystore AES-GCM and can be revoked. No analytics or third-party
tracking.
