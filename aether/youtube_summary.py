"""Read-only YouTube tutorial summaries from the public caption track.

Given one exact YouTube watch/share URL this fetches the public watch page
once (same SSRF-guarded, size-capped GET as the web tools), looks for the
video's own caption track, fetches that transcript and runs the existing
local extractive summarizer over it. No API key, no video download, no
playback, no account.

Honest limits: many videos have no captions, YouTube can rate-limit or change
its page markup, and auto-generated captions carry recognition errors. Any of
those produces an explicit failure, never an invented summary. The summary is
extractive - sentences lifted from the transcript, not new claims.
"""
from __future__ import annotations

import html
import json
import re

_WATCH_HOSTS = {'www.youtube.com', 'youtube.com', 'm.youtube.com'}
_SHORT_HOSTS = {'youtu.be'}
_VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
_CAPTIONS_RE = re.compile(r'"captionTracks"\s*:\s*(\[.*?\])')
_MAX_TRANSCRIPT_CHARS = 60000


def _video_id(url: str) -> str:
    from urllib.parse import parse_qs, urlsplit
    parsed = urlsplit(url if '://' in url else 'https://' + url)
    host = (parsed.hostname or '').lower()
    if host in _SHORT_HOSTS:
        candidate = parsed.path.strip('/').split('/')[0]
    elif host in _WATCH_HOSTS:
        if parsed.path == '/watch':
            candidate = (parse_qs(parsed.query).get('v') or [''])[0]
        elif parsed.path.startswith(('/shorts/', '/embed/')):
            candidate = parsed.path.split('/')[2]
        else:
            candidate = ''
    else:
        raise ValueError('Only exact youtube.com or youtu.be video URLs are read.')
    if not _VIDEO_ID.fullmatch(candidate or ''):
        raise ValueError('Could not find an 11-character video ID in that URL.')
    return candidate


def _transcript_text(xml: str) -> str:
    texts = re.findall(r'<text[^>]*>(.*?)</text>', xml, re.DOTALL)
    if not texts:
        raise ValueError('The caption track returned no text.')
    combined = ' '.join(html.unescape(re.sub(r'<[^>]+>', '', t)) for t in texts)
    return re.sub(r'\s+', ' ', combined).strip()[:_MAX_TRANSCRIPT_CHARS]


def summarize_youtube(url: str, fetch=None) -> dict:
    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
        raise ValueError('One exact bounded YouTube URL is required.')
    from aether.tools.net.web_tools import _fetch
    fetch = fetch or _fetch
    vid = _video_id(url)
    watch_url = f'https://www.youtube.com/watch?v={vid}'
    page, _ctype = fetch(watch_url)
    html_text = page.decode('utf-8', errors='replace')
    match = _CAPTIONS_RE.search(html_text)
    if not match:
        raise ValueError('This video exposes no caption track, so there is nothing to summarise. A summary is never invented without the words.')
    try:
        tracks = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError('The caption metadata on the page could not be parsed; the page format may have changed.') from exc
    base = None
    for track in tracks:
        candidate = track.get('baseUrl')
        if isinstance(candidate, str) and candidate.startswith('https://www.youtube.com/'):
            base = candidate
            break
    if base is None:
        raise ValueError('No usable caption track URL was found on the page.')
    xml, _ = fetch(base)
    transcript = _transcript_text(xml.decode('utf-8', errors='replace'))
    from app.document_summary import summarize_extracted_text
    summary = summarize_extracted_text(transcript, max_excerpts=6)
    return {'video_id': vid, 'transcript_chars': len(transcript), 'summary': summary,
            'notice': 'Extractive summary of the video caption track: excerpts lifted from the transcript, not new claims. Auto-generated captions can contain recognition errors. Nothing was downloaded or played.'}


def register_youtube_summary(registry):
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='youtube_summary',
        description='Read-only summary of one exact YouTube video URL from its public caption track, via the local extractive summarizer. Fails honestly when there are no captions; never invents content, downloads or plays video.',
        parameters={'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': ['url']},
        handler=lambda url: {'success': True, 'data': summarize_youtube(url)},
        risk=Risk.LOW, category='research'))
