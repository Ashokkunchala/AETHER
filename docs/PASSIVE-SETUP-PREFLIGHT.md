# AETHER passive setup preflight

Run from the reviewed installed source folder to see missing package metadata and opt-in configuration without starting AETHER, a provider, ADB, audio or a network listener:

```powershell
.\.venv\Scripts\python.exe -B -m aether.setup_preflight
```

`-B` avoids Python's ordinary bytecode-cache writes for this command. The command intentionally creates no application files, folders or databases. It reads installed distribution metadata and selected environment-variable presence/shape, not `.env` contents, secret-store values or source-code configuration imports. Normal Python startup/environment hooks remain outside its control. Use a trusted interpreter and environment.

Optional `--strict-base` exits1 if Python is older than3.11 or metadata for FastAPI/Uvicorn/google-genai is missing/unreadable. This is a small base-metadata check, not a full dependency solver, supported-version check, voice check, end-to-end readiness verdict or security certification. Without that flag the inventory prints even when optional packages are absent.

Output includes:

- Python version and OS family; package metadata presence for API, provider chat, browser, document, native secret-store and microphone-related groups. Present is not importable/compatible/working. Unreadable metadata is grouped with missing rather than printing potentially private exception text.
- Whether the model key exists in this process's environment. A false value does not prove no usable key exists: `.env` and native secret stores are deliberately not read. A true value says nothing about validity, quota, billing or permission to call it.
- Browser off/configuration-present/invalid-host-shape state and configured host count. No host names, DNS, Chromium binary, browser session or website requests are inspected. Shape validation is only a quick hint; the real browser path still performs its stronger live checks.
- File-discovery off/configuration-present/invalid-JSON-shape state and folder count. Paths are not printed or accessed. Shape presence does not validate that a folder is absolute, local, accessible or permitted. The real tool validates scope again after fresh review.
- Presence of an owner policy path and typed-live opt-in flag, without printing the path. It does not inspect policy/stop databases, validate roles/targets or approve cloud work. If typed live is unexpectedly enabled, stop and review your launch environment before running any cloud operation.

No automatic repair, pip install, browser download, directory search, microphone/camera capture, speech playback, subprocess, pairing, device permission, credential validation, cloud read/write or provider message is part of this command. It intentionally does not answer whether the phone/laptop actually works. Follow the separate [installation](INSTALLABLE-FILES.md), [owner device](OWNER-DEVICE-AND-CLOUD-SETUP.md), [browser/dashboard](BROWSER-AND-DASHBOARDS.md) and [filename discovery](LOCAL-FILE-DISCOVERY.md) guides for exact reviewed next steps.

The older `aether doctor` is a separate active local diagnostic. It can initialize local stores, probe audio and run `adb devices` if ADB is available; ADB can start its local daemon. Do not mistake it for this passive preflight or run it merely to obtain package/configuration presence. Neither command was run on the owner's devices during development.

Tests cover no network/subprocess/application-write calls, no optional SDK/config/security import, secret/path/host omission, malformed configuration, unreadable package metadata, off defaults and the strict-base exit. Actual owner environment remains unverified.
