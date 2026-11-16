# AETHER Personal AI

A multi-provider personal assistant prototype for Indian English and Telugu, supporting Gemini, OpenRouter, and Groq for text chat. The intended personality is adaptive: friendly and witty for everyday chat, calm for serious topics, and energetic for coaching.

> **Status: multi-component prototype, not a complete AETHER yet.** This repository contains a local Gemini chat UI, authenticated SQLite APIs for explicit memories/reminders/workout logs, a first live web-search adapter, a restricted Windows helper, and a native Android starter screen. The branch has automated Python, Windows installer, static-analysis, and Android build checks. A CI build does not replace physical-device acceptance testing. Public cloud deployment is not safe yet.

## One-file Windows installer

Download [INSTALL-JARVIS.ps1](INSTALL-JARVIS.ps1) from this branch, open PowerShell in its download folder, and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\INSTALL-JARVIS.ps1
```

The installer downloads this branch, installs Python (using winget if needed), installs dependencies, asks for your Gemini key (OpenRouter/Groq are optional), creates local secrets, and registers a Windows sign-in task. After sign-in it starts the local backend, opens the browser UI, and opens the terminal assistant. It does not run as administrator or expose the server beyond localhost.

### One-click .exe installer (no PowerShell)

Build it once on any Windows 10/11 machine — the build is fully offline and uses the .NET Framework C# compiler that ships with Windows (no PyInstaller, no ps2exe, no Python needed to build):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build-installer-exe.ps1 -SelfTest     # -> dist\JARVIS-Setup.exe
```

Then double-click **`dist\JARVIS-Setup.exe`** — it embeds `INSTALL-JARVIS.ps1`, opens one console window, and runs the exact same installer flow described above (Python check/install, dependency install, API-key prompt, sign-in task, `jarvis doctor`, start). The window stays open at the end so you can read the result.

- ~62 KB, self-contained: copy it to another Windows machine and double-click — nothing else to ship.
- The exe installs the branch **published on GitHub**, so push your commits before sharing it.
- It is unsigned: SmartScreen may show "Windows protected your PC" — click **More info > Run anyway**.
- Rebuild any time with `.\scripts\build-installer-exe.ps1` (add `-OutFile` to choose the destination, e.g. the Desktop).

In the browser, enter your generated `JARVIS_API_TOKEN` from the installed `.env` file once. If you choose **Remember device token on this browser**, it is stored in browser local storage for convenience; this is less secure than session-only entry. Then click **Start Live Voice** and grant microphone permission. Voice is not silently activated on boot; the explicit start control is intentional.

**Android is a separate APK**, not installable by the Windows script. Build it on this machine with `.\scripts\setup-android.ps1` (add `-Install` to push it to a USB-connected phone), or get the debug APK from the successful [Android build artifact](https://github.com/Ashokkunchala/AETHER/actions). Install it on Android and configure your private HTTPS backend. Android 14 restricts starting microphone foreground services from boot, so the phone app cannot safely promise automatic always-listening voice after reboot; launch the app and start voice explicitly.

## One-click setup files (Windows + phone)

Double-click entry points in the repository root. Each one sets the process execution policy itself, so no manual PowerShell setup is needed:

| File | Does | Result |
| --- | --- | --- |
| `INSTALL_JARVIS.bat` | **Install + run (Windows)** | Creates `.venv`, installs dependencies, writes `.env` with random secrets, asks for your Gemini key, runs `jarvis doctor`, then offers to start the backend on `http://127.0.0.1:8000`. |
| `START-JARVIS.bat` | **Run (Windows)** | Starts the local HTTP backend + browser UI (already installed). |
| `SETUP-MOBILE.bat` | **Install + run (Windows + Android)** | Installs the Python environment if missing, mints the LAN HTTPS certificate, builds `app-debug.apk` (optionally installs it over USB), opens the firewall port for TCP 8443, prints the phone-side steps without exposing secrets, and starts the HTTPS backend. |
| `START-MOBILE.bat` | **Run (phone backend)** | Serves `https://<LAN-IP>:8443` for the Android app (already installed). Keep the window open; Ctrl+C stops it. |

Equivalent PowerShell (same behaviour, scriptable):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-windows.ps1    # = INSTALL_JARVIS.bat
.\scripts\start-windows.ps1    # = START-JARVIS.bat
.\scripts\setup-mobile.ps1     # = SETUP-MOBILE.bat   (add -Install for USB)
.\scripts\start-mobile.ps1     # = START-MOBILE.bat
```

Prove the phone-facing stack end to end (boots uvicorn with TLS, verifies the certificate chain and hostname, then checks `GET /health` returns 200):

```powershell
.\scripts\https-smoke-test.ps1
```

The app never sends cleartext: `android/app/src/main/res/xml/network_security_config.xml` disables HTTP and opts in to user-installed CA certificates, so the phone trusts your laptop's self-signed certificate after you install `data\tls\jarvis-ca.crt` once. Full phone setup: [android/README.md](android/README.md).

## Optional local Docker deployment

Docker Compose is available for a local backend-only deployment. It binds the
host port to `127.0.0.1:8000`, runs as a non-root user, drops Linux capabilities,
uses a read-only container filesystem, and stores SQLite data in a named volume.
It is not a public/cloud deployment profile and does not provide TLS termination.

Create and configure the local `.env` first (for example with
`scripts/setup-windows.ps1`), then run:

```powershell
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f jarvis
docker compose down
```

The API is available at `http://127.0.0.1:8000`. Do not change the port binding
to `0.0.0.0`, add a public tunnel, or expose this development container to the
internet. For Android, use the dedicated private-LAN HTTPS flow in
`scripts/setup-mobile.ps1`.

## Start here

### AETHER global cinematic terminal (Windows)

The cinematic terminal command centre is a separate, on-demand interface. It does not replace PowerShell, CMD, Windows Terminal, or the user's shell. It opens in its own terminal window and shares the existing AETHER assistant brain, tool registry, and approval prompts.

```powershell
# Open the command centre in the current terminal
.\.venv\Scripts\python.exe jarvis_cli.py command-center

# Register the per-user global shortcut (default: Ctrl+Alt+A)
.\scripts\install-global-hotkey.ps1

# Remove the shortcut
.\scripts\install-global-hotkey.ps1 -Remove
```

The shortcut is installed in the current user's Start Menu Programs folder. Windows resolves the shortcut hotkey globally; if another application already uses Ctrl+Alt+A, choose another combination with `-Hotkey "CTRL+ALT+B"`. The microphone remains off until you explicitly start a voice session in a voice-enabled client. Sensitive AETHER tools continue to require approval. This is a Windows shortcut integration, not a replacement shell or a background keylogger/hotkey service.

### AETHER integrations

See [AETHER integrations and daily automation](docs/AETHER-INTEGRATIONS.md) for Google OAuth setup, official WhatsApp Cloud API configuration, Android/Windows notifications, authorized document search, AI planning and the approval model. Configure provider credentials only in your local `.env`; never commit them.

### AETHER personal life manager

Open `http://127.0.0.1:8000/life` after starting the authenticated AETHER server. The responsive workspace includes:

- Today dashboard with open/overdue task counts, notes, monthly expenses and priority snapshot.
- Persistent tasks with priority, timezone-aware deadlines, completion and one-day postponement.
- Reminders using the existing reminder API, plus calendar event drafts stored locally.
- Personal, meeting, work and voice-transcript notes.
- Expense capture and monthly category totals in INR.
- Travel and shopping request preparation, with live research handed to the AETHER assistant.
- Google Calendar and Gmail OAuth integration, with calendar changes and email sends gated by approval.
- Official WhatsApp Business Cloud API message drafts with approval-gated sending.
- Authorized TXT, Markdown, LOG, PDF and DOCX folder search.
- AI daily-plan proposals, proactive reminder notifications, Android notification polling and native Windows toast delivery.

All life-manager and integration API routes require the authenticated device token. The token is held in browser `sessionStorage` for the current tab only. Configure provider credentials in `.env` using [the integration setup guide](docs/AETHER-INTEGRATIONS.md). Calendar changes, Gmail sends and WhatsApp sends are queued for explicit approval. Documents are searched only in folders listed in `DOCUMENT_ALLOWED_ROOTS`.

### Terminal clients

There are two independent terminal chat clients. The default one needs **any one** of `GEMINI_API_KEY`, `OPENROUTER_API_KEY` or `GROQ_API_KEY` — it drives the same local tool-calling brain the browser uses, with no backend process, and automatically falls back through every configured provider (`JARVIS_AI_PROVIDER` controls the order, default `auto`). The floating robot animation itself needs no key. Press `v` in the robot (or run `jarvis call`) to add a live Gemini voice call, which needs `GEMINI_API_KEY`.

```powershell
# Floating robot (the default command) with laptop CPU/RAM/battery/disk gauges.
.\.venv\Scripts\python.exe jarvis_cli.py

# Live voice call: speak immediately, no "Hey JARVIS" wake word.
.\.venv\Scripts\python.exe jarvis_cli.py call

# One-shot or interactive chat in the current pane (streams as it thinks).
.\.venv\Scripts\python.exe jarvis_cli.py ask "what's my battery level?"

# Direct device control, no model required.
.\.venv\Scripts\python.exe jarvis_cli.py laptop status
.\.venv\Scripts\python.exe jarvis_cli.py android devices

# List the 137 registered tools by category.
.\.venv\Scripts\python.exe jarvis_cli.py tools
```

To launch the robot automatically at sign-in, run `.\scripts\install-jarvis-startup.ps1` (add `-Call` to start a live call at sign-in, or `-Remove` to delete the shortcut). The microphone stays closed in the default mode until you press `v`.

`jarvis_cli.py chat` is the **backend** client: it requires `JARVIS_API_TOKEN` and a running `jarvis_cli.py serve`, and streams from the authenticated HTTP API. Use it when you want the browser's memory/reminder/coaching context in the terminal. Both clients read `JARVIS_API_URL` if set and only send a token to HTTPS endpoints or localhost.

- [Master Codex implementation brief](docs/CODEX-IMPLEMENTATION-PROMPT.md) — product vision, roadmap, repository rules, testing, and delivery requirements
- [Windows setup](docs/SETUP-WINDOWS.md)
- [Installation and live terminal microphone guide](docs/INSTALLATION-AND-LIVE-TERMINAL.md)
- [Features and known limitations](docs/FEATURES.md)
- [AETHER Command Center dashboard](app/static/dashboard.html) — responsive live performance dashboard
- [Milestone plan](docs/NEXT-MILESTONES.md)
- [Personal data APIs and AI coaching](docs/PERSONAL-DATA-API.md)
- [Live web research](docs/WEB-RESEARCH.md)
- [Windows reminder notifications](docs/REMINDER-NOTIFICATIONS.md)
- [Android starter](android/README.md)
- [Windows companion agent](windows_agent/README.md)
- [Security](docs/SECURITY.md)
- [Deployment plan](docs/DEPLOYMENT.md)
- [Development guide](docs/DEVELOPMENT.md)

## Implemented in code

### Personal-assistant core (`jarvis/`)

- **Local Gemini tool-calling brain** (`jarvis/core/brain.py`): streams replies, dispatches to registered tools, retries with a model fallback chain, and enforces per-tool confirmation. Shared by the CLI chat and the WebSocket endpoint.
- **Tool registry** (`jarvis/tools/`): 137 typed tools across 20 categories (system, apps, audio, window, power, screen, input, files, process, clipboard, network, shell, notify, and six `android_*` groups) with JSON schemas for Gemini function-calling and schema validation.
- **Laptop control** (`jarvis/control/`): apps, audio, windows, power, screen capture, input, files, processes, clipboard, network, guarded shell, notifications, hardware info.
- **Android control over ADB** (`jarvis/android_bridge/`): device state, apps, input, screen, files, SMS/calls/contacts, notifications, settings, location, wireless debugging, plus automatic ADB provisioning (`jarvis android setup`).
- **Floating robot terminal** (`jarvis/terminal/robot.py`): a small robot that hovers, blinks and flickers its thruster, with a live clock, rotating status line and a cached CPU/RAM/battery/disk gauge. The animation is standard-library only; `psutil` is optional for the gauge. Press `v` to dial a live Gemini voice call through `jarvis/terminal/voice.py` (background thread, no wake word) or run `jarvis call`. The audio stack is imported only when a call starts. (`jarvis` with no arguments launches it; `jarvis tui` remains an alias.)
- **Realtime HTTP/WebSocket API** (`app/ws.py`): JSON protocol carrying the same streamed events plus interactive tool confirmation.

### Backend and clients

- FastAPI chat backend with Gemini, OpenRouter, and Groq text providers; choose a preferred provider or use automatic fallback. Provider keys stay on the server. Real-time audio remains on Gemini Live.
- Live authenticated terminal chat (`python jarvis_cli.py chat`) against the HTTP backend, plus a streaming local chat (`python jarvis_cli.py ask`) and a floating robot animation (`python jarvis_cli.py robot`). Session context is held in process memory.
- Adaptive personality instructions and English/Telugu response preference.
- Browser speech input (only when manually activated and supported) and browser text-to-speech.
- Optional browser-local conversation history and local checklist.
- SQLite-backed, token-protected APIs to create/list/edit/delete explicit memories, export personal data, create/list/complete reminders, manage saved checklist plans, schedule opt-in read-only system checks, and log/delete workouts.
- Token-protected AI workout and general nutrition suggestion endpoints.
- Token-protected user-triggered web search with source links.
- Experimental Windows agent integrated with the local dashboard: authenticated status and user-confirmed HTTPS URL opening for allow-listed domains.
- Optional Windows toast reminder worker that polls the local backend while its process is running.
- Native Kotlin/Jetpack Compose Android client with HTTPS health check, master-token-backed device pairing and confirmed revocation, Android Keystore-encrypted device token/backend URL/device ID, authenticated chat, user-started full-duplex Live Voice, tap-to-speak fallback, explicit memory review/save/delete, recurring reminders, and opt-in WorkManager notifications. Pairing and Android changes still need build and physical-device verification.
- Python API tests and GitHub Actions test/build workflows.

## Major gaps

- The Android app can pair a per-device token using the master token, revoke that token after confirmation, send authenticated requests over HTTPS, and encrypt the device token/backend URL/device ID with Android Keystore. Its latest changes still need an Android build and physical-device verification.
- The Windows companion agent (`windows_agent/`) remains restricted to allow-listed HTTPS URL opening. The Python laptop-control suite (`jarvis/control/`) is broader by design and guards destructive paths, critical processes, and blocked shell patterns.
- Android control requires a physical device with USB debugging (or wireless debugging); ADB is provisioned on demand, and most actions have only been exercised in degraded "no device connected" mode here.
- Shell execution is allow/confirm/deny classified, not sandboxed; the model cannot run blocked patterns, but a confirmed command runs with your full user rights.
- Reminder notification delivery is experimental: Windows uses a local toast worker and Android uses opt-in WorkManager polling with a 15-minute minimum interval. Neither is a guaranteed alarm. Recurrence advances when the user completes an occurrence.
- Memories are explicitly entered via API; there is no consent-driven extraction or review UI.
- Web research is a small HTML search adapter, not full browser automation or authenticated website workflows.
- Workout/nutrition endpoints give general AI suggestions; no wearable integration, progress charts, or medical service exists.
- No secure cloud deployment, TLS termination, multi-user authorization, distributed rate limits, or complete authentication for every route. The CLI backend supports per-device tokens and revocation, but this is not production-ready authentication.

## Quick start — Windows PowerShell

Requirements: Python 3.11+ and a Gemini API key from [Google AI Studio](https://aistudio.google.com/).

```powershell
git clone https://github.com/Ashokkunchala/AETHER.git
cd AETHER
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-windows.ps1
notepad .env
```

The setup script verifies Python 3.11+, creates the virtual environment, installs dependencies, generates the local secrets in `.env`, and finishes with a `jarvis doctor` health check.

In the local `.env`, set at least one AI provider key (`GEMINI_API_KEY`, `OPENROUTER_API_KEY` or `GROQ_API_KEY` — optionally set `JARVIS_AI_PROVIDER` to `gemini`, `openrouter`, `groq` or `auto` to pick the order) and replace the example `JARVIS_API_TOKEN` with a random secret generated using:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep `HOST=127.0.0.1`. Save `.env`, then start:

```powershell
.\scripts\start-windows.ps1
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Open the responsive [AETHER Command Center dashboard](http://127.0.0.1:8000/dashboard) for live authenticated CPU/RAM/disk/battery telemetry and charts (enter your local device token). API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The local assistant (robot, `ask`, laptop/android control) works without starting the backend — only one provider key (`GEMINI_API_KEY`, `OPENROUTER_API_KEY` or `GROQ_API_KEY`) is required:

```powershell
.\.venv\Scripts\python.exe jarvis_cli.py           # floating robot (press v to call)
.\.venv\Scripts\python.exe jarvis_cli.py call      # live voice call, no wake word
.\.venv\Scripts\python.exe jarvis_cli.py ask "set volume to 30"
.\.venv\Scripts\python.exe jarvis_cli.py laptop status
```

`jarvis_cli.py serve` boots the HTTP + WebSocket backend (`/`, `/ws`, personal-data APIs).

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## API overview

- `GET /health` — health check.
- `GET /` — browser chat UI.
- `POST /api/chat` — Gemini chat returning JSON; requires the configured bearer token.
- `POST /api/chat/stream` — Gemini chat streamed as server-sent events for the browser; uses the same bearer token. Keep the service local until production security is completed.
- `POST /api/ws-ticket` + `WS /ws?ticket=…` — exchange a bearer token for a 60-second, single-use WebSocket ticket, then use it for realtime streamed text, tool lifecycle events, and interactive tool confirmation. Remote clients cannot self-approve sensitive actions.
- Token-protected APIs: `/api/memories`, `/api/reminders`, `/api/workouts`, `/api/research`, `/api/coach/workout`, and `/api/coach/nutrition`.
- `GET /docs` — local API reference.

## Security rules

- Never expose this server directly to the public internet. Do not bind to `0.0.0.0`, port-forward it, or use a public tunnel.
- Keep real API keys and tokens in `.env`, never in source control, Android resources, screenshots, or logs.
- The protected APIs reject missing/invalid bearer tokens; a shared token is not production device pairing.
- Sensitive OS or browser actions need user confirmation and explicit allow-lists. Model-generated shell commands are classified (`safe` / `confirm` / `blocked`); blocked patterns never run, and every risky tool prompts before executing. Nothing runs on the model's say-so alone.
- Fitness and nutrition outputs are general information, not medical advice.
- Check Google model availability, quotas, and pricing for your account; do not assume every request is free.

See [docs/NEXT-MILESTONES.md](docs/NEXT-MILESTONES.md) for the staged acceptance criteria.

## Naming and compatibility

The assistant is **AETHER**. The repository is now
[ashokkunchala/AETHER](https://github.com/Ashokkunchala/AETHER). Internal `jarvis`
commands/packages, configuration variable names, stored settings, installer filenames
and Windows scheduled-task identities remain unchanged so existing installations keep
working. Product display names are being updated without moving saved data.

The browser wake phrase is **Hey Aether**. The separate local neural wake detector still
uses the legacy `jarvis` detector selection, with its original spoken trigger
"hey jarvis". Renaming the assistant does not train a new wake model. Use `jarvis call`
for immediate voice without a wake word. No custom AETHER neural model is bundled or
claimed. See [companion styles and memory/voice boundaries](docs/COMPANION-STYLE.md).
