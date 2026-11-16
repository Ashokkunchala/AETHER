"""Fresh-approved fixed Python wheel build, no install/publish/deploy or sandbox claim."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ENV_KEYS = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "PATHEXT",
    "LANG",
    "LC_ALL",
}
_MAX_WHEEL = 268435456


def _canonical(value, directory):
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        raise ValueError("Explicit canonical local paths required.")
    path = Path(value)
    if value.startswith(("\\\\", "//")) or not path.is_absolute():
        raise ValueError("Relative/network paths refused.")
    if path.resolve(strict=True) != path or path.is_symlink():
        raise ValueError("Noncanonical/symlink path refused.")
    if directory and not path.is_dir() or not directory and not path.is_file():
        raise ValueError("Required path type unavailable.")
    return path


def _plan(project, output, timeout):
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise ValueError("Timeout must be an integer from5 through300seconds.")
    root = _canonical(project, True)
    _canonical(str(root / "pyproject.toml"), False)
    target = _canonical(output, True)
    if target.parent != root or not re.fullmatch(r"aether-wheel-[A-Za-z0-9_-]{1,64}", target.name):
        raise ValueError(
            "Output must be an existing dedicated aether-wheel-NAME direct child of the project."
        )
    with os.scandir(target) as entries:
        if next(entries, None) is not None:
            raise ValueError("Output directory is not empty; no overwrite/cleanup is performed.")
    python = Path(sys.executable)
    if not python.is_absolute() or not python.is_file():
        raise ValueError("Current interpreter unavailable.")
    argv = [
        str(python),
        "-I",
        "-B",
        "-m",
        "build",
        "--wheel",
        "--no-isolation",
        "--outdir",
        str(target),
        str(root),
    ]
    return root, target, argv


def preview_python_wheel(project: str, output: str, timeout: int = 120):
    try:
        root, target, argv = _plan(project, output, timeout)
    except (ValueError, OSError, RuntimeError):
        return {
            "success": False,
            "error": "Invalid/unavailable canonical project, pyproject.toml, empty dedicated output directory, current interpreter or timeout. No build started.",
        }
    return {
        "success": True,
        "project": str(root),
        "output_directory": str(target),
        "argv": argv,
        "shell": False,
        "timeout_seconds": timeout,
        "overwrites_or_cleanup": False,
        "notice": (
            "This runs trusted project build-backend hooks and installed dependencies as your user. "
            "Review the exact project, empty output directory and command. Backend code can read/write "
            "any accessible files, launch children, use file credentials or the network, spend money "
            "or change systems. --no-isolation avoids build frontend dependency installation, not "
            "backend side effects. A reduced environment and -I are not a security sandbox. "
            "Project/dependency bytes are not frozen or reviewed and can change after approval. "
            "The backend may write intermediate files outside output. Direct-process timeout/stop "
            "does not guarantee children/remote work stops or undo changes. stdout/stderr are discarded, "
            "not uploaded/retained by this wrapper; backends can write their own logs. "
            "Paths, final artifact filename, size, digest and status may enter configured assistant/model "
            "context. No automatic dependency install, repair, retry, signing, upload, publish or deploy. "
            "One resulting local .whl file is hashed, not validated as safe/correct/installable. "
            "No source freeze, reproducibility, test/scan/provenance or readiness claim."
        ),
    }


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _artifact(root, target):
    # Recheck canonical target after untrusted backend execution; not a hostile-local-code boundary.
    if _canonical(str(root), True) != root or _canonical(str(target), True) != target:
        raise ValueError("Output identity unavailable.")
    with os.scandir(target) as entries:
        selected = []
        for entry in entries:
            selected.append(entry.name)
            if len(selected) > 1:
                raise ValueError("Expected one artifact, not multiple output entries.")
    if len(selected) != 1 or not re.fullmatch(r"[A-Za-z0-9_.+\-]{1,200}\.whl", selected[0]):
        raise ValueError("Expected one bounded ASCII wheel filename.")
    path = _canonical(str(target / selected[0]), False)
    before = path.stat()
    if (
        not stat.S_ISREG(before.st_mode)
        or not 1 <= before.st_size <= _MAX_WHEEL
        or before.st_nlink != 1
    ):
        raise ValueError("Unsupported artifact size/type/link count.")
    digest = hashlib.sha256()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (
            _identity(opened) != _identity(before)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
        ):
            raise ValueError("Artifact changed before hashing.")
        count = 0
        while True:
            chunk = stream.read(min(1048576, _MAX_WHEEL + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            if count > _MAX_WHEEL:
                raise ValueError("Artifact grew beyond hash bound.")
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    if (
        count != before.st_size
        or _identity(after) != _identity(before)
        or _identity(path.stat()) != _identity(before)
        or path.is_symlink()
    ):
        raise ValueError("Artifact changed during hashing.")
    # Nothing is extracted, imported, installed or executed from this output.
    return {
        "filename": path.name,
        "path": str(path),
        "bytes": count,
        "sha256": digest.hexdigest(),
        "format_verified": False,
        "contents_safety_verified": False,
        "notice": "Digest of observed local bytes only, not an immutable artifact, provenance signature, valid wheel, malware scan, passing test or successful install. Recheck before any later use.",
    }


def build_python_wheel(project: str, output: str, timeout: int = 120):
    preview = preview_python_wheel(project, output, timeout)
    if not preview.get("success"):
        return preview
    try:
        root, target, argv = _plan(project, output, timeout)
    except (ValueError, OSError, RuntimeError):
        return {
            "success": False,
            "error": "Project/output changed or became unavailable after review; no build started.",
        }
    env = {k: v for k, v in os.environ.items() if k.upper() in _ENV_KEYS}
    env.update(PYTHONNOUSERSITE="1", PYTHONIOENCODING="utf-8")
    common = {
        "as_of": datetime.now(UTC).isoformat(),
        "argv": argv,
        "project": str(root),
        "output_directory": str(target),
        "process_output_retained": False,
        "artifact_cleanup_performed": False,
        "child_process_completion_verified": False,
        "product_readiness_verified": False,
        "automatic_retry": False,
        "cleanup_performed": False,
        "wrapper_published": False,
        "wrapper_installed": False,
        "notice": "No output cleanup or retry. Partial artifacts/backend side effects can remain even on failure. Direct process completion does not prove child/remote completion. Nothing was installed/published by this wrapper, but backend side effects are not constrained.",
    }
    try:
        result = subprocess.run(
            argv,
            cwd=str(root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            **common,
            "success": False,
            "timed_out": True,
            "error": "Direct build process timed out; children/remote work and partial output may remain. No automatic cleanup/retry.",
        }
    except Exception:
        return {
            **common,
            "success": False,
            "error": "Build process could not be completed. Exception/output details omitted; side effects may remain.",
        }
    code = result.returncode
    if code != 0:
        return {
            **common,
            "success": False,
            "timed_out": False,
            "exit_code": code,
            "error": f"Build direct process exited with status {code}. Output discarded; no automatic install, repair, retry or cleanup.",
        }
    try:
        artifact = _artifact(root, target)
    except (OSError, ValueError, RuntimeError):
        return {
            **common,
            "success": False,
            "timed_out": False,
            "exit_code": code,
            "error": "Build returned zero but a single bounded regular unchanged wheel-named artifact could not be verified/hashed. No valid build or readiness claimed; files retained for local review.",
        }
    return {
        **common,
        "success": True,
        "timed_out": False,
        "exit_code": code,
        "artifact": artifact,
        "outcome": "Direct build process exited zero and one local wheel-named file was hashed. Format, tests, security, dependency correctness and installability remain unverified.",
    }


def register_python_wheel(registry):
    from jarvis.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="build_python_wheel",
            description="Fresh-approved fixed python -m build --wheel --no-isolation in one trusted canonical project with an existing empty dedicated output directory. Executes arbitrary backend code, not a sandbox. No install/publish/deploy. Hashes one bounded local wheel-named output, not a correctness/security pass.",
            parameters={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Canonical local absolute trusted project root with regular pyproject.toml.",
                    },
                    "output": {
                        "type": "string",
                        "description": "Existing empty canonical project/aether-wheel-NAME directory, direct child, NAME1-64ASCII letters/digits/_/-.",
                    },
                    "timeout": {"type": "integer", "minimum": 5, "maximum": 300},
                },
                "required": ["project", "output"],
                "additionalProperties": False,
            },
            handler=build_python_wheel,
            confirmation_preview=preview_python_wheel,
            risk=Risk.HIGH,
            category="devops",
            requires_confirmation=True,
            never_auto_approve=True,
            allow_auto_approve=False,
            allow_always=False,
        )
    )


# Execution is permitted only through the existing fresh-review registry boundary.
