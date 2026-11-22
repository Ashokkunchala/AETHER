# Security and privacy manager, operating modes, and architecture

Survey of the requested security/privacy manager (part 11), the operating
modes (part 12) and the architecture/stack list against what exists on main.
Every entry names the module; limits are stated, not smoothed over.

## Part 11: security and privacy manager

| Requested | Where it exists | Limits |
| --- | --- | --- |
| Secure API key storage | `aether/secret_store.py`: native OS credential vault (Windows/macOS/SecretService), fixed supported-name set, no plaintext fallback | Legacy `.env` mode remains until the owner selects `os-keyring`; no secret-valued tools or routes |
| Encrypted phone-laptop communication | Android HTTPS client refuses cleartext; `app/core/auth.py` hashed bearer tokens | Private HTTPS/CA setup and real-device acceptance are still owner steps; the status tool says so |
| Authentication for remote commands | Per-device hashed tokens, one-use websocket tickets, session revalidation (`app/core/auth.py`, `app/core/ws_sessions.py`) | Bearer tokens are not hardware attestation |
| Role-based permissions | `aether/access_policy.py`: owner-installed local policy, exact per-tool allowlist | Off until the owner installs a policy file; local configuration, not multi-user account RBAC |
| The four permission levels (1 Read, 2 Suggest, 3 Execute, 4 Critical) | Exactly `Permission.READ/SUGGEST/EXECUTE/CRITICAL` in `aether/access_policy.py`; intrinsic tool risk can only strengthen, never weaken | Critical names (deletes, sends, calls) always need fresh explicit confirmation; no auto-approval |
| Command allowlists | Approved-app allowlist with expected SHA256 (`aether/control/approved_apps.py`), guarded-shell hard-block list, policy exact tool allowlist | Blocked commands can never be approved past |
| Audit logs | Redacted audit (`aether/security.py`) and `auth_audit` (`app/core/auth.py`) | Not tamper-proof; a compromised same-user process could alter SQLite |
| File access restrictions | Policy `paths` roots with symlink refusal and exact-argument coverage (`aether/access_policy.py`) | Only inside hardened policy mode |
| Malware and dependency scan integration | `aether/security_scans.py`: optional owner-run ClamAV single-file and pip-audit pinned-requirement scans | Nothing auto-installs, auto-scans or auto-fixes; scans run only on owner request |
| Login alerts | Master-only local audit cursor `/api/security/alerts`: invalid-token attempts, registrations, revocations, issued sessions | A reviewable feed, not push alerts; not a complete login detector |
| Session management | One-use websocket tickets with revalidation (`app/core/ws_sessions.py`) | - |
| Memory privacy controls | Memory review, correction, expiry, confirmed purge (`aether/memory/controls.py`, `app/personal_data.py`); structured categories and sensitive-content scanning on review branch feature/smart-memory | Expiry excludes future context only; backups and prior exports are separate |
| Device registration and revocation | Devices table with hashed tokens and `revoked_at` (`app/core/auth.py`) | Revocation is record-level; a leaked token already copied is a re-pairing event |
| Emergency stop | Registry emergency stop (`aether/security.py`, `security_manager_status` describes it) | Blocks not-yet-started registry writes; not an OS kill switch, rollback or provider cancellation |

`security_manager_status` (SAFE tool) returns this inventory with its limits
in one read; it is a capability inventory, not a safety attestation.

## Part 12: operating modes

All ten requested modes exist in `aether/personality_modes.py`: Personal,
Friend, Mentor, DevOps, Developer, Research, System Admin, Security, Fitness
and Emergency (plus assistant default and friend-adjacent styles: funny,
calm, motivational, teacher, storyteller, doctor health-guide).

Switching works by exact key and, added on this branch, by natural phrase:
"activate DevOps mode", "switch to friend mode", "become my Python mentor",
"activate laptop management" and "enter emergency troubleshooting mode" all
resolve through filler-word stripping and a fixed alias table. Unknown
phrases still raise; the web/brains fall back to the default mode.

Deliberate design, kept: a mode is a style/workflow overlay and never
changes what tools can do. The restriction mechanism he described lives in
the access policy's four levels, which apply in every mode. Weakening that
(modes that silently grant or remove abilities) would make authority depend
on conversation state, so it is documented rather than built.

## Architecture requirements

| Requested | Status |
| --- | --- |
| Offline basics | `aether/offline_workflows.py`; local SQLite stores work without a provider |
| Graceful fallback when internet/provider is down | `app/ai_providers.py` runs providers in order with automatic fallback and logs each fallback |
| Health checks and recovery | `aether/doctor.py` local checks |
| Background jobs | Existing backend scheduler (proactive tick, briefing schedules, reminders) |
| Persistent user-controlled memory | Local stores with review/correct/expiry/purge/export |
| Audit logs | Above |
| Independent agents with restricted tool permissions | Registry categories plus per-tool policy levels; agents see only their category's tools |

## Stack list: adopted vs not adopted

Adopted: Python + FastAPI backend; Kotlin + Compose Android companion;
SQLite first (his own config note says PostgreSQL later); GitHub Actions CI;
Docker packaging (container-build CI job); Gemini/OpenRouter/Groq provider
keys; Piper among TTS options; local agents with a private-cloud option left
to him; AWS integration is read-only and approval-gated.

Not adopted (documented, not silently swapped): PostgreSQL, pgvector and
Redis (his config says SQLite first; no migration without his word);
Tauri/Electron desktop shell (existing web UI and dashboards instead);
Prometheus/Grafana/ELK monitoring; MCP tool integration; Whisper STT (voice
input path is the existing Gemini Live client). Indian English is the
default voice; Telugu appears in conversation (friend mode guidance);
a full Telugu UI is not built.

Nothing in this document changes database engines, frameworks or deployment.
