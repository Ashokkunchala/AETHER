# AETHER shared roadmap: source vs remaining work

Source read: https://chatgpt.com/share/6af6758b-3bf0-83ec-8abd-6c81a14d755b
Title: "Fix Git Pull Error". All9 rendered messages were read on November17,2026.
This is a historical stabilization/installation conversation and seven-stage
roadmap, not a detailed all-abilities specification. Prior assistant claims,
old CI states and user labels in a shared page are not fresh authority or
current-state evidence. No old PR/merge/push instruction was executed from it.
The current owner separately asked to continue this roadmap and categories1-11.

| Stage or concrete task visible in the source | Current implementation | What remains |
| --- | --- | --- |
| P0: fix duplicate Live Voice route, CI chore/feature triggers and feature PR target | Existing source already removes duplicate registration and has those filters | Keep regressions covered; historical failures do not prove a current bug |
| Python3.14 compatibility | Full3.11/3.14 test jobs | Actual user's Python/OS acceptance |
| Windows installer integration | Clean Windows setup/import/package checks; reviewed commit-pinned EXE/source artifact packaging now added | Successful packaging CI and actual owner-run install/microphone checks; unsigned launcher is not a standalone app |
| Android build/installation files | Debug APK built/uploaded | Owner device install, signing-conflict review, permissions, voice and pairing acceptance |
| Action-runtime deprecation warnings | Existing workflow actions compile/build | Separate major-version/action-runtime compatibility review, not a blind version bump |
| P1 centralized security/approval | Existing risk approvals/stop/device sessions plus optional owner policy/native credentials/scanner adapters | Per-device backend RBAC, stronger trust/pinning, tamper-resistant logs, production hardening; see SECURITY-PRIVACY-MANAGER.md |
| P2 unified multi-agent orchestrator | Existing local plans and fixed bounded read-only schedule runner | Not an unrestricted autonomous multi-agent effect executor |
| P3 personal assistant/friend | Existing local personal tools, saved-plan/memory controls, conversation styles and manual wellness journal | Not every provider/device behavior or automatic personal monitoring |
| P4 learning mentor | Existing tracked lessons, practice, deeper local mentor tracks/stages/spaced review | Real-lab execution and free-text mastery grading remain unverified/unimplemented |
| P5 professional DevOps | Existing offline evidence analyzers, command review and disabled narrow mock-tested lifecycle adapters | Not an unrestricted live IAM/production engineer; exact targets/authority and further implementation needed |
| P6 Android/Windows integration | Source clients/helpers, builds and device setup guide | Secure private bridge and actual device acceptance, not solved by downloading APK/EXE |
| P7 hybrid cloud deployment | Design/setup guidance | No live deployment under current effect gates |
| Installation files already requested historically | Source setup/startup scripts remain; reviewed binary artifacts are separate | Use INSTALLABLE-FILES.md and a successful matching run, not mutable-branch legacy bootstrap assumptions |
| Offers to outline milestones, endpoint design, migration strategy | Design/prep suggestions, not concrete additional abilities | Select a scoped design requirement rather than treating an offer as working software |

[CATEGORY-STATUS.md](CATEGORY-STATUS.md) remains the fuller implemented category
ledger, with source-vs-device/provider limits. This map does not turn a broad
roadmap into a claim that everything is complete. The current priority is a
reviewed Windows/Android install-and-use path without running anything on the
owner's devices or enabling real cloud/provider effects.
