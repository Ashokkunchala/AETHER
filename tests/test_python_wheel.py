import asyncio
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.devops import python_wheel as mod


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text('[build-system]\nrequires=[]\nbuild-backend="example"\n')
    out = root / "aether-wheel-test"
    out.mkdir()
    return root, out


def test_preview_fixed_command_no_build(project, monkeypatch):
    root, out = project

    def forbidden(*args, **kwargs):
        raise AssertionError("No process in preview")

    monkeypatch.setattr(mod.subprocess, "run", forbidden)
    result = mod.preview_python_wheel(str(root), str(out))
    assert result["success"]
    assert result["argv"] == [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "build",
        "--wheel",
        "--no-isolation",
        "--outdir",
        str(out),
        str(root),
    ]
    assert not result["shell"] and not result["overwrites_or_cleanup"]
    for phrase in [
        "not a security sandbox",
        "spend money",
        "not frozen",
        "stdout/stderr",
        "No automatic dependency install",
    ]:
        assert phrase in result["notice"]
    assert not list(out.iterdir())


@pytest.mark.parametrize("timeout", [True, None, 1, 4, 301, 600, "60", 60.0])
def test_bad_timeout_no_dispatch(project, monkeypatch, timeout):
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    assert not mod.build_python_wheel(*map(str, project), timeout=timeout)["success"]


@pytest.mark.parametrize(
    "which,value",
    [
        ("root", "."),
        ("out", "."),
        ("root", "relative"),
        ("out", "relative"),
        ("root", "//host/share"),
        ("out", "//host/share"),
        ("root", ""),
        ("out", ""),
        ("root", None),
        ("out", True),
        ("root", "x\x00y"),
    ],
)
def test_bad_paths_no_dispatch(project, monkeypatch, which, value):
    root, out = map(str, project)
    if which == "root":
        root = value
    else:
        out = value
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    assert not mod.build_python_wheel(root, out)["success"]


def test_missing_pyproject_and_nonempty_output_not_overwritten(project, monkeypatch):
    root, out = project
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    (out / "keep.txt").write_text("keep")
    assert not mod.build_python_wheel(str(root), str(out))["success"]
    assert (out / "keep.txt").read_text() == "keep"
    (root / "pyproject.toml").unlink()
    assert not mod.preview_python_wheel(str(root), str(out))["success"]


def test_output_scoped_to_named_direct_child(project, tmp_path):
    root, out = project
    for path in [root, tmp_path, out / "aether-wheel-inner", root / "arbitrary"]:
        path.mkdir(exist_ok=True)
        assert not mod.preview_python_wheel(str(root), str(path))["success"]
    assert not mod.preview_python_wheel(str(root), str(root / "aether-wheel-missing"))["success"]


def test_symlinks_rejected(project, tmp_path):
    root, out = project
    link = tmp_path / "link"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create symlinks")
    assert not mod.preview_python_wheel(str(link), str(link / out.name))["success"]
    (root / "aether-wheel-link").symlink_to(out, target_is_directory=True)
    assert not mod.preview_python_wheel(str(root), str(root / "aether-wheel-link"))["success"]


def test_success_observed_bytes_not_wheel_validation(project, monkeypatch):
    root, out = project
    data = b"This is not a valid wheel archive."
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-inherit")
    monkeypatch.setenv("PYTHONPATH", "must-not-inherit")

    def fake(argv, **kwargs):
        assert kwargs["cwd"] == str(root) and kwargs["shell"] is False and kwargs["check"] is False
        assert kwargs["timeout"] == 120 and kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.DEVNULL and kwargs["stderr"] == subprocess.DEVNULL
        assert "AWS_SECRET_ACCESS_KEY" not in kwargs["env"] and "PYTHONPATH" not in kwargs["env"]
        assert kwargs["env"]["PYTHONNOUSERSITE"] == "1"
        (out / "example-1-py3-none-any.whl").write_bytes(data)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake)
    result = mod.build_python_wheel(str(root), str(out))
    assert result["success"] and result["exit_code"] == 0
    assert result["artifact"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["artifact"]["bytes"] == len(data)
    assert (
        not result["artifact"]["format_verified"]
        and not result["artifact"]["contents_safety_verified"]
    )
    assert (
        not result["child_process_completion_verified"] and not result["product_readiness_verified"]
    )
    assert (
        not result["wrapper_installed"]
        and not result["wrapper_published"]
        and not result["process_output_retained"]
    )
    assert not result["cleanup_performed"] and not result["automatic_retry"]


@pytest.mark.parametrize("code", [1, 2, 42, -9])
def test_nonzero_never_hashes_or_cleans_partial(project, monkeypatch, code):
    root, out = project
    count = []

    def fake(*a, **kw):
        count.append(1)
        (out / "partial.txt").write_text("private")
        return SimpleNamespace(returncode=code)

    monkeypatch.setattr(mod.subprocess, "run", fake)
    monkeypatch.setattr(mod, "_artifact", lambda *a: pytest.fail("nonzero must not hash"))
    result = mod.build_python_wheel(str(root), str(out))
    assert not result["success"] and result["exit_code"] == code and len(count) == 1
    assert (out / "partial.txt").read_text() == "private" and "private" not in str(result)


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("private", 120), OSError("private")])
def test_errors_no_raw_output_retry_or_cleanup(project, monkeypatch, error):
    def fake(*a, **kw):
        raise error

    monkeypatch.setattr(mod.subprocess, "run", fake)
    result = mod.build_python_wheel(*map(str, project))
    assert (
        not result["success"] and not result["cleanup_performed"] and not result["automatic_retry"]
    )
    assert "private" not in str(result)
    if isinstance(error, subprocess.TimeoutExpired):
        assert result["timed_out"]


@pytest.mark.parametrize(
    "mode", ["empty", "two", "directory", "wrong_extension", "zero", "nonascii", "too_big"]
)
def test_zero_exit_is_not_sufficient(project, monkeypatch, mode):
    root, out = project

    def fake(*a, **kw):
        if mode == "two":
            (out / "one.whl").write_bytes(b"one")
            (out / "two.whl").write_bytes(b"two")
        elif mode == "directory":
            (out / "one.whl").mkdir()
        elif mode == "wrong_extension":
            (out / "one.txt").write_bytes(b"text")
        elif mode == "zero":
            (out / "one.whl").write_bytes(b"")
        elif mode == "nonascii":
            (out / "తెలుగు.whl").write_bytes(b"one")
        elif mode == "too_big":
            (out / "one.whl").write_bytes(b"12345")
        return SimpleNamespace(returncode=0)

    if mode == "too_big":
        monkeypatch.setattr(mod, "_MAX_WHEEL", 4)
    monkeypatch.setattr(mod.subprocess, "run", fake)
    result = mod.build_python_wheel(str(root), str(out))
    assert not result["success"] and result["exit_code"] == 0 and "artifact" not in result


def test_artifact_link_not_followed(project, tmp_path):
    root, out = project
    external = tmp_path / "external"
    external.write_bytes(b"outside")
    try:
        (out / "one.whl").symlink_to(external)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(ValueError):
        mod._artifact(root, out)


def test_changed_file_during_hash_refused(project, monkeypatch):
    root, out = project
    wheel = out / "one.whl"
    wheel.write_bytes(b"one")
    original = mod.hashlib.sha256

    class Hash:
        def __init__(self):
            self.inner = original()

        def update(self, data):
            self.inner.update(data)
            wheel.write_bytes(b"different")

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(mod.hashlib, "sha256", Hash)
    with pytest.raises(ValueError):
        mod._artifact(root, out)


def test_dispatch_revalidates_after_preview(project, monkeypatch):
    root, out = project
    original = mod.preview_python_wheel

    def preview(*a, **kw):
        result = original(*a, **kw)
        (out / "appeared").touch()
        return result

    monkeypatch.setattr(mod, "preview_python_wheel", preview)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    assert not mod.build_python_wheel(str(root), str(out))["success"]


def test_registry_fresh_review_deny_and_emergency_stop(project, monkeypatch, tmp_path):
    from jarvis.tools.builtin_tools import build_registry
    from jarvis.security import SecurityStore

    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    tool = registry.tools["build_python_wheel"]
    assert (
        tool.never_auto_approve
        and tool.confirm_required
        and not tool.allow_always
        and not tool.allow_auto_approve
    )
    calls = []
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *a, **kw: calls.append(1) or SimpleNamespace(returncode=1)
    )
    args = {"project": str(project[0]), "output": str(project[1])}
    assert not asyncio.run(registry.execute("build_python_wheel", args, auto_approve=True)).ok

    async def deny(tool, args):
        return False

    assert not asyncio.run(registry.execute("build_python_wheel", args, confirm=deny)).ok
    previews = []

    async def approve(tool, args):
        previews.append(args["_preview"])
        return True

    assert not asyncio.run(registry.execute("build_python_wheel", args, confirm=approve)).ok
    assert len(calls) == 1 and previews[0]["argv"][4] == "build"
    SecurityStore().set_stop(True)
    assert not asyncio.run(registry.execute("build_python_wheel", args, confirm=approve)).ok
    assert len(calls) == 1


def test_stop_or_output_changed_during_review_prevents_dispatch(project, monkeypatch, tmp_path):
    from jarvis.tools.builtin_tools import build_registry
    from jarvis.security import SecurityStore

    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: pytest.fail("must not execute"))
    args = {"project": str(project[0]), "output": str(project[1])}

    async def changed(tool, args):
        (project[1] / "appeared").touch()
        return True

    assert not asyncio.run(registry.execute("build_python_wheel", args, confirm=changed)).ok
    (project[1] / "appeared").unlink()

    async def stopped(tool, args):
        SecurityStore().set_stop(True)
        return True

    assert not asyncio.run(registry.execute("build_python_wheel", args, confirm=stopped)).ok
