# DevOps professional: laptop DevOps automation

AETHER as an engineering agent on your own laptop. The design is
approval-first: plan-only by default, one fresh approval per executed command,
a hard deny-list approval cannot override, and a local audit log of every
execution. Nothing touches real cloud accounts, spends money, deletes data or
pushes code without your explicit approval at run time.

## How command execution is guarded

1. **Plan first**: `plan_commands` (new) classifies up to 25 candidate commands
   without running them - safe, confirm or blocked - with the exact next step
   for each.
2. **Approve each run**: `run_shell` executes one exact command and always asks
   for your fresh confirmation first - even for read-only commands. It cannot
   be auto-approved or set to "always allow".
3. **Hard deny-list**: destructive patterns (`rm -rf /`, `diskpart`, fork bombs,
   formatting drives, recursive deletes of system paths) are blocked outright.
   Approval cannot unblock them.
4. **Audit log**: every tool execution is recorded locally (tool, timestamp,
   outcome - never arguments, outputs or credentials). Read it with the
   `execution_audit` tool, `GET /api/devops/audit`, or `python -m aether.security audit`.
5. **Emergency stop**: the existing stop control blocks all execution until resumed.

## Ability map

| Ability | Where it lives |
| --- | --- |
| Terminal control (approved PowerShell/CMD/Bash) | `run_shell` with fresh per-command approval, timeout and output caps; `plan_commands` for the plan-only first pass |
| Linux management | Process/service inspection tools (`aether/control/process.py`), service snapshots; service changes run as approved commands |
| File management | `aether/control/files.py` guarded file tools with policy-scoped paths |
| Git (clone, pull, push, branch, merge, conflicts) | Read-only git (status/log/diff/branch) is policy-safe; writes like pull/push/merge run through `run_shell` with your approval per command |
| Code development | Code review mentors (Python, JS, TS, HTML, shell) plus the developer personality mode |
| Python automation | `run_python_tests` (fixed approved pytest command), `python_wheel` build preview |
| Docker | `review_dockerfile` (offline checks); `docker build/ps/inspect` run as approved shell commands |
| Kubernetes | `review_k8s` and RBAC snapshots (offline); `kubectl get/describe/apply` run as approved shell commands |
| Terraform | `review_terraform` (offline risky-pattern scan); `terraform validate/plan` run as approved shell commands. Apply is never run by AETHER |
| Jenkins | `review_cicd` reviews Jenkinsfiles offline. No live Jenkins connection exists yet |
| GitHub Actions | `review_cicd` scans workflows for unpinned actions and privilege boundaries; CI failures are diagnosed from logs with `triage_log` |
| Networking | DNS lookup tool, `Test-NetConnection`/ping/tracert classed read-only, network inspection in `aether/control/network.py` |
| System monitoring | CPU/RAM/disk/battery sampling with opt-in local alert rules (`aether/proactive.py`) and the terminal command-center panels |
| Security | `dependency_audit` (pip-audit JSON summaries), IAM policy review, security scans (`aether/security_scans.py`) |
| Backup | `aether/backup.py` + `aether/backup_verify.py` create and verify local backups; EBS snapshot tooling is confirm-gated |

## Added on this branch

- `plan_commands` chat tool: batch plan-only classification, never executes.
- `execution_audit` chat tool: read the local audit log.
- `GET /api/devops/audit?limit=N`: read-only audit history for the dashboard
  (device token required).
- This document.

## Honest limits

- AETHER is not a sandbox: an approved command runs as you on your laptop, and
  command output may reach the configured model provider. Approve only commands
  you would run yourself.
- No Jenkins, Docker daemon, Kubernetes cluster or cloud account is connected
  by default. Reviews are offline; live commands go through `run_shell` with
  your per-command approval and use whatever CLI profile you already configured.
- `terraform apply`, pushes, deletes and any spend always need your explicit
  approval at run time - and stay your decision, never AETHER's default.
