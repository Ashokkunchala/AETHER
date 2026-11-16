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
confirmation-gated shell/start_process primitives are distinct, not an alternative way to
claim approved-app automation; no command execution authority is created here.
The loopback Windows helper's narrow URL route is separate and now requires
one-time laptop-local interactive review. Its HTTP caller cannot approve it.

Mock tests cover exact ID/path/hash, aliases/injection/URL/relative-path refusal,
missing/default config, malformed config, executable change, fresh/denied/auto
approval, config revocation/redirection during prompt, stop and legacy denial.
No real application/device/OS launch occurs. The registry's trusted confirmation
callback, single-use local approval store and frozen args own authority, not a
caller `confirmed` field. Arbitrary Python code can call internal primitives;
this is not a hostile-code sandbox.

## Default-handler path launch closed

Legacy `open_path`/`LaptopController.open_path` and old `open_file` now fail closed
for every path, before filesystem resolution or OS launch. Previously the LOW-risk
path route called `os.startfile` on any existing path, including executables and
scripts, bypassing exact-app launch. The registry marks it HIGH/fresh-only and its
preview refuses before asking for an unusable approval. This is an intentional
compatibility change: no document/folder/default-association launch is claimed.
Data list/search/read/preview and reviewed document creation remain unchanged.
A safe document-handler workflow needs its own resolved handler/arguments/content
review; a familiar extension or default association is not approved-app authority.
Generic fresh-approved shell remains separate, not an automatic fallback or
permission to bypass this policy. No real OS action was executed for the fix.
