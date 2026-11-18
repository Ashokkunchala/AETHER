import asyncio
import json

import pytest

from aether.job_evidence import review_job_evidence, register_job_evidence
from aether.security import SecurityStore
from aether.tools.registry import ToolRegistry


def request(phrase='Python', resume='Built a Python demo.', job='Python is required.'):
    return {'resume_text': resume, 'job_text': job, 'requirements': [{'phrase': phrase, 'importance': 'required'}]}


def test_exact_context_no_score_and_caller_labels():
    result = review_job_evidence(**request(resume='Personal notes\nNo Python production experience\nA future learning goal'))
    row = result['requirements'][0]
    assert row['literal_mention_in_resume']
    assert 'No Python production experience' in row['resume_mentions'][0]['exact_excerpt']
    assert row['importance_asserted_by_caller'] == 'required'
    assert result['score'] is None
    assert not result['resume_version_verified']
    assert row['state'] == 'literal_mention_needs_review'


@pytest.mark.parametrize('resume,expected', [('Pythonic', False), ('CPython', False), ('PYTHON', True), ('Ｐｙｔｈｏｎ', True), ('(Python)', True), ('Python_thing', False), ('No experience in Python', True)])
def test_literal_normalization_and_boundaries(resume, expected):
    assert review_job_evidence(**request(resume=resume))['requirements'][0]['literal_mention_in_resume'] == expected


def test_whole_text_match_across_lines_is_not_fake_excerpt():
    result = review_job_evidence(**request('distributed systems', 'Studied distributed\nsystems in a fictional exercise', 'distributed systems required'))
    row = result['requirements'][0]
    assert row['literal_mention_in_resume'] and not row['context_excerpt_available']
    assert row['resume_mentions'] == []


def test_no_synonym_claim_or_skills_inference():
    row = review_job_evidence(**request('Kubernetes', 'Deployed a k8s toy example', 'Kubernetes required'))['requirements'][0]
    assert not row['literal_mention_in_resume']
    assert row['state'] == 'no_literal_mention_found'
    assert 'does not prove a skill gap' in row['review_prompt']


@pytest.mark.parametrize('mutate', [lambda d:d.update(resume_text=''), lambda d:d.update(job_text='unrelated job'), lambda d:d.update(requirements=[]), lambda d:d.update(requirements=[{'phrase': 'Python', 'importance': 'must'}]), lambda d:d.update(requirements=[{'phrase': 'Python', 'importance': []}]), lambda d:d.update(resume_text='x'*60001), lambda d:d.update(requirements=[{'phrase': 'Python', 'importance': 'required'}]*41), lambda d:d.update(resume_text='x\x00secret')])
def test_bad_or_invented_evidence_refused(mutate):
    data = request();mutate(data)
    with pytest.raises(ValueError):
        review_job_evidence(**data)


def test_duplicate_normalized_requirements_refused():
    data = request();data['requirements'].append({'phrase': 'PYTHON', 'importance': 'preferred'})
    with pytest.raises(ValueError):
        review_job_evidence(**data)


def test_excerpt_limits_and_no_instruction_execution():
    data = request(resume='Python ' + 'x'*5000 + '\nPython\nPython\nPython\nPython')
    result = review_job_evidence(**data)
    rows = result['requirements'][0]['resume_mentions']
    assert len(rows) == 3
    assert all(len(row['exact_excerpt']) <= 1200 for row in rows)
    assert rows[0]['excerpt_truncated']
    assert 'not ATS score' in result['notice']


def test_registry_fresh_review_stop(tmp_path, monkeypatch):
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    registry = ToolRegistry();registry.security_store = SecurityStore();register_job_evidence(registry)
    tool = registry.get('review_job_evidence')
    assert tool.never_auto_approve and not tool.allow_always and not tool.allow_auto_approve
    assert not asyncio.run(registry.execute(tool.name, request(), auto_approve=True)).ok
    async def approve(*_):
        return True
    assert asyncio.run(registry.execute(tool.name, request(), confirm=approve)).ok
    SecurityStore().set_stop(True)
    assert not asyncio.run(registry.execute(tool.name, request(), confirm=approve)).ok


def test_programming_punctuation_is_literal():
    assert review_job_evidence(**request('C++', 'Built a C++ demo', 'C++ preferred'))['requirements'][0]['literal_mention_in_resume']
    assert not review_job_evidence(**request('C++', 'Used C only', 'C++ preferred'))['requirements'][0]['literal_mention_in_resume']


def test_console_job_review_exact_spec(tmp_path, monkeypatch, capsys):
    import sys
    from types import SimpleNamespace
    from aether import owner_console as console
    path = tmp_path / 'evidence.json';path.write_text(json.dumps(request()))
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'review.db'))
    monkeypatch.setattr(sys, 'argv', ['owner-console', 'job-review', '--spec', str(path)])
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr('builtins.input', lambda _: 'APPROVE review_job_evidence')
    console.main()
    assert 'literal_mention_needs_review' in capsys.readouterr().out
