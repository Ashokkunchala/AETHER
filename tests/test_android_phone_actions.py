"""Source safety regressions, not Android runtime/intent/visual tests."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'android/app/src/main/java/com/ashok/aether/PhoneActions.kt'


def test_phone_actions_wired_without_broad_grants_or_direct_send():
    text=SOURCE.read_text()
    assert 'PhoneActionsCard()' in (SOURCE.parent/'MainActivity.kt').read_text()
    for marker in ['Intent.ACTION_DIAL','Intent.ACTION_SENDTO','Intent.ACTION_INSERT','ActivityResultContracts.PickContact()','ActivityResultContracts.OpenDocument()','ActivityResultContracts.GetContent()']:
        assert marker in text
    for marker in ['Intent.ACTION_CALL','SmsManager','takePersistableUriPermission','rememberSaveable {','HttpURLConnection','URL(','TokenVault','LiveVoice']:
        assert marker not in text
    manifest=(ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
    for permission in ['CALL_PHONE','SEND_SMS','READ_CONTACTS','WRITE_CALENDAR','READ_EXTERNAL_STORAGE','MANAGE_EXTERNAL_STORAGE','ACCESS_FINE_LOCATION','CAMERA']:
        assert permission not in manifest


def test_local_status_limits_unknown_and_clipboard_explicit():
    text=SOURCE.read_text()
    for marker in ['unknown','Not all-files inventory','Not a security/malware audit','No upload','no monitor or upload','No pixels read','does not send','does not call','does not save','primaryClip?.getItemAt(0)?.text','validPhoneTarget(number)','calendarTimes(begin, end)']:
        assert marker.lower() in text.lower()
    assert 'internal fun validPhoneTarget' in text
    assert 'internal fun calendarTimes' in text
