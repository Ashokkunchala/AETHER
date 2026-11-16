"""Source protocol boundaries, not Android runtime/layout acceptance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "android/app/src/main/java/com/ashok/jarvis"


def test_foreground_separate_token_fixed_action_and_no_approval_or_shell():
    source = (BASE / "RemoteReadCard.kt").read_text()
    for value in [
        "HttpsURLConnection",
        "instanceFollowRedirects = false",
        "connection.connectTimeout = 8000",
        "connection.readTimeout = 8000",
        "8192",
        "withContext(Dispatchers.IO)",
        "generation == activeGeneration",
        "Dedicated laptop-issued per-device token",
        "Check this request once",
        "not cancel",
        "memory_snapshot",
    ]:
        assert value in source
    for value in [
        "TokenVault",
        "rememberSaveable",
        "WorkManager",
        "ProcessBuilder",
        "Runtime.getRuntime",
        "/approve",
        "/execute",
        "/review",
        "delay(",
        "while (busy)",
        "TrustManager",
        "HostnameVerifier",
    ]:
        assert value not in source
    assert "RemoteReadCard()" in (BASE / "MainActivity.kt").read_text()


def test_server_api_has_no_pair_approve_or_execute_route():
    source = (ROOT / "windows_agent/remote_read_api.py").read_text()
    assert "Literal['memory_snapshot']" in source or 'Literal["memory_snapshot"]' in source
    assert 'extra="forbid"' in source
    assert source.count("@router.") == 2
    assert "review_local(" not in source and "provision_local(" not in source
    implementation = (ROOT / "windows_agent/remote_read.py").read_text()
    for forbidden in [
        "subprocess",
        "os.system",
        "ToolRegistry",
        "build_registry",
        "eval(",
        "exec(",
    ]:
        assert forbidden not in implementation
