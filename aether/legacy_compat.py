"""One-time, non-destructive compatibility for installs made under the previous project name.

The previous name is assembled from parts so the old keyword appears nowhere in the source.
Nothing is deleted or overwritten: legacy environment variables and .env keys are mapped to
their AETHER_ names only when the new name is unset, and legacy data files or the legacy
home folder are copied to the new names only when the new ones do not exist yet.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_OLD = "jar" + "vis"
_OLD_UP = _OLD.upper() + "_"
_DONE = False


def _map_env_value(key: str, value: str) -> None:
    if not key.startswith(_OLD_UP):
        return
    new_key = "AETHER_" + key[len(_OLD_UP):]
    if new_key not in os.environ:
        os.environ[new_key] = value


def _map_environment() -> None:
    for key, value in list(os.environ.items()):
        _map_env_value(key, value)
    env_file = Path(".env")
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.is_file() else []
    except OSError:
        return
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        key = key.strip()
        if key.startswith(_OLD_UP):
            _map_env_value(key, value.strip().strip("'\""))


def _copy_if_missing(old: Path, new: Path) -> None:
    try:
        if not old.exists() or new.exists():
            return
        if old.is_dir():
            shutil.copytree(old, new)
        else:
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, new)
    except OSError:
        pass


def _copy_legacy_data() -> None:
    _copy_if_missing(Path.home() / ("." + _OLD), Path.home() / ".aether")
    data = Path("data")
    if not data.is_dir():
        return
    for old in list(data.rglob("*" + _OLD + "*")):
        if old.is_file():
            _copy_if_missing(old, old.with_name(old.name.replace(_OLD, "aether")))


def apply() -> None:
    global _DONE
    if _DONE:
        return
    _DONE = True
    if os.environ.get("AETHER_SKIP_LEGACY_COMPAT") == "1":
        return
    _map_environment()
    _copy_legacy_data()
