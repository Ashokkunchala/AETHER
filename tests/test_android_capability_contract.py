"""Source-contract checks only. Never attach to or operate an Android device."""
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
ANDROID=ROOT/'android'/'app'
NAMESPACE='{http://schemas.android.com/apk/res/android}'


def test_native_manifest_permission_baseline_no_broad_access():
    root=ET.parse(ANDROID/'src/main/AndroidManifest.xml').getroot()
    assert {row.attrib[NAMESPACE+'name'] for row in root.findall('uses-permission')}=={
        'android.permission.INTERNET','android.permission.RECORD_AUDIO','android.permission.POST_NOTIFICATIONS'}
    assert not root.findall('.//service') and not root.findall('.//receiver')
    assert len(root.findall('.//activity'))==1


def test_visible_voice_stops_on_activity_stop_and_dispose():
    source=(ANDROID/'src/main/java/com/ashok/jarvis/MainActivity.kt').read_text()
    assert 'if (event == Lifecycle.Event.ON_STOP) liveVoiceController.stop()' in source
    assert 'lifecycleOwner.lifecycle.removeObserver(observer)\n            liveVoiceController.stop()' in source
    assert 'Voice captured. Review the transcript, then tap Send.' in source


def test_notifications_user_tap_no_background_voice_activation():
    source=(ANDROID/'src/main/java/com/ashok/jarvis/ReminderWorker.kt').read_text()
    assert 'private const val POLL_MINUTES = 15L' in source
    assert 'setRequiredNetworkType(NetworkType.CONNECTED)' in source
    assert 'PendingIntent.getActivity(' in source and 'FLAG_IMMUTABLE' in source
    assert 'areNotificationsEnabled()' in source and 'POST_NOTIFICATIONS' in source
    assert 'LiveVoiceController' not in source and 'startForegroundService' not in source


def test_contract_lists_requested_gaps_and_no_device_acceptance():
    text=(ROOT/'docs/ANDROID-CAPABILITY-CONTRACT.md').read_text()
    for phrase in ['No device was connected','targetSdk/compileSdk 35','not device testing','Wake word/background voice','Calls','SMS','Contacts','Camera/gallery','Calendar','Location reminders','Clipboard','Battery/storage/network','Voice notes','GitHub failure','not an exact alarm','not normal-app capabilities','laptop-side command authority separate','not promised on-device/offline','January 27, 2027']:
        assert phrase in text
    gradle=(ANDROID/'build.gradle.kts').read_text()
    assert 'minSdk = 26' in gradle and 'targetSdk = 35' in gradle and 'compileSdk = 35' in gradle


def test_readme_no_stale_memory_editing_absence():
    text=(ROOT/'android/README.md').read_text()
    assert 'ANDROID-CAPABILITY-CONTRACT.md' in text
    assert 'Memory editing, workout tracking and background data sync are not implemented' not in text
    assert 'Memory add/list/delete UI exists' in text
