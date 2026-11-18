# AETHER resumable offline evidence workflows

A new local journal can save an owner-authored sequence of1-10 fixed offline review steps, run one freshly reviewed step at a time and resume after application restart. This is a narrow executable workflow, not unrestricted autonomous agents or an approval for live accounts, shell commands, files or production changes.

## Fixed operations

Each step has exactly `operation` and `inputs`. Only these code-owned analyzers can run:

| operation | Exact inputs |
| --- | --- |
| `terraform_plan` | `document`: supplied Terraform plan JSON object |
| `security_groups` | `document`: supplied AWS SecurityGroups export object |
| `daily_costs` | `daily`, `currency`, `complete_days`, `increase_percent`, `minimum_increase` |
| `slo_budget` | `windows`, `target_percent`, `complete_window`, `event_definition` |

The existing analyzers still validate their own evidence semantics at execution. Successful plan saving does not mean all inputs are analytically valid. Cost data needs complete consecutive daily totals; SLO data needs completed contiguous timestamped windows and an explicit event definition. Supplied claims of completeness/freshness are not independently verified. The Terraform/security-group reviews retain their documented structural/heuristic limits.

No tool/module name supplied by a model is imported or executed. No shell, command runner, plugin, browser, network/provider, AWS SDK, file-body read, deployment or credential operation is an available step. Inputs are copied finite JSON, capped at256KiB for the whole plan; outputs are separately capped at256KiB per step. Earlier outputs are not automatically injected into later inputs. No scheduling, external event trigger or notification is created.

## Use through the existing tool-enabled interface

1. Ask AETHER to prepare the exact JSON workflow for review. It needs `title` and `steps`. Use fictional/nonsecret data first. See [example](examples/offline-workflow.json). The example's group/instance IDs are not real target identities and no account is contacted.
2. `offline_workflow_create(spec)` previews title, operation list and a digest, then requires fresh confirmation to save exact supplied inputs locally. Review the actual supplied JSON as well, not only the digest. Saving does not run an analyzer.
3. `offline_workflow_status(workflow_id)` gives title, workflow digest, step positions, input digests and states, not raw inputs/results. Indexes are zero-based. A pending step after completed predecessors is resumable.
4. To run one step, call `offline_workflow_run_next(workflow_id, expected_digest, expected_position, expected_input_digest)` using the exact current status values for the next pending position. A fresh confirmation names the exact step and digests. Stale/different digests, a different position, an earlier incomplete step or a competing claim are refused.
5. The result includes that one analyzer output and a durable state. It never starts the next step automatically. To continue later, get status again and review the next step separately.
6. `offline_workflow_result(workflow_id, position)` retrieves a stored result after fresh confirmation. It is historical supplied-data output, not a fresh live check, and may include private supplied identifiers. `offline_workflow_cancel(workflow_id)` freshly confirms blocking pending steps and suppressing a running result when it returns. It does not delete prior completed outputs or terminate processes.

The existing global auto/always-approve options cannot bypass create/run/result/cancel review. The optional owner policy must explicitly allowlist these new tools; they do not grant themselves a role. The emergency stop blocks new state-changing registry actions, is checked within create/run and suppresses a result when noticed after analysis. It cannot undo a previously returned result or interrupt Python/OS work already executing.

## Durable state and races

SQLite atomically claims one step before analysis. Concurrent runners cannot both claim it. A normal analyzer exception marks the step failed and returns a generic error without reflecting exception/input text. Later steps stay blocked; no automatic retry occurs. A process crash or journal failure after claim leaves `running`, which means unresolved, not success. Reopening does not reset or replay it. This version has no force-reset/retry operation. Inspect the saved evidence and create a separately reviewed corrected workflow if necessary; do not treat unresolved as an invitation to repeat a live effect. There are no live effects in this implementation.

Completed output is published only after its local result state commits. Cancellation racing with an analyzer discards that result and prevents pending steps; already returned output cannot be recalled. Cancellation retains prior completed evidence. A stop/journal failure can leave a claim unresolved, which requires review rather than a fabricated success.

## Local data and limits

Journal default: `~/.aether/offline-workflows.db`, override with owner-controlled `AETHER_OFFLINE_WORKFLOW_DB`. Creating the store can initialize its folder/schema. New POSIX journal files are created mode0600; Windows inherits directory ACLs. This is not encryption, secure erasure, a retention service or tamper-proof audit. Keep the folder private. No clear/delete operation is added. Existing backups/processes may retain data; do not include secrets. A same-user program can edit the journal and paths can race, so this is not an OS sandbox or per-device authorization.

Inputs persist locally, including supplied resource identifiers. Results can enter the configured AI through the existing chat tool loop. Use only evidence approved for that workflow. No provider send was performed during development. The engine is local single-journal orchestration, not distributed execution, arbitrary effect workflows, dependency DAGs, dynamic planning, remote cancellation, automatic remediation or general multi-agent autonomy.

Tests cover exact schemas/limits, unsupported execution refusal, immutable copied inputs, restart/resume, review digest/position binding, single atomic claim, failed/crashed-step no-replay, stop/cancel result suppression, persisted result retrieval and all four real offline analyzer paths. Actual owner-device/runtime acceptance remains unverified.
