import asyncio

import pytest

from jarvis.devops.postmortem import draft_postmortem


def test_supplied_cause_not_verification_and_draft_carries_notice():
    result=draft_postmortem('API errors',root_cause='Suspect timeout, not confirmed')
    assert result['success'] and result['draft_only'] and not result['root_cause_verified']
    assert 'root_cause' not in result['missing_sections']
    assert 'Suspect timeout, not confirmed' in result['markdown']
    assert '> DRAFT - caller-supplied claims' in result['markdown']
    assert 'not independently verified' in result['markdown']


def test_blank_list_entries_count_as_missing():
    result=draft_postmortem('Test',timeline=['  ','\n'],action_items=[''])
    assert {'timeline','action_items'} <= set(result['missing_sections'])
    assert result['timeline_entries_supplied']==0 and result['action_items_supplied']==0
    assert 'No timeline provided' in result['markdown']


def test_text_preserved_not_claimed_redacted_or_sanitized():
    text='PRIVATE_VALUE <b>markup</b> [link](https://example.invalid)'
    result=draft_postmortem('Draft',summary=text,timeline=['Later','Earlier'],action_items=['No owner/date'])
    assert text in result['markdown']
    for flag in ['sensitive_content_redacted','caller_claims_verified','timeline_chronology_verified','impact_verified','recovery_verified','action_owners_dates_verified','shared','followups_created']:
        assert result[flag] is False
    assert result['timeline_entries_supplied']==2 and result['action_items_supplied']==1


@pytest.mark.parametrize('field,value',[('title',1),('title','x'*201),('title','a\nb'),('summary',None),('impact','x'*10001),('root_cause',{}),('detection',False),('resolution',3),('timeline','text'),('timeline',[1]),('timeline',['x'*2001]),('timeline',['x']*101),('action_items',[None]),('action_items',{}),('action_items',['x']*101)])
def test_invalid_types_bounds_refused_without_partial_report(field,value):
    params={'title':'Test',field:value}
    result=draft_postmortem(**params)
    assert not result['success'] and 'markdown' not in result


def test_boundary_limits_and_no_source_inference():
    result=draft_postmortem('t'*200,summary='x'*10000,timeline=['x'*2000]*100,action_items=['x']*100)
    assert result['success'] and result['timeline_entries_supplied']==100
    assert 'impact' in result['missing_sections']


def test_no_files_or_execution(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.chdir(tmp_path)
    def fail(*a,**kw):raise AssertionError('Must not execute')
    monkeypatch.setattr(subprocess,'run',fail)
    assert draft_postmortem('Draft')['success'] and list(tmp_path.iterdir())==[]


def test_safe_registry_after_stop(tmp_path,monkeypatch):
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB',str(tmp_path/'security.db'))
    registry=build_registry(force=True);SecurityStore().set_stop(True)
    result=asyncio.run(registry.execute('draft_postmortem',{'title':'Draft'}))
    assert result.ok and not result.data['shared']
