# Resumable read-only plans

A saved plan is an ordered set of SAFE, read-only tool steps with explicit
dependencies. Every settled step is checkpointed in the shared local SQLite
database, so a plan interrupted by a tool failure or a process restart resumes
from its last incomplete step instead of starting over.

## Tools

- `plan_save_readonly(plan_id, tasks)` validates and stores a plan. Saving the
  same plan id with an identical definition is idempotent; a different
  definition under an existing id is rejected.
- `plan_run_readonly(plan_id)` runs or resumes the plan. Steps checkpointed as
  successful are seeded as completed and never re-executed. Failed, skipped
  and pending steps run in dependency order.
- `plan_status_readonly(plan_id)` reports per-step status and counts.
- `plan_list_readonly()` lists saved plans with per-status step counts.
- `plan_forget_readonly(plan_id)` removes one saved plan and its checkpoints.

## Boundaries

- Only SAFE tools without a confirmation requirement can be saved. Mutating or
  confirmation-gated steps stay interactive-only: an approval given before a
  restart must never silently authorize a later run.
- Step arguments are stored locally so the plan can resume. They are rejected
  when they look credential-shaped and capped at 4096 UTF-8 bytes per step;
  status, lists and runtime events never return them.
- Plans are bounded: at most 100 steps and 65536 UTF-8 bytes per plan, and at
  most 50 saved plans.
- Status and events keep the runtime-history rules: no prompts, tool
  arguments, raw errors, outputs or credentials. Step outcomes are recorded
  through the existing allow-listed runtime event history.
- Dependencies on failed steps mark dependents as skipped; a later resume
  runs them once the prerequisite succeeds. Plans with dependency cycles,
  duplicate ids or unknown dependencies are rejected before anything runs.

This is a local convenience store for read-only checkups, not a distributed
job queue, a scheduler for mutating actions, or proof that a step's earlier
result is still current.

## Verification

Focused tests cover successful runs, checkpoint persistence across fresh
connections, failure/resume without re-executing successful steps,
skip-then-run dependents, rejection of mutating/confirmation/unknown tools,
credential-shaped and oversized arguments, cycles, idempotent re-save,
argument/output hiding in status and lists, targeted forget, and the
allow-listed runtime events emitted per step.
