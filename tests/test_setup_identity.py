"""Source-only checks: never execute installers or change a Windows device."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checkout_guide_targets_current_feature_branch():
    text = (ROOT / 'docs/INSTALLATION-AND-LIVE-TERMINAL.md').read_text()
    assert 'improve/security-quality-gates' not in text
    assert 'git switch jarvis-cinematic-local-voice' in text
    assert 'git pull origin jarvis-cinematic-local-voice' in text
    assert 'git clone --branch jarvis-cinematic-local-voice https://github.com/Ashokkunchala/AETHER.git' in text
    assert 'Keep its current folder name' in text


def test_installer_displays_aether_but_keeps_existing_paths_and_task():
    text = (ROOT / 'INSTALL-JARVIS.ps1').read_text()
    assert 'AETHER Personal AI - Windows installer' in text
    assert 'Programs\\JarvisPersonalAI' in text
    assert '-TaskName "JARVIS Personal AI"' in text
    assert 'JARVIS_API_TOKEN' in text
    assert 'JARVIS_AI_PROVIDER' in text
    assert 'jarvis-cinematic-local-voice' in text
    assert 'Starting AETHER' in text
    assert (ROOT / 'scripts/uninstall-jarvis.ps1').is_file()
    assert (ROOT / 'scripts/install-jarvis-startup.ps1').is_file()


def test_batch_entry_points_preserve_scripts_and_show_current_name():
    for name in ['INSTALL_JARVIS.bat', 'START-JARVIS.bat']:
        text = (ROOT / name).read_text()
        assert 'AETHER Personal AI -' in text
        assert 'scripts\\start-windows.ps1' in text
        assert 'stop JARVIS' not in text
    assert 'scripts\\setup-windows.ps1' in (ROOT / 'INSTALL_JARVIS.bat').read_text()


def test_legacy_readme_points_to_real_guides_without_unbounded_claims():
    import re
    text = (ROOT / 'JARVIS_README.md').read_text()
    assert text.startswith('# AETHER')
    assert 'Remembers everything' not in text
    assert 'Full Windows Control' not in text
    assert 'not verified app/track' in text
    assert 'legacy jarvis model' in text
    for link in re.findall(r'\]\(([^)]+)\)', text):
        assert (ROOT / link).is_file(), link


def test_terminal_transcript_label_matches_active_display():
    text = (ROOT / 'docs/WINDOWS-TERMINAL.md').read_text()
    assert '`You:` / `AETHER:`' in text
    assert '`JARVIS.lnk`' in text
    assert 'legacy neural wake trigger' in text
