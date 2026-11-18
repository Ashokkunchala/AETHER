"""Owner-configured reviewed document/folder launch through an exact approved app.

No default-file association, shell, URI, alias, network path or automatic launch is
used.  The local owner separately approves the handler executable and the target
roots; every launch revalidates both before passing one local path argument.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from jarvis.control.approved_apps import resolve_approved_app
from jarvis.control.files import PROTECTED_PREFIXES

MAX_CONFIG_BYTES = 64_000
MAX_HANDLERS = 50
MAX_ROOTS = 20
MAX_EXTENSIONS = 30
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_FOLDER_ENTRIES = 1_000
_HANDLER_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_CONFIG_ENV = "JARVIS_REVIEWED_OPEN_FILE"

# These formats can directly execute code, macros, scripts or shell associations.
# A familiar extension is never treated as approval; these stay refused even if
# an owner accidentally lists them in the local reviewed-open configuration.
BLOCKED_EXTENSIONS = frozenset({
    ".ade", ".adp", ".app", ".application", ".appref-ms", ".bat", ".chm",
    ".cmd", ".com", ".cpl", ".crt", ".csh", ".dll", ".docm", ".drv",
    ".exe", ".gadget", ".hta", ".htm", ".html", ".inf", ".ins", ".isp",
    ".jar", ".js", ".jse", ".ksh", ".lnk", ".mda", ".mdb", ".mde",
    ".mdt", ".mdw", ".mdz", ".msc", ".msi", ".msp", ".mst", ".ocx",
    ".ops", ".pcd", ".pif", ".potm", ".ppam", ".ppsm", ".pptm", ".prf",
    ".prg", ".ps1", ".ps1xml", ".ps2", ".ps2xml", ".psc1", ".psc2",
    ".psm1", ".pst", ".py", ".pyc", ".pyw", ".reg", ".rgs", ".scf",
    ".scr", ".sct", ".sh", ".shb", ".shtml", ".svg", ".sys", ".url",
    ".vb", ".vbe", ".vbs", ".vxd", ".wsc", ".wsf", ".wsh", ".xht",
    ".xhtml", ".xlsm", ".xltm", ".xml",
})


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate reviewed-open configuration keys are refused.")
        result[key] = value
    return result


def _config_path() -> Path:
    return Path(os.environ.get(_CONFIG_ENV, str(Path.home() / ".jarvis" / "reviewed_open.json"))).expanduser()


def _local_absolute(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not 1 <= len(value) <= 2_000 or "\x00" in value:
        raise ValueError(f"{label} must be a bounded local path string.")
    if value.startswith(("\\\\", "//")):
        raise ValueError(f"{label} must not be a network path.")
    path = Path(value)
    if not path.is_absolute() or ":" in path.name:
        raise ValueError(f"{label} must be a canonical absolute local path.")
    resolved = path.resolve()
    if resolved != path:
        raise ValueError(f"{label} must be canonical and contain no symlink/reparse component.")
    return path


def _protected(path: Path) -> bool:
    lowered = str(path).lower()
    return any(lowered.startswith(prefix.lower()) for prefix in PROTECTED_PREFIXES)


def _load_config() -> dict[str, Any]:
    config = _config_path()
    if not config.is_file() or config.is_symlink() or config.resolve() != config:
        raise ValueError("No canonical local reviewed-open handler configuration is installed.")
    raw = config.read_bytes()
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("Reviewed-open configuration exceeds 64KB.")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Reviewed-open configuration must be valid UTF-8 JSON without duplicate keys.") from exc
    if not isinstance(document, dict) or set(document) != {"version", "handlers"}:
        raise ValueError("Expected a version1 reviewed-open configuration with only version/handlers.")
    if type(document["version"]) is not int or document["version"] != 1:
        raise ValueError("Reviewed-open configuration version must be integer 1.")
    handlers = document["handlers"]
    if not isinstance(handlers, dict) or not 1 <= len(handlers) <= MAX_HANDLERS:
        raise ValueError("Reviewed-open configuration must name 1-50 handlers.")
    return handlers


def _extension(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\.[a-z0-9][a-z0-9_-]{0,18}", value):
        raise ValueError("Extensions must be simple lower-case suffixes such as .pdf.")
    extension = value.lower()
    if extension in BLOCKED_EXTENSIONS:
        raise ValueError(f"{extension} is an active-content format and cannot be opened by this route.")
    return extension


def _handler(handlers: dict[str, Any], handler_id: str) -> dict[str, Any]:
    if not isinstance(handler_id, str) or _HANDLER_ID.fullmatch(handler_id) is None:
        raise ValueError("Use an exact lower-case reviewed-open handler ID.")
    entry = handlers.get(handler_id)
    if not isinstance(entry, dict) or set(entry) != {"app", "roots", "targets", "extensions"}:
        raise ValueError("Handler entry must contain exactly app, roots, targets and extensions.")
    app = entry["app"]
    if not isinstance(app, str) or _HANDLER_ID.fullmatch(app) is None:
        raise ValueError("Handler app must be an exact approved-app ID.")
    roots = entry["roots"]
    if not isinstance(roots, list) or not 1 <= len(roots) <= MAX_ROOTS or len(set(roots)) != len(roots):
        raise ValueError("Handler must list 1-20 unique owner-approved roots.")
    resolved_roots = []
    for root_value in roots:
        root = _local_absolute(root_value, "Approved root")
        if not root.is_dir() or _protected(root):
            raise ValueError("Approved root must be an existing non-protected canonical local directory.")
        resolved_roots.append(root)
    targets = entry["targets"]
    if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets) or any(t not in {"file", "folder"} for t in targets):
        raise ValueError("Handler targets must uniquely select file and/or folder.")
    extensions = entry["extensions"]
    if not isinstance(extensions, list) or len(extensions) > MAX_EXTENSIONS or len(set(extensions)) != len(extensions):
        raise ValueError("Handler extensions must be unique and at most 30.")
    parsed_extensions = [_extension(value) for value in extensions]
    if "file" in targets and not parsed_extensions:
        raise ValueError("A file handler must list at least one allowed extension.")
    return {"app": app, "roots": resolved_roots, "targets": set(targets), "extensions": set(parsed_extensions)}


def _file_digest(path: Path) -> str:
    before = path.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError("Reviewed files are limited to 512MiB.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    after = path.stat()
    identity = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(getattr(before, name) != getattr(after, name) for name in identity):
        raise ValueError("Selected file changed while it was being hashed; request a fresh review.")
    return digest.hexdigest()


def _folder_snapshot(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with os.scandir(path) as iterator:
        for index, entry in enumerate(iterator):
            if index >= MAX_FOLDER_ENTRIES:
                raise ValueError("Reviewed folders are limited to 1000 immediate entries.")
            try:
                stat = entry.stat(follow_symlinks=False)
                if entry.is_symlink():
                    kind = "link"
                elif entry.is_dir(follow_symlinks=False):
                    kind = "folder"
                elif entry.is_file(follow_symlinks=False):
                    kind = "file"
                else:
                    kind = "other"
                entries.append({
                    "name": entry.name,
                    "kind": kind,
                    "size": stat.st_size if kind == "file" else None,
                    "mtime_ns": stat.st_mtime_ns,
                })
            except OSError as exc:
                raise ValueError("A folder entry changed or could not be inspected; request a fresh review.") from exc
    entries.sort(key=lambda item: item["name"])
    return entries


def _folder_digest(path: Path) -> str:
    first = _folder_snapshot(path)
    second = _folder_snapshot(path)
    if first != second:
        raise ValueError("Selected folder changed while it was being reviewed; request a fresh review.")
    encoded = json.dumps(first, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prepare(handler_id: str, path: str) -> dict[str, Any]:
    handler = _handler(_load_config(), handler_id)
    target = _local_absolute(path, "Selected path")
    if _protected(target):
        raise ValueError("Protected system locations are not reviewed-open targets.")
    if not any(target.is_relative_to(root) for root in handler["roots"]):
        raise ValueError("Selected path is outside this handler's owner-approved roots.")
    if target.is_symlink():
        raise ValueError("Selected path must not be a symlink/reparse point.")
    if target.is_file():
        kind = "file"
        if kind not in handler["targets"]:
            raise ValueError("This reviewed-open handler does not allow files.")
        if target.suffix.lower() not in handler["extensions"]:
            raise ValueError("Selected file extension is not in this handler's reviewed list.")
        digest = _file_digest(target)
        size = target.stat().st_size
    elif target.is_dir():
        kind = "folder"
        if kind not in handler["targets"]:
            raise ValueError("This reviewed-open handler does not allow folders.")
        digest = _folder_digest(target)
        size = None
    else:
        raise ValueError("Selected path must be an existing regular file or directory.")
    return {"handler_id": handler_id, "handler_app": handler["app"], "path": str(target), "kind": kind, "digest": digest, "size": size}


def plan_reviewed_open(handler_id: str, path: str) -> dict[str, Any]:
    """Read local config/target only and return exact values needed for review."""
    prepared = _prepare(handler_id, path)
    return {
        "success": True,
        "handler_id": prepared["handler_id"],
        "handler_app": prepared["handler_app"],
        "path": prepared["path"],
        "kind": prepared["kind"],
        "digest": prepared["digest"],
        "size_bytes": prepared["size"],
        "next_step": "Use these exact values with open_reviewed_path, including the separately approved handler executable path/hash. Fresh confirmation is required.",
        "limits": "The digest identifies current bytes/listing only; it is not malware, macro, content-safety, application-behavior or default-association verification.",
    }


def _validate_request(
    handler_id: str,
    path: str,
    expected_kind: str,
    expected_digest: str,
    expected_handler_app: str,
    expected_handler_executable: str,
    expected_handler_sha256: str,
) -> dict[str, Any]:
    if expected_kind not in {"file", "folder"}:
        raise ValueError("Expected kind must be exactly file or folder.")
    if not isinstance(expected_digest, str) or _HEX_64.fullmatch(expected_digest) is None:
        raise ValueError("Supply the exact lower-case reviewed target digest from plan_reviewed_open.")
    prepared = _prepare(handler_id, path)
    if prepared["kind"] != expected_kind or prepared["digest"] != expected_digest:
        raise ValueError("Selected path changed or no longer matches the reviewed kind/digest. Request a fresh review.")
    if prepared["handler_app"] != expected_handler_app:
        raise ValueError("Reviewed-open handler no longer maps to the expected approved app.")
    handler_executable = resolve_approved_app(expected_handler_app, expected_handler_executable, expected_handler_sha256)
    return {**prepared, "handler_executable": handler_executable}


def preview_reviewed_open(
    handler_id: str,
    path: str,
    expected_kind: str,
    expected_digest: str,
    expected_handler_app: str,
    expected_handler_executable: str,
    expected_handler_sha256: str,
) -> dict[str, Any]:
    """Confirmation preview; revalidates exact target/handler without launching."""
    prepared = _validate_request(
        handler_id, path, expected_kind, expected_digest,
        expected_handler_app, expected_handler_executable, expected_handler_sha256,
    )
    return {
        "success": True,
        "handler_id": prepared["handler_id"],
        "handler_app": prepared["handler_app"],
        "handler_executable": str(prepared["handler_executable"]),
        "path": prepared["path"],
        "kind": prepared["kind"],
        "digest": prepared["digest"],
        "effect": "Start the exact approved handler executable once with this one local file/folder path as its only argument. No shell, default association, elevation, upload or extra arguments.",
        "privacy": "The selected path and local content/listing digest enter the trusted approval context. The handler application may read the target and may have its own network or account behavior.",
        "limits": "Hash/listing review proves identity at recheck time, not content safety, malware status, macro safety, UI readiness or later unchanged state. Host OS, mapped drives and concurrent changes after launch are not sandboxed.",
        "approval": "Fresh confirmation for this exact target/handler/digest only; no standing, auto or always approval.",
    }


def open_reviewed_path(
    handler_id: str,
    path: str,
    expected_kind: str,
    expected_digest: str,
    expected_handler_app: str,
    expected_handler_executable: str,
    expected_handler_sha256: str,
) -> dict[str, Any]:
    """Internal registry handler; trusted local confirmation owns authority."""
    prepared = _validate_request(
        handler_id, path, expected_kind, expected_digest,
        expected_handler_app, expected_handler_executable, expected_handler_sha256,
    )
    executable = prepared["handler_executable"]
    process = subprocess.Popen([str(executable), prepared["path"]], shell=False, cwd=str(executable.parent))
    return {
        "success": True,
        "handler_id": prepared["handler_id"],
        "handler_app": prepared["handler_app"],
        "handler_executable": str(executable),
        "path": prepared["path"],
        "kind": prepared["kind"],
        "digest": prepared["digest"],
        "pid": process.pid,
        "launch_requested": True,
        "application_ready_verified": False,
        "default_association_used": False,
        "elevated_requested": False,
    }
