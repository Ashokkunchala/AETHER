#!/usr/bin/env python3
"""Verify the AETHER mobile TLS certificate and HTTPS backend.

Modes:

local
    Inspect the certificate file on disk: loadable, CA:TRUE (so the phone can
    install it as a user CA), valid for at least 7 more days, and the
    subjectAltName covers ``--host`` (the LAN IP the phone will dial).

endpoint
    Dial the running uvicorn HTTPS backend with the certificate file loaded as
    the trusted CA - this proves both the certificate chain and hostname
    verification - then assert the served certificate is byte-identical to the
    file on disk, and GET ``/health`` must return JSON ``{"status": "ok"}``.

Used by ``scripts\\verify-mobile-common.ps1`` (local mode) and
``scripts\\https-smoke-test.ps1`` (endpoint mode).

Usage:
    python scripts/verify_tls.py --mode local --host 192.168.1.61
    python scripts/verify_tls.py --mode endpoint --host 192.168.1.61 --port 8443

Exit codes: 0 = all checks passed, 1 = a check failed, 2 = usage/dependency error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
except ImportError:  # pragma: no cover - cryptography is a hard dependency
    sys.stderr.write(
        "The 'cryptography' package is required. Install dependencies first:\n"
        "  .venv\\Scripts\\python -m pip install -r requirements.txt\n"
    )
    raise SystemExit(2) from None

# Keep in sync with scripts/generate_https_cert.py (Android user-CA limit).
MIN_VALIDITY_DAYS = 7
DEFAULT_CERT = Path(__file__).resolve().parent.parent / "data" / "tls" / "cert.pem"
DEFAULT_TIMEOUT_SECONDS = 5.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the AETHER mobile TLS certificate and HTTPS backend.",
    )
    parser.add_argument(
        "--mode",
        choices=("local", "endpoint"),
        default="endpoint",
        help="local: inspect the cert file only. endpoint: also dial the backend.",
    )
    parser.add_argument(
        "--host",
        required=True,
        metavar="ADDRESS",
        help="LAN IP address (or DNS name) the certificate must cover.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8443,
        help="HTTPS port for --mode endpoint (default 8443).",
    )
    parser.add_argument(
        "--cert",
        type=Path,
        default=DEFAULT_CERT,
        help=f"Certificate PEM to verify (default {DEFAULT_CERT}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Socket/HTTP timeout in seconds (default {DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    return parser.parse_args(argv)


def _pass(message: str) -> None:
    print(f"[PASS] {message}")


def _load_cert(cert_path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(cert_path.read_bytes())


def cert_covers_host(cert: x509.Certificate, host: str) -> bool:
    """True when the certificate's subjectAltName matches ``host``."""
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False
    ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    dns = {name.lower() for name in san.get_values_for_type(x509.DNSName)}
    try:
        return str(ipaddress.ip_address(host)) in ips
    except ValueError:
        return host.lower() in dns


def check_local(cert_path: Path, host: str) -> list[str]:
    """Run the on-disk certificate checks; return a list of failures."""
    errors: list[str] = []

    if not cert_path.is_file():
        return [f"certificate file missing: {cert_path}"]
    try:
        cert = _load_cert(cert_path)
    except ValueError as exc:
        return [f"cannot parse {cert_path}: {exc}"]

    try:
        is_ca = cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    except x509.ExtensionNotFound:
        is_ca = False
    if is_ca:
        _pass("basicConstraints CA:TRUE (installable as a phone CA certificate)")
    else:
        errors.append("certificate is not a CA; regenerate with generate_https_cert.py")

    now = dt.datetime.now(dt.UTC)
    not_after = getattr(cert, "not_valid_after_utc", None)
    if not_after is None:  # cryptography < 42
        not_after = cert.not_valid_after.replace(tzinfo=dt.UTC)
    remaining = not_after - now
    if remaining < dt.timedelta(days=MIN_VALIDITY_DAYS):
        errors.append(
            f"certificate expires in {remaining.days}d "
            f"({not_after:%Y-%m-%d}); needs >= {MIN_VALIDITY_DAYS}d"
        )
    else:
        _pass(f"validity: {remaining.days}d remaining (until {not_after:%Y-%m-%d})")

    if cert_covers_host(cert, host):
        _pass(f"subjectAltName covers {host}")
    else:
        errors.append(f"subjectAltName does not cover {host}; rerun with --force cert generation")

    return errors


def check_endpoint(host: str, port: int, cert_path: Path, timeout: float) -> list[str]:
    """Verify the live HTTPS backend: chain, hostname, served cert, /health."""
    errors = check_local(cert_path, host)
    if errors:
        return errors

    # Trust exactly our certificate file as the CA: the backend must present
    # this certificate (chain + hostname verified by OpenSSL), which is stronger
    # than skipping verification and comparing bytes alone.
    context = ssl.create_default_context()
    try:
        context.load_verify_locations(cafile=str(cert_path))
    except ssl.SSLError as exc:
        return [f"cannot load CA file {cert_path}: {exc}"]

    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                served_der = tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as exc:
        return [f"TLS handshake to {host}:{port} failed: {exc}"]
    _pass(f"TLS handshake + chain + hostname verified against {cert_path.name}")

    expected_der = _load_cert(cert_path).public_bytes(serialization.Encoding.DER)
    if served_der != expected_der:
        errors.append(
            f"backend at {host}:{port} serves a different certificate than {cert_path}"
        )
    else:
        _pass("served certificate is byte-identical to the file on disk")

    url = f"https://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, context=context, timeout=timeout) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return errors + [f"GET {url} failed: {exc}"]
    if status_code != 200:
        errors.append(f"GET {url} returned HTTP {status_code}, expected 200")
    elif payload.get("status") != "ok":
        errors.append(f"GET {url} returned {payload!r}, expected {{'status': 'ok'}}")
    else:
        _pass(f"GET {url} -> 200 {json.dumps(payload)}")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.port <= 65535:
        sys.stderr.write("--port must be between 1 and 65535.\n")
        return 2
    if args.timeout <= 0:
        sys.stderr.write("--timeout must be positive.\n")
        return 2

    cert_path = args.cert.expanduser().resolve()
    if args.mode == "local":
        errors = check_local(cert_path, args.host)
    else:
        errors = check_endpoint(args.host, args.port, cert_path, args.timeout)

    if errors:
        for message in errors:
            print(f"[FAIL] {message}", file=sys.stderr)
        return 1
    print(f"TLS verification passed ({args.mode} mode).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
