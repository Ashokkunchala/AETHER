# AETHER bounded system inspection

Three added desktop registry tools require fresh explicit approval on every read,
never auto/always approval. Their preview names the exact fixed scope and warns
that returned system names/status may be private and enter the configured
assistant/provider context. Emergency stop is rechecked after confirmation. No
system service, startup entry, interface, credential or real laptop was read or
changed during development. Tests mock all OS sources.

- windows_service_inventory: psutil Windows service names, display names, state
  and start type, at most300services. No binary path, command line, username,
  description, PID or mutation. Protected/denied/disappearing sources are partial
  or unavailable, not healthy/empty. Non-Windows reports unsupported. This is a
  snapshot, not service health or an ongoing monitor. A query may still block in
  the OS; no asynchronous cancellation or hard read timeout is promised.
- windows_startup_inventory: current-user/local-machine Run and RunOnce names in
  32/64bit registry views, plus conventional APPDATA/PROGRAMDATA Startup folder
  entry names. At most100names per source. Values are read by the enumeration API
  but never returned; no command/shortcut target content is opened or executed.
  Each source distinguishes queried, absent, unavailable or partial-limit. Views
  may overlap; this is not a unique app count, effective enabled state, publisher
  approval, scheduled-task/policy/other-user inventory or all Windows autostarts.
  No enable/disable/delete/rollback operation is supplied. Environment/OS and
  folder mapping must be trusted; UNC anchors and canonical/symlink mismatches
  fail, but mapped remote drives/reparse races/OS compromise are not isolated.
- network_link_inventory: local NIC link-up flag, reported link capacity and MTU,
  at most100interfaces. Speed0/negative/nonfinite means unknown, not zero-speed
  internet. No IP/MAC/SSID, connections, traffic capture, DNS/TCP/ping/external
  request, probe, speed test or configuration change. A local link does not prove
  internet/backend reachability and internet_reachability_verified remains false.

All results include UTC sample time and changes_made:false, plus explicit partial
and unavailable-source notices. No raw exception strings are returned. Names are
bounded display data, not commands/instructions. Names/status can still be private;
this is not automatic redaction or permission to share with other people. A local
metadata read can expose information even without mutation. Direct Python callers
can call internal functions; trusted confirmation is the registry boundary, not a
sandbox against hostile code under the same OS account. Existing older inspection
and shell paths are distinct; no blanket approved-machine-access claim is made.

Mock tests cover unsupported OS, service permission errors and bounds, unknown
states, fixed registry sources and omission of command values, absent vs denied,
partial folder/registry coverage, local NIC unknown speed, source failures, fresh
approval and emergency stop. Windows permissions/registry view/folder localization,
real service behavior and actual NIC metric semantics still need local acceptance.

Sources checked November16,2026:
- https://psutil.io/api/
- https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys
- https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-redirector
- https://learn.microsoft.com/en-us/windows/win32/services/service-security-and-access-rights
