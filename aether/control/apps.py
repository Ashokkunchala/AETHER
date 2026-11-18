"""Application discovery, launching, focusing and closing on Windows."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("aether.control.apps")

APP_ALIASES: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "cmd": "cmd",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "pwsh": "pwsh",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "spotify": "spotify",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "discord": "discord",
    "obs": "obs64",
    "paint": "mspaint",
    "snipping tool": "snippingtool",
    "settings": "ms-settings:",
    "control panel": "control",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
}

_APP_SEARCH_CACHE: dict[str, dict[str, str]] = {}
_CACHE_TTL_SECONDS = 300


def _start_menu_roots() -> list[Path]:
    roots = []
    for base in (
        os.environ.get("APPDATA", ""),
        os.environ.get("PROGRAMDATA", ""),
    ):
        if not base:
            continue
        for sub in (
            r"Microsoft\Windows\Start Menu\Programs",
            r"Microsoft\Windows\Start Menu\Programs\Startup",
        ):
            p = Path(base) / sub
            if p.is_dir():
                roots.append(p)
    return roots


def build_app_index(force: bool = False) -> dict[str, dict[str, str]]:
    """Index installed Start Menu shortcuts: {lower_name: {name, path}}."""
    import time

    cached = _APP_SEARCH_CACHE.get("__index__")
    if cached and not force and time.time() - cached["ts"] < _CACHE_TTL_SECONDS:
        return cached["apps"]

    index: dict[str, dict[str, str]] = {}
    for root in _start_menu_roots():
        for shortcut in root.rglob("*.lnk"):
            name = shortcut.stem
            entry = {"name": name, "path": str(shortcut)}
            index.setdefault(name.lower(), entry)
            # Drop " - Shortcut" suffix variants too
            if name.lower().endswith(" - shortcut"):
                index.setdefault(name[: -len(" - shortcut")].lower(), entry)
        for exe in root.rglob("*.exe"):
            name = exe.stem
            index.setdefault(name.lower(), {"name": name, "path": str(exe)})

    # Also index PATH executables
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory or not Path(directory).is_dir():
            continue
        try:
            for exe in Path(directory).glob("*.exe"):
                name = exe.stem
                index.setdefault(name.lower(), {"name": name, "path": str(exe)})
        except OSError:
            continue

    _APP_SEARCH_CACHE["__index__"] = {"apps": index, "ts": time.time()}
    logger.debug("Indexed %d applications", len(index))
    return index


def search_apps(query: str, limit: int = 15) -> list[dict[str, str]]:
    """Fuzzy-ish search across the Start Menu / PATH index."""
    query = query.strip().lower()
    if not query:
        return []
    index = build_app_index()
    starts, contains = [], []
    for key, entry in index.items():
        if key.startswith(query):
            starts.append(entry)
        elif query in key:
            contains.append(entry)
    results = starts + contains
    seen, ordered = set(), []
    for entry in results:
        if entry["name"].lower() in seen:
            continue
        seen.add(entry["name"].lower())
        ordered.append(entry)
    return ordered[:limit]


def launch_app(app: str, args: str | None = None) -> dict[str, Any]:
    """Legacy broad-launch route is disabled, including shell/alias/URI fallback."""
    return {"success": False, "error": "Use the approved-app registry tool with exact local allowlist ID/executable/SHA256 and fresh confirmation. Direct broad launch is disabled."}


def close_app(name: str, force: bool = False) -> dict[str, Any]:
    """Legacy broad termination fails closed."""
    return {"success": False, "error": "Name-based stop disabled. Use exact PID/create_time/executable process-stop registry with fresh confirmation."}


def list_running_apps() -> list[dict[str, Any]]:
    """Unique visible/windowed applications currently running."""
    import psutil

    seen: dict[str, dict[str, Any]] = {}
    for proc in psutil.process_iter(["name", "pid", "memory_info"]):
        try:
            name = proc.info["name"] or ""
            if not name:
                continue
            if name.lower() in {"system", "registry", "idle", "memory compression"}:
                continue
            if name in seen:
                continue
            mem = proc.info.get("memory_info")
            seen[name] = {
                "name": name,
                "pid": proc.info["pid"],
                "memory_mb": round(mem.rss / (1024 * 1024), 1) if mem else None,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(seen.values(), key=lambda x: x["name"].lower())
