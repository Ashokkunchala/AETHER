# Job application tracker

Local, manual tracking of job applications and leads. Records only what the
user explicitly supplies: nothing is scraped, fetched, emailed or inferred.

## Tools (category `jobs`)

| Tool | Risk | What it does |
| --- | --- | --- |
| `job_add` | LOW | Save one application/lead: company, role, status (`saved`/`applied`/`interview`/`offer`/`rejected`/`withdrawn`), optional `https://` link, `applied_day`, `follow_up_day`, notes. |
| `job_update` | LOW | Change status, notes, follow-up day or link for one entry (by id from `job_list`). Status changes are appended to a local history table. |
| `job_list` | SAFE | Read entries, optionally filtered to one status, newest update first. |
| `job_followups_due` | SAFE | Open applications (saved/applied/interview) whose `follow_up_day` is today or earlier in a supplied IANA timezone. Offers and closed outcomes never appear. |
| `job_summary` | SAFE | Count entries by status. Descriptive record counts, not a pipeline forecast. |
| `job_remove` | HIGH | Delete one entry and its history; requires the exact phrase `REMOVE APPLICATION <id>`. |

## Storage and posture

- SQLite at `~/.aether/jobs.db` (override with `AETHER_JOBS_DB`), file mode
  0600. No network, no provider account, no sync.
- Validation: bounded plain text (control characters refused), strict
  `YYYY-MM-DD` dates, future `applied_day` refused, single `https://` URL only.
- Rows are data, never instructions or authorization: stored notes/URLs are
  shown back verbatim and are not acted on.
- Nothing here sends email/messages or books interviews; pairing with the
  Gmail adapter's approved-send flow remains a separate, user-confirmed step.

## Not claimed

Delivery of reminders for follow-ups (use the existing reminder store), and
any verification of a recruiter or listing. The tracker keeps the user's own
records; it does not judge them.
