#!/usr/bin/env python3
"""Generate the self-signed TLS certificate used by the mobile HTTPS backend.

The Android app refuses cleartext HTTP (``usesCleartextTraffic="false"``) and
requires an ``https://`` backend for chat, pairing and Live Voice (``wss://``).
For a personal LAN setup there is no public CA, so this script creates a
self-signed certificate that is:

* a CA (basicConstraints CA:TRUE) so the phone can install it as a user
  trusted CA (Settings > Security > Install certificate > CA certificate);
* a server certificate (extendedKeyUsage serverAuth) so uvicorn can serve
  with it directly;
* stamped with every requested IP/DNS subjectAltName so Android hostname
  verification passes when the phone connects to ``https://<lan-ip>:8443``.

The generation is idempotent: an existing certificate is reused when it is
still valid for at least 7 days and already covers every requested name,
so routine restarts never invalidate the CA the phone trusts. When the
machine's DHCP address changes, the certificate is regenerated and the
phone must reinstall the CA (the caller prints that warning).

Usage:
    python scripts/generate_https_cert.py --out-dir data/tls --ip 192.168.1.20
    python scripts/generate_https_cert.py --out-dir data/tls --ip 10.0.0.5 --hostname MYPC --force

Outputs (in --out-dir):
    cert.pem  - PEM certificate (also copied to aether-ca.crt for phone install)
    key.pem   - PEM private key (0600 where the OS supports it)
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
import sys
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
except ImportError:  # pragma: no cover - cryptography is a hard dependency
    sys.stderr.write(
        "The 'cryptography' package is required. Install dependencies first:\n"
        "  .venv\\Scripts\\python -m pip install -r requirements.txt\n"
    )
    raise SystemExit(2) from None

MIN_VALIDITY_DAYS = 7
DEFAULT_VALIDITY_DAYS = 825  # Android rejects user CAs valid longer than ~825d
KEY_SIZE = 2048


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or refresh the self-signed HTTPS certificate "
        "for the AETHER mobile backend.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Directory for cert.pem / key.pem (created if missing).",
    )
    parser.add_argument(
        "--ip",
        action="append",
        default=[],
        metavar="ADDRESS",
        help="IP address to add as a subjectAltName (repeatable).",
    )
    parser.add_argument(
        "--hostname",
        action="append",
        default=[],
        metavar="NAME",
        help="DNS name to add as a subjectAltName (repeatable).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_VALIDITY_DAYS,
        help=f"Validity in days (default {DEFAULT_VALIDITY_DAYS}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when the existing certificate is still usable.",
    )
    return parser.parse_args(argv)


def _load_existing(cert_path: Path) -> x509.Certificate | None:
    if not cert_path.is_file():
        return None
    try:
        return x509.load_pem_x509_certificate(cert_path.read_bytes())
    except (ValueError, OSError):
        return None


def _cert_is_usable(
    cert: x509.Certificate,
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    hostnames: list[str],
) -> bool:
    """True when the cert is a CA, still fresh, and covers every requested name."""
    try:
        if not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            return False
    except x509.ExtensionNotFound:
        return False

    now = dt.datetime.now(dt.UTC)
    # cryptography >= 42 exposes aware datetimes; fall back for older versions.
    not_after = getattr(cert, "not_valid_after_utc", None)
    if not_after is None:
        not_after = cert.not_valid_after.replace(tzinfo=dt.UTC)
    if not_after - now < dt.timedelta(days=MIN_VALIDITY_DAYS):
        return False

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return False

    have_ips = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
    have_dns = {name.lower() for name in san.get_values_for_type(x509.DNSName)}
    if any(str(ip) not in have_ips for ip in ips):
        return False
    if any(name.lower() not in have_dns for name in hostnames):
        return False
    return True


def _build_certificate(
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    hostnames: list[str],
    days: int,
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
    now = dt.datetime.now(dt.UTC)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "AETHER Local HTTPS"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AETHER Personal AI (local only)"),
        ]
    )

    san_entries: list[x509.GeneralName] = [
        x509.IPAddress(ip) for ip in ips
    ] + [x509.DNSName(name) for name in hostnames]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)  # self-signed
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(
            # CA:TRUE so Android can install this file as a user CA certificate.
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=True,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _write_files(
    out_dir: Path,
    key: rsa.RSAPrivateKey,
    cert: x509.Certificate,
) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    cert_path = out_dir / "cert.pem"
    key_path = out_dir / "key.pem"
    ca_copy = out_dir / "aether-ca.crt"

    cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
    key_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_path.write_bytes(cert_bytes)
    key_path.write_bytes(key_bytes)
    ca_copy.write_bytes(cert_bytes)  # same file, phone-friendly name/extension

    # Restrict the key to the current user where the OS honours it (POSIX).
    if os.name == "posix":
        try:
            os.chmod(key_path, 0o600)
        except OSError:  # pragma: no cover - best effort
            pass

    return cert_path, key_path, ca_copy


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        ips = [ipaddress.ip_address(value) for value in args.ip]
    except ValueError as exc:
        sys.stderr.write(f"Invalid --ip value: {exc}\n")
        return 2

    hostnames = [name.strip() for name in args.hostname if name.strip()]
    if not ips and not hostnames:
        sys.stderr.write("At least one --ip or --hostname is required.\n")
        return 2
    if args.days < 30:
        sys.stderr.write("--days must be at least 30.\n")
        return 2

    out_dir: Path = args.out_dir
    cert_path = out_dir / "cert.pem"
    key_path = out_dir / "key.pem"

    existing = _load_existing(cert_path)
    if (
        not args.force
        and existing is not None
        and key_path.is_file()
        and _cert_is_usable(existing, ips, hostnames)
    ):
        not_after = getattr(existing, "not_valid_after_utc", None)
        if not_after is None:
            not_after = existing.not_valid_after.replace(tzinfo=dt.UTC)
        print(f"Reusing existing certificate: {cert_path}")
        print(f"Valid until: {not_after:%Y-%m-%d %H:%M %Z}")
        print(f"Install on phone: {out_dir / 'aether-ca.crt'}")
        return 0

    key, cert = _build_certificate(ips, hostnames, args.days)
    cert_path, key_path, ca_copy = _write_files(out_dir, key, cert)

    names = ", ".join([str(ip) for ip in ips] + hostnames)
    print(f"Generated new certificate: {cert_path}")
    print(f"Private key:               {key_path}")
    print(f"Phone install copy:        {ca_copy}")
    print(f"SubjectAltName:            {names}")
    print(f"Valid for {args.days} days (CA + serverAuth).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
