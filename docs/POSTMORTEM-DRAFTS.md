# AETHER caller-supplied postmortem drafts

`draft_postmortem(...)` remains the existing SAFE Markdown formatter. It creates
no file, share, message, task or follow-up and makes no source/network/model call.
The result is text for review, not a delivered report or an approved postmortem.
Caller wording can enter desktop model-backed tool chat if invoked there.

The Markdown now begins with a visible DRAFT notice: all supplied claims,
including root cause, impact, chronology, recovery and follow-up ownership/dates,
remain unverified. Presence of a root_cause field does not establish causality.
Put uncertainty in the supplied wording, for example "Hypothesis: timeout;
needs request traces and deployment evidence", rather than asserting a cause.
The formatter neither invents nor independently checks facts or endorsements.

Missing sections refer only to absent nonblank supplied text, not correctness or
completeness. Blank timeline/action entries are excluded; no actual entries
means those sections are missing. Action items now appear in missing_sections
when empty. No timestamp sorting/parsing, timezone normalization, source
correlation, owner/date extraction, approval, assignment or completion tracking
is performed. Timeline order and free-form action text stay caller supplied.

Inputs are bounded: title one line/up to 200 characters, summary/impact/cause/
detection/resolution text each up to 10000 characters, and timeline/action_items
lists each at most 100 strings of up to 2000 characters per entry. Invalid types
or oversized fields return success=false without a partial Markdown report.
Blank title remains an error. Existing API, section headings, Markdown and
missing-section fields remain; additive flags make acceptance limits explicit.

Caller Markdown/links/markup and possible private values are preserved, not
redacted or sanitized. The result says so. Do not publish it, click unverified
links or render it as trusted HTML automatically. Read the whole draft and use
safe rendering before sharing. Permission to prepare text is not permission to
publish, assign follow-ups or send it as the user. A real postmortem needs source
review, impact/timeline/cause confidence, system/process focus, appropriate
reviewers and owned follow-ups with dates, under the user's authority.

No live incident investigation, verified root cause, CPU/memory/trace analysis,
MTTR/SLO/SLA calculation, remediation, restart, deploy or production access occurs.
Existing incident-duration arithmetic and SLO review are distinct tools. Missing
information is not filled from a hypothesis, previous incident or an approval
prompt. This change does not complete CategoryE's production-investigation work.

Synthetic tests cover draft/verification notices, missing whitespace-only list
entries, preserved caller markup with no redaction claim, type/size bounds,
unchanged section structure, no writes/commands and SAFE formatting after stop.
No real incident information was used.

Postmortem-process guidance checked November 16, 2026:
- https://sre.google/sre-book/postmortem-culture/
