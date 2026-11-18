# AETHER AWS foundations: offline EBS inventory review

`review_ebs_volumes(path)` extends the existing desktop DevOps evidence registry.
It reads an existing local `describe-volumes` JSON export, never an AWS account.
No SDK, CLI, network, credential retrieval, detach, delete, snapshot, restore or
other cloud action is performed. The existing AWS read-operation allowlist is
unchanged: `describe-volumes` is not silently promoted to automatic live access.

## What the review means

The tool accepts an object with a `Volumes` array. It reports volume ID, known
state, supplied size/encryption/Multi-Attach/service-managed flags, attachment
record count/state counts and bounded fixed signals. It does not echo tags,
KMS key identifiers, snapshot identifiers, instance/device/account identifiers,
ARNs, operator principals or free-form values. Unknown future states are marked
unknown, not repeated as advice or converted into candidates.

Only `State=available` plus an explicitly present empty `Attachments` array can
be labelled `reported_available_unattached_review_candidate`. A supplied
`Operator.Managed=true` excludes that candidate classification. Missing Operator
metadata does not establish an unmanaged volume. Unknown/missing attachment
information, even a listed detached attachment, never substitutes for an empty
array. Contradictory in-use/empty or available/nonempty snapshots get fixed
signals; they are not silently repaired into a clean inventory.

Every row says `safe_to_delete=false`. A candidate is an invitation to investigate,
not proof unused, orphaned, billable waste or safe cleanup. An unattached volume
may still be needed for recovery, migration, a stopped workflow or retention.
No last-use date, attachment age, owner, dependency, backup validity, savings,
price or security conclusion is inferred. Reported unencrypted is a signal to
review the supplied evidence, not a full encryption/security audit.

## Scope, bounds and errors

- Existing regular local UTF-8 JSON, at most 2 MB and 500 volume objects.
  Symlink/junction and special-file paths are refused with existing path hygiene;
  this is not an OS sandbox against hostile concurrent path swaps.
- The export read checks size and modification time around a bounded read.
  Duplicate JSON fields, non-finite values, malformed IDs/types and duplicate
  volume IDs fail, rather than returning a plausible partial success.
- At most 100 attachment records per volume. Known attachment states are counted;
  unknown states remain unknown. Any attachment record blocks candidate status.
- A nonempty `NextToken` is reported without echoing or following it. An absent
  token does not prove complete pagination or complete accounts/regions/filters.
  Snapshot freshness, account/region scope and inventory completeness always stay
  unverified. No live follow-up is automatically started by an export's contents.
- The snapshot is private cloud metadata. Review local file scope before using
  it in a model-backed conversation. Tool output may enter that conversation;
  the parser itself does not call a model or provider.

Before considering a later change, separately confirm current account/region,
filters/pages and attachment state, ownership/purpose, dependencies, retention,
service management and backup recoverability. Then obtain exact change approval.
This tool does not grant it. There is no cleanup button or deletion command.

## Relationship to the wider AWS blueprint

Existing code has offline IAM policy heuristics, explicit public security-group
ingress review, Kubernetes pod restart/readiness snapshots, Terraform change
summaries and same-currency complete-day cost comparisons. Those are not full
service administration, verified live cost/billing, reachability analysis or
proof of security. Current direct live AWS reads remain narrowly reviewed
operations using a locally configured profile. Secrets retrieval and potentially
billed calls are not made by these offline tools.

EC2 lifecycle actions, EBS cleanup, full S3 access/inventory, VPC routing,
ECS/EKS operations, RDS/Lambda/CloudWatch live monitoring, Cost Explorer API use,
CloudFormation deployments, Terraform execution, AWS Backup monitoring and
Security Hub/GuardDuty ingestion need further scoped adapters and acceptance.
Secrets Manager values must never be retrieved merely because an operation
sounds read-only. Account/credential setup, service permissions, approval gates,
budgets and live acceptance are separate work. This foundation neither deploys
nor broadens shell/cloud authority to simulate completion of that list.

## Verification and sources

Tests use synthetic exports and temporary files only: candidate versus unknown/
contradictory states, service-managed records, multiple/detached attachments,
missing fields, pagination, duplicate IDs/JSON, data minimization, size/shape
bounds, symlink/FIFO refusal and safe registry execution after emergency stop.
No real AWS data, account, paid service or user device was accessed.

Official AWS documentation checked November 16, 2026:
- https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-volumes.html
- https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-volume.html

The deletion reference explains why deletion needs separate consideration. It
is evidence for the safety boundary, not an instruction or approval to delete.
