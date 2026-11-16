# AETHER conversation and companion styles

AETHER uses the existing personality registry, not a second assistant or permissions layer.
Friendly, Funny, Professional, Calm and Motivational join the existing Assistant, Friend,
Teacher, Storyteller, Health guide and specialist operating modes. The new styles are
available through the same CLI/TUI mode tools and the web Style selector. Existing mode
names and persisted selections remain valid. No mode changes tool access or approval rules.

## Conversation behavior

The shared web and desktop prompt asks for natural everyday conversation, sensitive
responses to emotional cues, original jokes/stories and Telugu comedy when welcome,
proportionate celebration, manageable encouragement and Telugu/English code-switching.
AETHER must not claim human feelings, invent previous conversations, encourage dependence,
or treat a music recommendation as successful playback. These are model instructions,
not guarantees that every model or every response will perform equally well. No live-model
quality evaluation was performed for this change.

## Web controls

- Choose Style and Language, then **Save settings** to keep them in this browser.
  The existing settings key is retained, including the existing token-storage opt-in.
  These preferences do not silently create backend memories or synchronize to another device.
- Browser spoken replies have speed (0.5-2.0x) and pitch (0.5-1.5) controls. Installed
  browser voices determine actual sound and language support. Auto language chooses Telugu
  speech when a reply contains Telugu script; otherwise it uses Indian English.
- Speed/pitch affect browser speech synthesis only, not streamed Gemini Live audio. No
  microphone starts from changing a style, greeting or speech setting.
- Style and language are included when a new Live Voice connection starts. A change during
  an active connection applies on reconnect, not retroactively. Unknown styles fall back to
  Assistant; these parameters cannot supply arbitrary system instructions or add tools.
- The browser wake phrase is **Hey Aether** (also accepts the transcription "ether").
  Its existing browser speech-service privacy warning and explicit opt-in are retained.
  This does not install or rename a local neural wake-word model.

## Context and memory boundaries

The empty text-chat view gives a local-time greeting and points to Life Manager for saved
priorities. It does not claim to have checked a calendar, news or today's events. No new
background greetings or notification schedule is created.

Text chat keeps recent context in the page. Optional browser history stores up to 40
messages; each request includes the last 20. With history off, reload loses that context.
A partial interrupted reply now keeps its associated user turn, so a follow-up can use both
rather than receiving an orphaned assistant reply. This is bounded context, not a promise to
resume any old conversation. Clear chat removes the page's context and saved browser chat
history. It does not erase backend memories, exports, backups or provider records.

Saved backend memories use the existing explicit memory controls. Live Voice has its own
provider-session context; reconnect does not restore the text chat or prior live session.
Its disconnect notice still says so. This change does not send text history or saved memories
to Live Voice behind the scenes.

## Compatibility and remaining work

Active web chat, dashboard, live-voice status, model identities and API title now say AETHER.
Internal `jarvis` packages, storage keys, branch name, configuration variable names and file
paths are retained for compatibility. This is not a full legacy-documentation/installer
branding migration. Music app/device control remains limited to actually supported tools;
no new playback integration was added. Real microphone, installed voice quality, emotional
response quality and device acceptance still need user-side testing. This change makes no
provider send, deployment, subscription or account change.

## Native and local display follow-up

Native Android's existing horizontal style chips include the same five new styles. The
selected style and language are passed when a new Live Voice connection starts; it does
not upload the typed conversation history. Its existing preference store and package ID
are unchanged. Device/emulator layout, installed TTS and audio still need acceptance.

The local desktop Live client now uses the same companion guidance and the current
persisted CLI/TUI style when the caller does not supply an explicit persona. An explicit
caller persona is preserved. The robot, terminal dashboard, CLI responses, Windows toast
labels, native Android chat/transcripts and backend titles use AETHER display names.
Compatibility commands, data paths, installer filenames and scheduled-task identities are
not migrated. The separate neural wake detector retains its legacy `jarvis` model
selection and spoken trigger; this work does not bundle a trained AETHER wake model.
