# Live cloud setup path (EC2 start/stop, Kubernetes scale)

November 18, 2026. This adds an owner-run wizard that prepares the previously
disabled typed live lifecycle for one exact real target. The wizard itself still
changes nothing in any cloud account: it writes a local opt-in file and the
reviewed plan, then prints the exact follow-up commands. Every live action still
needs the owner's typed approval on a trusted local terminal within 120 seconds
of a fresh preflight, and uses the owner's own already-configured AWS profile or
kubeconfig. No credentials are read, stored or requested by this feature, and no
provider call of any kind was made while developing or testing it.

## What the wizard does

`aether setup-live-cloud` runs interactively on the owner's terminal:

1. Explains that real targets can cost money, interrupt service or lose data,
   and asks for explicit confirmation before writing anything.
2. Offers exactly three operations: `ec2_start`, `ec2_stop`, `k8s_scale` (one
   Deployment). GitHub workflow dispatch stays disabled by design; mutable ref
   review is still an open implementation gap.
3. For each exact field it prints the AWS CLI or kubectl command that produces
   the current value, so the owner copies real identifiers instead of guessing
   (account ID, region, instance ID, cluster/deployment UID, CA hash,
   resourceVersion, replica counts, HPA state).
4. Validates the whole plan through the existing typed proposal designer, shows
   the warnings and the canonical scope digest, and requires the typed phrase
   `I REVIEWED REAL TARGETS AND COSTS`.
5. Writes `~/.aether/typed-live.env` (owner-only, mode 600) with a fresh random
   connection generation and the single allowlisted scope digest, plus the
   reviewed plan at `~/.aether/typed-live-plan.json`. An existing opt-in is only
   replaced after a separate confirmation; replacing invalidates the old
   generation and digest.

## What still needs the owner, every time

The printed next steps load the opt-in into one terminal and run the existing
`python -m aether.devops.lifecycle_runtime` prepare/review/execute flow:
live preflight evidence, typed `APPROVE COST AND EFFECTS <digest>` approval,
single atomic claim, drift refusal and explicit reconciliation. Preflight reads
can incur provider request charges. The software does not enforce a dollar
budget; the owner must arrange provider budgets and spending authority
separately. Timeouts end as `outcome_unknown`, never as success or retry.

## Limits

- One exact target per opt-in. Broad requests, wildcards, raw commands and
  caller approval booleans are refused by the existing designer.
- Start/stop/scale is not application health, rollback or proof the request
  alone caused the observed state.
- Enabling requires the owner to source the env file; nothing exports it
  globally or persists it into shells, services or scheduled tasks.
- No real target was enabled, approved or executed during development. Tests
  cover plan validation, digest binding, file permissions, symlink/overwrite
  refusal and the scripted wizard flow only.

Sources: `aether/devops/live_setup.py`, `aether/devops/lifecycle_runtime.py`,
`aether/devops/lifecycle_design.py`,
[typed lifecycle design](TYPED-LIFECYCLE-DESIGN.md),
[four capabilities](FOUR-CAPABILITIES.md).
