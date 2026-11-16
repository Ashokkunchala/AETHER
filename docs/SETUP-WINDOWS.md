# Windows Setup — Step by Step

## Recommended: one-file installer

Download [INSTALL-JARVIS.ps1](../INSTALL-JARVIS.ps1) and run it from PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\\INSTALL-JARVIS.ps1
```

It installs the current branch under `%LOCALAPPDATA%\\Programs\\JarvisPersonalAI`, creates a private virtual environment and `.env`, and configures JARVIS to start the backend, browser UI, and terminal at Windows sign-in. The server stays bound to `127.0.0.1`. To stop auto-start, disable the **JARVIS Personal AI** task in Task Scheduler.

### Or the one-click .exe (no PowerShell)

```powershell
.\scripts\build-installer-exe.ps1 -SelfTest     # builds dist\JARVIS-Setup.exe
```

Double-click `dist\JARVIS-Setup.exe`. It embeds the same `INSTALL-JARVIS.ps1` shown above and runs it in one console window — build it once, then copy the ~62 KB exe to any Windows 10/11 machine (the build uses the .NET compiler that ships with Windows; no Python or extra tools needed to build). Notes: the exe installs the branch published on GitHub (push commits first), and SmartScreen may require **More info > Run anyway** because the exe is unsigned. Set `JARVIS_SETUP_NO_PAUSE=1` to suppress the end-of-run keypress pause in automated runs.

At first use, enter the `JARVIS_API_TOKEN` from the installed `.env` into the browser UI. The optional **Remember device token on this browser** setting stores it in local storage and is less secure than session-only entry. Start Live Voice and grant microphone access explicitly; Windows and browser privacy controls are not bypassed.


This guide starts the JARVIS web interface and Gemini chat locally. Sections 7-8 are optional and add the phone (Android) setup over your LAN.

## One-click shortcuts (skip sections 2-5)

Double-click these in the repository root; each sets its own execution policy, so no manual PowerShell setup is required:

| File | Purpose |
| --- | --- |
| `dist\JARVIS-Setup.exe` | **The one-click installer exe.** Build with `.\scripts\build-installer-exe.ps1`, then double-click; installs JARVIS from the published branch without opening PowerShell yourself. |
| `INSTALL_JARVIS.bat` | Install everything (`.venv`, dependencies, `.env` with random secrets, `jarvis doctor`) and optionally start JARVIS right away. |
| `START-JARVIS.bat` | Start the already-installed backend at `http://127.0.0.1:8000`. |
| `SETUP-MOBILE.bat` | Install + build the Android APK + HTTPS certificate + firewall rule + start the phone backend (section 8). |
| `START-MOBILE.bat` | Start the already-installed phone HTTPS backend at `https://<LAN-IP>:8443`. |

## 1. Create a Gemini API key
1. Open [Google AI Studio](https://aistudio.google.com/).
2. Sign in and create a Gemini API key according to the current Google AI Studio instructions.
3. Review current model availability, quotas, and pricing for your account. Do not assume all usage is free.
4. Never paste the key into the browser, chat UI, GitHub issue, screenshot, or source file.

## 2. Install prerequisites
- Install Git for Windows if you do not already have it.
- Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/windows/). Enable the PATH option if offered.
- Open PowerShell and clone the repository:

```powershell
git clone https://github.com/Ashokkunchala/Jarvis-Personal-AI.git
cd Jarvis-Personal-AI
```

If you already cloned it, update it:

```powershell
git pull
```

## 3. Run the setup script

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-windows.ps1
```

This verifies a Python 3.11+ runtime, creates a virtual environment, installs dependencies, creates `.env` from `.env.example` if missing, generates random `JARVIS_API_TOKEN`/`SECRET_KEY`/`JARVIS_AGENT_TOKEN` values when the placeholders are still in place, prompts for a Gemini key if none is configured, and finishes by running `jarvis doctor` as a post-setup health check.

Useful switches: `-SkipDependencies` (reuse the existing `.venv`), `-SkipVerify` (skip the doctor run), `-NoApiKeyPrompt` (never prompt; configure `.env` yourself).

## 4. Add your key
Open the local `.env` file in Notepad:

```powershell
notepad .env
```

Replace `replace_me` with your real key:

```dotenv
GEMINI_API_KEY=your_real_key_here
OPENROUTER_API_KEY=your_real_key_here
GROQ_API_KEY=your_real_key_here
JARVIS_AI_PROVIDER=auto
GEMINI_MODEL=gemini-3.5-flash
HOST=127.0.0.1
PORT=8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
JARVIS_API_TOKEN=replace_with_a_random_secret_at_least_32_characters
JARVIS_DB_PATH=data/jarvis.sqlite3
```

Generate a random token in PowerShell with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and replace the placeholder `JARVIS_API_TOKEN` value with it. Never leave the example placeholder in place. The token protects memory, reminders, workout, research, and coaching APIs. The chat route now requires the configured bearer token. Keep the backend bound to localhost because shared-token authentication is not production device pairing. Do not include extra quotes unless required by the value. The suggested model is configurable; if Google changes model availability or your account cannot use it, select a currently supported model from Google's documentation. Keep the Gemini key and token only in this local file.

## 5. Start JARVIS

```powershell
.\scripts\start-windows.ps1
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

Keep the PowerShell window open while using JARVIS. Press Ctrl+C in that window to stop the server.

## 6. Test the API

In a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Test chat:

```powershell
$body = @{ message = "Hello JARVIS. Introduce yourself in friendly Indian English."; language = "en" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/chat -Method Post -ContentType "application/json" -Body $body
```

Run automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests do not need a paid Gemini request. A real chat does.

With the backend running, verify your real Gemini key with the one-request smoke test (provider quota may apply):

```powershell
.\\scripts\\smoke-test.ps1
```

## 7. Optional: HTTPS smoke test (prove TLS + /health)

The Android app only accepts `https://`. This end-to-end check boots a throwaway
uvicorn with TLS on your LAN IP, then verifies the certificate chain, the
hostname, that the served certificate matches `data/tls/cert.pem` byte for byte,
and that `GET /health` returns 200 with `{"status": "ok"}`. It picks a free port
if 8443 is already in use and always tears the test server down:

```powershell
.\scripts\https-smoke-test.ps1                    # pass = exit code 0
.\scripts\https-smoke-test.ps1 -Port 9443 -ForceCert   # other port / fresh cert
.\scripts\https-smoke-test.ps1 -KeepRunning       # leave the verified server up
```

The certificate is generated on demand by `scripts/generate_https_cert.py` into
`data\tls\` (`cert.pem`, `key.pem`, `jarvis-ca.crt`) and covers this machine's
LAN IPv4 address.

## 8. Optional: run it on your phone (Android over LAN)

One double-click does the whole Windows + phone setup:

```bat
SETUP-MOBILE.bat
```

or run the script directly:

```powershell
.\scripts\setup-mobile.ps1            # add -Install to push to a USB-connected phone
```

It verifies/creates `.env` and `.venv`, generates the HTTPS certificate, builds
`android\app\build\outputs\apk\debug\app-debug.apk` (JDK 17 + Android SDK
required), adds the inbound firewall rule for TCP 8443 (needs an elevated
PowerShell once; it prints the command if it cannot), prints your backend URL without exposing the master token, then starts `https://<LAN-IP>:8443`. For pairing, open the local `.env` file in Notepad and copy `JARVIS_API_TOKEN` directly into the Android app; do not paste it into terminal logs or screenshots.

On the phone:

1. Install the APK (USB with `-Install`, or copy the `.apk` over and tap it).
2. One-time CA install: send `data\tls\jarvis-ca.crt` to the phone, then
   Settings > Security > Encryption & credentials > Install a certificate >
   **CA certificate**. Without it the app rejects the self-signed server cert.
3. Open JARVIS > enter the backend URL and pairing token > **Pair device** >
   **Connect securely**.

Start it again later with `START-MOBILE.bat` (or `.\scripts\start-mobile.ps1`).
Keep the backend on the private LAN only - never port-forward 8443.

## Voice notes
- Browser voice recognition depends on browser support, microphone permission, and OS settings. Current Chrome/Edge usually provide the best support.
- The UI uses browser text-to-speech for spoken replies. Available Indian English and Telugu voices depend on the OS/browser.
- This is not continuous background listening. The microphone is activated only when you press Speak.

## Troubleshooting
- **503 / API not configured:** verify `.env` is in the repository root and the key is not still `replace_me`; restart the server after changing environment settings.
- **VOICE ERR / "voice stack missing":** the robot's `v` call and `jarvis start`/`jarvis call` preflight need `sounddevice`, `webrtcvad`, `openwakeword`, `numpy` and `scipy` in the environment that runs the robot. Install them there with `.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt` (for the installed copy: `%LOCALAPPDATA%\Programs\JarvisPersonalAI\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt` from the installed folder). Both `INSTALL-JARVIS.ps1` and `scripts\setup-windows.ps1` install and verify this file automatically; `jarvis doctor` shows the `voice-packages` row.
- **502 / AI request failed:** verify key validity, model availability, internet connection, quotas, billing, and server logs. Do not share the key when requesting help.
- **PowerShell blocks scripts:** use the process-scoped policy command above; do not change the machine-wide policy unnecessarily.
- **Port 8000 busy:** `.\scripts\start-windows.ps1` now reports what holds the port. If it prints `[PASS] ... already running`, JARVIS is up - just open `http://127.0.0.1:8000`. If it prints `[FAIL] ... used by another program (PID ...)`, run the printed `Stop-Process -Id <pid> -Force`, or use another port with `.\scripts\start-windows.ps1 -Port 8001` and open `http://127.0.0.1:8001`.
- **No microphone button support:** use a supported browser or type into the message box.
- **Telugu voice unavailable:** the model can return Telugu text, but local spoken output depends on installed browser/OS voices.

## Safety
The starter is deliberately bound to `127.0.0.1` for browser use. The optional phone listener (section 8) binds to your LAN IPv4 address over TLS only - it is a second, private-network endpoint, not a public one. Do not bind the browser UI to `0.0.0.0`, port-forward ports 8000/8443, or expose either via a public tunnel. Chat and personal-data APIs require the configured bearer token. Keep all routes on your private LAN; do not expose this prototype to the internet.

## Uninstall

To remove auto-start (the **JARVIS Personal AI** sign-in task and the `JARVIS.lnk` startup shortcut) while keeping installed files:

```powershell
.\scripts\uninstall-jarvis.ps1
```

To also delete `%LOCALAPPDATA%\Programs\JarvisPersonalAI` (a copy of `.env` is preserved next to it):

```powershell
.\scripts\uninstall-jarvis.ps1 -RemoveFiles
```

Add `-PurgeData` to delete `.env` and `data/` too, and `-WhatIf` for a dry run that changes nothing. The script never touches your cloned source checkout and never requires administrator rights; delete the clone yourself if you no longer need it.
