"""Process inspection and termination."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("jarvis.control.process")

CRITICAL_PROCESSES = {
    "csrss.exe",
    "lsass.exe",
    "services.exe",
    "smss.exe",
    "wininit.exe",
    "winlogon.exe",
    "system",
    "registry",
    "idle",
    "memcompression",
    "dwm.exe",
}


def list_processes(search: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    import psutil

    results = []
    for proc in psutil.process_iter(["pid", "name", "username", "memory_info", "cpu_percent", "create_time"]):
        try:
            info = proc.info
            name = info.get("name") or ""
            if search and search.lower() not in name.lower():
                continue
            mem = info.get("memory_info")
            results.append(
                {
                    "pid": info["pid"],
                    "name": name,
                    "username": info.get("username"),
                    "memory_mb": round(mem.rss / (1024 * 1024), 1) if mem else None,
                    "started": info.get("create_time"),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    results.sort(key=lambda r: (r["memory_mb"] or 0), reverse=True)
    return results[:limit]


def find_process(name: str) -> list[dict[str, Any]]:
    return list_processes(search=name, limit=50)


def terminate_process(name: str, force: bool = False) -> dict[str, Any]:
    return {"success": False, "error": "Name-based stop disabled. Use exact PID/create_time/executable process-stop registry with fresh confirmation."}


def start_process(command: str, elevated: bool = False) -> dict[str, Any]:
    """Start a program. elevated=true requests UAC elevation."""
    import subprocess

    try:
        if elevated:
            import ctypes  # noqa: F401

            result = subprocess.Popen(  # noqa: S602
                ["powershell", "-Command", f"Start-Process -FilePath '{command}' -Verb RunAs"],
                shell=False,
            )
            return {"success": True, "command": command, "elevated": True, "pid": result.pid}
        proc = subprocess.Popen(command, shell=True)  # noqa: S602
        return {"success": True, "command": command, "pid": proc.pid}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def process_details(pid: int) -> dict[str, Any]:
    import psutil

    try:
        proc = psutil.Process(int(pid))
        with proc.oneshot():
            return {
                "success": True,
                "pid": proc.pid,
                "name": proc.name(),
                "exe": proc.exe(),
                "cmdline": proc.cmdline(),
                "cpu_percent": proc.cpu_percent(interval=0.1),
                "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
                "status": proc.status(),
                "create_time": proc.create_time(),
                "num_threads": proc.num_threads(),
            }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
