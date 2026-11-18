# Signed-in browsing and reviewed form fill

November 18, 2026. This extends the existing rendered public-page browser with
an opt-in local profile so AETHER can read pages the owner is signed into, and
type reviewed text into reviewed form fields. It never submits forms, never
clicks buttons or links, and never touches password, hidden, file, payment,
code or token fields. No real account, website session or submission was used
while developing or testing this feature.

## Trust model

- The owner signs in **themselves**: `aether browser-login <url>` opens one
  visible window on an exact allowlisted page. AETHER never reads, stores or
  types usernames, passwords or one-time codes, and never clicks during login.
  Session cookies stay in the local owner-only profile folder
  (`~/.aether/browser-profile`, mode 700; override with
  `AETHER_BROWSER_PROFILE`). Signing out of the site or deleting the folder
  ends access.
- The same gates as public browsing still apply to every signed-in read:
  `AETHER_BROWSER_ENABLED=1`, the exact host allowlist
  (`AETHER_BROWSER_HOSTS`), HTTPS on port 443 with public DNS answers only, and
  a fresh approval each time. The approval preview shows the exact URL.
- Signed-in page content is **private**. Read results stay local (bounded text,
  links and a mode-600 screenshot) and must not be sent to any model/provider
  without a separate owner decision. Page text is untrusted data, never
  instructions.

## Reviewed form fill

`fill_reviewed_form` (registry tool, fresh confirmation required, never
auto-approved) or `python -m aether.profile_browser fill <url> '<fields json>'`:

- The plan is exact: one allowlisted URL and 1-10 fields, each a CSS selector
  (max 200 chars), a text value (max 1000 chars) and an optional label. The
  owner reviews every selector and value before anything launches.
- At fill time each field is rechecked live: exactly one matching element, a
  visible, enabled, editable `input` (text/search/email/tel/url/number) or
  `textarea`. Password/hidden/file/button/checkbox/radio/select targets and
  fields whose name, id, autocomplete or placeholder match the sensitive
  pattern (password, CVV/CVC, card number, OTP/verification/security codes,
  secrets, tokens, SSN) are refused with reasons.
- AETHER types the reviewed values, saves a local screenshot, and waits with
  the window open. It never submits; the owner reviews the page and submits or
  abandons it themselves. Typed values are visible to the site.
- Login and fill windows behave like the owner's own browser on that site
  (including the owner's own submissions); read mode sends GET/HEAD only.

## Limits

- This is not general web automation: no arbitrary clicks, navigation,
  downloads, uploads, CAPTCHA solving, MFA handling or multi-step flows.
- A persistent profile increases the impact of a compromised allowlist entry;
  keep the host list minimal. DNS/network races and malicious page content
  remain risks. This is not an OS or network sandbox.
- Headless signed-in reads can be detected or challenged by some sites; that is
  a site-policy outcome, not a bypass to engineer around.
- Tests use locally fulfilled fixture pages in real Chromium; no real signed-in
  site, account or submission was exercised.

Sources: `aether/profile_browser.py`, `aether/rendered_browser.py`,
[browser and dashboards](BROWSER-AND-DASHBOARDS.md).
