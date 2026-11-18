# AETHER provider-free owner console

The console makes the new local dashboard, filename and offline workflow paths usable without an AI key, chat/provider request, HTTP backend or Android pairing. It uses a small fixed tool registry, not arbitrary command execution. Browser reads are deliberately excluded because they use external websites.

From the reviewed installed source folder in a normal interactive PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -B -m aether.owner_console --help
.\.venv\Scripts\python.exe -B -m aether.owner_console preflight
```

`preflight` is passive package metadata/configuration presence, not a real device check. `-B` avoids normal Python bytecode cache writes; Python environment hooks remain outside this command's control. No backend/provider is started. All console commands require an interactive terminal. There is no `--yes`, batch approval, generic tool name, arbitrary shell or auto-install.

## Create a sample dashboard

Review the illustrative JSON before running:

```powershell
.\.venv\Scripts\python.exe -B -m aether.owner_console dashboard --spec docs/examples/dashboard-spec.json --name release-demo
```

The prompt prints exact supplied arguments and a preview. Type exactly `APPROVE create_custom_dashboard` only if the request is correct. Any other input cancels. The result gives a new local HTML path. Open and visually inspect it yourself. It is not uploaded/hosted or automatically opened. The sample data is fictional. See [dashboard limits](BROWSER-AND-DASHBOARDS.md).

## Search selected folder names

Choose and configure the exact local folder as the [filename guide](LOCAL-FILE-DISCOVERY.md) explains, then:

```powershell
.\.venv\Scripts\python.exe -B -m aether.owner_console files --root 'C:\Users\YOUR-NAME\Documents\ReviewFolder' --query report --mode plan
```

Fresh exact approval reads only bounded filename/size/date metadata and extension-based grouping suggestions. It never moves/renames/deletes/uploads/opens files or reads their body. Paths/results may be private, so use a private terminal. Unlike the AI chat tool loop, this console does not transmit them to a model. Owner access-policy restrictions remain in force; this is not a policy bypass or OS sandbox.

## Save and resume offline reviews

Review the fictional example, then save it:

```powershell
.\.venv\Scripts\python.exe -B -m aether.owner_console workflow-create --spec docs/examples/offline-workflow.json
```

Approve `offline_workflow_create` only after reviewing all inputs. The result provides a new workflow ID. Replace `YOUR-WORKFLOW-ID` below with that exact ID, not the placeholder:

```powershell
.\.venv\Scripts\python.exe -B -m aether.owner_console workflow-status --id YOUR-WORKFLOW-ID
.\.venv\Scripts\python.exe -B -m aether.owner_console workflow-next --id YOUR-WORKFLOW-ID
.\.venv\Scripts\python.exe -B -m aether.owner_console workflow-result --id YOUR-WORKFLOW-ID --position 0
.\.venv\Scripts\python.exe -B -m aether.owner_console workflow-cancel --id YOUR-WORKFLOW-ID
```

`workflow-next` obtains the current exact position/workflow/input digests, then prompts for `APPROVE offline_workflow_run_next`. A race during review refuses rather than silently advancing to a different step. One approved analyzer runs, its result persists, and execution stops. Repeat only after reviewing the next status and intended step. `workflow-result` and `workflow-cancel` have their own exact approval phrases. Status reads local metadata without an additional prompt once the owner explicitly invokes that command; store/schema initialization can occur. It does not expose raw inputs/results.

The [workflow guide](OFFLINE-WORKFLOWS.md) defines the four fixed analyzers, input schemas, limits, failure/crash no-replay behavior and stop/cancel semantics. Cancel is not delete, undo or secure erasure. No live/cloud/remote command can be represented by this console's fixed workflow operations.

## Privacy and trust

Selected JSON spec files are read locally before displaying the confirmation, with a256KiB cap and no direct symlink input. This is an explicit local file read, not file sandboxing against hostile parent links or concurrent changes. Do not use untrusted specs or secrets. JSON text remains data, not instructions to run anything else. Confirm only the exact printed operation and values. The console preserves the existing one-use/expiry/stop/audit and optional owner-policy checks. It stores no provider keys and sends no results externally by itself. Local terminal history, files, logs and screen captures can still retain private data.

Actual Windows/Android runtime acceptance is still owner-side. The tests use temporary local data and reviewed fixtures, not the owner's folders, microphone, phone, account or credentials. Console support does not prove every AETHER interface exposes the same abilities.
