# Laptop control centre: ability map and boundaries

Part 6 of the AETHER spec: manage the Windows laptop through the approved
Windows companion agent, including approved remote control from the paired
Android phone. This document maps every requested ability to what exists, what
this change adds, and what is deliberately not built.

Standing rule for the whole page: nothing on this page executes from the
network. Queueing a request from the phone is never approval. Every sensitive
action requires a fresh laptop-local interactive decision at run time, and the
hard blocked list can never be approved past.

## System management

| Requested ability | Status | Where |
| --- | --- | --- |
| Show CPU, RAM, disk usage | Exists | `aether/control/info.py` (`cpu_usage`, `memory_usage`, `disk_usage`, `summary`) |
| GPU | Partial, exists | `gpu_info()` reports adapter name/driver only. GPU utilization is not exposed; no claim otherwise. |
| Battery | Exists | `battery()` (percent, plugged, status) where the hardware reports it |
| Temperature | Not available | Windows does not expose CPU temperature through supported user-mode APIs AETHER uses; honestly absent, not emulated |
| Inspect running processes | Exists | `aether/control/process.py` (`list_processes`), `top_processes` |
| Stop approved applications/processes | Exists, gated | `aether/control/process_stop.py`: exact PID + create-time + executable identity, critical-process and self/ancestor protection, fresh confirmation, forceful-termination warning |
| Start approved applications | Exists, gated | `aether/control/approved_apps.py`: exact allowlisted `.exe` with expected SHA256, no PATH/alias/shell fallback |
| Manage startup applications | Read-only, exists | `windows_startup_inventory` (names only, targets deliberately omitted). Enable/disable/delete is not built: registry/startup mutation needs a designed undo path first |
| Inspect Windows services | Read-only, exists | `windows_service_inventory` (names/status/start type, no command lines, no mutation) |
| Monitor internet connectivity | Partial, exists | `network_link_inventory` (local link flags/capacity only, explicitly not reachability) and `aether/control/network.py` (ping/public IP on explicit call) |

## Application management

| Requested ability | Status | Where |
| --- | --- | --- |
| Launch VS Code, PowerShell, Docker Desktop, Android Studio | Exists, gated | Any app can be launched only after the owner adds it to the approved-app allowlist with its exact SHA256; each launch is separately confirmed |
| Open browser tabs / GitHub repositories | Exists, gated | `windows_agent` exact-URL flow: one HTTPS URL, owner-configured host allowlist, laptop-local typed OPEN review, approval consumed before the OS call |
| Manage approved installations and updates | Not built as a module | Install/update commands run only through the guarded shell with per-command confirmation (`aether/control/shell.py`). There is no unattended or remote installer path |

## Development

| Requested ability | Status | Where |
| --- | --- | --- |
| Create projects, edit source code | Exists, gated | File tools under `aether/tools/system/file_ops.py` with protected prefixes; project scaffolds in the mentor and pipeline modules |
| Run tests | Exists, gated | `run_python_tests` executes freshly approved fixed pytest commands only (docs/PYTHON-TEST-RUNNER.md) |
| Inspect logs, debug errors | Exists (reviewers) | `aether/devops/logs.py`, incident evidence review (docs/CICD-REVIEW.md) |
| Generate documentation | Exists | Documentation/reviewer drafting tools; CI/CD docs |
| Commit to Git, create pull requests | Exists, gated | Git mutations run only through the guarded shell with per-command confirmation; nothing commits or pushes unattended |

## Remote control (Android to Windows)

This is the part this change builds, extending the existing per-device paired
protocol (`windows_agent/remote_read.py`) with the same shape: dedicated
per-device tokens, queue-only HTTP, laptop-local interactive review, short
lifetimes, owner-bound cancellation, and closed result schemas. Devices are
shared with the remote-read protocol; pair and revoke with
`python -m windows_agent.remote_read pair|revoke`.

| Requested ability | Status | Where |
| --- | --- | --- |
| View laptop CPU, RAM and disk usage from the phone | Added | `windows_agent/remote_status.py` (`system_snapshot`): reported CPU percent, core count, RAM bytes, drive-letter capacity/free bytes, battery, up-link count. Queued by the phone, collected only after the laptop operator types SHARE STATUS, result released to the requesting device token for 120 seconds |
| Send commands from Android to Windows | Added, gated | `windows_agent/remote_shell.py`: the phone submits one exact command (1-300 printable characters). Blocked-list commands are refused at queue time and can never run. Everything else waits for the laptop operator to review the exact stored command and type RUN COMMAND |
| Monitor command execution | Added | `GET /v1/remote-shell/requests/{id}` reports pending/running/denied/completed/failed/expired states and the bounded result after local approval |
| Return terminal output when explicitly requested | Added, bounded | Output is captured only for a command the laptop operator explicitly approved this time: at most 4000 characters each of stdout/stderr, 120-second result lifetime, then gone |
| Stop long-running tasks | Bounded, honest | Commands run synchronously with a fixed 60-second cap, so no remote command can run long. Phone cancellation works while a request is pending (execution never starts) and suppresses unpublished results; it is not an OS kill and never claimed as one |
| Request approval for sensitive operations | Built-in | Every remote command and status read requires the laptop-local typed review; the HTTP API has no approval or execution endpoint, and caller-supplied confirmation flags are rejected |
| Return screenshots | Not remote | Screenshots stay laptop-local only via the explicit scoped preview/capture flow (docs/SCOPED-SCREENSHOT.md). No screenshot is ever queued, captured or returned through the remote protocols |

## Deliberately not built

- Remote startup/service/install mutation of any kind.
- Remote arbitrary app control outside the approved-app allowlist.
- GPU utilization and CPU temperature (not exposed by supported APIs used here).
- Continuous background monitoring pushed to the phone; every result is a
  single explicitly reviewed snapshot.
- Any HTTP route that approves, dispatches or executes; the network can only
  queue, poll and cancel.

See also: docs/WINDOWS-CAPABILITY-CONTRACT.md, docs/ANDROID-WINDOWS-READONLY.md,
docs/EXECUTION-SAFETY.md, docs/SCOPED-SCREENSHOT.md.
