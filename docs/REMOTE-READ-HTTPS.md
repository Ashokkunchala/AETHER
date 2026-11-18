# AETHER dedicated private HTTPS remote-read listener

This is source preparation for the reachability gap, not a network deployment or a claim the phone can connect. It creates a separate minimal ASGI app for the existing [read-only request protocol](ANDROID-WINDOWS-READONLY.md). It never imports or proxies the general Windows agent. No socket opens at import or during an offline plan check. Existing general-agent loopback settings remain unchanged.

## Closed surface

Only these exact routes/methods exist:

- `POST /v1/remote-read/requests` with `{"action":"memory_snapshot"}` queues an inert request.
- `GET /v1/remote-read/requests/32-lowercase-hex-ID` retrieves only the authenticated device's bounded state/result.
- `POST /v1/remote-read/requests/32-lowercase-hex-ID/cancel` with `{}` cancels/suppresses/clears that request.

There is no health/docs/OpenAPI, login/pair/token-management, shell/tool, generic proxy, execute, approve or review route. Queueing never collects RAM. The laptop owner must separately use the existing local interactive review command before the fixed RAM read and disclosure. Dedicated per-device tokens, expiry, stop, revocation, cancellation and requester-bound results remain enforced by the existing store. A token cannot remotely approve anything.

The listener requires TLS and one exact reviewed Host, rejects duplicate Host/auth headers, alternate ports, query strings, browser Origin, content/transfer encoding and unsupported routes/methods. Proxy headers cannot upgrade HTTP or change peer identity. POST requires one JSON Content-Type and one exact Content-Length of1-256 bytes, checked against the actually received body. Body receipt has a five-second total deadline. Header count/combined sizes are bounded after HTTP parsing. Responses use no-store; no access logs or Server header are enabled. A single-process global120-request/minute budget avoids an unbounded per-IP/token map. Invalid requests consume that budget once they reach the allowed path/host/TLS checks. There is no per-device fairness or distributed/network DoS protection.

## Offline configuration review

The optional launcher accepts an exact RFC1918 private IPv4 bind address, one exact lowercase DNS hostname or the same IPv4, and existing reviewed leaf certificate/key files. Wildcard/public/loopback/link-local/multicast/CGNAT/IPv6 binds are refused by the launcher. A private address alone does not prove a network is trusted or inaccessible from elsewhere.

It checks certificate dates (currently valid and at least seven more days), an exact SAN (no wildcard matching), non-CA BasicConstraints, explicit server-auth EKU, RSA2048+/EC256+ public key, SHA256-or-stronger signature, matching loadable key and bounded files. It prints the leaf SHA256 fingerprint, expiry and exact planned bind/host/port. It never prints key bytes. Encrypted private keys are not supported and are not prompted for. It does not create/decrypt a key, install a CA, verify Windows ACLs, resolve DNS or prove the phone trusts the certificate. Do not use an unreviewed key file or put credentials in chat.

From the installed source, `python -m windows_agent.remote_read_https --help` shows the arguments. Supplying `--bind`, `--host`, `--cert` and `--key` without `--serve` only performs the offline validation and prints the plan. Use only exact values from the separately reviewed intended network/certificate arrangement, not copied placeholders. Selected certificate/key reads occur on that command; the rest of the filesystem and OS remain trusted, not sandboxed against parent links or concurrent changes.

Serving is a separate, consequential network-exposure action. Do not launch it until the owner approves that exact arrangement. Adding `--serve` requires both input/output terminals and the exact typed phrase `EXPOSE READ-ONLY ADDRESS:443`. Anything else cancels. Configuration is revalidated after review. The launcher then runs only the dedicated app on443, one worker, no trusted proxy, no access logging, concurrency16, backlog32 and keep-alive5 seconds. Standard server TLS defaults are at least TLS1.2 in the tested runtimes. Existing same-account file/process compromise and a small validation-to-load race remain outside the boundary. Do not change a conflicting port/service automatically or run elevated just to force it to work.

No firewall, tunnel, certificate issuance/trust installation, DNS, startup registration, pairing or general-agent network change occurs. Existing mobile setup scripts are not silently repurposed. In particular, a CA certificate/private key made by older mobile scripts is not accepted as this listener's server leaf. Do not disable Android hostname/certificate verification, expose the general agent, forward a port or bypass an unexplained TLS warning to make it connect. The Android foreground read-only card still requires a separately trusted HTTPS443 origin and dedicated token.

## Evidence and remaining work

Tests cover the dedicated queue/local-review/result/cancel path; excluded routes and actions; HTTP/proxy/Host/origin/header/body restrictions; bounded rate handling; certificate/target refusals; default no-serve and exact interactive approval; configuration-change refusal; and a real ephemeral loopback TLS server with certificate trust/hostname verification, refused untrusted certificate and no remote execution. The TLS fixture never binds a LAN/public address and installs no trust/certificates. Launcher tests mock the final server call; they do not expose the user's network.

Actual Windows LAN serving, certificate-chain/Android trust, intended DNS routing, firewall policy, phone-to-laptop connectivity, token entry, permission review, microphone/voice and device acceptance remain unverified. This listener is not full phone-laptop command control, production hardening, tamper-resistant audit or a complete denial-of-service defense. Network launch/deployment still needs its own approval; source/build success is not that approval.
