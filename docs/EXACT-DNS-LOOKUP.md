# AETHER exact-name OS DNS lookup

`lookup_dns_name` adds one fresh-reviewed local operating-system getaddrinfo call
through the existing registry. It is separate from passive network-link snapshots
and generic shell commands. No shell, subprocess, ping, HTTP request, socket connect,
route change, credential setter or automatic monitor is added by this wrapper.
Resolver infrastructure may itself open network connections to answer the lookup.

## Scope and approval

The input is one lowercase ASCII dotted absolute hostname ending in a dot, for
example `example.test.`. It rejects URLs, IP literals, single-label search names,
ports, user-info, whitespace, wildcards, underscores and non-ASCII labels. ASCII
punycode labels can be supplied deliberately; this is not IDN spoof detection.
Labels have 1-63 characters and the whole input is at most 254 characters. No spelling,
case, suffix or country is guessed. The trailing dot requests an absolute name,
but is not proof of resolver authenticity, no suffix handling or authoritative DNS.

Every request requires a new confirmation, including the exact name and result
privacy warning. Auto-approve and "always allow" cannot skip it. No approval handler,
a denial, expired/consumed approval or emergency stop blocks dispatch through the
existing execution boundary. Stop during review also blocks it. A name may itself
be private. The approval covers sending this name to configured resolver systems
and sharing the bounded name/address/status result with the configured assistant/
model context. Do not approve an internal hostname for a provider that should not
receive it. Other processes/callers remain outside this registry boundary.

The fixed call is `socket.getaddrinfo(hostname, None, AF_UNSPEC, SOCK_STREAM,
IPPROTO_TCP, 0)`. No port/service is selected and no application connection is
attempted. This is OS name resolution, not a chosen-server DNS packet tool. Local
hosts/cache, VPN/split DNS, OS policies and plugins may affect or answer it without
a DNS query. One call can emit multiple packets and internal retries. No DNSSEC,
authoritative server, TTL, CNAME chain, DNS record provenance, reverse lookup,
DNS configuration or DNS traffic capture is inspected.

## Waiting, records and limits

The call runs in one daemon worker. The selected wait is an integer 1-15 seconds,
default 5. A timeout means only AETHER stopped waiting; it cannot cancel the OS
resolver call. Its gate permits at most one outstanding lookup in this process,
including after a timeout. Later requests fail closed until that call actually
exits. Other processes still have their own OS activity. No retry, polling,
background result notification or continuing monitoring is created. The worker
may remain blocked until process exit if the resolver never returns. An emergency
stop cannot undo the already-disclosed name or stop a running OS resolver request.

Only supported IPv4/IPv6 SOCK_STREAM records are considered, at most 500 returned
records scanned and 20 unique supported address/scope-presence records returned.
Truncation sets partial=true. Canonical names/raw tuples/errors are not reflected.
IPv6 numeric scope identifiers are omitted and flagged, so those address strings
are not directly usable as returned. The underlying OS may allocate a larger raw
result before wrapper scanning; this is not a hard memory/time bound on the OS.

A completed result is a timestamped report from that machine's resolver, not a
claim about global current DNS, address ownership, public/private safety, malware,
service identity, reachability, port connectivity, latency or application health.
Zero supported addresses is not a DNS-nonexistence conclusion. A resolver error is
not proof the name does not exist or the network/service is down. No raw exception
is sent to the assistant. The wrapper stores no report; chat/model/caller logs or
OS/resolver history may separately retain names/results. This is not secure erasure.

## Evidence and acceptance

Synthetic resolver tests cover exact fixed arguments, strict host/wait validation,
IPv4/IPv6 deduplication/scope omission, canonical/error omission, malformed replies,
scan/return bounds, empty results, worker-start failure, timeout/one-outstanding-call
gating, fresh confirmation/no-auto approval, and stop during review. No real DNS
lookup, owner device command, resolver configuration, network test, cloud account
or provider send was used during development. Actual resolver/VPN/hosts/platform
behavior needs explicit local acceptance under the approved-command model.
This feature alone does not complete port/route/connectivity diagnostics or remote
Android-to-Windows networking control.

Official source checked November 17, 2026:

- https://docs.python.org/3/library/socket.html
