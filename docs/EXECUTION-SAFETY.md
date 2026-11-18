# Local execution safety

The shared `ToolRegistry.execute` path now uses a persistent SQLite safety store.
The brain, CLI and TUI calls that use this registry inherit the checks. This is
not an operating-system sandbox and does not cover code that bypasses the registry.

## What it enforces

- MEDIUM and HIGH tools always need the existing trusted confirmation callback.
  Global `auto_approve` cannot bypass that check, nor an explicit confirmation flag.
- An approval is bound to the tool name, a canonical hash of its exact arguments,
  and a fresh invocation ID. It expires 120 seconds after the prompt starts.
- Approved records are atomically consumed once. Replays, expired approvals,
  different arguments and different invocation IDs fail closed.
- Execution arguments are copied before waiting. A UI callback cannot change the
  arguments after the user reviews them. Only the literal boolean `True` approves.
- A persistent emergency stop blocks new LOW, MEDIUM and HIGH registry actions.
  It is checked before the prompt and again after confirmation. SAFE reads remain
  available. An unavailable safety store blocks execution instead of bypassing it.
- The new audit table records timestamps, tool names and fixed outcomes, never
  argument values, outputs or exception text. This does not change legacy logging
  elsewhere in the application.

## Operator controls

Run these locally from the installed project environment:

```console
python -m aether.security status
python -m aether.security stop
python -m aether.security audit
python -m aether.security resume
```

`resume` is deliberately not a model-callable tool. It is an operator recovery
command. The database defaults to `~/.aether/security.db`; set
`AETHER_SECURITY_DB` to use another local path. New database files are created
with owner-only permissions on POSIX; Windows inherits the user's directory ACLs.
Keep that directory private and writable only by the operating user.

## Limits

The stop gates dispatch, not already-running processes. It cannot undo or kill
an action already started, and it is not a process-isolation or malware defense.
Tools must be correctly classified by risk. Local programs with the same user's
file access can modify the database; this is not remote multi-user authorization.
Approvals bind to an invocation, not a separately authenticated remote actor or
device. Remote role/device authorization and versioned approval APIs are future
work. Existing UI "always allow" callbacks must not be mistaken for a new remote
permission system. No cloud credentials, paid services or deployment are needed.

## Verification

`tests/test_execution_security.py` covers single use, tool/argument/invocation
binding, approval expiry, concurrent replay, rejection, missing decisions,
emergency stop before and during approval, argument substitution, global bypass,
MEDIUM tools missing a flag, malformed truthy approvals, unavailable storage,
redacted audit and audit failure after a completed action. Existing registry,
brain, orchestrator and file-preview regression tests also run unchanged.

## WebSocket session boundary

The enhanced backend exchanges bearer credentials for 60-second, single-use
WebSocket tickets. Tickets store a credential hash and device identity, never the
bearer secret. Handshake, incoming frames, new turns and approval completion
recheck token rotation/device revocation. Approvals belong to one socket, require
an explicit JSON boolean, expire after 60 seconds, and cannot be reused. Invalid
or missing decisions never mean approval. Clients cannot self-grant auto approval.

This is not a role system or a universal execution boundary. Existing API routes,
local voice tools and provider integrations keep their separate policies. Idle
sockets are checked on their next frame; revocation does not undo completed work
or reliably stop an already-running thread/process. Tickets are in-process and
require a single backend worker (a restart loses outstanding tickets). Paired
devices still inherit the existing broad tool catalogue; do not expose this
prototype on the public internet. No device-control or provider-send tool was
added by this change.

## Explicit generic shell and background process review

`run_shell` and `start_process` are HIGH-risk, fresh-review-only registry actions.
Auto/always approval is disabled. Their previews show the exact command and
working-directory policy and explain shell/network/provider-output/child-process
risk. With no explicit cwd, the launcher process working directory is inherited
at execution time, not pinned or checked by the preview.
Read-only-looking commands are not exempt. Empty/oversized/NUL inputs and existing
blocked command patterns fail before approval. Legacy process elevation is denied
both in preview and in its primitive; no PowerShell string interpolation is used
to request UAC. Background start returns only a PID, not readiness/completion.

This does not convert generic shell into an app allowlist, command sandbox, scoped
remote executor or deployment adapter. Alias/PATH/script contents and shell
startup behavior are not verified. The user must approve the actual command and
its authority separately. Direct internal calls remain outside registry authority;
no guarantee covers hostile code running as the same OS user. `run_shell` timeout
and registry stop do not guarantee cancellation of started children. No command
was run on the owner's machine for these tests; subprocesses were mocked.
