"""Short troubleshooting runbooks for the AWS stack Ashok works with.

Static text: each step is a read-only check first, then a fix to approve.
"""

from __future__ import annotations

from typing import Any

RUNBOOKS: dict[str, dict[str, Any]] = {
    "ecs-task-stopped": {
        "title": "ECS task keeps stopping or never reaches RUNNING",
        "checks": [
            "aws ecs describe-tasks --cluster C --tasks T  -> read stoppedReason and container exitCode",
            "aws ecs describe-services --cluster C --services S  -> read the events list (health check, no capacity, image pull)",
            "aws logs tail LOG_GROUP --since 30m  -> application error before exit",
            "CannotPullContainerError: check ECR repo/tag exists, task execution role has ecr:GetAuthorizationToken and image pull rights, and subnets reach ECR (NAT or VPC endpoints)",
            "Exit code 137: container hit its memory limit or was killed; compare memory reservation to usage",
            "Target group unhealthy: health check path/port/matcher and security group from ALB to task",
        ],
        "fixes": ["Fix image tag or role policy", "Raise task memory/cpu", "Correct health check path", "Add NAT or VPC endpoints"],
    },
    "eks-pod-crashloop": {
        "title": "EKS pod in CrashLoopBackOff, Pending or ImagePullBackOff",
        "checks": [
            "kubectl describe pod P -n NS  -> Events section first",
            "kubectl logs P -n NS --previous  -> last crash output",
            "Pending: kubectl describe node and look for insufficient cpu/memory, taints, or unbound PVC",
            "ImagePullBackOff: image name/tag, imagePullSecrets, node role ECR permissions",
            "OOMKilled in lastState: raise memory limit or fix the leak",
            "Readiness/liveness probe failing: path, port, initialDelaySeconds",
        ],
        "fixes": ["Fix manifest or image", "Adjust resources/probes", "Scale node group or fix taints/tolerations"],
    },
    "terraform-state-lock": {
        "title": "Terraform state lock or drift problems",
        "checks": [
            "Read the lock ID and holder in the error message; confirm no apply is running (CI job, teammate)",
            "aws dynamodb scan on the lock table (read) to see the lock item, or check the S3 lockfile if use_lockfile is set",
            "terraform plan -refresh-only  -> shows drift without changing anything",
        ],
        "fixes": ["terraform force-unlock LOCK_ID only after confirming nothing is running", "terraform apply -refresh-only after review"],
    },
    "jenkins-aws-pipeline": {
        "title": "Jenkins pipeline fails on AWS steps",
        "checks": [
            "ExpiredToken / AccessDenied: which credentials does the agent use (instance profile vs stored keys)? run `aws sts get-caller-identity` in the job",
            "Terraform step: confirm backend bucket/table access and the workspace",
            "Docker push: ecr get-login-password then docker login; repository policy and region",
            "Agent disk full: docker system df, clean old images",
        ],
        "fixes": ["Move to an instance role or OIDC-like short-lived creds", "Rotate leaked keys immediately", "Add cleanup stage"],
    },
    "alb-5xx": {
        "title": "ALB returns 502/503/504",
        "checks": [
            "CloudWatch HTTPCode_ELB_5XX vs HTTPCode_Target_5XX: ELB-side or app-side",
            "aws elbv2 describe-target-health  -> unhealthy reason codes",
            "504: target idle timeout shorter than ALB idle timeout, or slow upstream",
            "502: target closed connection early or sent malformed response; check keep-alive timeout > ALB idle timeout",
        ],
        "fixes": ["Fix health check", "Match keep-alive and idle timeouts", "Scale targets"],
    },
    "lambda-errors": {
        "title": "Lambda function errors or timeouts",
        "checks": [
            "aws lambda list-functions (read) -> note runtime, memory and timeout; review_lambda_functions on the export",
            "aws cloudwatch list-metrics --namespace AWS/Lambda (read) -> which metrics exist for the function",
            "Errors/duration metrics and log events are approval-path reads (aws_change with dry_run first)",
            "Timeout at the 900s cap or memory at maximum: compare against the reported configuration",
            "Recent change? compare last modified time with the first error in logs",
        ],
        "fixes": ["Raise memory/timeout after reviewing usage", "Fix the code path from the log evidence", "Roll back the last version/alias change"],
    },
    "rds-health": {
        "title": "RDS instance looks unhealthy or slow",
        "checks": [
            "aws rds describe-db-instances (read) -> reported status; review_rds_instances on the export",
            "Status storage-full: allocated storage vs usage; autoscaling settings",
            "CPU/connections/freeable memory: approval-path CloudWatch reads, not guesses",
            "PubliclyAccessible true or StorageEncrypted false in the snapshot: review before any exposure change",
            "Failover or reboot in progress: check reported status and recent events before acting",
        ],
        "fixes": ["Scale storage or instance class after metric review", "Enable deletion protection and backup retention", "Investigate slow queries via performance insights (approval path)"],
    },
    "cloudformation-stack-failed": {
        "title": "CloudFormation stack in ROLLBACK/FAILED state",
        "checks": [
            "aws cloudformation describe-stacks (read) -> StackStatus and StatusReason",
            "aws cloudformation describe-stack-events (approval path) -> first FAILED event reason",
            "CREATE_FAILED on one resource: quota, name conflict, missing permission or bad property",
            "UPDATE_ROLLBACK_FAILED: a resource the rollback depends on was changed outside the stack",
        ],
        "fixes": ["Fix the failing resource property and update again", "Continue update rollback only after reading the events", "Import or remove out-of-band changes deliberately"],
    },
    "security-finding-triage": {
        "title": "Security Hub or GuardDuty findings to triage",
        "checks": [
            "aws securityhub get-findings / guardduty get-findings (read) -> review_security_hub_findings / review_guardduty_findings on the export",
            "Sort by reported severity band first, then by finding type and resource type",
            "Cross-check a finding against its owning service (GuardDuty type docs, Security Hub standard controls) before accepting it",
            "A workflow status of RESOLVED or a low severity label is a claim, not proof; verify the underlying change",
        ],
        "fixes": ["Remediate the root cause, then confirm the finding closes itself", "Suppress/archive only with a documented reason", "Never bulk-resolve without review"],
    },
    "aws-monthly-cost": {
        "title": "Understand this month's AWS cost",
        "checks": [
            "Cost Explorer reads are billed per request: build the exact ce get-cost-and-usage command with aws_change dry_run and approve it deliberately",
            "Export the JSON, then review_cost_explorer for native periods, metrics and estimated flags",
            "analyze_daily_costs compares complete same-currency days against a short baseline",
            "Group by service and by linked account before calling anything an anomaly",
        ],
        "fixes": ["Tag untagged resources before cutting anything", "Confirm idle resources with owners; snapshots/backups first", "Set a budget alert instead of repeated manual checks"],
    "api-5xx-investigation": {
        "title": "API returns 500/502/503 errors",
            "Normalize authorized log windows with triage_log; read the peak error minute first",
            "Check for a deploy_event in the same scope shortly before the first error (review_incident_evidence)",
            "Correlate metric and trace windows with compare_telemetry_windows before blaming a layer",
            "502/503: check endpoints and targets (review_kubernetes_endpoints, review_k8s_service_endpoints_json); 500 with tracebacks: application errors",
            "review_incident_evidence for a timeline and correlation-only candidates; never restart or roll back without approval",
        "fixes": ["Roll back a correlated change only with explicit approval", "Scale or restart only with explicit approval", "Add the missing evidence first when candidates are weak"],
    "deploy-rollback-decision": {
        "title": "Decide whether to roll back a deployment",
            "Confirm errors started after the deploy and share its scope (review_kubernetes_deployments on a supplied snapshot)",
            "Rule out a separate cause: dependency outage, config change, traffic spike",
            "Confirm the previous revision is still available and its own health was clean",
            "Rollback is a change: build the exact command, show it, and get explicit approval before running",
        "fixes": ["kubectl rollout undo / previous task-definition update only after approval", "Record the decision and evidence in the incident summary"],
    "node-high-memory": {
        "title": "Abnormal CPU or memory on a node or workload",
            "review_kubernetes_nodes on a supplied node snapshot for pressure conditions",
            "Identify the top consumers before acting; a pressure condition is not a culprit",
            "Check for a recent deploy or traffic change that raised baseline usage",
            "OOMKilled in a container: compare its limit with real usage before raising it",
        "fixes": ["Raise limits/requests after reviewing usage", "Cordon/drain a node only with explicit approval", "Fix the leak rather than growing the box forever"],
    "ci-publish-checklist": {
        "title": "Publish artifacts or deploy from CI safely",
            "Immutable inputs: pinned action/image digests, exact revision, no floating tags",
            "Secrets: never echoed to logs; masked or short-lived OIDC, no static AWS keys (review_cicd flags these)",
            "Artifacts: build once, promote the same digest; never rebuild per environment",
            "Publish and deploy steps stay approval-gated; verify the published digest afterwards",
        "fixes": ["Pin digests and revisions", "Move credentials to short-lived assumed roles", "Separate build, publish and deploy into separately approved stages"],
    },
    "iam-access-denied": {
        "title": "AccessDenied or UnauthorizedOperation",
        "checks": [
            "Decode the error: which action, which resource ARN, which principal",
            "aws sts get-caller-identity  -> confirm you are the principal you think",
            "Check identity policy, permission boundary, SCP, resource policy and session policy; an explicit Deny wins",
            "CloudTrail event history for the denied call shows the exact principal and action",
        ],
        "fixes": ["Add the narrowest allow for that action and ARN", "Do not attach AdministratorAccess to unblock"],
    },
}


def list_runbooks() -> dict[str, Any]:
    return {"success": True, "runbooks": {k: v["title"] for k, v in RUNBOOKS.items()}}


def get_runbook(topic: str) -> dict[str, Any]:
    key = topic.strip().lower().replace(" ", "-").replace("_", "-")
    if key in RUNBOOKS:
        return {"success": True, "topic": key, **RUNBOOKS[key]}
    matches = [k for k, v in RUNBOOKS.items() if key in k or key in v["title"].lower()]
    if len(matches) == 1:
        return {"success": True, "topic": matches[0], **RUNBOOKS[matches[0]]}
    return {"success": False, "error": f"No runbook named {topic!r}.", "available": list(RUNBOOKS)}
