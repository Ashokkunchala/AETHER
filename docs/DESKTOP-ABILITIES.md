# Desktop abilities (voice)

- **Open apps**: run `aether setup-apps` once. It finds Chrome, Edge, Firefox, VS Code, Notepad,
  Calculator, Paint and File Explorer at their standard paths, shows each exact path, and you
  answer y/n. Approved apps are stored with their SHA256 in `~/.aether/approved_apps.json`.
  "Open Chrome" then works by voice. If an app updates and its hash changes, re-run the command.
- **YouTube**: "play a latest Telugu song on YouTube" opens the top result in your default browser.
- **Create files**: "create a Dockerfile in Documents". AETHER previews the full path, you say yes,
  then it writes. Only inside your user folder, never overwrites, no script/program file types.
- **Email**: read-only, see GMAIL-READONLY.md.

Not done by voice: sending email, deleting files, installing software, AWS changes, purchases.
