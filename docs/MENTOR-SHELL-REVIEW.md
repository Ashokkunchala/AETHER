# AETHER shell command teaching review

`mentor_review_shell` accepts one small redacted shell command as text and returns bounded literal observations. It extends the existing mentor registry without changing Python review, deep lessons, projects, progress records, command execution or approval policy. It does not open a path, resolve variables, contact a URL, run the command or write progress.

## What it checks

Five literal patterns produce fixed explanations, line/column locations and source links:

- `$(...)` or backtick command-substitution markers outside single quotes.
- A spelled `rm` command combining recursive and force options, including `-rf`, split short options or `--recursive --force`.
- A literal output redirection `>` outside single quotes, including `2>`; append-only `>>` is not flagged by this rule.
- A spelled `sudo` command word.
- A spelled `curl` or `wget` pipeline into `sh` or `bash`, optionally through `sudo`.

Findings omit the supplied command, paths, URLs, arguments and values. Locations use one-based lines and zero-based UTF-8 byte columns. At most 100 findings are returned; `finding_count` still reports all detected rule/location pairs and `partial=true` marks truncation.

## Limits and privacy

Input is limited to 32768 UTF-8 bytes and fewer than 512 lines. Credential-shaped values such as private-key blocks, common password/token fields and AWS access-key-shaped text are rejected; redact them and submit only the command shape.

This is not shell parsing, a sandbox, a security audit, command approval, an execution test, correctness grading or mastery assessment. Single-quoted text is ignored for these literal checks; double quotes do not suppress shell substitution and are still visible to the checks. Aliases, functions, variables, globs, current directory, path targets, shell options and remote content are not resolved. Findings may be false positives and unreported risks remain. A zero finding count is not a pass.

No command text or result is stored by this module. That does not erase the input from the conversation, assistant/provider context, logs, exports or backups. Supply only small redacted commands you intend the assistant to process. Any later run, download, install or repository change needs its own fresh review and applicable approval. No lesson pass, project verification, interview grade or certification readiness is recorded.

## Evidence

Synthetic tests cover each exact pattern, intentionally uncovered forms, secret rejection, strict input limits, location ordering, UTF-8 columns, truncation, result independence, no file side effect and preservation of existing mentor tools/progress. No user command was executed or independently reviewed, and no real-device acceptance is claimed.

Official sources checked November 18, 2026:

- https://pubs.opengroup.org/onlinepubs/9799919799.2024edition/utilities/V3_chap02.html
- https://man7.org/linux/man-pages/man1/bash.1.html
