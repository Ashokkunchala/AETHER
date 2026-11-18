# AETHER local filename discovery and organization review

`discover_local_files(root, query?, mode?)` adds bounded local filename search and extension-based grouping suggestions. It is disabled until the owner configures exact folders. This is metadata-only discovery, not file-content search, duplicate detection, an automatic organizer or a file-transfer service.

## Owner-run setup

In a fresh installed source environment, choose a small non-sensitive local folder. The value is a JSON list of exact absolute folders, not an instruction to search the whole computer. No folder is selected by default. Example shape on Windows, replace it with your own reviewed folder:

```powershell
$env:AETHER_FILE_ROOTS = '["C:\\Users\\YOUR-NAME\\Documents\\ReviewFolder"]'
.\.venv\Scripts\python.exe -m aether.file_discovery --root 'C:\Users\YOUR-NAME\Documents\ReviewFolder' --query report --mode search
```

It displays the exact folder, literal filename query, mode and limits, then asks `READ FOLDER METADATA`. It refuses non-interactive execution. Review the folder and its privacy before approving. Do not choose credential stores, sensitive work folders or folders managed by an untrusted process.

Use `--mode plan` to add a suggested group per matching file: Documents, Spreadsheets, Presentations, Images, Audio, Video, Archives or Review manually. Groups depend only on the filename extension. They are not verified file types and do not judge whether a file is safe, redundant or disposable. No commands, destination paths, automatic move/rename/delete or overwrites are produced. Existing files and directories stay unchanged.

The normal registry path uses the same implementation and requires fresh confirmation, even with global auto-approval. The emergency stop blocks starting and discards results when detected during/before returning the scan. It cannot recall names already returned or cancel a blocked operating-system directory call. A failure of the stop store fails the action instead of bypassing it.

## Scope and privacy

- Only an exact configured root is accepted. A descendant must be separately configured before it can be a different scan root. Relative, filesystem/drive-root, parent-traversal, UNC and device paths are refused. Mapped/network filesystems are not reliably identified, so choose genuinely local folders.
- The walk examines at most2,000 entries, returns at most100 files, descends at most4 directory levels beneath the root and checks a3-second budget between entries. A slow filesystem call may exceed that budget; this is not an interruptible OS deadline.
- Symlinks, Windows reparse points, special files, dot/hidden entries and other filesystem devices are skipped. Windows hidden/system attributes are also excluded. No excluded subtree is searched deliberately. Same-device bind mounts and concurrent local path changes are not a solved security boundary.
- Returned fields are relative path, byte size and UTC modification time, plus suggested group in plan mode. No file body, content hash, thumbnail, archive expansion, application launch or upload is performed by this tool.
- Names and metadata can themselves be sensitive. The existing AI chat loop may include tool results in requests to the configured provider. CLI output stays local unless the owner shares it or another process captures it. Approve only scope suitable for that workflow.
- Results are a changing, partial snapshot. Iteration order decides which files fit limits; sorting applies only to returned rows. Skips, limits and errors are disclosed. An empty result is not proof a file is absent; counts do not describe the whole folder/disk. Date/size metadata can change immediately.

## Existing policy and remaining gaps

The optional hardened exact-tool policy does not gain a new exemption. This tool uses the filesystem category and inherits its conservative exact-path coverage checks. In hardened mode a root-only call can be allowlisted with an exact root path restriction; extra `query`/`mode` arguments are rejected by that policy's all-arguments-as-paths rule. Use the interactive CLI for this bounded workflow or leave it unavailable under that policy; do not weaken the policy to make it work. There is no claim of per-device filesystem RBAC or a universal sandbox.

Name checks and repeated lexical directory checks reduce accidental out-of-scope traversal but do not defend against a malicious same-user process swapping paths between checks. No filesystem search can promise not to touch network-backed storage when the OS mounts it as local. Do not use this against hostile folders. This tool neither inventories already-open files nor reads arbitrary executable contents.

Test coverage includes disabled/unconfigured roots, exact-root matching, bad paths/queries/modes, hidden files/links/reparse markers/FIFOs, case-insensitive filename search, extension-only suggestions, no content reads or mutation, depth/entry/time/result bounds, unreadable folders, fresh-confirmation and stop discard. Actual owner laptop filesystem behavior remains unverified. No folder on the owner's computer was accessed during development.
