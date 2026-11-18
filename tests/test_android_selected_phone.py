"""Static scope checks, not Android provider/grant/UI acceptance."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'android/app/src/main/java/com/ashok/aether'


def test_specific_number_picker_requires_local_review_before_number_field():
    source = (BASE/'PhoneActions.kt').read_text()
    assert 'ActivityResultContracts.StartActivityForResult()' in source
    assert 'Intent(Intent.ACTION_PICK).setType(ContactsContract.CommonDataKinds.Phone.CONTENT_TYPE)' in source
    assert 'selectedPhoneCandidate = candidate' in source
    assert 'Use this candidate in number field' in source
    assert 'Discard selected candidate' in source
    assert 'result.resultCode != Activity.RESULT_OK' in source
    assert 'No recipient identity verified' in source
    assert source.count('Button(enabled = selectedPhoneCandidate == null, onClick = {') == 2
    assert 'Previous number field cleared to avoid using another contact' in source


def test_only_selected_content_uri_number_column_no_fallback_or_directory_grant():
    source = (BASE/'SelectedPhoneNumber.kt').read_text()
    assert 'uri.scheme != "content"' in source
    assert 'context.contentResolver.query(uri, arrayOf(ContactsContract.CommonDataKinds.Phone.NUMBER, ContactsContract.Data.MIMETYPE)' in source
    assert 'if (cursor.moveToNext()) null else number' in source
    assert 'cursor.getString(kind) != ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE' in source
    assert 'selectedPhoneRouteAllowed(uri.authority, uri.pathSegments, uri.query, uri.fragment)' in source
    assert 'authority != "com.android.contacts"' in source
    for marker in ['CONTENT_URI', 'DISPLAY_NAME', 'takePersistableUriPermission', 'getContacts',
                   'HttpURLConnection', 'URL(', 'TokenVault', 'Intent.ACTION_CALL', 'SmsManager']:
        assert marker not in source
    manifest = (ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
    assert 'READ_CONTACTS' not in manifest


def test_docs_keep_narrow_scope_and_device_uncertainty():
    text = ' '.join((ROOT/'docs/ANDROID-SELECTED-PHONE-NUMBER.md').read_text().split()).lower()
    for phrase in ['No country code', 'temporary', 'not verified identity', 'no directory',
                   'No emulator', 'No READ_CONTACTS', 'explicit review']:
        assert phrase.lower() in text
