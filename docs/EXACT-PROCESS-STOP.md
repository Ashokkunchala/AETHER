# AETHER exact selected-process stop

The desktop close_app and kill_process registry tools now require one exact PID,
create_time and absolute executable path. Select these from a fresh process_details
read, not from a guessed name or a substring search. Preview queries that same
identity; execution queries it again after a fresh trusted confirmation. Missing
or changed identity, protected PID/name, AETHER itself or an ancestor, unreadable
process details, denied permission or emergency stop fail closed. No model/caller
confirmed flag, auto or always approval replaces this confirmation.

The preview warns that unsaved work can be lost. Windows psutil terminate uses
TerminateProcess and is forceful, not graceful application close. On other OSes
its behavior differs. The only action requested is terminate on this selected
process. It does not enumerate a name, stop a process tree, kill children, request
elevation, retry with kill or escalate permissions. psutil also checks process
identity before termination, but this is not an atomic OS security guarantee
against hostile process/path replacement. Local OS/account and psutil are trusted.

It waits up to5seconds for that process to exit. A timeout is explicitly unverified
and unsuccessful, with termination_requested true; no automatic force retry is
performed. Unexpected wait errors produce failure, not a claim of exit. Already
exited or changed processes are not presented as successful terminations. A verified
exit means the selected process exited, not that work was saved, all children
exited, the app UI closed or a service did not restart it. A fresh inspection and
new user decision are required for a new/reused/restarted identity.

Legacy name-based apps.close_app, process.terminate_process, SystemController and
system app helper now fail closed; LaptopController inherits that denial. This
intentionally removes broad compatibility. Other generic shell/Python/ADB paths
are distinct and must not be used as implicit approval to stop processes. The
critical-name list is a precaution, not an exhaustive Windows protection policy;
an arbitrary chosen user process can still be important. Fresh exact user review
is required. No real laptop process was queried, stopped or waited on in this
change. Tests use fake psutil Process objects and mocked waits only, covering
identity/PID reuse, malformed input, denial, emergency stop, permission/query
errors, timeout and verified exit. The trusted registry approval callback and
local approval record boundary remain the authority boundary, not hostile code
running under the same OS account.
