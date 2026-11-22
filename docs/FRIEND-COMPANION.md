# Friend: natural human-like companionship

AETHER's companion experience: a friend you can talk to, not a command line.
Everything below runs locally-first; conversation quality comes from the model
you connect (Gemini or a local model), and no companion feature sends data
anywhere on its own.

## What the experience includes

| Ability | Where it lives |
| --- | --- |
| Natural conversations, listening and responding like a companion | Base personality in `app/personality.py` (`SYSTEM_INSTRUCTIONS` + `COMPANION_GUIDANCE`) behind every chat interface (web chat, CLI, TUI, voice) |
| Emotional awareness: notices stress or tiredness, responds gently, offers a choice (talk, break, small next step) | `COMPANION_GUIDANCE` in `aether/personality_modes.py`; calm and motivational modes |
| Jokes, funny stories and Telugu comedy | `funny` conversation mode plus the storytelling guidance; jokes are always original, never cruel, and dropped when things get serious |
| Storytelling | `storyteller` personality mode (original stories only, with natural pauses to continue or branch) |
| Music recommendations | Companion guidance: mood- and taste-based recommendations. Controlling a music app requires a supported integration; none is connected yet, so AETHER says so honestly instead of pretending to play |
| English, Indian English and Telugu | `language_instruction` (en/te/auto) with natural English/Telugu code-switching; Telugu technical terms stay in English where clearer |
| Conversation memory with user controls | `memories` API (view, edit, delete one, delete all, export) plus the on/off control added on this branch: `GET`/`PUT /api/memory/settings`. Off stops new saves and chat personalization; saved memories stay stored until you clear them |
| Daily greetings | `GET /api/companion/greeting` (this branch): time-of-day greeting with a read-only snapshot of today's tasks, reminders and calendar drafts |
| Motivation and celebration | `motivational` mode; companion guidance celebrates real progress without inventing milestones, shaming or forcing positivity |
| Conversation modes (friendly, funny, professional, calm, motivational) | `aether/personality_modes.py` registry; the CLI/TUI choice persists in `~/.aether/personality_mode.json`, the web chat passes the mode per request |
| Voice personality | Every mode carries `voice_style` (pace, tone) the voice layer uses; the Live Voice browser interface speaks replies |

## Special friend features

- **Voice conversations without typing**: Live Voice (`app/live_voice.py`, browser
  dashboard) and the terminal voice interface. Voice never bypasses approvals.
- **Remember ongoing conversations and continue later**: chat history lives in
  the active session; when an interrupted conversation is not available, AETHER
  asks for a short recap instead of inventing what was said.
- **Telugu and English switching mid-conversation**: `auto` language mode
  follows your code-switching naturally.
- **Remember your preferred style**: save it as a memory (for example "prefers
  funny mode in the evening") or set the CLI/TUI mode once; AETHER never claims
  it saved a style unless the save actually succeeded.
- **Company without pretending to be human**: AETHER offers company, humor and
  encouragement but never claims human feelings, lived experiences or an
  exclusive bond, and it supports your real-world relationships.

## Companion endpoints added on this branch

| Endpoint | Purpose |
| --- | --- |
| `GET /api/companion/greeting?timezone=Asia/Kolkata` | Deterministic greeting for the time of day plus counts of overdue/due tasks, reminders and calendar drafts, and the top three priorities. Read-only; no AI call, nothing changed or sent |
| `GET /api/memory/settings` | Current memory on/off state and how to view/clear saved memories |
| `PUT /api/memory/settings` | Turn memory on or off (`{"enabled": false}`). Off blocks new saves (`POST /api/memories` returns 409) and removes memories from chat context; existing memories stay viewable and clearable |

All endpoints require the usual device token. The greeting reads the same
local life records as the reports API; calendar entries it mentions are
unconfirmed drafts, not booked events.

## Honest limits

- A greeting is a deterministic local snapshot; the warm words around it come
  from chat with a personality mode.
- Music playback control needs a supported music-app integration, which does
  not exist yet; recommendations work today.
- AETHER does not sing: `prepare_song` shapes original lyrics into a spoken,
  rhythmic performance and says so cheerfully.
