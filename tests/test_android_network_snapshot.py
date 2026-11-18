"""Android source-scope checks only, not Android runtime/pixel acceptance."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'android/app/src/main/java/com/ashok/aether'


def test_network_snapshot_explicit_foreground_button_and_normal_grant():
    source = (BASE / 'PhoneActions.kt').read_text()
    assert 'Button(onClick = { status = networkSnapshotText(readLocalNetworkSnapshot(context)) })' in source
    manifest = (ROOT / 'android/app/src/main/AndroidManifest.xml').read_text()
    assert 'android.permission.ACCESS_NETWORK_STATE' in manifest
    assert 'ACCESS_WIFI_STATE' not in manifest
    assert 'ACCESS_FINE_LOCATION' not in manifest


def test_capabilities_not_probes_identifiers_or_radio_changes():
    source = (BASE / 'NetworkSnapshot.kt').read_text()
    for marker in ['manager.activeNetwork', 'manager.getNetworkCapabilities(network)',
                   'NET_CAPABILITY_INTERNET', 'NET_CAPABILITY_VALIDATED',
                   'NET_CAPABILITY_CAPTIVE_PORTAL', 'NET_CAPABILITY_NOT_METERED',
                   'NetworkVisibility.NONE_VISIBLE', 'NetworkVisibility.UNAVAILABLE']:
        assert marker in source
    for marker in ['getLinkProperties', 'WifiManager', 'SSID', 'BSSID', 'getNetworkInfo',
                   'getAllNetworks', 'registerNetworkCallback', 'requestNetwork',
                   'HttpURLConnection', 'URL(', 'Socket(', 'setWifiEnabled', 'TokenVault',
                   'BackendClient', 'LiveVoiceController', 'registerReceiver']:
        assert marker not in source
    assert 'none or blocked for this caller' in source
    assert 'connectivity unknown' in source
    assert 'No AETHER/backend reachability check' in source


def test_local_scope_docs_preserve_unverified_device_acceptance():
    text = ' '.join((ROOT / 'docs/ANDROID-NETWORK-SNAPSHOT.md').read_text().split()).lower()
    for phrase in ['ACCESS_NETWORK_STATE', 'last check', 'not a backend', 'No emulator',
                   'SSID', 'not global offline', 'normal permission', 'No automatic polling']:
        assert phrase.lower() in text
