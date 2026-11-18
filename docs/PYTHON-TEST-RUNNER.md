# AETHER fixed local Python test execution

`run_python_tests(project, selection="tests", timeout=60)` adds a typed execution
path to the existing desktop registry. It is not a shell fallback, approved-app
launcher, installation helper, CI service, coding sandbox or deployment adapter.
The user must review the exact invocation before every run; no auto/always approval
is accepted, and the persistent emergency stop is checked again after approval.
The new tests for this feature mock every child process, not the owner's machine.

## Exact scope

- Existing canonical local absolute project directory with a canonical `tests`
  directory. Select `tests`, or one existing Python file/directory below it using
  slash-separated relative text. No traversal, flags, symlinked paths or UNC paths.
  This is not a guarantee against junction/reparse races, mapped remote drives,
  hostile simultaneous file changes or code running as the same OS user.
- Only the currently running AETHER Python interpreter is used, with fixed argv:
  `-I -B -m pytest -q --tb=no --disable-warnings -p no:cacheprovider -o addopts=`
  followed by the selected absolute path. There is no shell, user-supplied flag,
  interpreter substitution, pip install, elevation, repair or automatic retry.
- An explicit project working directory, closed stdin, stdout/stderr discarded,
  direct-process timeout 5-300 seconds and a small environment key allowlist.
  Credential variables, PYTHONPATH, PYTEST_ADDOPTS and ordinary plugin autoload
  are not forwarded. Paths/home/basic OS values are still available. This does
  not hide the user's files, installed Python packages, process account or network.
- Pytest addopts is overridden and cacheprovider disabled. Tests, conftest,
  explicitly imported plugins, other configuration and imports still execute
  arbitrary code. The current interpreter/site packages are already trusted by
  AETHER, not independently reviewed or frozen for this invocation. Pytest/plugin
  versions and repository contents are not pinned by the tool. Disabled autoload
  or Python isolated mode can make a previously passing project's imports/plugins
  unavailable. No claim is made that all projects or async test suites will work.

## Review and result semantics

The approval preview shows exact argv, selected project/path, timeout, output
policy and effects. Test code can read/write arbitrary permitted files, retrieve
credentials from disk, launch children, contact providers or production services,
spend money, or change remote systems. This is a trusted-code execution workflow,
not safe automatic analysis. A generic "run tests" request does not waive review
of these effects or the owner's spending/deployment/destructive-action limits.
Reject unfamiliar or untrusted projects. No command, script, import, dependency
or repository revision is inspected for safety by this tool.

Paths are revalidated after approval. File contents, dependencies, interpreter
bytes and test/config/import graphs are not frozen; review must account for that
race. The registry's invocation/argument-bound single-use approval and stop gate
apply only to dispatch. Direct internal Python calls bypass that authorization,
so this is not protection from hostile local code or a remote role system.

The wrapper returns only timestamp, exact command/project, direct exit code and
a bounded interpretation. These fields can enter model tool context. No stdout,
stderr, traceback, assertion payload or test log is returned or saved by the
wrapper. Tests/plugins may still create their own files/logs/reports and network
traffic. Discarding output is not secure erasure and prevents useful automatic
failure detail. The user can separately review local evidence using an approved
workflow. Test counts and child-process completion always remain unverified.

Exit zero means the selected pytest process reported success, not independent
proof of coverage, actual test execution, absence of skipped/xfail tests, app
correctness or readiness. Nonzero values 1-5 have pytest's usual failure,
interruption, internal, usage/configuration or no-tests meanings. Current pytest
documentation also defines 6 for an exceeded warning limit; installed older
versions may differ. Unrecognized exits remain unrecognized. There is no automatic
retry or repair. Source changes/tests that call sys.exit or plugins can affect the
meaning of any code; no output parsing attempts to invent passing counts.

On timeout Python's subprocess.run kills and waits for the direct child. Process
creation itself may delay timeout handling. Descendants, remote actions or files
already changed are not guaranteed stopped/undone. The emergency stop cannot
reliably cancel already-running work. This feature is not process-tree management,
long-running task cancellation, rollback or remote Android execution.

## Verification

Mock tests cover fixed argv and no shell/installation, environment/output scope,
invalid/traversal/flag/missing/symlink paths, timeout bounds, all exit statuses,
unknown status, redacted errors, timeout without child-stop or retry claim,
fresh review, frozen arguments and stop during review. Full repository CI and
mock tests do not replace a separately approved Windows/Python/project acceptance
run. No project on the owner's laptop or live provider was used for development.

Sources checked November 16, 2026:
- https://docs.pytest.org/en/stable/reference/exit-codes.html
- https://docs.pytest.org/en/stable/how-to/plugins.html
- https://docs.python.org/3/library/subprocess.html
