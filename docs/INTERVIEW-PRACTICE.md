# Interview practice

Offline interview practice from a small, curated, reviewable question bank.
Everything stays on the local machine: no AI grading of answers, no uploads,
no scheduling.

## Tools (category `practice`)

| Tool | Risk | What it does |
| --- | --- | --- |
| `interview_topics` | SAFE | List topics and question counts (aws, ci-cd, docker, kubernetes, linux, terraform, monitoring, behavioral). |
| `interview_question` | LOW | Draw the next question for one topic: least-shown first, fully deterministic, no randomness. Returns self-check points to compare against after answering. |
| `interview_record` | LOW | Save a self-rating (`hard`/`shaky`/`ok`/`confident`) and optional notes for a question id. |
| `interview_progress` | SAFE | Per-topic practice counts and self-rating breakdown. Bookkeeping, not a skill score. |

## Design

- The bank lives in `aether/interview_practice.py` (`BANK`): 16 questions with
  self-check points, weighted toward DevOps/AWS/Linux/CI-CD/Kubernetes/
  Terraform plus one behavioral prompt. Extending it means editing a visible
  literal list, not tuning a model.
- Selection is deterministic (least shown, then least recently shown, then
  lowest id) so practice coverage is even and tests are stable.
- SQLite at `~/.aether/practice.db` (mode 0600, `AETHER_PRACTICE_DB`
  override). No network use at all.

## Not claimed

Answer evaluation or grading, an interview guarantee, or a complete syllabus.
Self-ratings describe how practice felt; they are not measured skill.
