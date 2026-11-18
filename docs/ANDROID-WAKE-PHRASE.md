# Foreground "Hey Aether" wake phrase (Android)

The phone app can listen for "Hey Aether" while it is open, so the owner can
start a voice command hands-free.

## What it does

- A toggle under the chat box ("Enable 'Hey Aether' wake phrase") starts
  Android's on-device `SpeechRecognizer` with partial results.
- When a transcript contains "hey aether", "hey ether" (a common mishearing)
  or a standalone "aether", the listener stops and opens the app's normal
  voice capture. The recognized text lands in the message box and still
  requires the owner to review it and tap Send - the wake phrase never sends
  anything by itself.
- After a wake, the listener stays off until the owner enables it again.

## Limits and guarantees

- Foreground only. The listener runs exclusively while the app screen is
  visible and stops automatically when the app goes to background
  (ON_STOP) or closes. It is not an always-on hotword service and cannot
  wake the phone from the lock screen or background.
- Microphone permission is required and requested only when the owner first
  enables the toggle. The Android mic indicator shows while it listens.
- No audio is recorded, stored or uploaded by this feature; recognition is
  done by the device's own speech service (whose own data policies apply -
  on many devices it is on-device, but AETHER does not control that).
- Restart-after-silence is bounded (short delays, gives up after repeated
  recognizer failures) and the whole feature is off unless enabled.
- The matcher is deliberately narrow ("aether" token or "hey ether/aether")
  and unit-tested against lookalikes ("either", "ethernet", "hey there"),
  but false triggers are still possible; the worst case is the normal voice
  capture opening, which sends nothing without the owner tapping Send.

## Development honesty

No real microphone, speech recognition session or device was used while
developing this feature. JVM tests cover the phrase matcher only. Real
recognition behavior, battery impact and device acceptance remain unverified
until the owner tries it on their phone.
