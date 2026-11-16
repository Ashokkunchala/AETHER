"""Offline source/metadata checks only. Never query/control the host laptop."""
from pathlib import Path

from jarvis.tools.builtin_tools import build_registry
from windows_agent.agent import app

ROOT=Path(__file__).resolve().parents[1]


def test_helper_has_only_narrow_business_endpoints():
    routes={(r.path,method) for r in app.routes for method in getattr(r,'methods',set()) if r.path not in {'/openapi.json','/docs','/docs/oauth2-redirect','/redoc'}}
    assert routes=={('/health','GET'),('/v1/status','GET'),('/v1/open-url','POST')}


def test_source_contract_does_not_claim_remote_enforcement():
    text=(ROOT/'docs/WINDOWS-CAPABILITY-CONTRACT.md').read_text()
    for phrase in ['No real laptop','not proof','not utilization','not an approved-app allowlist',"isn't task cancellation",'explicitly requested','remaining gaps','not a newly implemented API','unknown/still running','PID reuse','loopback-only']:
        assert phrase.lower() in text.lower()


def test_registry_sensitive_execution_gates_without_controller_calls(tmp_path,monkeypatch):
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    registry=build_registry(force=True)
    for name in ['run_shell','kill_process','start_process','close_app']:
        assert registry.get(name).confirm_required
    # Existing gap is named explicitly, never misrepresented as enforcement.
    assert registry.get('screenshot').confirm_required
    text=(ROOT/'docs/WINDOWS-CAPABILITY-CONTRACT.md').read_text()
    assert 'fresh scoped confirmation' in text


def test_stop_contract_does_not_claim_thread_cancellation():
    source=(ROOT/'jarvis/tools/orchestrator.py').read_text()
    assert 'Never report such an action as stopped by timeout.' in source
    text=(ROOT/'docs/WINDOWS-CAPABILITY-CONTRACT.md').read_text()
    assert 'Does not guarantee cancellation' in text


def test_readme_aether_and_scope_link():
    source=(ROOT/'windows_agent/README.md').read_text()
    assert source.startswith('# AETHER') and 'WINDOWS-CAPABILITY-CONTRACT.md' in source
    assert 'caller-supplied confirmed boolean' in source
