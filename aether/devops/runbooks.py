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
    "api-5xx-investigation": {
        "title": "API returns 500/502/503 errors",
        "checks": [
            "Normalize authorized log windows with triage_log; read the peak error minute first",
            "Check for a deploy_event in the same scope shortly before the first error (review_incident_evidence)",
            "Correlate metric and trace windows with compare_telemetry_windows before blaming a layer",
            "502/503: check endpoints and targets (review_kubernetes_endpoints, review_k8s_service_endpoints_json); 500 with tracebacks: application errors",
            "review_incident_evidence for a timeline and correlation-only candidates; never restart or roll back without approval",
        ],
        "fixes": ["Roll back a correlated change only with explicit approval", "Scale or restart only with explicit approval", "Add the missing evidence first when candidates are weak"],
    },
    "deploy-rollback-decision": {
        "title": "Decide whether to roll back a deployment",
        "checks": [
            "Confirm errors started after the deploy and share its scope (review_kubernetes_deployments on a supplied snapshot)",
            "Rule out a separate cause: dependency outage, config change, traffic spike",
            "Confirm the previous revision is still available and its own health was clean",
            "Rollback is a change: build the exact command, show it, and get explicit approval before running",
        ],
        "fixes": ["kubectl rollout undo / previous task-definition update only after approval", "Record the decision and evidence in the incident summary"],
    },
    "node-high-memory": {
        "title": "Abnormal CPU or memory on a node or workload",
        "checks": [
            "review_kubernetes_nodes on a supplied node snapshot for pressure conditions",
            "Identify the top consumers before acting; a pressure condition is not a culprit",
            "Check for a recent deploy or traffic change that raised baseline usage",
            "OOMKilled in a container: compare its limit with real usage before raising it",
        ],
        "fixes": ["Raise limits/requests after reviewing usage", "Cordon/drain a node only with explicit approval", "Fix the leak rather than growing the box forever"],
    },
    "ci-publish-checklist": {
        "title": "Publish artifacts or deploy from CI safely",
        "checks": [
            "Immutable inputs: pinned action/image digests, exact revision, no floating tags",
            "Secrets: never echoed to logs; masked or short-lived OIDC, no static AWS keys (review_cicd flags these)",
            "Artifacts: build once, promote the same digest; never rebuild per environment",
            "Publish and deploy steps stay approval-gated; verify the published digest afterwards",
        ],
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
