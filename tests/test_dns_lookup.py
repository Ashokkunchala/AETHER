import asyncio
import socket
import threading

import pytest

from jarvis.control import dns_lookup as mod


def record(address="192.0.2.1", family=socket.AF_INET, scope=0):
    return (
        family,
        socket.SOCK_STREAM,
        socket.IPPROTO_TCP,
        "PRIVATE_CANONICAL",
        (address, 0) if family == socket.AF_INET else (address, 0, 0, scope),
    )


@pytest.fixture(autouse=True)
def isolated_gate(monkeypatch):
    monkeypatch.setattr(mod, "_GATE", threading.Lock())


def test_preview_no_resolution_and_exact_risks(monkeypatch):
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a: pytest.fail("no lookup in preview"))
    result = mod.preview_dns_lookup("example.test.")
    assert result["success"] and result["hostname"] == "example.test."
    for phrase in [
        "private",
        "multiple DNS",
        "cannot be cancelled",
        "One outstanding",
        "No automatic",
        "not identity",
    ]:
        assert phrase in result["notice"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        "",
        "example",
        "example.test",
        "EXAMPLE.test.",
        "https://example.test.",
        "example.test.:80",
        "user@example.test.",
        "*.example.test.",
        "_srv.example.test.",
        "-bad.test.",
        "bad-.test.",
        "a..test.",
        "192.0.2.1.",
        "127.0.0.1.",
        "[::1].",
        "localhost.",
        "అ.example.",
        "bad\n.test.",
        "a" * 64 + ".test.",
        "a." * 128,
    ],
)
def test_bad_hostname_never_resolved(value, monkeypatch):
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a: pytest.fail("no invalid lookup"))
    assert not mod.lookup_dns(value)["success"]


@pytest.mark.parametrize("wait", [None, True, 0, 16, 1.0, "5"])
def test_wait_strict(wait):
    assert not mod.preview_dns_lookup("example.test.", wait)["success"]


def test_exact_resolver_call_dedup_canonical_omission(monkeypatch):
    calls = []

    def fake(*args):
        calls.append(args)
        return [
            record(),
            record(),
            record("2001:db8::1", socket.AF_INET6),
            record("fe80::1", socket.AF_INET6, 3),
        ]

    monkeypatch.setattr(mod.socket, "getaddrinfo", fake)
    result = mod.lookup_dns("example.test.")
    assert calls == [
        ("example.test.", None, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP, 0)
    ]
    assert result["success"] and result["returned_address_records"] == 3
    assert (
        not result["partial"]
        and not result["connectivity_verified"]
        and not result["dns_authenticity_verified"]
    )
    assert result["addresses"][2]["scope_identifier_omitted"]
    assert "PRIVATE_CANONICAL" not in str(result)
    assert not mod._GATE.locked()


def test_bound_unique_addresses_and_scan_limit(monkeypatch):
    monkeypatch.setattr(
        mod.socket, "getaddrinfo", lambda *a: [record(f"192.0.2.{i}") for i in range(1, 31)]
    )
    result = mod.lookup_dns("example.test.")
    assert result["returned_address_records"] == 20 and result["partial"]
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a: [record()] * 501)
    assert mod.lookup_dns("example.test.")["partial"]


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [()],
        [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("bad", 0))],
        [record("2001:db8::1")],
        [record("fe80::1%3", socket.AF_INET6)],
        [(socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("fe80::1", 0, 0, "3"))],
    ],
)
def test_malformed_no_raw_exception_or_partial_success(rows, monkeypatch):
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a: rows)
    result = mod.lookup_dns("example.test.")
    assert not result["success"] and result["resolver_completion_verified"]
    assert "addresses" not in result and not mod._GATE.locked()


def test_error_not_nxdomain_or_outage_claim(monkeypatch):
    def fake(*a):
        raise socket.gaierror("PRIVATE_RESOLVER_ERROR")

    monkeypatch.setattr(mod.socket, "getaddrinfo", fake)
    result = mod.lookup_dns("example.test.")
    assert not result["success"] and "PRIVATE_RESOLVER_ERROR" not in str(result)
    assert "not proof" in result["error"] and not mod._GATE.locked()


def test_empty_supported_results_not_name_nonexistence(monkeypatch):
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a: [])
    result = mod.lookup_dns("example.test.")
    assert (
        result["success"]
        and result["addresses"] == []
        and "not a DNS-nonexistence" in result["outcome"]
    )


def test_timeout_outstanding_gate_and_no_retry(monkeypatch):
    done = threading.Event()
    entered = threading.Event()
    exited = threading.Event()
    calls = []

    def fake(*a):
        calls.append(a)
        entered.set()
        done.wait(5)
        exited.set()
        return [record()]

    monkeypatch.setattr(mod.socket, "getaddrinfo", fake)
    try:
        result = mod.lookup_dns("example.test.", 1)
        assert entered.is_set() and not result["success"] and result["wait_timed_out"]
        assert not result["resolver_completion_verified"] and not result["automatic_wrapper_retry"]
        assert not mod.lookup_dns("other.test.", 1)["success"] and len(calls) == 1
    finally:
        done.set()
        assert exited.wait(2)
        assert mod._GATE.acquire(timeout=2)
        mod._GATE.release()


def test_worker_start_failure_releases_gate(monkeypatch):
    class Broken:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise RuntimeError("PRIVATE_START_ERROR")

    monkeypatch.setattr(mod.threading, "Thread", Broken)
    result = mod.lookup_dns("example.test.")
    assert (
        not result["success"]
        and not mod._GATE.locked()
        and "PRIVATE_START_ERROR" not in str(result)
    )


def test_registry_fresh_review_and_stop(tmp_path, monkeypatch):
    from jarvis.tools.builtin_tools import build_registry
    from jarvis.security import SecurityStore

    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    calls = []
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a: calls.append(a) or [record()])
    registry = build_registry(force=True)
    tool = registry.tools["lookup_dns_name"]
    assert (
        tool.confirm_required
        and tool.never_auto_approve
        and not tool.allow_always
        and not tool.allow_auto_approve
    )
    args = {"hostname": "example.test."}
    assert not asyncio.run(registry.execute(tool.name, args, auto_approve=True)).ok

    async def deny(*a):
        return False

    assert not asyncio.run(registry.execute(tool.name, args, confirm=deny)).ok
    previews = []

    async def approve(t, a):
        previews.append(a["_preview"])
        return True

    assert asyncio.run(registry.execute(tool.name, args, confirm=approve)).ok
    assert len(calls) == 1 and previews[0]["hostname"] == "example.test."

    async def stop(t, a):
        SecurityStore().set_stop(True)
        return True

    assert not asyncio.run(registry.execute(tool.name, args, confirm=stop)).ok
    assert len(calls) == 1
