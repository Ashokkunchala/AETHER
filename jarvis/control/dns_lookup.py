"""Fresh-reviewed one-name OS resolver lookup, not connectivity or DNS authenticity."""

from __future__ import annotations

import ipaddress
import queue
import re
import socket
import threading
from datetime import UTC, datetime

_GATE = threading.Lock()


def _name(hostname):
    if (
        not isinstance(hostname, str)
        or not 4 <= len(hostname) <= 254
        or not hostname.isascii()
        or not hostname.endswith(".")
    ):
        raise ValueError(
            "Supply an explicit lowercase ASCII absolute dotted hostname ending in a dot."
        )
    name = hostname[:-1]
    labels = name.split(".")
    if len(labels) < 2 or all(part.isdigit() for part in labels):
        raise ValueError("Dotted hostname required, not an IP address or single-label search name.")
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in labels):
        raise ValueError(
            "Each label must be lowercase ASCII letters/digits/hyphens with no edge hyphen."
        )
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return hostname
    raise ValueError("Use a hostname, not an IP address.")


def preview_dns_lookup(hostname: str, wait_seconds: int = 5):
    try:
        exact = _name(hostname)
        if type(wait_seconds) is not int or not 1 <= wait_seconds <= 15:
            raise ValueError("Wait must be an integer1-15seconds.")
    except ValueError:
        return {
            "success": False,
            "error": "Use one explicit lowercase ASCII dotted absolute hostname ending in a dot, no URL/IP/wildcards/ports/path/credentials; wait_seconds integer1-15. No lookup started.",
        }
    return {
        "success": True,
        "hostname": exact,
        "wait_seconds": wait_seconds,
        "operation": "socket.getaddrinfo(exact-hostname, None, AF_UNSPEC, SOCK_STREAM, IPPROTO_TCP, 0)",
        "application_connection_attempted": False,
        "notice": (
            "Fresh approval for this exact OS name-resolution request and result disclosure only. "
            "The name may be private and may be sent to configured DNS/VPN/mDNS/OS resolver infrastructure; "
            "addresses/name/status can enter configured assistant/model context. Resolver settings, caches, "
            "hosts files, plugins and split DNS can affect the result. One getaddrinfo call may cause "
            "multiple DNS/network packets or internal retries; this is not one-packet or authoritative "
            "DNS querying. A trailing dot requests an absolute name, not resolver authenticity/security. "
            "No chosen DNS server, DNSSEC verification, TTL/record provenance, reverse lookup, port "
            "connection, HTTP request, ping, speed test, routing/health check or configuration change. "
            "Wait timeout only stops waiting: the OS resolver operation cannot be cancelled here and "
            "may finish later. One outstanding lookup blocks further lookups in this process until it "
            "actually exits. Emergency stop blocks dispatch but cannot undo/cancel a running resolver. "
            "No automatic wrapper retry or monitor. Up to 20 unique supported address records are returned; "
            "an IP address is not identity, public accessibility, connectivity, ownership or safety proof."
        ),
    }


def _result(rows):
    if not isinstance(rows, list):
        raise ValueError("Unsupported resolver records.")
    seen, addresses = set(), []
    scanned_partial = len(rows) > 500
    for row in rows[:500]:
        if not isinstance(row, tuple) or len(row) != 5:
            raise ValueError("Unsupported resolver record.")
        family, socktype, proto, _canonical, sockaddr = row
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        if socktype != socket.SOCK_STREAM or proto not in (socket.IPPROTO_TCP, 0):
            continue
        if not isinstance(sockaddr, tuple) or len(sockaddr) != (
            2 if family == socket.AF_INET else 4
        ):
            raise ValueError("Unsupported address tuple.")
        value = sockaddr[0]
        if not isinstance(value, str) or "%" in value:
            raise ValueError("Unsupported scoped address text.")
        address = ipaddress.ip_address(value)
        if address.version != (4 if family == socket.AF_INET else 6):
            raise ValueError("Address family mismatch.")
        scope_omitted = False
        if family == socket.AF_INET6:
            if type(sockaddr[3]) is not int or sockaddr[3] < 0:
                raise ValueError("Unsupported scope identifier.")
            scope_omitted = sockaddr[3] != 0
        key = (str(address), scope_omitted)
        if key not in seen:
            seen.add(key)
            addresses.append(
                {
                    "address": str(address),
                    "family": "IPv4" if address.version == 4 else "IPv6",
                    "scope_identifier_omitted": scope_omitted,
                }
            )
    return addresses[:20], scanned_partial or len(addresses) > 20


def lookup_dns(hostname: str, wait_seconds: int = 5):
    preview = preview_dns_lookup(hostname, wait_seconds)
    if not preview.get("success"):
        return preview
    common = {
        "hostname": hostname,
        "as_of": datetime.now(UTC).isoformat(),
        "source": "Local operating-system getaddrinfo result, not verified authoritative DNS",
        "connectivity_verified": False,
        "dns_authenticity_verified": False,
        "automatic_wrapper_retry": False,
        "application_connection_attempted": False,
        "notice": "Names/addresses may be private. Resolver/hosts/cache/VPN behavior is not verified. No service identity, safety, current global DNS, availability or connectivity claim. IPv6 scope identifiers are omitted and scoped addresses are not directly usable as returned.",
    }
    gate = _GATE
    if not gate.acquire(blocking=False):
        return {
            **common,
            "success": False,
            "error": "An earlier resolver call is still outstanding in this process; no new lookup started.",
        }
    results = queue.Queue(maxsize=1)

    def work():
        try:
            rows = socket.getaddrinfo(
                hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP, 0
            )
            addresses, partial = _result(rows)
            result = ("ok", addresses, partial)
        except Exception:
            # Never reflect resolver exception strings/canonical names or raw malformed records.
            result = ("error", None, None)
        finally:
            gate.release()
        results.put(result)

    try:
        thread = threading.Thread(target=work, name="aether-one-name-lookup", daemon=True)
        thread.start()
    except Exception:
        gate.release()
        return {
            **common,
            "success": False,
            "error": "Resolver worker could not start; no lookup completion claimed.",
        }
    try:
        kind, addresses, partial = results.get(timeout=wait_seconds)
    except queue.Empty:
        return {
            **common,
            "success": False,
            "wait_timed_out": True,
            "resolver_completion_verified": False,
            "error": "Stopped waiting, not resolver cancellation. OS lookup may still run; no new lookup in this process until it exits. No retry or monitor.",
        }
    if kind != "ok":
        return {
            **common,
            "success": False,
            "wait_timed_out": False,
            "resolver_completion_verified": True,
            "error": "OS lookup failed or returned unsupported data. Failure reason omitted; not proof the name does not exist or the network/service is down.",
        }
    return {
        **common,
        "success": True,
        "wait_timed_out": False,
        "resolver_completion_verified": True,
        "addresses": addresses,
        "returned_address_records": len(addresses),
        "partial": partial,
        "outcome": "OS resolver call completed; bounded supported address records only, not connection/health proof. Empty results are not a DNS-nonexistence conclusion.",
    }


def register_dns_lookup(registry):
    from jarvis.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="lookup_dns_name",
            description="Fresh-reviewed one exact lowercase ASCII dotted absolute hostname lookup through OS getaddrinfo. No port connection/health/authenticity claim. Can disclose private names to resolver and results to assistant; timeout stops waiting, not OS cancellation.",
            parameters={
                "type": "object",
                "properties": {
                    "hostname": {"type": "string", "maxLength": 254},
                    "wait_seconds": {"type": "integer", "minimum": 1, "maximum": 15},
                },
                "required": ["hostname"],
                "additionalProperties": False,
            },
            handler=lookup_dns,
            confirmation_preview=preview_dns_lookup,
            risk=Risk.LOW,
            category="network",
            requires_confirmation=True,
            never_auto_approve=True,
            allow_auto_approve=False,
            allow_always=False,
        )
    )


# Only synthetic resolver calls are used by development tests.
