# Note dictation

The life-manager Notes page supports optional browser speech recognition for the
user's own dictation. This is not a meeting recorder or a replacement for the
separate Gemini Live voice chat.

Choose a language and processing mode, confirm the own-voice/privacy notice, then
click Start. The default requires on-device processing through the browser's
`SpeechRecognition.processLocally` option. If that option is unavailable, nothing
starts. A missing local language pack produces an error; AETHER does not download
packs or fall back to cloud processing automatically.

Browser-service mode is an explicit choice. The browser may send audio to its
speech provider, needs internet, and controls its own permissions/privacy. AETHER
does not implement or guarantee that provider's retention policy. No audio file
is stored by this feature. Recognition support/languages vary by browser/device.
Use localhost or HTTPS; type/paste remains available when dictation fails.

Final text first goes to an unsaved, editable draft (12000-character limit).
Repeated result events rebuild the final text instead of appending duplicates.
Stop and review, append the draft to the note, then explicitly Save note. There
is no automatic note save, AI upload or command execution. Choose Meeting type
when saving an authorized meeting transcript; this feature does not record other
participants, diarize, or extract meeting actions.

A two-minute timer stops capture. Stop waits briefly for final text, then aborts
if the recognition service does not finish. Leaving Notes, hiding/leaving the
page, disconnecting, submitting the note form or changing privacy/language/mode
aborts capture and ignores late results. There is no auto-restart. Already-sent
browser-service audio cannot be recalled.

Mocked recognizer and browser UI tests cover the state machine, not actual
microphone access, transcription quality or language-pack availability. These
need acceptance on the user's Windows/Android browsers.

API reference: https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
Local-only option: https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/processLocally
