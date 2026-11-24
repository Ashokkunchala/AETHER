from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android/app'
JAVA = ANDROID / 'src/main/java/com/ashok/aether'
NS = '{http://schemas.android.com/apk/res/android}'


def test_launcher_icon_and_explicit_shortcut_are_registered():
    manifest = ET.parse(ANDROID / 'src/main/AndroidManifest.xml').getroot()
    app = manifest.find('application')
    assert app.attrib[NS+'icon'] == '@mipmap/ic_launcher'
    shortcut = ET.parse(ANDROID / 'src/main/res/xml/shortcuts.xml').find('shortcut')
    intent = shortcut.find('intent')
    assert intent.attrib[NS+'targetPackage'] == 'com.ashok.aether'
    assert intent.attrib[NS+'targetClass'] == 'com.ashok.aether.MainActivity'
    assert intent.attrib[NS+'action'] == 'com.ashok.aether.action.START_LIVE_VOICE'
    assert 'android.intent.category.HOME' not in ET.tostring(manifest).decode()


def test_launcher_does_not_start_microphone_from_intent():
    main = (JAVA / 'MainActivity.kt').read_text()
    activity = main[main.index('class MainActivity'):main.index('@Composable')]
    assert 'startLiveVoice' not in activity
    assert 'savedInstanceState == null' in activity
    assert 'SectionCard(title = "QUICK START")' in main
    assert 'safeDrawingPadding()' in main


def test_authenticated_connections_do_not_follow_redirects():
    main = (JAVA / 'MainActivity.kt').read_text()
    assert 'connection.instanceFollowRedirects = false' in main
    assert main.count('backendOrigin(base)') == 3
    voice = (JAVA / 'LiveVoiceController.kt').read_text()
    assert 'followRedirects(false).followSslRedirects(false)' in voice
    assert 'connection.instanceFollowRedirects = false' in voice
    worker = (JAVA / 'ReminderWorker.kt').read_text()
    assert 'connection.instanceFollowRedirects = false' in worker
    assert 'inboxConnection.instanceFollowRedirects = false' in worker


def test_unsigned_release_never_uses_debug_signer():
    gradle = (ANDROID / 'build.gradle.kts').read_text()
    assert 'signingConfigs.getByName("debug")' not in gradle
