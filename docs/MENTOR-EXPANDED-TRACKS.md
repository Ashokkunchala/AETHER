# AETHER expanded scenario mentor

The existing deeper mentor now has36 objective scenario lessons across12 tracks, three gated stages each. It adds24 lessons without replacing existing progress, starter checkpoints, practice projects or command boundaries.

| Track | Three scenario stages | Reference read for this addition |
| --- | --- | --- |
| Frontend | Derived state; user-event effects; external synchronization | https://react.dev/learn/you-might-not-need-an-effect |
| TypeScript | Narrowing; truthiness/empty values; exhaustive tagged unions | https://www.typescriptlang.org/docs/handbook/2/narrowing.html |
| CI/CD | Untrusted input; immutable action identity; privileged trigger boundaries | https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions |
| Terraform | Backend lock support; failed lock acquisition; force-unlock review | https://developer.hashicorp.com/terraform/language/state/locking |
| Linux | Process start/readiness; exec/notify contracts; reload completion | https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html |
| Observability | Trace/span identity; overlapping timings; asynchronous work | https://opentelemetry.io/docs/concepts/signals/traces/ |
| AI safety | Retrieved-content trust; least-privilege tools; output/evidence review | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ |
| Security | Credential lifecycle; rotation verification; dynamic credential exposure | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html |

The pre-existing Python, backend/PostgreSQL, Kubernetes and AWS tracks remain. Sources were read during development on November17,2026. Source links support the teaching topics; the lessons are AETHER's bounded practice material, not source-owner endorsements, official courses or exam guarantees. Live references can change.

## Use the existing mentor workflow

Ask the tool-enabled AETHER interface for `mentor_deep_catalog`, choose an exact lesson ID, then use `mentor_deep_start`. Examples: `frontend-1`, `typescript-1`, `cicd-1`, `terraform-1`, `linux-1`, `observability-1`, `ai-safety-1`, `security-1`. Subsequent stages unlock through the existing consecutive objective-checkpoint pass rule. Existing lesson IDs do not change.

Each lesson gives a scenario, teaching notes, randomized multi-decision choices, a fictional/offline lab task and its source. Submit the selected choice indexes and your explanation through `mentor_deep_submit`. The engine objectively compares the declared decisions, persists attempts/weak areas and schedules its existing spaced-review suggestions. The explanation is retained for self-review but is **not automatically graded**. Repeated correct choices are not mastery, attendance or proof a lab was performed.

To list catalog metadata without provider access or initializing progress, run locally from the reviewed source environment:

```powershell
.\.venv\Scripts\python.exe -B -c "import json; from jarvis.mentor_deep import DeepMentor; print(json.dumps(DeepMentor.catalog(), indent=2))"
```

Starting/submitting a lesson writes the existing local mentor database; progress/retention/clear behavior is unchanged. The existing stop and clear-confirmation rules apply. Nothing in a lesson approves a real system action. Labs are paper/fake/local-example exercises, not automatically executed scripts. No compiler, shell, cloud connection, CI dispatch, state unlock, key rotation, provider send, deployment or live exploit test is run by the mentor.

## What this does not finish

These are deeper scenario checkpoints, not a full beginner-to-expert curriculum, certification preparation for every named tool/cloud, a coding sandbox, free-text evaluator, real lab runner, teacher accreditation or evidence of learning outcomes. Broader Azure/GCP/CloudFormation/GitLab/Jenkins/ELK/MCP and framework-specific advanced curricula remain partial in the overall blueprint. Real command practice needs its own exact trusted project/environment/authority; do not use generic shell permission to imply automatic lab safety.

Regression tests traverse every track/stage, prerequisites, randomized objective feedback, persisted weak-area state, duplicate/expired submission rejection and atomic races. Added catalog tests cover dynamic exact IDs, malformed IDs, hyphenated track IDs, complete scenario schemas and source presence. These tests prove engine/content structure, not pedagogical effectiveness or real-world skill.
