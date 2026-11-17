"""Packaging invariants, not execution on the owner's machine."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reviewed_installer_pinned_fresh_folder_and_no_automatic_launch():
    source = (ROOT / 'scripts/install-aether-reviewed.ps1').read_text()
    assert "'__AETHER_BUILD_COMMIT__'" in source
    assert "'^[0-9a-f]{40}$'" in source
    assert 'archive/$commit.zip' in source
    assert 'DOWNLOAD AETHER' in source and 'INSTALL REVIEWED PACKAGES' in source
    assert "-cne 'DOWNLOAD AETHER'" in source and "-cne 'INSTALL REVIEWED PACKAGES'" in source
    assert 'Destination already exists. No overwrite allowed.' in source
    assert '-NoApiKeyPrompt' in source
    assert 'NewGuid()' in source
    for forbidden in ('Register-ScheduledTask', 'Set-NetFirewall', 'Start-Process', 'start-windows.ps1', 'install-jarvis-startup.ps1', 'git reset', 'git clean', 'Uninstall'):
        assert forbidden not in source
    assert source.count('Remove-Item') == 1
    assert 'Remove-Item -LiteralPath $tempRoot' in source


def test_ci_builds_and_uploads_exact_windows_payload_without_running_it():
    workflow = (ROOT / '.github/workflows/tests.yml').read_text()
    assert "Replace('__AETHER_BUILD_COMMIT__', $env:GITHUB_SHA)" in workflow
    assert '-InstallerPath' in workflow and '-SelfTest' in workflow
    assert 'dist/AETHER-Setup.exe' in workflow and 'dist/AETHER-Source.zip' in workflow
    assert 'name: aether-windows-setup' in workflow
    assert 'name: jarvis-android-debug-apk' in workflow
    assert 'SHA256SUMS.txt' in workflow and 'SOURCE-COMMIT.txt' in workflow
    assert 'retention-days: 14' in workflow
    assert '& .\\dist\\AETHER-Setup.exe' not in workflow
    assert 'git archive --format=zip --output=dist/AETHER-Source.zip HEAD' in workflow


def test_binary_guide_is_honest_about_setup_vs_standalone():
    guide = (ROOT / 'docs/INSTALLABLE-FILES.md').read_text()
    assert 'not a standalone' in guide and 'unsigned' in guide
    assert 'do not bypass unexplained' in guide
    assert 'not an offline installer' in guide and '14 days' in guide
    assert 'same successful run' in guide
