# AETHER offline AWS Backup job evidence

`review_aws_backup_jobs(path)` reviews an existing local AWS Backup
`list-backup-jobs` JSON snapshot through the desktop DevOps evidence registry.
It performs no AWS, SDK, CLI, network, model or paid-service call. The live AWS
command policy is unchanged; AWS Backup list calls remain on the confirmation
path, not new automatic reads. It creates no alerts or background monitor.

This differs from AETHER's local selected-document ZIP integrity verifier.
Neither tool proves that AWS recovery points can restore an application.

## What the classifications mean

- COMPLETED and MessageCategory SUCCESS: reported completed/success category.
  This is not a clean, protected, recoverable or tested-restore verdict.
- COMPLETED and another nonempty MessageCategory: reported completed with issues.
  AWS documents that console status as COMPLETED with a non-SUCCESS category.
- COMPLETED without MessageCategory: category unknown, not assumed SUCCESS.
- FAILED, ABORTED, EXPIRED or PARTIAL: reported failure/incomplete, needs review.
- CREATED, PENDING, RUNNING or ABORTING: reported pending/in progress. No stuck
  or overdue inference is made because timestamps are not evaluated.
- Unknown future states: UNKNOWN/review, never silently successful.

A SUCCESS category never overrides a noncompleted State. Missing flags remain
unknown. Parent/composite and child indicators are preserved, with signals for
both indicators or a self-parent reference. No child-outcome rollup or parent
health is inferred. Counts are of records, not distinct protected resources:
parent and child records can overlap. The snapshot may also be filtered or old.

## Deliberate limits

At most 2 MB UTF-8 JSON and 500 records. Each record needs a bounded job ID and
State. Duplicate IDs, invalid types, malformed parent flags, duplicate JSON
fields, non-finite JSON and oversized exports are refused. Unknown states are
retained as UNKNOWN instead of being discarded. Missing category is unknown;
explicit null/empty/invalid category values are refused rather than accepted as
success. The input file is not edited. No command text is executed.

Output job_index refers to that row in the supplied local file. Job, resource,
account, vault, IAM role, key and parent IDs, resource type/name values, exact
message categories and free-form status messages are not returned. Human review
must correlate an index with the private original. No automatic troubleshooting
or remediation is based on omitted descriptions. ResourceType syntax is checked
if present, but resource-specific backup semantics are not evaluated.

A nonempty NextToken is flagged but never exposed or followed. No token does not
prove every page/account/region/filter is present. Regular-file, symlink/junction
and bounded stable-read checks apply, but are not a full sandbox against hostile
concurrent path swaps. Keep exports in a trusted local directory.

CreationDate, CompletionDate, ExpectedCompletionDate and StartBy are not parsed.
No backup-age, latest-job, RPO/RTO, duration, missing-job, schedule or deadline
claim is made. Size fields are not totaled: AWS notes these values vary by
resource type, including legitimate zero values. A job report does not establish
resource coverage, recovery-point retention/availability, application consistency,
permissions, encryption strength, integrity or restore-test success.

Freshness, query scope, completeness, resource coverage and restore verification
always remain false/unverified. Empty BackupJobs means no records were supplied,
not that no backups are needed. Independently verify live scope/status, intended
resource coverage and current recovery/restore-test evidence before relying on
it. Review and approval are separate requirements for every cloud change.

No retry, cancel, backup, restore, copy, delete, plan edit, credential/secret read,
payment or deployment occurs. If the tool is invoked inside a model-backed chat,
returned states/counts can be included in that conversation; the parser itself
makes no model call. This is an offline triage foundation, not operational AWS
Backup monitoring or disaster recovery acceptance.

Tests use synthetic snapshots and temporary files, including completed-with-
issues vs missing-category, partial/failed/in-progress/unknown states, parent/
child overlap, bounds, private-field omission and SAFE execution after stop.
No real account, backup job, recovery point, restore or billed API was used.

Official AWS sources checked November 16, 2026:
- https://docs.aws.amazon.com/cli/latest/reference/backup/list-backup-jobs.html
- https://docs.aws.amazon.com/aws-backup/latest/devguide/monitoring.html
