# AETHER - legacy entry-point guide

The assistant is named AETHER. This is the original entry-point guide.
The active repository is https://github.com/Ashokkunchala/AETHER and the current
feature branch is `aether-cinematic-local-voice`.

## Start here

- [Main README](README.md): current setup and project overview.
- [Windows setup](docs/SETUP-WINDOWS.md): local backend and browser setup.
- [Terminal guide](docs/INSTALLATION-AND-LIVE-TERMINAL.md): checkout, dependencies,
  direct terminal chat and voice.
- [Floating robot](docs/WINDOWS-TERMINAL.md): terminal display and controls.
- [Abilities blueprint](docs/ABILITIES.md): intended scope with implemented
  foundations and remaining limits. A blueprint is not acceptance evidence.
- [Verification checklist](docs/VERIFICATION-CHECKLIST.md): device checks and limits.
- [Companion styles](docs/COMPANION-STYLE.md): conversation, voice controls and
  memory boundaries.

## Names and voice

Existing `aether` commands, Python packages, environment variables, installer
filenames, local data paths and scheduled-task names remain for compatibility.
Do not rename these paths manually or create a second set of credentials.
`INSTALL_AETHER.bat`, `START-AETHER.bat` and `INSTALL-AETHER.ps1` keep their names.

The local neural wake detector still uses the built-in pre-trained openWakeWord model and its original spoken
trigger (not "Hey AETHER"). It has not been replaced with a trained AETHER detector. The browser
wake phrase is Hey Aether. `aether call` and the robot's `v` control start a live
call without a wake phrase. The microphone and provider must be explicitly
started; actual Windows/Android audio still needs testing on the target device.

## Honest capability limits

System/device actions depend on the selected interface, installed libraries,
permissions and the existing approval/stop controls. This is not unrestricted
system access. Do not bypass approval prompts or use administrator privileges
by default. Music media keys are global key signals, not verified app/track
playback; absolute play/pause is refused when playback state is unknown.

Conversation context is bounded, not a recording of everything. Backend saved
memories are separate from browser chat history and live voice sessions.
External mail/calendar/WhatsApp actions require configured providers and their
own reviewed approvals. Do not infer connection or successful delivery from a
screen or test. Keep secrets in the local configuration and the backend private.
No deployment, provider subscription or remote account connection is performed
by this documentation change.
