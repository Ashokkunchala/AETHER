# AETHER optional signed GitHub Actions failure reports

This is a disabled-by-default inbound adapter, not a deployment, GitHub account
connection, automatic workflow inspection or verified notification delivery.
It accepts a narrowly scoped signed workflow_run report and adds one safe summary
to the existing local authenticated notification inbox. Windows/Android polling
can display that inbox when separately enabled, reachable and permitted by the OS.
No GitHub API call, log download, model analysis, external message, restart, retry,
workflow dispatch or other remediation is performed by this adapter.

## Configuration and reachability

The endpoint is POST /api/integrations/github/actions-webhook in both HTTP apps.
It uses HMAC authentication, not the ordinary API bearer token. Without both of
these local server settings it returns 503 and stores nothing:

- GITHUB_ALERT_WEBHOOK_SECRET: a dedicated random secret of 32-1024 characters,
  kept outside source, chat and screenshots. Never reuse an API/provider token.
- GITHUB_ALERT_REPOSITORIES: exact numeric repository ID and owner/repo map, for
  example `12345=example/project;67890=example/another`. These are fictional
  format examples, not verified repositories or authorization. Maximum 50.

The owner must verify actual repository IDs/names and choose which reports may
appear on their paired devices. No repository/account/webhook was created or
connected during development. Rotating the secret, editing the map or clearing
settings requires local operator control, not an unauthenticated HTTP setter.
Restart the server to apply changed cached settings. Empty either setting to
disable. Existing inbox entries/receipts remain; disabling is not deletion.

A localhost-only backend cannot receive GitHub's hosted webhook deliveries.
Do not open a public port/tunnel, deploy or register a webhook simply to make this
feature run. A reviewed inbound HTTPS architecture, network access controls,
GitHub repository webhook configuration and current provider policies are separate
approval/setup work. Existing local per-process IP limits are not distributed
DoS protection. A receipt response is not a promise to meet GitHub's delivery
response deadline. Missed GitHub deliveries do not automatically retry through
this adapter; explicit redelivery and alert health monitoring are not automated.

## Verification and accepted event scope

- Read the exact raw body, at most 262144 bytes. The shared API middleware also
  applies its 1 MiB request cap. Require X-Hub-Signature-256 with lowercase
  `sha256=` hex and compare SHA256 HMAC in constant time before parsing JSON.
  SHA1 is not accepted. A valid signature proves possession of the configured
  secret and body integrity, not that arbitrary text is an authorized instruction.
- Require a GUID-shaped X-GitHub-Delivery and workflow_run event with completed
  action/status, exact configured repository numeric ID and case-insensitive
  full-name match, positive numeric run ID/attempt and an exact HTTPS GitHub run
  URL from the signed payload. No enterprise/custom hosts or URL query/fragment.
- Only failure, timed_out and startup_failure conclusions enqueue. Success,
  cancelled, skipped, neutral, action_required, unknown/null conclusions and
  other events/actions are ignored. This is not all possible CI attention states.
- Require an explicit UTC seconds timestamp updated_at, no older than 24 hours
  or more than five minutes ahead of the local clock. Old/future reports are
  ignored, not treated as current failures. Clock skew and late/redelivered
  events can therefore miss alerts. Correct server time is required.
- Malformed UTF-8/JSON, duplicate JSON keys, nonfinite values, out-of-scope IDs,
  incomplete runs and unexpected URLs fail without enqueue. Free-form workflow,
  branch, commit, actor, log/step output and arbitrary outside instructions are
  never included, fetched, interpreted or executed.

The summary uses only locally configured repository name, bounded numeric run
identity/attempt, fixed conclusion vocabulary, timestamp and the checked URL.
It says "Signed webhook reported" and "Historical report", not a live-health,
root-cause, read-receipt or successful-device-delivery claim. A run may already
have changed or succeeded on a later attempt. No automatic current-status lookup,
resolution notice, run cancellation or root-cause analysis is added.

## Replay, storage and delivery limits

A local SQLite transaction claims both repository/run/attempt and a hashed
case-normalized delivery ID together with notification insertion. Replays using
a different unsigned delivery header still cannot create a second notice for the
same run attempt. GitHub redelivery uses the same delivery ID. Concurrent duplicate
reports enqueue at most once. Failed insertion rolls back the claim and notice.
An unsuccessful storage operation returns 503, never delivery success.

Receipts retain numeric repository/run/attempt, delivery hash, receipt time and
notification ID, not the full payload, secret, headers, log text or raw delivery
identifier. Existing notification rows retain the bounded summary/URL. The route
does not add a private per-repository recipient model: existing authorized inbox
clients may see every queued summary, and OS notifications can show content on
lock screens. Configure only intended repositories and device permissions.

At 10000 receipts, new alerts fail closed with 503 until the operator reviews
retention; old receipts are never automatically deleted to make replay possible.
There is no automatic receipt cleanup/export/settings UI yet. Other local code
with database access can modify these rows, so this is not a hostile-local-user
boundary. Existing notification read/clear/backup behavior remains separate.

## Evidence and remaining acceptance

Synthetic signed payload, temporary-database and source/API tests check valid,
wrong/tampered signatures; exact repository/run scope; stale/future events;
ignored actions/conclusions; malformed JSON; duplicate-key/nonfinite input;
wrong URL/body size; duplicate/concurrent delivery; rollback/capacity; disable/
reenable replay behavior; and route presence in both apps. No live GitHub webhook,
real repository setting, deployment, external endpoint or owner device was used.
Actual GitHub delivery, HTTPS/reverse-proxy setup, receiver availability, paired
client polling and OS notification timing remain unverified. An enqueued local
row does not prove a phone/laptop displayed anything. This adapter alone does
not complete the broader proactive/remote-control/SRE blueprint.

Official sources checked November 17, 2026:
- https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_run
- https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
