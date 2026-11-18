# AETHER supplied IAM policy pattern review

The existing `review_iam_policy(policy_json)` tool now validates bounded input
shapes instead of silently skipping malformed statements. Its name and established
success/files_scanned/counts/findings response fields remain. Findings keep
existing rule IDs, but messages describe patterns rather than final permissions.
New counts describe Allow/Deny statements and condition blocks. They are not
permission counts. This change does not attach, edit or fetch any policy.

## Supported input, not an AWS validator

A policy object or JSON text, at most 512 KB with 1-500 statement objects. Top
level fields: Version, Id, Statement. Supported language versions, if present,
are 2012-10-17 and 2008-10-17. Every statement needs an exact Allow/Deny Effect,
exactly one Action/NotAction and a resource scope or principal. The reviewer
accepts a bounded subset of string/list principal/resource/action/condition
shapes; unknown fields or unsupported shapes fail the whole review, not a
partial success. Resource/NotResource and Principal/NotPrincipal pairs cannot
coexist. Trust-policy-shaped input without Resource is accepted with a principal,
but the tool does not know which policy type the owner intended.

Duplicate JSON keys, non-finite numbers, malformed/null/empty action lists,
invalid statement rows, oversized data and unsupported condition shapes are
refused. Arrays/maps are bounded. Condition values support scalar strings,
numbers and booleans, not null or nested objects. This is deliberately narrower
than every possible AWS policy document. A refusal is not proof AWS would reject
the policy. Success is not proof AWS would accept it: action/service/principal/
ARN existence, per-policy-type grammar, condition/operator validity, quotas and
resource-level support are not checked. No URL-decoded policy documents are
silently decoded. Supply the intended JSON policy document, not an encoded blob
or a get-policy-version response envelope.

## Review patterns and meaning

- All-action/service-wide/partial action wildcards, Resource star and PassRole-
  capable patterns are review signals. Some actions require Resource star;
  this tool does not know whether a particular star is excessive.
- Allow with NotAction covers unlisted *applicable* actions within the statement
  scope, not automatically every AWS action. Allow with NotResource or
  NotPrincipal uses complement scope and is flagged for human review.
- All-principals wildcard in an Allow is flagged even with Condition present.
  A condition may restrict it, but presence is not proof of a safe restriction.
  Findings do not say the resource is actually public.
- Deny statements are shape-checked, counted and left unanalyzed. They do not
  subtract patterns from the reported Allow findings. The reviewer does not
  resolve policy interactions or evaluate conditions/request context.
- IAM action comparisons used for the named checks are case-insensitive. No
  wildcard expansion, service-action catalogue or effective permission engine
  is provided. Exact supported pattern checks are not every escalation path.

Effective permissions remain unverified. Explicit denies, applicable identity/
resource policies, permissions boundaries, session policies, SCPs/RCPs, service
controls and the request context can change the result. No finding means only
no selected pattern was found, never secure, private or least privilege.

Raw Sid, action/resource/principal/condition values and policy IDs are not echoed
in findings or errors. Findings refer to Statement[index] only. This reduces
accidental disclosure and instruction-like text in model output; it does not
make the caller's own pasted policy private from its conversation. The reviewer
itself performs no network/model/AWS/API call or credential read. It is SAFE in
the existing desktop registry and stays available after emergency stop. No
runtime AWS allowlist, provider integration, consent scope or execution path
outside this reviewer is changed.

Tests use synthetic policies: bounded/malformed input, duplicate keys, no skipped
rows, conditions, Allow/Deny, trust-shaped input, NotAction applicability,
complement patterns, case-insensitive actions, private-value omission and the
existing SAFE registry invocation. No live IAM validation, policy simulation,
attachment or actual AWS permission test was performed.

Official AWS sources checked November 16, 2026:
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notaction.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_grammar.html
