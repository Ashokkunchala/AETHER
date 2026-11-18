# AETHER typed cloud / Kubernetes / CI lifecycle design

Status: executable proposal validation and pure protocol simulation, **no effect adapters**. This is an approval-gated design stage, not live AWS management, Kubernetes scaling, GitHub workflow control or deployment completion. No account, cluster, machine, provider or paid resource was changed to develop it.

The `design_lifecycle_change` tool is registered in the existing AETHER tool registry. It accepts a single closed JSON object, validates an exact target and computes an order-independent SHA-256 digest of the supplied scope. It returns operation-specific live checks, approval binding requirements and the proposed state graph. Its mode is always `design_only`; execution, authority, current-state verification, cost verification and external-outcome verification remain false. It never records an approval or creates an execution receipt. A digest detects changes in supplied bytes; it does not prove identity, ownership, provenance or safety.

## Runtime addendum

The separate [four-capability follow-up](FOUR-CAPABILITIES.md) adds a disabled
local TTY runtime, durable approval/claim/reconciliation and typed EC2/Kubernetes
SDK drivers tested against fakes. GitHub has only an injected typed transport,
not live HTTP. This original design tool and simulator remain design-only and
cannot create runtime approvals. The addendum does not retrofit generic tools,
grant actual-target authority or claim provider acceptance.

## Supported proposal shapes

All keys shown are required, and extra keys are refused. No caller `approved`, approval ID, raw CLI args, shell, credentials, arbitrary URLs, wildcard targets, force options or workflow inputs are accepted. Keep input within 8 KiB. Only the narrow shown operations are supported; destroy, delete, terminate, rollout restart/rollback, Helm, ECK, Terraform apply and CloudFormation execution are not included.

### EC2 start / stop

```json
{"operation":"ec2_stop","account_id":"123456789012","partition":"aws","region":"ap-south-1","profile":"sandbox","instance_id":"i-0123456789abcdef0","expected_state":"running"}
```

For `ec2_start`, expected state must instead be `stopped`. One exact modern 17-hex instance ID is supported. Legacy short IDs, no-op/transient states and partition/region-family mismatch are refused. Region syntax validation is not region availability or an account lookup. Profile is only a supplied label; its current credentials are not read.

Before a future adapter could be enabled, live account/partition/region/instance identity and EBS root support must be checked. Review workload outage, stop protection, instance-store data, RAM, attached resources, public-address changes and current costs. Instance-store data may be erased by stop. Starting may incur charges; stopping does not eliminate EBS or all other charges. A start after stop is not a safe data recovery/rollback operation. Force, skip-OS-shutdown, hibernation and termination variants are excluded. No AWS DryRun is performed; even a dry run would require approved account access.

### Kubernetes deployment scaling

```json
{"operation":"k8s_scale","context":"dev-cluster","cluster_uid":"cluster-1","cluster_ca_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","namespace":"dev","deployment":"web","deployment_uid":"deployment-1","resource_version":"101","current_replicas":2,"target_replicas":3,"hpa_state":"absent"}
```

Only a single named Deployment is designed, with replicas 0-1000 and a non-no-op desired count. `hpa_state` is `absent`, `present` or `unknown`, all still supplied/unverified. Present or unknown HPA/controller ownership blocks future execution; an absent claim also requires a live check. The cluster UID must be a future adapter's documented stable cluster binding, not a guessed globally standardized cluster UID API field. The CA fingerprint alone is insufficient to identify a shared cluster and does not authenticate a context.

A future adapter must resolve the live context to an authorized cluster identity, CA, namespace and exact Deployment UID. Fresh resourceVersion and current replicas must match server-checked concurrency preconditions. Drift invalidates the proposal and approval, not an excuse to retry against a newer version. Capacity/quota, autoscaler ownership, cost and workload effects need review. Scale-to-zero is an explicit outage risk, not a harmless small integer. Reaching desired replicas alone does not verify ready replicas, application health or SLOs. Scaling back needs a new plan and owner approval.

### GitHub no-input workflow dispatch

```json
{"operation":"github_dispatch","repository_id":1234,"owner":"example","repository":"demo","workflow_id":5,"ref":"reviewed-build","resolved_commit_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","workflow_blob_sha":"cccccccccccccccccccccccccccccccccccccccc"}
```

The repository and workflow numeric IDs bind the desired target, while owner/name are supplied human-readable cross-checks. `ref` is a narrow supported branch/tag name, not arbitrary shell syntax or an execution guarantee. The resolved commit and workflow blob hashes must be checked live alongside the default-branch workflow_dispatch requirement. A branch/tag ref can move between review and submit; the provider's ref parameter is not an immutable commit lock. Dispatch stays blocked until a reviewed strategy can address that race.

Even without inputs, a workflow can execute arbitrary code, use default inputs, access secrets, consume runner/artifact budget, call reusable workflows, deploy or send messages. A future adapter must inspect the complete reviewed workflow/dependency scope, permissions, environments and defaults. Only a reviewed no-input workflow is considered by this design. Omitted inputs are not evidence that no defaults/effects exist. The owner must approve minutes/storage costs and any external effects separately. Provider acceptance must be correlated with the actual returned run identity and then checked for an outcome; acceptance is not success. Unknown outcomes are reconciled before any new request, never blindly retried.

## Proposed approval protocol

The graph returned by the tool is a design, not a live approval store:

1. Draft exact scope, with every supplied observation marked unverified.
2. Resolve live requester/account/connection/target/artifact identity and permission. Collect fresh preflight state and conflict checks. Review cost, audience, outage, data-loss and undo limits.
3. Obtain explicit owner approval bound to requester credential hash/device, connection generation, canonical scope/artifact digest, preflight evidence digest, short expiry and exact cost/effect limits. The proposed 120-second TTL is a design default, not an issued approval or an actual expiration timestamp.
4. Revalidate active credential, revocation, stop, expiry, identity, scope and live preconditions at dispatch entry. A missing safety store fails closed. Drift needs a new plan and new approval.
5. Atomically claim once, then call exactly one typed adapter. No shell, generic CLI fallback, automatic broadening or automatic retry. A process crash or timeout after claim leaves the outcome unknown until reconciled.
6. Verify the external result against the same identity/target and record evidence. Distinguish provider acceptance, operation completion and application health. Only verified external evidence can justify a success claim.

The pure `simulate_lifecycle` helper checks hypothetical event traces in tests. It always returns `simulation_only=true`, `dispatch_count=0`, `execution_authorized=false` and `external_outcome_verified=false`, even when its hypothetical state is `verified`. Caller-supplied `approval_verified` labels are only simulation events, not owner authority. This helper is not a registered effect tool and cannot grant permission.

Expiry, denial, stop, revocation, preflight failure and drift are terminal before dispatch. They never revive automatically. Once dispatch has begun, stop/revoke/cancel produce `cancellation_requested`, not proof that the remote work was killed. The adapter must distinguish a verified no-effect outcome from an effect that needs verification, or an unknown outcome. No undo/recall or provider-wide atomicity is promised. Unknown outcomes have no retry transition.

## Integration boundary and remaining work

The existing `aws_change`, terminal and provider tools retain their own policies. This design does not retrofit their execution paths, authorize them, weaken confirmation or make the older generic interface equivalent to typed execution. No approved event can route from this module to them. This module imports no subprocess, network, provider, credential, database or filesystem adapter.

Still required before any typed live operation: per-adapter implementation, persistent authenticated approval/claim/result store, live identity and artifact resolver, permission/cost checks, exact owner approval, request-local safety guard, reconciliation, cancellation semantics, provider sandbox tests and real account acceptance under separate authority. A user permitting source development has not permitted deploying, scaling, starting/stopping resources, triggering a workflow or spending money. The normal registry confirmation policy is not a substitute for that authority.

Tests validate closed shapes, exact identity fields, numeric limits, duplicate/nonfinite/oversize refusal, digest sensitivity, registry invocation, all reachable protocol states, no gate-skipping, no terminal resurrection, no unknown-outcome retry and zero effect dispatch. They establish the proposal/simulation behavior only, not live protocol enforcement or actual provider results.

## References

- EC2 stop/start and data-loss limits: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html
- EC2 states and billing: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
- Scale preconditions and versions: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_scale/
- Workflow dispatch parameters and permissions: https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28
- Manual dispatch/default-branch requirement: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
