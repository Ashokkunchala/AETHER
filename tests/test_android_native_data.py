from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "android/app/src/main/java/com/ashok/jarvis"


def test_native_data_is_integrated_not_backend_or_shell():
    card = (JAVA / "NativeDataCard.kt").read_text()
    assert "NativeDataCard()" in (JAVA / "MainActivity.kt").read_text()
    for forbidden in ("HttpURLConnection", "okhttp", "TokenVault", "ProcessBuilder", "Runtime.getRuntime", "takePersistableUriPermission", "getLastKnownLocation", "requestLocationUpdates"):
        assert forbidden not in card
    assert "Dispatchers.IO" in card
    assert "Lifecycle.Event.ON_STOP" in card
    assert "ticket == generation" in card
    assert "task?.cancel()" in card
    assert "rememberSaveable" not in card


def test_permissions_are_readonly_foreground_and_picker_scoped():
    manifest = ET.parse(ROOT / "android/app/src/main/AndroidManifest.xml").getroot()
    name = "{http://schemas.android.com/apk/res/android}name"
    permissions = {row.attrib[name] for row in manifest.findall("uses-permission")}
    assert "android.permission.READ_CALENDAR" in permissions
    assert "android.permission.ACCESS_COARSE_LOCATION" in permissions
    for suffix in ("WRITE_CALENDAR", "ACCESS_FINE_LOCATION", "ACCESS_BACKGROUND_LOCATION", "READ_MEDIA_IMAGES", "READ_EXTERNAL_STORAGE", "CAMERA"):
        assert "android.permission." + suffix not in permissions


def test_calendar_reads_instances_and_edits_only_via_composer():
    card = (JAVA / "NativeDataCard.kt").read_text()
    assert "CalendarContract.Instances.CONTENT_URI" in card
    assert "start + 7 * 86_400_000L" in card
    assert "rows.size < 21" in card and "result.take(20)" in card
    assert "CalendarContract.Calendars.VISIBLE" in card
    assert "Intent.ACTION_EDIT" in card and "row.id" in card
    for method in (".insert(", ".update(", ".delete(", "Intent.ACTION_DELETE"):
        assert method not in card
    assert "Tap Read next 7 days separately" in card


def test_image_stream_and_pixels_are_bounded_and_explicit():
    card = (JAVA / "NativeDataCard.kt").read_text()
    assert 'uri.scheme == "content"' in card
    assert 'setOf("image/jpeg", "image/png", "image/webp")' in card
    assert "8 * 1024 * 1024 + 1" in card
    assert "inJustDecodeBounds = true" in card and "imageSampleSize" in card
    assert "bitmap.recycle()" in card
    assert 'Text("Analyze selected pixels locally' in card
    assert "No object recognition, OCR" in card


def test_location_one_shot_has_timeout_age_accuracy_and_cancel_gates():
    card = (JAVA / "NativeDataCard.kt").read_text()
    assert "withTimeout(20_000)" in card
    assert "Build.VERSION.SDK_INT >= 30" in card
    assert "LocationManager.NETWORK_PROVIDER" in card
    assert "manager.getCurrentLocation" in card
    assert "invokeOnCancellation { signal.cancel() }" in card
    assert "SystemClock.elapsedRealtimeNanos() - fix.elapsedRealtimeNanos" in card
    assert "fix.hasAccuracy() && freshLocation" in card
    assert "definitelyInside" in card
    assert "catch (_: TimeoutCancellationException)" in card
    assert "Tap Check location separately" in card


def test_native_policy_has_executable_jvm_boundary_tests():
    tests = (ROOT / "android/app/src/test/java/com/ashok/jarvis/NativeDataPolicyTest.kt").read_text()
    for case in ("sampleBoundsAndRounding", "rejectsHostileImageDimensions", "rejectsStaleFutureAndInvalidFixes", "proximityNeedsWholeAccuracyCircle", "distanceHandlesDatelineAndPoles"):
        assert case in tests
