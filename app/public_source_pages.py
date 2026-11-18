"""Cookie-free, DNS-pinned HTTPS source reading for user-selected comparisons."""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.personal_data import require_device_token
from aether.tools.net.web_tools import _TextExtractor

router = APIRouter(prefix='/pages', dependencies=[Depends(require_device_token)])
MAX_BYTES = 1_000_000
MAX_TEXT = 12000


def _public_address(address):
    ip = ipaddress.ip_address(address)
    if not ip.is_global or ip.is_reserved or ip.is_multicast or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Reject transition/tunnel ranges that could hide an embedded private IPv4 target.
        if ip.is_site_local or ip.ipv4_mapped or ip.sixtofour or ip.teredo or ip in ipaddress.ip_network('64:ff9b::/96') or ip in ipaddress.ip_network('64:ff9b:1::/48'):
            return False
    return True


def public_target(url):
    if not url or len(url) > 2000 or any(ord(c) < 33 for c in url) or '\\' in url:
        raise ValueError('Use an ordinary public HTTPS page URL.')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Only public HTTPS pages on port 443 without embedded credentials are supported.')
    if any(re.search(r'(?:token|password|secret|signature|credential|api.?key|^auth$|^code$|^sig$)', key, re.I) for key, _ in parse_qsl(parsed.query)):
        raise ValueError('Signed or credential-bearing query URLs are not supported.')
    host = parsed.hostname.encode('idna').decode('ascii')
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses or any(not _public_address(address) for address in addresses):
        raise ValueError('Private, loopback, reserved and mixed public/private network targets are refused.')
    normalized = urlunsplit(('https', '['+host+']' if ':' in host else host, parsed.path or '/', parsed.query, ''))
    return normalized, host, addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, port=443, timeout=8, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the checked numeric address, never resolve the hostname again.
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def read_source(url):
    requested = url
    deadline = time.monotonic() + 15
    for hop in range(4):
        url, host, address = public_target(url)
        if time.monotonic() >= deadline:
            raise TimeoutError('Source read time budget exceeded.')
        parsed = urlsplit(url)
        connection = PinnedHTTPS(host, address)
        try:
            connection.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')),
                               headers={'Accept':'text/html,text/plain,application/xhtml+xml',
                                        'Accept-Encoding':'identity', 'User-Agent':'AETHER-SourceReader/1.0'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if hop == 3 or not location:
                    raise ValueError('Too many redirects or a redirect has no destination.')
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError('The source page did not return readable content.')
            content_type = response.getheader('Content-Type', '').split(';', 1)[0].strip().lower()
            if content_type not in ('text/html', 'application/xhtml+xml', 'text/plain'):
                raise ValueError('Only HTML and plain-text source pages are supported.')
            if response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise ValueError('Compressed source responses are not supported.')
            chunks, size = [], 0
            while size <= MAX_BYTES:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Source read time budget exceeded.')
                chunk = response.read(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            raw = b''.join(chunks)
            decoded = raw[:MAX_BYTES].decode('utf-8', errors='replace')
            if content_type == 'text/plain':
                text, title, partial = decoded[:MAX_TEXT], host, len(decoded) > MAX_TEXT
            else:
                parser = _TextExtractor()
                parser.feed(decoded)
                parser.close()
                text, partial = parser.text(MAX_TEXT)
                title = parser.title.strip()[:300] or host
            return {'requested_url':requested, 'url':url, 'title':title, 'text':text,
                    'partial': partial or len(raw) > MAX_BYTES, 'page_read':True, 'claims_verified':False,
                    'read_at':datetime.now(UTC).isoformat()}
        finally:
            connection.close()
    raise ValueError('Source could not be read.')


PATTERNS = {
    'Price-like mentions (not quotes)': r'(?:₹|\$|€|£|\b(?:INR|USD|EUR|GBP|Rs\.?|price|fare|tax|fee)\b)',
    'Specifications / route / date mentions': r'\b(?:model|storage|RAM|battery|display|processor|GB|TB|route|train|flight|departure|arrival|duration|check-in|check-out|202[6-9])\b',
    'Terms / warranty / cancellation mentions': r'\b(?:warranty|return|refund|cancel|cancellation|non-refundable|terms|stock|available|seller)\b',
}


def evidence(text):
    # Quote complete bounded lines, never infer a price, product identity or policy.
    lines = list(dict.fromkeys(line.strip() for line in text.splitlines() if line.strip()))
    return {label:[line[:500] for line in lines if re.search(pattern, line, re.I)][:5]
            for label, pattern in PATTERNS.items()}


class SourceComparison(BaseModel):
    model_config = ConfigDict(extra='forbid')
    urls: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=3)


@router.post('/compare')
def compare_sources(item: SourceComparison):
    def read(url):
        try:
            page = read_source(url)
            return {**page, 'status':'page_read', 'evidence':evidence(page['text'])}
        except Exception:
            # Do not return internal addresses, resolver details or arbitrary server errors.
            return {'requested_url':url, 'status':'unavailable', 'page_read':False, 'claims_verified':False,
                    'notice':'Could not safely read this public HTTPS source. It may need JavaScript/sign-in, block readers, be unsupported, or fail the public-network checks. Open it yourself; no availability conclusion can be drawn.'}
    urls = list(dict.fromkeys(item.urls))
    with ThreadPoolExecutor(max_workers=3) as pool:
        pages = list(pool.map(read, urls))
    return {'pages':pages, 'partial':any(not page['page_read'] or page.get('partial') for page in pages),
            'booked':False, 'purchased':False,
            'notice':'Read-only source-text comparison, not a verified recommendation or quote. Page text and price-like mentions can be stale, promotional, incomplete or for the wrong model/date/market. A successful read can still be a login, challenge or incomplete dynamic page. No cookies, login or saved records are sent. Only the selected URLs are requested. Read the original source and verify exact specifications, seller, taxes, stock, dates and terms before relying on them. No bookings, purchases or AI provider calls.'}
