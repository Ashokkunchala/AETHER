from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "android/app/src/main/java/com/ashok/jarvis"


def test_semantic_image_models_are_bundled_bounded_and_never_dispatch_ocr():
    source = (JAVA / "ImageUnderstanding.kt").read_text()
    gradle = (ROOT / "android/app/build.gradle.kts").read_text()
    assert 'com.google.mlkit:image-labeling:17.0.9' in gradle
    assert 'com.google.mlkit:text-recognition:16.0.1' in gradle
    assert "play-services-mlkit" not in gradle
    for marker in ("8 * 1024 * 1024 + 1", "inJustDecodeBounds = true", "imageSampleSize", "labeler.process(input).finished()", "reader.process(input).finished()", "take(8)", "take(4000)", "reader.close()", "labeler.close()", "bitmap.recycle()", "not calibrated truth probabilities", "never instructions"):
        assert marker in source
    for prohibited in ("HttpURLConnection", "okhttp", "TokenVault", "ProcessBuilder", "Runtime.getRuntime", "exec(", "ToolRegistry"):
        assert prohibited not in source


def test_camera_and_analysis_are_distinct_user_actions_with_lifecycle_suppression():
    card = (JAVA / "AdvancedCompanionCard.kt").read_text()
    assert "AdvancedCompanionCard()" in (JAVA / "MainActivity.kt").read_text()
    for marker in ("TakePicturePreview()", "GetContent()", "Understand selected image locally", "Lifecycle.Event.ON_STOP", "ticket == generation", "currentCoroutineContext().ensureActive()", "job?.cancel()", "reviewReminder = false"):
        assert marker in card
    assert "rememberSaveable" not in card
    manifest = ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml").getroot()
    permissions = {node.attrib['{http://schemas.android.com/apk/res/android}name'] for node in manifest.findall("uses-permission")}
    assert "android.permission.CAMERA" not in permissions
    assert "android.permission.ACCESS_FINE_LOCATION" not in permissions
    assert "android.permission.ACCESS_BACKGROUND_LOCATION" in permissions


def test_background_worker_is_local_expiring_once_and_separate_from_foreground_card():
    source = (JAVA / "LocationReminderWorker.kt").read_text()
    for marker in ("PeriodicWorkRequestBuilder<LocationReminderWorker>(15", "ACCESS_BACKGROUND_LOCATION", "ACCESS_COARSE_LOCATION", "POST_NOTIFICATIONS", "BOOT_COUNT", "expires_elapsed", "created_elapsed", "freshLocation", "definitelyInside", "current != target", "state", "cancelUniqueWork"):
        if marker == "state":
            continue
        assert marker in source
    for prohibited in ("TokenVault", "HttpURLConnection", "getLastKnownLocation", "requestLocationUpdates", "Result.retry()", "ACCESS_FINE_LOCATION"):
        assert prohibited not in source
    assert source.index('prefs(context).edit().clear().commit()', source.index('val message =')) < source.index('manager.notify(')
    card = (JAVA / "AdvancedCompanionCard.kt").read_text()
    assert "does NOT disable" in card and "Enable this exact local background reminder" in card
    assert "best-effort every 15 minutes" in card and "separate time reminder" in card
