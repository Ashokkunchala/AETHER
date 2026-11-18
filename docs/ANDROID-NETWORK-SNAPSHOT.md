# AETHER Android foreground network snapshot

The LOCAL PHONE ACTIONS card now has an explicit "Read local network capabilities
now" button. It reads the current default network visible to this app through
ConnectivityManager.activeNetwork and getNetworkCapabilities. It adds the normal
permission ACCESS_NETWORK_STATE, not a runtime location/Wi-Fi permission prompt.
This is a normal permission. The previous three-permission source baseline is superseded by this narrowly
scoped fourth declaration. Dependency-merged manifest/device behavior still
needs acceptance. Normal permission availability is not approval to send data.

The snapshot shows fixed transport labels (Wi-Fi, cellular, Ethernet, VPN,
Bluetooth, or other/unknown) and separately reports Android's INTERNET, VALIDATED,
CAPTIVE_PORTAL and NOT_METERED capability flags. More than one transport can be
reported. It does not infer the underlying transport hidden by a VPN.

- INTERNET says configured for general internet, not current reachability.
- VALIDATED reflects Android's last check of general internet connectivity, not a backend
  health check or a promise that this moment's request will succeed.
- A flag not reported is not proof that its opposite is true. In particular,
  absence of CAPTIVE_PORTAL is not proof there is no captive portal, and
  NOT_METERED is not a tariff or cost guarantee.
- A null activeNetwork means none visible or blocked to this caller, not global offline. Null capabilities, service failure, permission errors and races remain
  unavailable/unknown, not healthy or offline. The display includes sample time
  and warns that state may change immediately.

No SSID/BSSID, network handle, IP/DNS/MAC address, location, signal strength,
configured-network list or traffic contents are requested. No network probe,
Wi-Fi/radio/VPN change, network binding, callback registration or backend/model
upload is added. No automatic polling or background observer is started. The
result stays in the existing transient local status field until another action
replaces it or the activity state is lost; that is not secure erasure. Other
backend/voice features keep their own network behavior and disclosures.

Tests cover pure summary formatting in JVM tests and source-scope regressions.
They do not prove the OS service returns correct/live flags. No emulator or phone
was connected, run or visually inspected for this change. Runtime/layout tests,
Wi-Fi/cellular/VPN transitions, captive portals, missing access and actual OS
behavior remain unverified. This completes only a passive foreground snapshot,
not a continuous connectivity monitor or laptop/backend health test.

Official sources checked November 16, 2026:
- https://developer.android.com/reference/android/net/ConnectivityManager
- https://developer.android.com/reference/android/net/NetworkCapabilities
- https://developer.android.com/reference/android/Manifest.permission#ACCESS_NETWORK_STATE
