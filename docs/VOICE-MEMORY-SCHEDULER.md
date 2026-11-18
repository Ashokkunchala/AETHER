# Voice backends, document memory and the briefing scheduler

Three upgrades inspired by the Stanford-linked OpenJarvis project
(Apache-2.0, <https://github.com/open-jarvis/OpenJarvis>). The ideas were
adapted; the implementations here are original and standard-library first.
No OpenJarvis code was copied, so no license notices were required beyond
this credit.

## 1. Speech backends (`aether/core/voice/speech.py`)

One shared interface for the voice-first terminal and the server the Android
app pairs with. Four settings stay independent:

| Setting | Meaning | Where |
| --- | --- | --- |
| STT engine | speech to text | `stt_engine` in `aether/config/settings.py` |
| TTS backend | text to speech | `AETHER_TTS_BACKEND` (this module) |
| chat model | which LLM replies | `GEMINI_MODEL` etc. |
| voice id | which voice speaks | backend-specific, never the model id |

- **local (default)**: `pyttsx3`, on-device, free. Missing package is
  reported as "pip install pyttsx3", not a crash.
- **elevenlabs (opt-in)**: `AETHER_TTS_BACKEND=elevenlabs` with
  `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` set (two different values).
  Optional model override: `ELEVENLABS_MODEL` (default
  `eleven_multilingual_v2`). Cloud synthesis costs money on ElevenLabs' side;
  it is never selected silently.
- Comma lists set a fallback chain: `AETHER_TTS_BACKEND=elevenlabs,local`.
- All backends enforce timeouts and cancellation, and errors are sanitized:
  API keys never appear in exceptions, logs, or `aether doctor`.

Tools: `speak_text` (speak a short reply), `speech_status`.

## 2. Document memory (`aether/memory/doc_memory.py`)

Read-only search over your own notes with citations, backed by SQLite FTS5.
Nothing leaves the machine.

```
aether memory add C:\Users\Ashok Kunchala\Desktop\FDE\notes
aether memory search "readiness probe"
aether memory list
aether memory reindex
aether memory forget <folder>
```

- Explicit opt-in: nothing is indexed until you add a folder. Whole drives
  and the home directory are refused - pick a specific notes/docs folder.
- Secret hygiene: `.env*`, `*.pem`, `*.key`, keystores, files with
  secret/credential/token in the name, and files whose contents look like a
  private key are never indexed. `.git`, `node_modules`, venvs and build
  output are skipped. Files over 512 KB are skipped.
- Incremental reindex (mtime + size), deleted files drop out of the index.
- Every result includes `path:line` so answers can be checked at the source.
- AETHER only ever reads these files; `forget` and `clear` delete index rows,
  never your documents.

Tools: `memory_add_folder`, `memory_search`, `memory_folders`,
`memory_forget_folder`, `memory_reindex`.

## 3. Briefing scheduler (`aether/briefing_schedule.py`)

The daily briefing becomes a real scheduled job:

```
aether briefing schedule --at 07:30 --tz Asia/Calcutta
aether briefing status
aether briefing now
aether briefing run-due      # call on startup / hourly to fire what's due
aether briefing cancel
```

- Persistent and timezone-aware (IANA names via `zoneinfo`; empty = system
  timezone). Survives restarts: after a reboot, the next `run-due` picks up
  whatever came due while AETHER was off.
- Dedup: at most one recorded briefing per schedule per local day.
- Missed-run policy per schedule: `catchup` (default, run once when AETHER
  wakes) or `skip` (record the miss and move on).
- Full audit history (`aether briefing status` shows recent runs).
- Local data only: notes, habits, expenses, commitments. Nothing is emailed
  or sent anywhere.

Tools: `schedule_daily_briefing`, `briefing_schedule_status`,
`cancel_daily_briefing`, `run_due_briefings`.

## 4. `aether doctor`

One health check for the whole local stack: Python version, model key
(presence only), realtime voice packages, microphone/speaker, speech
backends, ElevenLabs key presence (never the value), adb/Android, storage,
document memory and scheduler state. Critical failures exit non-zero so the
installer can gate on it. No network calls, no audio is played or recorded.
