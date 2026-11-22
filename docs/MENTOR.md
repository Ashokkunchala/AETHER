# Mentor: your personal technology trainer

AETHER's mentor experience: an interactive teacher with lessons, objective
checkpoints, study plans, practice interviews and code review. Everything is
local-first. AETHER never executes lab commands, contacts a certification
provider or claims a score it did not objectively compute.

## Learning subjects

All twelve requested domains exist as starter lessons with sourced notes,
a safe manual practice task and an objective checkpoint (`mentor_catalog`):

| Requested domain | Lesson ID |
| --- | --- |
| Programming (Python, JavaScript, TypeScript) | `programming` plus dedicated code-review tools for Python, JavaScript, TypeScript, HTML and shell |
| Backend (FastAPI, REST APIs, PostgreSQL) | `backend` |
| Frontend (React, HTML, CSS) | `frontend` plus a source-linked React scenario track |
| DevOps (CI/CD, Jenkins, GitHub Actions, GitLab) | `cicd` plus a CI/CD security scenario track |
| Cloud (AWS, Azure, GCP) | `cloud` |
| Infrastructure (Terraform, CloudFormation) | `infrastructure` plus a Terraform scenario track and manual Terraform practice |
| Containers (Docker, Kubernetes, EKS, ECS) | `containers` |
| Linux (shell scripting, administration) | `linux` plus shell command review |
| Observability (ELK, Grafana, Prometheus) | `observability` |
| AI (LLMs, RAG, agents, MCP) | `ai` |
| Architecture (distributed systems, microservices) | `systems` |
| Security (IAM, secrets, vulnerability management) | `security` |

## Teaching abilities

| Ability | Where it lives |
| --- | --- |
| Explain concepts beginner to advanced | Lesson notes (`mentor_lesson`) plus the mentor personality mode, which teaches in small steps and checks understanding |
| Daily learning schedules | `mentor_plan`, `mentor_reschedule_preview`, `mentor_reschedule_session` - one local session per day, no external calendar |
| Real-world examples | Source-linked scenario tracks (`mentor_deep`, `aether/mentor_tracks.py`) |
| Hands-on labs | Every lesson and scenario ships a safe manual practice task. Labs are plan-only: AETHER guides, you run commands in your own terminal |
| Open a terminal and guide practical exercises | Guided practice text per lesson; AETHER's terminal interface can walk an exercise step by step. AETHER does not execute lab commands itself |
| Check commands and expected outputs | Terraform `validate` JSON review (`mentor_terraform`); shell command review; expected outcomes are described in each practice task |
| Quizzes and coding tests | `mentor_quiz` objective checkpoints; deterministic rubric signals for free-text practice (`mentor_rubric`) |
| Evaluate answers | `mentor_submit` scores the objective checkpoint and explains the correct choice |
| Identify weak areas | `mentor_progress` lists failed checkpoints as weak areas |
| Interview questions | One interview question per lesson (`mentor_interview_start`) |
| Mock technical interviews | Resumable interview sessions with stored answers and reference concepts for feedback (`mentor_interview_*`) |
| Track daily learning progress | `mentor_progress` plus `mentor_daily_activity` for per-day checkpoint attempts |
| Create GitHub practice projects | `mentor_projects`: local project briefs with milestone journals |
| Review code and explain mistakes | `mentor_python`, `mentor_javascript_review`, `mentor_typescript_review`, `mentor_html_review`, `mentor_shell_review` |
| Certification study plans | `mentor_cert_catalog` and `mentor_cert_plan` (this branch): dated outlines for AWS CCP/SAA, Azure AZ-104, GCP ACE, CKA and Terraform Associate mapped to the local lessons, with an optional persist step |

## The Terraform example, end to end

"Aether, teach me Terraform from scratch":

1. `mentor_lesson infrastructure` explains plan/apply and state safety, with a source link.
2. The Terraform scenario track (three levels) teaches state locking and related decisions with sourced scenarios.
3. `mentor_terraform` manual practice gives a bounded exercise; you run commands
   locally and paste `terraform validate -json` output for review.
4. `mentor_quiz infrastructure` + `mentor_submit` check understanding objectively.
5. `mentor_cert_plan terraform-associate` lays out a dated study outline.
6. `mentor_interview_start` runs a practice interview on the same topics.
7. Errors are explained conversationally in mentor mode; AETHER never runs
   `apply` or touches a cloud account. Any real infrastructure change requires
   your explicit approval outside the mentor flow.

## HTTP API added on this branch (read-only)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/mentor/catalog` | Twelve starter domains and lesson IDs |
| `GET /api/mentor/lessons/{id}` | Lesson notes, safe practice task, source |
| `GET /api/mentor/quiz/{id}` | Objective checkpoint question (correct choice never included) |
| `GET /api/mentor/progress` | Checkpoints, weak areas, overdue sessions |
| `GET /api/mentor/activity?start_date&end_date&timezone` | Checkpoint attempts per local day |
| `GET /api/mentor/cert-plans` | Certification outlines mapped to local lessons |

All endpoints need the device token and never change study data. Actions that
record something (quiz submissions, plan saves, interview answers) stay in the
chat tool surface with their own risk levels.

## Honest limits

- Checkpoints are objective starter checks, not mastery grading or certification.
- Free-text interview answers get reference concepts for feedback, never an invented numeric score.
- Labs never execute: no shell commands, no Terraform runs, no cloud or paid resources. "Validate JSON review" means you paste output; AETHER reviews it.
- Certification outlines are mapped to AETHER's starter lessons. Use the provider's official exam guide for the full curriculum.
