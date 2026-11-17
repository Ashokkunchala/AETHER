# AETHER native calendar, selected image and foreground location

This source stage adds a connected card to the existing Android command centre. It does not replace the older phone composers, selected text, remote Windows read card or user modules. Nothing in this card is sent to the backend, chat history or a model. The OS or a selected cloud-content provider can still perform its own network access.

## Calendar

1. Open `NATIVE CALENDAR / IMAGE / LOCATION`.
2. Request read-only calendar permission in Android. Granting it does not read anything automatically.
3. Tap `Read next 7 days locally`. The app queries visible calendar occurrences, across the device's visible calendar accounts, from the current instant through seven elapsed days. At most 20 occurrences are displayed in time order, with a truncation notice when there is a 21st. Titles, event IDs, time and all-day status are read; descriptions and attendees are not queried.
4. Each row has an explicit system-calendar edit handoff. Check the account, attendee effects and one-occurrence/series scope in that app. AETHER does not directly save, delete, change recurring events or report those changes as successful. The calendar app may or may not provide cancellation in its editor. Use the existing insert composer for a new event.

Permission can be denied/revoked; missing providers and editors fail without a direct-write fallback. Refresh before relying on external changes. Local timed events display the device timezone; all-day values display UTC with an end-exclusive label. No WRITE_CALENDAR permission is declared. Clearing or leaving the foreground suppresses late results, but cannot guarantee interruption of an already executing provider query or undo changes in another app.

## Selected image pixel analysis

1. Choose one image through the system picker. No media-library or camera permission is requested, and no directory is scanned.
2. Selection alone does not read pixels. Tap the separate local analysis button.
3. Only content URIs with JPEG, PNG or WebP MIME types are accepted. The stream is capped at 8 MiB plus a one-byte overflow sentinel, even if provider size metadata is absent or false. Image bounds must be positive, at most 32768 on either side and at most 100 million encoded pixels.
4. Decode uses power-of-two subsampling to at most 512 by 512. The card reports encoded/sample dimensions, mean RGB luminance and the proportion of near-dark sampled pixels. The temporary bitmap is recycled. No persistent URI grant, file, EXIF/location read, export or upload is created.

This is real local pixel processing, not semantic photo analysis. It does not identify objects or people, perform OCR, interpret medical images, search your gallery or capture camera images. Rotation, transparency and color profiles affect simple statistics. Provider stream reads and codec work may finish after cancellation, but results are suppressed. Memory clearing is not guaranteed secure erasure. A selected cloud image may be downloaded by its provider.

## One-shot approximate location and local proximity reminder

1. Request approximate foreground location permission, then tap the separate check button. Permission approval alone never starts a read.
2. Requires Android 11/API30 or later and an enabled network location provider. Older supported app versions show an unavailable result, not an unsafe fallback. There is no GPS/precise or background location permission.
3. A single `getCurrentLocation` request has a 20-second timeout and cancellation signal. Null, stale (over 60 seconds old by monotonic clock), future-monotonic, nonfinite and missing-accuracy fixes are refused. There is no stored last-known-location fallback.
4. The result displays approximate coordinates, accuracy, captured time and age at the explicit check. It is a timestamped snapshot, not a continuously current position or street address.
5. Optional target latitude/longitude, a 100-50000 m radius and a reminder can be entered. The reminder appears only during an explicit check, only if distance plus the fix's accuracy fits inside the radius. A centre point inside the circle is not enough. Ambiguous/coarse results do not claim arrival.

This is a foreground, manual proximity check. It is not a background geofence, automatic arrival notification, reliable safety alert or scheduled reminder. No polling, WorkManager job, service, stored target or location history is created. Network location can be unavailable indoors, offline or on devices without the provider. Stop/collapse/clear cancels the request and suppresses late results. OS-granted permissions remain until revoked in Android Settings.

## Acceptance and limits

Python source-contract checks cover integration and the absence of network/shell/direct-provider-write paths. Executable JVM policy tests cover dimension/sample bounds, stale/future/invalid location rejection, distance calculations and accuracy-aware proximity. Native build/JVM CI is required separately. These are not tests of actual providers, permissions, OEM pickers, codecs or location hardware.

No actual calendar read/edit, image selection/read, permission grant, location acquisition or device action was performed while building this stage. Native pixels and runtime remain unverified on a phone/emulator. Device acceptance must check denial/revocation, repeated request cancellation, leaving the app during reads, recurring/all-day/DST calendar rows, missing editors/providers, malformed/oversize/nonseekable images and coarse/disabled/stale/timeout locations. Real device work and any external effects remain separate approval items.

This original card still has no semantic analysis, camera capture or automatic reminder. The separate [four-capability follow-up](FOUR-CAPABILITIES.md) now adds bundled labels/Latin OCR, camera thumbnail handling and an opt-in best-effort background proximity worker; those paths have their own permissions and limits. Direct calendar writes remain unimplemented. Do not describe this stage as completing all Android capabilities.

## Android references

- Calendar permission, Instances and edit-intent semantics: https://developer.android.com/identity/providers/calendar-provider
- Location one-shot/cancellation behavior: https://developer.android.com/reference/android/location/LocationManager
- Approximate and foreground permissions: https://developer.android.com/develop/sensors-and-location/location/permissions
- Bounds-first and sampled image decode: https://developer.android.com/topic/performance/graphics/load-bitmap
