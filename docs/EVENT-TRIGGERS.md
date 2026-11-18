# Event-triggered read-only plans

A trigger rule watches the bounded local runtime-event history. When a new
event matches the rule, the referenced saved read-only plan runs once. Rules
are checked roughly once a minute by the existing backend scheduler while it
runs.

## Tools

- `trigger_configure(rule_id, category, plan_id, action?, tool?,
  cooldown_seconds=3600, enabled=false)` creates or updates a rule. New rules
  are disabled; enabling is an explicit opt-in.
- `trigger_rules()` lists rules with filters, cooldowns and last fired time.
- `trigger_delete(rule_id)` removes a rule without touching saved plans.

## How matching works

- Categories are the runtime-history categories: `provider`, `tool`, `task`,
  `error`. Optional `action` and `tool` filters must match exactly.
- The first scheduler tick after setup starts from the newest known event, so
  old history never retroactively fires a fresh rule.
- Matching is at-most-once: the event cursor advances before a plan runs, so
  a crash or a failing plan does not retry the same events.
- Each rule fires at most once per cooldown window (300-86400 seconds, default
  one hour), even when many events match in one pass.
- A triggered run is recorded as a `trigger_fire` runtime event whose success
  reflects whether the plan completed all steps.

## Boundaries

- Only saved read-only plans (see [RESUMABLE-PLANS.md](RESUMABLE-PLANS.md))
  can be referenced. A trigger can never start a mutating or
  confirmation-gated action, and approvals never carry into a triggered run.
- At most 20 rules. A rule watching the `task` category can react to plan
  step events, including its own; the cooldown is the only frequency bound.
- Delivery is best-effort while the backend runs. This is local automation
  for read-only checkups, not a scheduler for mutating work, a notification
  channel or a guarantee of execution.

## Verification

Focused tests cover rule validation and bounds, cursor initialization without
retroactive firing, matching on category/action/tool filters, disabled rules,
one run per matching pass, cooldown blocking and expiry, failure recording
without same-event retries, and the 20-rule cap.
