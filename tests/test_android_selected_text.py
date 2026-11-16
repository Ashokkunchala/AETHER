"""Source boundaries only. No Android device/provider content is read."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'android/app/src/main/java/com/ashok/jarvis'


def test_selected_text_requires_separate_explicit_read_and_keeps_io_off_main():
    source = (BASE/'SelectedTextCard.kt').read_text()
    assert 'ActivityResultContracts.OpenDocument()' in source
    assert 'picker.launch(arrayOf("text/plain", "text/markdown"))' in source
    assert 'Read selected text locally (max 64 KiB)' in source
    assert 'withContext(Dispatchers.IO)' in source
    assert 'resolver.openInputStream(uri)?.use { decodeSelectedText(it) }' in source
    assert 'mime == "text/plain" || mime == "text/markdown"' in source
    assert 'ensureActive()' in source
    assert 'if (generation == thisGeneration) busy = false' in source
    parent = (BASE/'PhoneActions.kt').read_text()
    assert 'key(selectedTextReset) { SelectedTextCard() }' in parent
    assert 'selectedTextReset++;' in parent
    for marker in ['TokenVault', 'BackendClient', 'HttpURLConnection', 'URL(',
                   'takePersistableUriPermission', 'OpenDocumentTree', 'setPrimaryClip',
                   'rememberSaveable', 'Intent.ACTION_VIEW']:
        assert marker not in source


def test_bounded_strict_text_and_literal_search_not_regex_or_instructions():
    source = (BASE/'SelectedText.kt').read_text()
    for marker in ['SELECTED_TEXT_MAX_BYTES = 65536', 'CodingErrorAction.REPORT',
                   'bytes.size() > SELECTED_TEXT_MAX_BYTES', 'count == 0',
                   'line.contains(query, ignoreCase = true)', 'matches.size == 100',
                   'query.length <= 200', '0x202A..0x202E', '0x2066..0x2069']:
        assert marker in source
    for marker in ['readBytes()', 'readText()', 'Regex(', 'ProcessBuilder', 'Runtime.getRuntime']:
        assert marker not in source


def test_text_guide_preserves_missing_device_acceptance_and_provider_risks():
    text = ' '.join((ROOT/'docs/ANDROID-SELECTED-TEXT.md').read_text().split()).lower()
    for phrase in ['No emulator', 'not secure erasure', 'provider may download',
                   'no upload', 'not a device-wide', 'not guaranteed', '65536',
                   'not verified identity', 'UTF-8']:
        assert phrase.lower() in text
