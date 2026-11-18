# Public source-text comparisons

After a travel or shopping source search, select up to three distinct HTTPS
sources and click Read and compare. The endpoint `/api/research/pages/compare`
reads only those selected public URLs, using GET without cookies, authorization,
saved records or an AI provider. Search snippets remain separate from page text.

The comparison shows the source title, original/final URL, read time, partial
status and quoted text lines matching price, specification/route/date and
warranty/cancellation terms. These are page-listed claims, not verified quotes,
stock checks, seller verification or advice. Missing text means not found in the
bounded extraction, not that a feature/policy does not exist. A successful fetch
can still contain a login/challenge page or omit dynamic content. Inspect the
original page and verify the exact model/date/market, total and terms yourself.
No booking, purchase or message can be made here.

Safety/limits:
- HTTPS only, port 443; no URL usernames/passwords. Common credential/signed-query
  keys are refused. Do not supply private or signed links.
- Resolve each target/redirect, require all DNS answers to be public, reject
  private/loopback/link-local/reserved/multicast/transition targets, then pin the
  actual connection to a checked numeric address. TLS still verifies the
  original hostname. No environment proxy or login session is used.
- Up to three redirects are revalidated; no HTTP downgrade. HTML/plain text only,
  at most 1 MB raw and 12000 extracted characters. Compressed responses are refused
  rather than decompressed without a bound. Network sockets have 8-second
  timeouts with a 15-second loop budget; OS DNS resolution may take longer.
- JavaScript is not run. Sites requiring it, login, anti-bot interaction or proxy
  access may fail or return incomplete content. No CAPTCHA bypass, repeated
  monitoring, automatic retry or alternative account use is performed.

Mocked tests cover target validation, mixed DNS answers, pinned TLS host/IP,
redirects, compression/MIME/size limits, auth and partial failures. One public
neutral page at https://example.com/ was read successfully during development;
this does not establish acceptance on real merchants, airlines or hotels.
