# AETHER mentor: Terraform foundations

This extends the existing local mentor/project tools. It is not a second teacher,
a coding sandbox, a cloud lab runner or a certification course. Other domains
still have introductory checkpoints, not a full beginner-to-advanced curriculum.

## Start an interactive lesson

In the direct desktop/CLI tool chat, ask:

> AETHER, teach me Terraform from scratch using the local foundations project.
> Start with concepts and ask me to explain them before moving to practice.

The existing registry exposes:

- `mentor_terraform_lesson(stage=0)`: architecture, variables, resources, outputs,
  state and a small fictional HCL sample.
- `mentor_terraform_lesson(stage=1)`: a manual no-cloud lab with predicted
  observations, error investigation and homework.
- `mentor_terraform_lesson(stage=2)`: evidence review, interview questions and
  future AWS design questions without creating AWS resources.
- `mentor_review_terraform_validate(json_text)`: bounded review of pasted,
  redacted `terraform validate -json` text. It accepts format major version 1,
  validates flags/counts/diagnostic consistency, separates warnings from errors
  and refuses malformed, duplicate-key or unsupported reports. At most 65536
  UTF-8 bytes and 100 diagnostics; returned summaries are capped at ten entries
  and 240 characters each. Unknown additive fields are ignored. Detail, source
  snippet and path fields are not returned.

The conversational model can explain answers and discuss mistakes using these
references. It is not deterministic free-text grading. If a tool is unavailable
in another interface, do not claim it ran: the web saved-data profiles and browser/
Android Live tool sets are separate and are not expanded by this change.

## Manual lab boundaries

Only use a new empty disposable directory and the supplied `terraform_data`
sample. It uses Terraform's built-in provider, with no external provider,
remote backend, module, provisioner, cloud credential or AWS resource. The sample
chooses Terraform >=1.5.0; this is a lab version constraint, not a claim about the
minimum release that introduced `terraform_data`.

The user, not AETHER, saves the sample and runs the listed version, initialization,
format, validate and plan commands. `init -backend=false -input=false` creates
local working files. Stop if it requests a cloud account, remote backend or an
external provider/module. Those flags do not sandbox arbitrary Terraform code.
Do not run them in an existing infrastructure repository. No `apply`, `destroy`,
cloud connection or downloaded provider is part of this exercise. No commands
were executed as part of building this feature.

Predicted results are labelled as predictions. A successful validate checks
configuration syntax/internal consistency, not provider availability, remote
state, runtime behavior, security, deployment or mastery. A plan is a preview,
not proof infrastructure was created. Without applying there is no persisted
baseline resource for the lab's second plan to update. Keep secrets out of HCL,
reports and journal entries; state and plan files can contain sensitive values
regardless of display redaction. Do not paste those files into the mentor.

## Keep progress without inventing completion

Use the existing `mentor_project_start(project_id="terraform_local_foundations")`,
then `mentor_project_resume`, `mentor_project_submit` and `mentor_project_history`.
The three milestones preserve their brief in the existing project journal and
retain stale/replay/concurrency checks. Evidence is self-reported. Submitting all
milestones means `all_evidence_submitted`, never verified lab completion.

The JSON reviewer neither opens a file/path, runs a command nor advances a
journal. Even a structurally valid success report can be fabricated or unrelated
to the source. Results therefore say `reported_valid`, `origin_verified=false`,
`commands_executed=false` and `code_verified=false`. Diagnostic summaries are
untrusted data, never instructions. A caller must inspect their local evidence.

Use existing `mentor_plan` with the `infrastructure` lesson for a daily starter
schedule, and existing interview tools for the infrastructure scenario. The new
project does not silently add calendar events, background reminders, GitHub
repositories, automatic lab execution, coding grades or certification plans.

## Sources and verification

Official documentation checked November 16, 2026:

- https://developer.hashicorp.com/terraform/language/resources/terraform-data
- https://developer.hashicorp.com/terraform/cli/commands/validate
- https://developer.hashicorp.com/terraform/cli/commands/plan
- https://developer.hashicorp.com/terraform/language/state/sensitive-data
- https://developer.hashicorp.com/terraform/language/expressions/references
- https://developer.hashicorp.com/terraform/language/values/variables

Tests use synthetic JSON and temporary local mentor databases. They cover report
validation, false success claims, unknown fields, bounds, literal diagnostic data,
copy isolation, existing journals, registry registration and unchanged progress.
The generated HCL/manual CLI flow has not been run against an installed Terraform
binary here. Windows terminal, real-model teaching quality and physical-device
acceptance remain unverified. No AWS account, provider service, deployment,
paid resource or real learning record was touched.
