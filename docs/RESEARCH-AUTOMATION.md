# Research, browsing and automation

What AETHER can do as a research and browser agent, what was reused, what this
branch adds, and the limits that are deliberate. Everything read from the web
is untrusted content: it is summarised and quoted with its source, never
followed as instructions.

## The requested list, mapped

| Requested | Status | Where |
| --- | --- | --- |
| Search the web | Exists | `web_search` tool: DuckDuckGo HTML endpoint, no API key, attributable result links (`aether/tools/net/web_tools.py`) |
| Read pages / compare technical documentation / research products | Exists | `web_read_page`: SSRF-guarded, size-capped GET with text extraction; comparison and product research are the assistant composing these read-only tools and citing sources |
| Read GitHub repositories | Exists | Public repos are ordinary pages for the read tools; rendered browsing of owner-allowlisted hosts adds JS-heavy pages (`aether/rendered_browser.py`, per-page approval, no login) |
| Find job openings | Exists (composition) | `web_search` over job boards, read-only; no account, no auto-apply |
| Analyze job descriptions, match jobs against resume | Exists | `review_job_evidence`: literal evidence matrix over the exact supplied resume and JD text. True facts only: no scoring, no skill inference, nothing invented |
| Prepare applications / draft LinkedIn posts | Added, draft-only | `draft_create`/`draft_update`/`draft_get` (`aether/draft_workspace.py`): prepared words stored locally. Nothing is ever sent, submitted, posted or published; "reviewed" is a reading marker, never an approval |
| Summarize YouTube tutorials | Added, bounded | `youtube_summary` (`aether/youtube_summary.py`): fetches the public watch page once, uses the video's own caption track, and runs the local extractive summarizer. No captions means an honest failure, never an invented summary; no download, no playback |
| Extract information from PDFs | Exists | PDF text extraction (pypdf, 80-page bound) in `app/personal_documents.py` / `app/integrations.py` plus the local extractive summarizer (`app/document_summary.py`) |
| Create technical reports | Exists + drafts | Reports are composed by the assistant from read sources and can be stored via `draft_create` kind `report` or written to a local file with the existing approved file tools |
| Monitor selected websites | Added, polite | `site_watch_*` (`aether/site_watch.py`): opt-in per-URL watching, one guarded GET per interval, default one hour, hard floor 15 minutes, at most 20 URLs, no retries inside a check. Change detection is a hash of the fetched bytes: dynamic pages (ads, timestamps) report "changed", so an event is a cue to look, never a summary of what changed |
| Automate approved browser workflows | Exists, constrained | `aether/rendered_browser.py`: rendered browsing of owner-allowlisted public hosts, each exact page with fresh approval, no form fill/submit, no arbitrary clicks or scripts, no account login. Saved read-only plans (`aether/tools/plan_resume.py`) can chain only SAFE non-confirmation steps, so an approval never silently carries across a restart |

## Confirmation rule

Job applications, purchases and sending messages always require the user's
explicit confirmation before submission, and in practice stay manual: the
browser module cannot submit forms at all, and the draft store cannot send.
AETHER prepares; the user submits.

## Deliberately not built

- Auto-applying to jobs or any form submission through the browser.
- YouTube summaries for videos without captions (honest failure instead).
- Continuous or sub-15-minute site polling, and any monitoring of logged-in
  pages.
- Invented resume content: job matching stays literal evidence over the
  supplied resume text.
