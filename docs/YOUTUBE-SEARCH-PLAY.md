# YouTube search and visible playback handoff

Two registry tools close the "find a video and play it" request at honest
evidence levels. Neither downloads, embeds or plays media itself.

## `youtube_search` (SAFE, research)

One exact search query (1-200 characters) fetches the public YouTube results
page once through the same SSRF-guarded, size-capped GET as the other web
tools, extracts video IDs and titles from the page's initial-data JSON,
dedupes them and returns canonical `https://www.youtube.com/watch?v=<id>`
URLs (1-10 results, default 5). No API key, account or cookies.

Honest limits:

- YouTube can rate-limit or change its page markup at any time; both produce
  an explicit failure ("page layout may have changed"), never invented
  results.
- Titles are untrusted page text. The tool result carries that note; a model
  or client must never follow instructions embedded in a title.
- A search result existing on the page is not proof the video is playable,
  available in the user's region, or still online.

## `youtube_play` (LOW, media)

Accepts one exact YouTube video - a watch/share/shorts URL or a bare
11-character video ID - validates it with the same parser as
`youtube_summary`, canonicalises it to
`https://www.youtube.com/watch?v=<id>` and hands it to the same visible
default-browser open path as `open_website`.

Honest limits:

- The handoff is not verified playback. The browser and YouTube own what
  happens next (ads, sign-in walls, region blocks, removed videos); the tool
  reports that explicitly instead of claiming "now playing".
- Only canonical `youtube.com`/`youtu.be` targets are accepted; lookalike
  hosts and non-YouTube URLs are refused.
- It is not a bypass for the approved-app allowlist: it opens one exact
  HTTPS URL in the default browser, nothing else.

## Typical flow

1. User: "find a video about ECS blue-green deployments" -> `youtube_search`.
2. User picks one from the list -> `youtube_play` with that exact URL.
3. For a supplied link, `youtube_play` directly; `youtube_summary` remains
   the read-only caption-summary path.

## Verification

Unit tests parse fixture results HTML (dedupe, unescaping, result limits,
honest failure on markup change or fetch error) and exercise the play
handoff with an injected opener (all accepted URL shapes, refusal of
lookalike hosts, opener failures). Registry integration tests pin both
tools' risk levels and run the search through `ToolRegistry.execute`.
Real browser playback on Windows remains device acceptance, as with every
visible-launch path.
