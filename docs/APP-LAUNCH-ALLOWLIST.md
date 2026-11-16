# AETHER exact approved-app launch

The desktop `open_app` tool now requires an exact local app ID, canonical absolute
.exe path and lower-case SHA256. No built-in app is approved by default. Fresh
trusted confirmation shows that exact target/hash/effect before every launch;
auto/always approval is disabled and emergency stop/revocation are rechecked.
Only the executable is passed as a single argv element with shell=False and its
parent as working directory. No supplied arguments, PATH search, alias, URI,
shortcut, script, elevation or shell fallback is accepted.

A local owner-managed file, default ~/.jarvis/approved_apps.json or the explicitly
configured JARVIS_APPROVED_APPS_FILE, must already contain exactly:

```json
{"version":1,"apps":{"editor":{"executable":"C:\\Approved\\editor.exe","sha256":"the-reviewed-64-lowercase-hex-digest"}}}
```

This is format illustration, not an actual approved hash/path or an installer.
The file must be canonical/non-symlink UTF-8 JSON <=64KB, with version1 and at
most100 app entries. Duplicate keys and unknown selected-entry/root fields fail.
The exact requested ID/path/hash must match the local entry. The executable is
hashed before preview and again immediately before launching. Updates changing
its bytes need a newly reviewed allowlist entry; nothing auto-updates the entry.
No model/remote endpoint edits this allowlist. Selecting an app for this file is
separate local setup, not granted by a generic blueprint or this documentation.

The local config and OS account are trusted. Hash matching is not publisher/
signature/malware verification, approval of application network behavior, or a
sandbox against executable/DLL/config replacement after validation. Paths with
symlinked parents, UNC/network-style paths, scripts and alternate streams are
refused; mapped remote drives, hostile junction/reparse races and OS compromise
are not guaranteed isolated. Dependencies/DLL search, child processes and the
application's own startup effects require separate trust review. A large approved
executable can make hashing take time; no background launch is created to hide it.

Success means a process-start request returned a PID. It does not prove the UI
opened, the launcher didn't hand off, readiness, workflow completion or no later
error. No app on the real laptop was inspected, hashed, approved or launched for
this change. Tests use fake executable bytes and mocked Popen only.

Legacy broad apps.launch_app, older SystemController/system-app helper and legacy
voice open_app now fail closed. LaptopController.open_app inherits that denial.
Existing open_website/open_app_and_type routes relying on that broad launcher
therefore cannot launch/type through it; no insecure fallback is restored. This
is an intentional compatibility change until separately scoped URL/typing routes
are implemented. Search/discovery is informational and never approval. Generic
HIGH-risk shell/start_process primitives are distinct, not an alternative way to
claim approved-app automation; no command execution authority is created here.
The loopback Windows helper's own narrow URL route remains separate and still
needs its own local-approval hardening.

Mock tests cover exact ID/path/hash, aliases/injection/URL/relative-path refusal,
missing/default config, malformed config, executable change, fresh/denied/auto
approval, config revocation/redirection during prompt, stop and legacy denial.
No real application/device/OS launch occurs. The registry's trusted confirmation
callback, single-use local approval store and frozen args own authority, not a
caller `confirmed` field. Arbitrary Python code can call internal primitives;
this is not a hostile-code sandbox.
