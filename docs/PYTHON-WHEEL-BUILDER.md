# AETHER trusted-project local Python wheel builder

`build_python_wheel` is a narrow local Python build adapter through the existing
registry, not a general CI/CD lifecycle or permission to run project code. Every
execution needs a new exact-command review. Auto-approve and "always allow" are
disabled; absent/denied approval, emergency stop, expired/replayed approval and a
stop during the review wait use the existing fail-closed execution boundary.

## Command and prerequisites

Choose one trusted canonical absolute local project with a regular pyproject.toml
and a dedicated existing empty direct-child directory named aether-wheel-NAME.
NAME is 1-64 ASCII letters, digits, underscores or hyphens. AETHER does not create
or clear that directory for you. Preparing the directory/installing prerequisites
on your machine is separate approved-command work. Symlinked, relative, missing,
UNC-style and noncanonical paths are rejected. Local path spelling alone does not
prove a mount is offline or its contents are trusted.

The preview displays the exact argv, project/output paths, timeout and risks.
The fixed command uses the Python interpreter already running AETHER:

`<current-python> -I -B -m build --wheel --no-isolation --outdir <empty-output> <project>`

There is no shell or user-supplied extra flag, executable, config setting, backend
override, installer option or retry. Timeout is an integer from 5 through 300 seconds.
The build frontend and all backend dependencies must already be installed in that
interpreter by separately approved setup. --no-isolation leaves frontend dependency
installation disabled and retains the frontend's dependency checks. Missing build
or backend dependencies fail; the wrapper never installs/repairs them or switches
to a different interpreter. Backend behavior and version compatibility may vary.

The project/output are revalidated immediately before dispatch, including after
the review wait. Nonempty output fails without overwrite, deletion or cleanup.
Existing files and failed/partial artifacts are never removed by this wrapper.
Build backends can still overwrite source/build files or write elsewhere, which
is part of the arbitrary-code risk, not a filesystem isolation promise.

## Trust, privacy and cancellation

This executes arbitrary trusted-project build-backend hooks and installed code as
your operating-system user. --no-isolation, -I, fixed argv and a reduced environment
are not a security sandbox. Backend/plugin/import code can read or alter accessible
files, read credentials from files, start children, access networks, install its
own software, spend money or change systems. Only a small reviewed environment
allowlist is inherited, but that does not prevent file-based credentials or other
ambient access. Source/config/dependency bytes are not frozen; approval does not
prove the exact repository content remains unchanged. Use only trusted projects
and the intended account, never an untrusted pull request or unknown archive.

The wrapper discards stdout/stderr rather than storing or sending build logs to
the assistant. Backend-generated logs, source intermediates and artifacts can
still remain on disk. Project/output paths, selected artifact filename, byte count,
SHA256 digest and result can enter the configured assistant/model context. Review
that disclosure as part of the command approval. Do not use a private repository
name/path with a provider you have not approved to receive it.

The emergency stop blocks queued dispatch. An already-running direct subprocess
is not a fully cancellable job. Timeout terminates the direct process only; child
processes/remote effects may continue. Returning zero does not prove children have
finished. No stop/timeout undoes backend effects, deletes partial output or makes
a retry safe. This is not remote Android-to-Windows command transport.

## What success means

After direct exit zero, the output must contain exactly one bounded ASCII-named
.whl file, no directory/symlink/multiple entries. It must be regular, have one hard
link, contain 1-268435456 bytes and remain the same observed device/inode/size/mtime/
ctime during hashing. AETHER reads it in bounded chunks for SHA256 and rechecks the
file identity. No archive extraction, import, installation or artifact execution
occurs. A malformed file called example.whl can be hashed, so format_verified and
contents_safety_verified remain false. Output inspection failure after exit zero
is reported as failure, never as a valid build.

The digest identifies bytes observed locally at that time, not an immutable file,
provenance signature, reproducible build, safe wheel, compatible dependency set,
passing tests, scan, installability or product readiness. Backend/local code can
change files afterward and a hostile process can evade ordinary stat/race checks;
this is not a hostile-local-code boundary. Recheck before any later use. No upload,
artifact publication, signing, package installation, deployment, cloud call,
rollback or production acceptance is performed by the wrapper. New external
sharing or changes still require their own exact approval.

## Evidence and open acceptance

Mocked-subprocess and temporary-file tests cover fixed argv/environment, strict
path/timeout/output rules, direct success/failure/timeout, output identity changes,
symlinks, size/type/count/name limits, no automatic cleanup/retry, fresh approval,
no auto/always bypass and stop/review-wait revalidation. No owner project/backend
was executed, no real machine setup was changed and no native Windows build was
used as runtime acceptance. These tests do not establish third-party backend
behavior or compatibility on the owner's environment. Real trusted-project/device
acceptance needs explicit setup/command approval. This local adapter does not
complete the broader Docker/Kubernetes/cloud/CI deployment blueprint.

Official sources checked November 17, 2026:

- https://build.pypa.io/en/latest/reference/cli.html
- https://build.pypa.io/en/latest/reference/environment-variables.html
