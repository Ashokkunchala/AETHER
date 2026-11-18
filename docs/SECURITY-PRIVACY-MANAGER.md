# AETHER security and privacy manager

This is a source-level security control inventory and owner-run setup guide. It is not a claim that your phone/laptop are configured securely, that any file is malware-free, or that AETHER is ready for public/production access. No real key was saved, device registered/revoked, scanner run on your files, remote command sent or provider changed for this work. Tests use temporary stores, fake credentials and scanner stubs.

`security_manager_status` returns this capability inventory without reading secret values or changing settings. Existing functionality is preserved. The optional stronger local policy and native secret mode below are **not enabled automatically**.

## Requested controls: existing paths, additions, remaining gaps

| Request | Implemented source path | Limit that matters |
| --- | --- | --- |
| Secure API key storage | NEW `aether/secret_store.py`: opt-in native Windows Credential Locker, macOS Keychain or Linux Secret Service via `keyring`. Backend settings, main text brain provider lookups and core Gemini/ElevenLabs configuration use it. Android already stores pairing details with Keystore AES-GCM. | Default remains legacy environment/.env for compatibility. No migration/deletion of plaintext copies. Optional voice/other helpers that directly read environment variables are not all migrated. An unlocked user session/Python process can access its credentials; this is not a vault against a compromised OS. |
| Encrypted phone/laptop communication | Existing Android HTTPS-only client, server-side provider keys, private-CA setup guide and loopback backend/helper boundaries. | This change does not create TLS, open ports, bypass certificate checks or solve the pending private HTTPS bridge. Android currently trusts user-installed CAs app-wide; pinning/per-backend trust remains a gap. Physical-device acceptance remains required. |
| Remote command authentication | Existing master/device hashed bearer tokens, master-only device administration, single-use short-lived WebSocket tickets and credential revalidation. | A bearer token is not hardware identity or multi-user account isolation. No new remote execution channel is enabled. Keep backend loopback/private, never public. |
| Four permission levels/role-based permissions | NEW `aether/access_policy.py`: local configured READ, SUGGEST, EXECUTE, CRITICAL capability ceiling and exact tool allowlist, enforced at shared registry dispatch and again after review. | This is one owner-configured process policy, **not per-device/per-user backend RBAC**. Other HTTP write handlers, direct Python handlers and standalone helper processes do not inherit this policy. No policy means existing risk/confirmation behavior, not hardened roles. |
| Command allowlists | Exact registry tool names under the optional policy; shell/background-process routes and generic desktop/Android input/app-launch categories refused in this mode. Existing exact approved-app/typed lifecycle paths keep their own restrictions. | No arbitrary shell string is certified safe. A tool allowlist is not an OS sandbox or an argument-level allowlist for every command. Generic automation is refused rather than claimed to be safe. |
| Audit logs | Existing local execution approvals/audit store, authentication audit and redacted bounded runtime-event summaries. Policy denials and policy changes during review are logged. | Local administrators can edit logs. Not tamper-proof, comprehensive, encrypted or a full compliance trail. Some pre-existing records have separate retention. |
| File access restrictions | Existing document allowed roots; NEW policy supports exact absolute path arguments inside approved roots, rejects missing paths/links/outside roots and refuses uncovered arguments for generic file tools. | Strict policy is intentionally narrow: `read_file`/`file_info` with one exact `path` work; broad search, optional unmodeled arguments and most mutations stay refused. Not descriptor-based sandboxing: another local process can race/replace files. It does not confine every file reader across the repository. |
| Malware/dependency scans | NEW `aether/security_scans.py`: optional owner-reviewed ClamAV single-file and pip-audit exact-pinned-requirement adapters. Existing `review_dependency_audit` parses a supplied audit export offline. | No antivirus installed, signatures updated, automatic scan/fix/quarantine or provider effect performed. Scan availability/database freshness and native scanner behavior need owner acceptance. Dependency scan shares package names/versions with PyPI after explicit interactive review. |
| Login alerts | NEW enhanced-backend master-only `/api/security/alerts` cursor feed for recorded invalid nonempty-token attempts, device issuance/revocation and WebSocket ticket issuance. | Local event feed, not push/email alerts or proof of a human login. Missing-header/unconfigured-service cases are not a complete login detector; logging is best effort. No external notification service added. |
| Session management | Existing expiring one-use tickets, active credential checks, master rotation/device revocation, bounded audio/session duration and per-process concurrent limits. New ticket issuance events appear in the local alert feed. | Not distributed session administration, per-tenant sessions, MFA or a global logout UI. Stop/revocation cannot undo an already completed effect. |
| Memory privacy controls | Existing explicit memory storage, review/search/correction, expiry, confirmed purge/delete and separate document-root controls. | Expiry only excludes future context. Previous chats/provider sends, document indexes, exports/backups and SQLite remnants are separate; deletion is not secure disk erasure. No automatic collection consent is inferred. |
| Device registration/revocation | Existing master-restricted device endpoints and Android user-started pairing/revocation UI. | Native/device acceptance still needed. No device was registered/revoked by this source change. |
| Emergency stop | Existing persistent local stop blocks pending registry writes and is rechecked after approval. Hardened policy also blocks its explicitly review-required actions when stopped. | Does not kill OS processes, recall messages, cancel provider work, roll back cloud actions or block all backend HTTP writes. Keep physical/OS controls available. |

## Four levels and explicit critical review

The optional policy uses uppercase enum names:

1. `READ`: named read/analyze tools only.
2. `SUGGEST`: reads and explicitly marked suggestion tools. Suggestions do not execute commands or promote their own permission.
3. `EXECUTE`: named low-risk actions only, with fresh review for each action.
4. `CRITICAL`: named higher-risk actions, still requiring fresh explicit confirmation. This is not blanket permission to execute critical work.

The required level is the stricter of the owner entry and the tool's existing risk metadata. Medium/high-risk tools require CRITICAL; known delete/send/call routes cannot be downgraded by an entry. The existing fresh approval is single-use, argument/task-bound and expiring. Global auto-approval cannot bypass the stronger local policy. An absent/malformed/unreadable active policy, unknown tool, disallowed level, changed policy during review or stopped write fails closed. Registry policy administration and secrets are not exposed as model tools.

Deleting files, IAM/security changes, production infrastructure, message sends, purchases and production deployment require exact action review independently of this local ceiling. No live IAM/purchase/production adapter is created or authorized here. Classifying all future plugins correctly still requires a trusted code review; a mislabeled read-only handler is not made safe by a role name. Do not grant a broad UI/clipboard/network adapter as a way around a denied command.

## Optional local policy: owner reviews before use

This example allows only the security status inventory. It makes no device change by itself. Save as a private, absolute local file outside model-writable content, using an editor you control:

```json
{
  "version": 1,
  "level": "READ",
  "tools": {
    "security_manager_status": {"level": "READ"}
  }
}
```

For a separate read-file entry, review a real absolute path root first. Shape only, not a real approved root:

```json
"read_file": {"level": "READ", "paths": {"path": ["C:/Users/YOUR_NAME/AETHER-Reviewed-Notes"]}}
```

`AETHER_ACCESS_POLICY` must be the absolute path to that owner file in the launcher environment. On Windows PowerShell, after replacing the example with the exact file you reviewed:

```powershell
$env:AETHER_ACCESS_POLICY = 'C:\Users\YOUR_NAME\AETHER-Owner-Policy.json'
```

Do not copy this placeholder unchanged, set a policy through chat/model file writes, or weaken it merely to make a tool pass. This variable affects only newly launched processes inheriting it. The file is reread before each registry action and after review; edits invalidate an outstanding review. File/directory permissions and preventing untrusted code from modifying the configuration remain an OS responsibility. An owner removing the variable returns to compatibility behavior on a new call; removing it during an outstanding action blocks that action. It is not a durable tamper-proof restriction.

Test with harmless temporary data in a new isolated environment and confirm denied tools really remain denied before allowing any effect. Broader tool lists/roots/actions need your exact approval. No machine command was run on your behalf to activate this.

## Optional native secret mode

Native OS storage is opt-in and fail-closed. Only exact known native backend classes are accepted, not chained/plaintext/third-party fallbacks. Backend unavailable/locked/read failure means an error, not a fallback to `.env`. A missing native secret remains unconfigured, even if a plaintext copy exists. Unknown credential mode errors rather than silently switching.

After approving package installation in the isolated environment, the optional extras are `.[security]`. They add `keyring` and `pip-audit`; they do not install ClamAV or configure an OS keychain. Review package/version resolution before installing on your machine.

Owner-operated hidden terminal entry, one credential at a time:

```powershell
python -m aether.secret_store put GEMINI_API_KEY
```

The command accepts no secret in arguments and prompts twice with hidden input. It saves under `AETHER.local.credentials.v1`, never prints the saved value and does not offer a secret-reading tool or endpoint. Supported names include the main three AI providers, ElevenLabs, backend token/secret, Google OAuth client secret, WhatsApp token and GitHub webhook secret. Saving a value does not change a provider's key or rotate its remote credential.

After the needed entries and actual native backend are verified locally, select mode for new processes:

```powershell
$env:AETHER_SECRET_BACKEND = 'os-keyring'
```

Do not send secrets in chat or screenshots. No native password/key can be proven protected against all local software, and Python cannot guarantee wiping strings from memory. Server/dataclass repr hides the integrated keys, but programmatic config dictionaries, debug tools, old files, console history, crash dumps and unrelated scripts are not automatically scrubbed. Review removal/rotation of any older copies as a separate explicit task; nothing is silently deleted. Headless Linux needs its own working unlocked Secret Service session. Native backend/device tests remain unverified.

## Optional scanner review, no unattended scan

The scanner module accepts one existing regular file, at most 64 MiB, in an exact absolute reviewed root, with no symlinks. It prints a plan only unless `--run` is supplied. No shell, elevated execution, auto-install/update/fix/delete/move/quarantine flags, wildcard directory walk or background scan is added.

Shape only, replace and review local paths before running:

```powershell
python -m aether.security_scans malware 'C:\Users\YOUR_NAME\Reviewed\sample.bin' --root 'C:\Users\YOUR_NAME\Reviewed'
python -m aether.security_scans dependencies 'C:\Users\YOUR_NAME\Reviewed\pinned.txt' --root 'C:\Users\YOUR_NAME\Reviewed'
```

The malware path requires an owner-installed `clamscan` on the trusted launcher PATH and a separately maintained signature database. This adapter does not establish signature freshness. A zero scanner code means only no findings reported, not safe to run. Findings/errors/timeout/truncated output remain distinct. Scanner settings/engine limits may still skip content; inspect the full local report.

The dependency input is restricted to `package==version` lines and whole-line comments, no URLs/includes/options/markers/editable/unpinned packages. The fixed invocation disables pip/dependency resolution and automatic fixes. A dependency audit is not malware detection. A reviewed dependency scan discloses the displayed package names/versions to the PyPI vulnerability service over HTTPS, not source-file contents by AETHER. That disclosure needs your approval. JSON result validation/coverage is checked; skipped/missing/malformed results are not a clean result. Returned report text is untrusted data, never authority to upgrade/run code.

To actually scan, the owner must independently add `--run`, read the exact plan/disclosure/input digest, and type `RUN REVIEWED SCAN` in an interactive terminal. No model tool exposes the runner. Changed inputs/plan invalidate review. This is an owner-process boundary, not protection against hostile code running in the same user account or swapping a file after final check. Timeout is unknown and does not promise every descendant stopped. Scanner output stays in the local terminal and can contain paths/data; do not paste it into a provider without reviewing it.

## What needs your OK, and what is still engineering

- Approve the exact launcher/environment and named tool allowlist/level/roots before activating the optional owner policy. No arbitrary shell or generic UI path is authorized by this category.
- Approve native keychain package/setup and owner-performed tests; enter secrets only via the hidden local prompt. Any old plaintext deletion or provider rotation is a separate exact approval.
- Approve scanner installation/targets, and package-name/version disclosure for an actual dependency scan. No scan/update/remediation is automatic.
- Continue the existing owner-device/private HTTPS acceptance guide before remote use. Per-device backend roles, dedicated trust/pinning, distributed sessions, tamper-resistant logs and external alert delivery are **unimplemented engineering gaps**, not features that an approval alone enables.

[Existing device/private HTTPS and cloud acceptance guide](OWNER-DEVICE-AND-CLOUD-SETUP.md). Keep backend loopback/private and real cloud adapters disabled until their exact targets/effects are separately reviewed. Source tests/builds are not security certification.

## References

- Native keyring supported stores, configuration and security considerations: https://keyring.readthedocs.io/en/latest/
- pip-audit invocation, disclosure model, limitations and exit codes: https://github.com/pypa/pip-audit
- ClamAV scanning, engine behavior and unsafe cleanup options deliberately omitted here: https://docs.clamav.net/manual/Usage/Scanning.html
