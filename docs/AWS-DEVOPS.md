# AETHER AWS DevOps foundations

AETHER has offline reviewers and a guarded local AWS CLI wrapper in the desktop
brain/CLI/TUI tool registry. These are foundations, not full AWS operations or
acceptance evidence. Saved-data chat, Live Voice and provider panels do not
universally expose the same tools, memory or approval path. Configuring one
interface does not connect every other interface.

The wrapper uses an AWS CLI profile configured on the user's machine. It does
not set up, read or store credentials itself. No real AWS account, cloud change,
backup/restore, production incident or device acceptance was exercised for these
foundations. Request charges and data disclosure depend on the actual operation;
read-only does not mean free or non-sensitive.

## Exact AWS read policy

`aws_read` accepts only these reviewed service/operation pairs and reviewed flags:

| Service | Operation |
| --- | --- |
| `ec2` | `describe-instances` |
| `ec2` | `describe-vpcs` |
| `ec2` | `describe-subnets` |
| `ec2` | `describe-route-tables` |
| `ec2` | `describe-security-groups` |
| `ecs` | `list-clusters` |
| `ecs` | `describe-clusters` |
| `eks` | `list-clusters` |
| `eks` | `describe-cluster` |
| `rds` | `describe-db-instances` |
| `lambda` | `list-functions` |
| `cloudwatch` | `list-metrics` |
| `logs` | `describe-log-groups` |
| `logs` | `describe-log-streams` |
| `cloudformation` | `describe-stacks` |
| `cloudformation` | `list-stacks` |
| `s3` | `ls` |
| `s3api` | `list-buckets` |
| `iam` | `list-users` |
| `iam` | `list-roles` |
| `iam` | `list-policies` |
| `iam` | `get-policy` |
| `iam` | `get-policy-version` |
| `secretsmanager` | `list-secrets` |
| `securityhub` | `get-findings` |
| `guardduty` | `list-detectors` |
| `guardduty` | `list-findings` |
| `guardduty` | `get-findings` |
| `sts` | `get-caller-identity` |

This is an exact allowlist, not permission for every operation whose name starts
with describe, list or get. Unknown/repeated flags, global endpoint overrides,
local-file argument loading, flag abbreviations and malformed pagination values
are refused on the read path. See `aether/devops/awscli.py` for each operation's
flag contract. No new AWS read is enabled by the offline reviewers below.

`aws_read` is a LOW registry action: the persistent emergency stop blocks it.
`aws_change` is a HIGH registry action and always requires confirmation, including
billed reads, unlisted reads and secret-returning operations. Some explicitly
blocked account actions remain blocked. Secret reads such as Secrets Manager,
SSM parameters, KMS decrypt and STS assume-role are not automatic reads. Cost
Explorer, Pricing and Bedrock Runtime stay on the approval path, even for reads.

`aws_change(dry_run=true)` only builds/displays the local command. It is not an
AWS-side dry run and does not validate permissions, account, region, price,
resource existence, quota or rollback. Any real operation needs a separately
reviewed exact command, scope, expected effect, possible charges and undo plan.
The generic wrapper is not a typed safe lifecycle adapter for every AWS service.
Do not use it or generic shell access to bypass the user's approved-command,
no-deployment, no-paid-service or no-destructive-action boundaries.

[Local execution safety](EXECUTION-SAFETY.md) describes invocation-bound
confirmation, stop behavior and limits. This is not an OS sandbox, remote role
system or a way to revoke work that already started.

## Offline evidence tools

SAFE evidence reviews do not call AWS or run export commands. They remain
available after the registry stop, so they must not be confused with LOW live
reads. Select an existing local export yourself; a missing snapshot is not
permission to fetch one. No export below proves current account/region/filter
scope, freshness, completeness or actual resource health.

| Tool | Reported evidence and limits |
| --- | --- |
| `review_security_groups` | Explicit public ingress patterns from supplied describe-security-groups JSON. No effective reachability or full network audit. |
| `review_terraform_plan` | Delete/replacement/state-removal actions in a supplied plan JSON. No apply, sensitive attribute echo or proof of a safe deployment. |
| `review_kubernetes_pods` | Supplied Pod/PodList readiness/restart/termination signals. No cluster access, root-cause proof or inferred readiness from Running. |
| `review_ebs_volumes` | Reported attachment state. Available with explicit empty attachments is only a human-review candidate, never proof unused or safe cleanup. |
| `review_cost_explorer` | Native supplied cost/usage periods, metrics, units and estimated flags kept separate. No billed request, implicit grand total or final-invoice/savings claim. |
| `review_aws_backup_jobs` | Supplied job states and category status, including completed-with-issues and unknown categories. No protected-resource coverage, backup integrity or restore-readiness claim. |
| `analyze_daily_costs` | Caller-normalized complete-day same-currency totals against a short baseline. Not native export parsing, monthly billing, forecasting or learned anomaly detection. |
| `review_rds_instances` | Supplied describe-db-instances fields and public-access/encryption/backup-retention/deletion-protection signals. No live monitoring, metrics, health verdict or change. |
| `review_lambda_functions` | Supplied list-functions runtime/package/memory/timeout/code-size fields. No invocation evidence, troubleshooting, deprecation verdict or change. |
| `review_security_hub_findings` | Supplied get-findings severity/workflow/record/compliance tallies. No posture, coverage, suppression or remediation. |
| `review_guardduty_findings` | Supplied get-findings types and numeric severities banded by the documented ranges. No threat posture, archive or remediation. |

Detailed input bounds and acceptance limits:
[cloud evidence scope](ABILITIES.md), [EBS review](AWS-EBS-REVIEW.md),
[Cost Explorer review](AWS-COST-REVIEW.md),
[AWS Backup jobs](AWS-BACKUP-REVIEW.md).

## Other existing offline helpers

- `review_terraform`, `review_dockerfile`, `review_cicd`, `review_k8s` and
  `review_iam_policy` flag selected text/JSON patterns. They are heuristics, not
  complete parsers, vulnerability scans, effective IAM permission simulation or
  proof secure. No finding does not mean safe. IAM/S3/VPC live inventories are
  not created by these reviewers.
- `triage_log` matches known local log patterns and minute strings; a match is a
  signal, not a verified root cause. Raw examples/patterns can include sensitive
  log content in its result. Select and redact logs before model-backed use.
  This is not CloudWatch collection, trace correlation or a monitoring service.
- `devops_runbook` returns manual checklists. `draft_postmortem` formats supplied
  facts and flags missing sections, not an independently verified incident report.
- [Terraform mentor](MENTOR-TERRAFORM.md) provides a no-cloud lesson and a bounded
  supplied validation-report reviewer. It does not execute Terraform or provision
  infrastructure. [Local backup verification](BACKUP-VERIFICATION.md) checks a
  selected ZIP snapshot against a caller's trusted hash, not AWS Backup recovery.

Read-path coverage now includes reviewed VPC/subnet/route-table/security-group,
EKS, RDS, Lambda, CloudWatch metadata, CloudFormation stack, Secrets Manager
metadata (never secret values), Security Hub and GuardDuty inventory reads, plus
offline snapshot reviewers for RDS instances, Lambda functions and Security
Hub/GuardDuty findings. EBS volume and AWS Backup job listing deliberately stay
on the approval path and are reviewed from local exports instead. No dedicated
validated Git/Docker/Jenkins lifecycle adapters, general Linux administrator,
coding sandbox or complete ECS/EKS/RDS/Lambda/CloudWatch/S3/VPC/Secrets Manager/
Security Hub/GuardDuty/CloudFormation operational suite is established here. Generated code or a generic command wrapper is not execution
acceptance. Live credentials, hardware/provider checks and separate action
approval remain prerequisites for work that needs them. Never expose this local
prototype directly to the public internet.

## Typed lifecycle proposal design

The existing registry now includes `design_lifecycle_change`, documented in
[TYPED-LIFECYCLE-DESIGN.md](TYPED-LIFECYCLE-DESIGN.md). It validates closed exact
EC2 start/stop, Deployment scale or GitHub workflow-dispatch proposal shapes and
returns a supplied-scope digest plus approval/live-check requirements. A pure
protocol simulator tests no gate-skipping, unknown-outcome handling and
cancellation distinctions. Neither function can contact providers, record real
approval or execute. Every result is design-only and unauthorized. This is not
a replacement for existing tools' confirmation policies or a completed typed
provider lifecycle. Real adapters, permission/cost/account checks, durable claims,
owner approval and external-result verification remain separate work.
