"""Dedicated remote-read HTTPS app. No general agent, proxy, shell or pairing API.

Importing/building the ASGI app does not open a socket or load a private key.
The optional launcher requires an interactive exact network-exposure review.
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import re
import ssl
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from windows_agent.remote_read_api import router


_ROUTE = re.compile(r'^/v1/remote-read/requests(?:/[0-9a-f]{32}(?:/cancel)?)?$')


def exact_host(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 253 or value != value.lower():
        raise ValueError('Exact lowercase certificate hostname or IPv4 required.')
    if any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in value):
        raise ValueError('Host only, no scheme, port, path or wildcard.')
    try:
        address = ipaddress.ip_address(value)
        if address.version != 4:
            raise ValueError('IPv4 only.')
        return str(address)
    except ValueError:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+', value) or all(c.isdigit() or c == '.' for c in value):
            raise ValueError('Exact lowercase DNS hostname or IPv4 required.') from None
        return value


async def _refuse(send, status):
    data = b'{"detail":"Request refused by dedicated read-only listener."}'
    await send({'type': 'http.response.start', 'status': status, 'headers': [(b'content-type', b'application/json'), (b'cache-control', b'no-store'), (b'content-length', str(len(data)).encode())]})
    await send({'type': 'http.response.body', 'body': data})


class Boundary:
    """Small closed HTTP surface, bounded body and fixed global rate budget.

    The budget is intentionally global, not an unbounded per-IP/token cache.
    It is a best-effort single-process limit, not network DoS protection.
    """
    def __init__(self, app, host, clock=time.monotonic):
        self.app, self.host, self.clock = app, host, clock
        self.start, self.count = clock(), 0
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            if scope['type'] == 'websocket':
                await send({'type': 'websocket.close', 'code': 1008})
                return
            await self.app(scope, receive, send)
            return
        # No trusted proxy: scheme must be TLS, and host must be one exact value.
        headers = scope.get('headers', [])
        hosts = [v for k, v in headers if k.lower() == b'host']
        allowed = {self.host.encode(), (self.host + ':443').encode()}
        path, method = scope.get('path', ''), scope.get('method', '')
        valid_path = len(path) <= 100 and _ROUTE.fullmatch(path) is not None
        valid_method = (method == 'POST' and (path == '/v1/remote-read/requests' or path.endswith('/cancel'))) or (method == 'GET' and re.fullmatch(r'/v1/remote-read/requests/[0-9a-f]{32}', path) is not None)
        if scope.get('scheme') != 'https' or len(hosts) != 1 or hosts[0] not in allowed or scope.get('query_string') or not valid_path or not valid_method:
            await _refuse(send, 404)
            return
        with self.lock:
            now = self.clock()
            if now - self.start >= 60:
                self.start, self.count = now, 0
            self.count += 1
            limited = self.count > 120
        if limited:
            await _refuse(send, 429)
            return
        # Header limits bound parser-facing metadata here, not TCP/TLS itself.
        if len(headers) > 40 or sum(len(k) + len(v) for k, v in headers) > 8192:
            await _refuse(send, 431)
            return
        auth = [v for k, v in headers if k.lower() == b'authorization']
        lengths = [v for k, v in headers if k.lower() == b'content-length']
        types = [v for k, v in headers if k.lower() == b'content-type']
        if len(auth) != 1 or not auth[0].startswith(b'Bearer ') or not 39 <= len(auth[0]) <= 263 or any(k.lower() in (b'transfer-encoding', b'content-encoding', b'origin') for k, v in headers):
            await _refuse(send, 400)
            return
        if method == 'POST':
            if len(lengths) != 1 or not re.fullmatch(rb'[0-9]{1,3}', lengths[0]) or not 1 <= int(lengths[0]) <= 256 or len(types) != 1 or types[0].split(b';')[0].strip().lower() != b'application/json':
                await _refuse(send, 400)
                return
            expected = int(lengths[0])
        else:
            if lengths not in ([], [b'0']):
                await _refuse(send, 400)
                return
            expected = 0
        body = bytearray()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5
        while True:
            try:
                item = await asyncio.wait_for(receive(), timeout=max(0, deadline - loop.time()))
            except asyncio.TimeoutError:
                await _refuse(send, 408)
                return
            if item['type'] == 'http.disconnect':
                return
            if item['type'] != 'http.request':
                await _refuse(send, 400)
                return
            part = item.get('body', b'')
            if len(body) + len(part) > expected:
                await _refuse(send, 413)
                return
            body.extend(part)
            if not item.get('more_body', False):
                break
        if len(body) != expected:
            await _refuse(send, 400)
            return
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return {'type': 'http.disconnect'}
        async def private_send(message):
            if message['type'] == 'http.response.start':
                message = {**message, 'headers': list(message.get('headers', [])) + [(b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]}
            await send(message)
        await self.app(scope, bounded_receive, private_send)


def make_app(host):
    host = exact_host(host)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
    app.include_router(router)
    # Boundary handles Host strictly, including duplicate headers; framework host
    # validation is defense in depth, not authority for proxy forwarding.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[host], www_redirect=False)
    return Boundary(app, host)


def launch_plan(bind, host, cert, key):
    """Validate explicit offline configuration. No bind, DNS or network request."""
    host = exact_host(host)
    address = ipaddress.IPv4Address(bind)
    private = any(address in ipaddress.IPv4Network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    if not private:
        raise ValueError('Bind must be an exact RFC1918 private IPv4, not wildcard/public/loopback.')
    cert, key = Path(cert), Path(key)
    if cert.is_symlink() or key.is_symlink() or not cert.is_file() or not key.is_file() or cert.stat().st_size > 65536 or key.stat().st_size > 65536:
        raise ValueError('Existing reviewed bounded certificate/key files required, not direct links.')
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa, ec
    from cryptography.x509.oid import ExtendedKeyUsageOID
    from datetime import datetime, timedelta, timezone
    certificate = x509.load_pem_x509_certificate(cert.read_bytes())
    now = datetime.now(timezone.utc)
    if not certificate.not_valid_before_utc <= now or certificate.not_valid_after_utc < now + timedelta(days=7):
        raise ValueError('Certificate not currently valid for at least seven more days.')
    if certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise ValueError('Serve a leaf certificate, never a CA certificate/private key.')
    if ExtendedKeyUsageOID.SERVER_AUTH not in certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
        raise ValueError('Explicit server-auth certificate required.')
    public = certificate.public_key()
    if not ((isinstance(public, rsa.RSAPublicKey) and public.key_size >= 2048) or (isinstance(public, ec.EllipticCurvePublicKey) and public.key_size >= 256)) or certificate.signature_hash_algorithm is None or certificate.signature_hash_algorithm.digest_size < 32:
        raise ValueError('Reviewed strong RSA/EC leaf and SHA256-or-stronger signature required.')
    names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    try:
        desired = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        covered = host in names.get_values_for_type(x509.DNSName)
    else:
        covered = desired in names.get_values_for_type(x509.IPAddress)
        if str(desired) != str(address):
            raise ValueError('IP certificate hostname must equal the exact bind address.')
    if not covered:
        raise ValueError('Certificate SAN must cover exact host, no wildcard matching.')
    # Checks PEM key loads and matches cert. Never print or return key bytes.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(cert), str(key), password=lambda: b'')
    return {'bind': str(address), 'host': host, 'port': 443, 'certificate_sha256': certificate.fingerprint(hashes.SHA256()).hex(), 'certificate_expires_utc': certificate.not_valid_after_utc.isoformat(), 'notice': 'Separate minimal HTTPS listener only. No firewall, certificate installation, pairing, startup registration, proxy or general agent is configured. Existing per-device tokens and laptop-local approval still required. Phone trust, DNS/network reachability and actual acceptance are not verified. New listener exposes the inert queue/status/cancel protocol to devices able to reach this private address; TLS/token/OS trust are required. No arbitrary remote command exists.'}


def main():
    parser = argparse.ArgumentParser(description='AETHER separately reviewed private HTTPS remote-read listener, no general agent')
    parser.add_argument('--bind', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--cert', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--serve', action='store_true', help='After offline validation, require exact interactive exposure approval')
    args = parser.parse_args()
    from cryptography.x509 import ExtensionNotFound
    from cryptography.exceptions import UnsupportedAlgorithm
    try:
        plan = launch_plan(args.bind, args.host, args.cert, args.key)
        print(json.dumps(plan, indent=2))
        if not args.serve:
            return
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError('Network launch requires interactive owner terminal.')
        phrase = 'EXPOSE READ-ONLY ' + plan['bind'] + ':443'
        if input('Type ' + phrase + ' only after separately approving network exposure: ') != phrase:
            raise ValueError('Launch cancelled.')
        # Revalidate after review, but files/OS remain owner trust, not a sandbox.
        current = launch_plan(args.bind, args.host, args.cert, args.key)
        if current != plan:
            raise ValueError('TLS configuration changed during review.')
        import uvicorn
        uvicorn.run(make_app(plan['host']), host=plan['bind'], port=443, ssl_certfile=args.cert, ssl_keyfile=args.key, ssl_keyfile_password='', ssl_version=ssl.PROTOCOL_TLS_SERVER, workers=1, proxy_headers=False, server_header=False, access_log=False, limit_concurrency=16, backlog=32, timeout_keep_alive=5, h11_max_incomplete_event_size=8192, log_level='warning')
    except (ValueError, OSError, RuntimeError, ssl.SSLError, ExtensionNotFound, UnsupportedAlgorithm):
        raise SystemExit('Dedicated listener refused or stopped. No successful network launch or device acceptance is claimed. Review local configuration privately; do not bypass TLS or expose the general agent.') from None


if __name__ == '__main__':
    main()
