import asyncio
import json

import pytest

from aether.mentor_terraform import SAMPLE_HCL, review_validate, terraform_lesson


def report(**kwargs):
    value = {'format_version': '1.0', 'valid': True, 'error_count': 0,
             'warning_count': 0, 'diagnostics': []}
    value.update(kwargs)
    return json.dumps(value)


def test_progressive_teaching_has_sample_manual_commands_and_review():
    assert 'resource "terraform_data" "service"' in SAMPLE_HCL
    assert 'aws_' not in SAMPLE_HCL and 'provisioner' not in SAMPLE_HCL
    first, practice, review = [terraform_lesson(i) for i in range(3)]
    assert first['lesson']['sample_hcl'] == SAMPLE_HCL
    assert practice['lesson']['manual_commands'][-1] == 'terraform plan -input=false -refresh=false'
    assert 'terraform validate -json' in practice['lesson']['manual_commands']
    assert all(not any(word in c for word in ['apply', 'destroy', 'aws ']) for c in practice['lesson']['manual_commands'])
    assert len(review['lesson']['interview_questions']) == 4
    assert 'No AWS resources' in first['scope']
    first['lesson']['deliverables'].clear()
    assert terraform_lesson(0)['lesson']['deliverables']


@pytest.mark.parametrize('stage', [-1, 3, True, '1', None])
def test_invalid_stage(stage):
    with pytest.raises(ValueError):
        terraform_lesson(stage)


def test_supplied_success_never_claims_verified_code_or_execution():
    result = review_validate(report())
    assert result['reported_valid'] is True
    assert result['origin_verified'] is False
    assert result['commands_executed'] is False and result['code_verified'] is False
    assert 'fabricated' in result['notice']
    assert 'score' not in result
    assert 'plan may still fail' in result['next']


def test_errors_and_warnings_are_not_blended():
    result = review_validate(report(valid=False, error_count=1, warning_count=1,
        diagnostics=[{'severity': 'error', 'summary': 'Undeclared variable', 'detail': 'private detail', 'snippet': {'code': 'private code'}},
                     {'severity': 'warning', 'summary': 'Deprecated expression'}]))
    assert result['reported_errors'] == result['reported_warnings'] == 1
    assert result['reported_valid'] is False
    assert result['diagnostics'][0] == {'severity': 'error', 'summary': 'Undeclared variable'}
    assert 'private' not in json.dumps(result)
    assert review_validate(report(warning_count=1, diagnostics=[{'severity': 'warning', 'summary': 'Check me'}]))['reported_valid'] is True


@pytest.mark.parametrize('text', ['', '/tmp/report.json', 'not-json', '[]', 'null', '1', '{"x":NaN}', '[' * 2000,
    '{"format_version":"1.0","format_version":"1.1"}', 'x' * 65537])
def test_bad_or_ambiguous_input_rejected(text):
    with pytest.raises(ValueError):
        review_validate(text)


@pytest.mark.parametrize('change', [
    {'format_version': '2.0'}, {'format_version': 1}, {'format_version': '1.0beta'},
    {'valid': 'true'}, {'valid': 1}, {'error_count': True}, {'error_count': -1},
    {'warning_count': 1.5}, {'diagnostics': {}}, {'valid': False},
    {'error_count': 1}, {'warning_count': 1},
    {'diagnostics': [{'severity': 'info', 'summary': 'Hello'}]},
    {'warning_count': 1, 'diagnostics': [{'severity': 'warning'}]},
    {'warning_count': 1, 'diagnostics': [{'severity': 'warning', 'summary': 4}]},
    {'diagnostics': [None]}, {'diagnostics': [{'severity': [], 'summary': 'bad type'}]},
])
def test_inconsistent_report_not_treated_as_pass(change):
    with pytest.raises(ValueError):
        review_validate(report(**change))


def test_additive_minor_fields_accepted_without_reflecting_them():
    value = review_validate(report(format_version='1.99', future_private_field='UNIQUE_PRIVATE_SENTINEL'))
    assert value['reported_valid']
    assert 'UNIQUE_PRIVATE_SENTINEL' not in str(value)


def test_diagnostic_summary_is_bounded_literal_data(tmp_path):
    marker = tmp_path / 'never-created'
    text = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    result = review_validate(report(warning_count=12, diagnostics=[{'severity': 'warning', 'summary': text + ('x' * 300)} for _ in range(12)]))
    assert len(result['diagnostics']) == 10 and result['diagnostics_truncated']
    assert len(result['diagnostics'][0]['summary']) == 240
    assert not marker.exists()
    assert 'untrusted data' in result['notice']
    with pytest.raises(ValueError):
        review_validate(report(warning_count=101, diagnostics=[{'severity': 'warning', 'summary': 'a'}] * 101))


def test_utf8_byte_limit_and_strict_types():
    with pytest.raises(ValueError):
        review_validate(None)
    with pytest.raises(ValueError):
        review_validate(report(extra='\u0c05' * 22000).replace('\\u0c05', '\u0c05'))


def test_existing_project_journal_tracks_evidence_not_verified_labs(tmp_path):
    from aether.mentor_projects import ProjectStore
    store = ProjectStore(tmp_path / 'mentor.db')
    key = store.start('terraform_local_foundations')['session_id']
    for i in range(3):
        result = store.submit(key, i, 'Self-reported local practice, not a verified run')
        assert result['verified'] is False
    assert result['session']['state'] == 'all_evidence_submitted'
    assert ProjectStore(store.path).resume(key)['state'] == 'all_evidence_submitted'


def test_registry_uses_existing_safe_boundary_and_does_not_write_progress(tmp_path, monkeypatch):
    from aether.mentor import MentorStore
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_MENTOR_DB', str(tmp_path / 'mentor.db'))
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'security.db'))
    registry = build_registry(force=True)
    before = MentorStore().progress()
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('mentor_review_terraform_validate', {'json_text': report()}))
    assert result.ok and result.data['reported_valid'] and not result.data['code_verified']
    assert asyncio.run(registry.execute('mentor_terraform_lesson', {'stage': 0})).ok
    extra = asyncio.run(registry.execute('mentor_terraform_lesson', {'stage': 0, '_method': 'execute'}))
    assert extra.ok and extra.data == terraform_lesson(0)
    assert MentorStore().progress() == before
