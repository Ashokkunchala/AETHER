# AETHER mentor: daily checkpoint activity

The existing mentor progress view keeps each starter topic's latest result and
attempt count. It cannot reconstruct which days old attempts happened. This
addition records new objective-checkpoint attempts in an append-only table in
the same local mentor database. It does not backfill a fictional history.

## Use

In the existing desktop tool chat, request a daily activity report with explicit
dates and an IANA timezone. The registry tool is:

```text
mentor_daily_activity(start_date="2026-11-01", end_date="2026-11-16", timezone="Asia/Kolkata")
```

Dates are inclusive and must be YYYY-MM-DD, with a range of 1-366 days. A timezone
is required, not inferred from UTC or a device location. Local-midnight boundaries
are converted to UTC, so DST days need not be 24 hours. The report returns each
day, attempts, correct/incorrect choices, topic IDs, active checkpoint days and
explicit partial/invalid-row notices. A zero means no captured checkpoint attempts,
not that the learner did not study. Repeat attempts count individually, including
repeated identical answers; no retry deduplication is implied by this old submit
interface. Correct choices are not skill certification or course completion.

## Preservation and limits

- Existing `mentor_submit`, `mentor_progress`, plan, interview and project
  response fields are unchanged. Existing records are not rewritten or deleted.
- Each new valid checkpoint submission writes its attempt in the same SQLite
  transaction as the existing latest-result upsert. If either fails, both roll
  back. Invalid answers and submissions blocked by the existing emergency stop
  do not create attempt records.
- New rows contain topic, choice index, correct/incorrect and UTC capture time,
  not free-text answers, credentials, terminal output or private code. Times
  reflect local submission capture, not when the person actually studied.
- The report scans at most 10000 earliest rows in its requested range. It fetches
  one extra to detect truncation. With `partial=true`, totals and day counts are
  incomplete. Malformed scanned rows are skipped and counted, not silently
  counted as success. Future-only history remains distinct from older latest
  results, even if the older row has an updated timestamp or attempt count.
- No duration, attendance, project/interview activity, live coding grade,
  external calendar, background reminder or notification is inferred or added.
  The web saved-data and Live Voice tool sets are not widened by this change.
- Attempts remain in the local mentor database, under `AETHER_MENTOR_DB` or its
  existing default. There is no new retention/deletion control. Backend-memory
  expiry does not delete these rows. Backups may include them.

Tests use temporary databases: local-day boundaries, DST 23/25-hour days, leap
date, input validation, additive schema/reopen, no backfill, rollback, concurrent
submissions, limits, invalid rows, stop behavior and compatible latest progress.
No real learning record, user device, provider or cloud account was touched.
