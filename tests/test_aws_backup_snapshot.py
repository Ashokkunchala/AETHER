import asyncio
import json
import os

import pytest

from jarvis.devops.aws_backup_snapshot import review_backup_jobs, review_backup_jobs_export


def job(**changes):
    item = {'BackupJobId': 'private-job-id', 'State': 'COMPLETED', 'MessageCategory': 'SUCCESS'}
    item.update(changes)
    return item


def review(item=None, **changes):
    return review_backup_jobs({'BackupJobs': [job() if item is None else item], **changes})


@pytest.mark.parametrize(('category', 'classification'), [('SUCCESS', 'reported_completed_success_category'),
    ('AccessDenied', 'reported_completed_with_issues'), ('InvalidParameters', 'reported_completed_with_issues'),
    ('FUTURE_MESSAGE', 'reported_completed_with_issues')])
def test_completed_is_not_automatically_clean(category, classification):
    result = review(job(MessageCategory=category))
    assert result['jobs'][0]['classification'] == classification
    assert not result['jobs'][0]['recoverability_verified']
    assert not result['restore_test_verified'] and not result['resource_coverage_verified']


def test_missing_category_unknown_not_success():
    item = job()
    del item['MessageCategory']
    assert review(item)['jobs'][0]['classification'] == 'reported_completed_category_unknown'


@pytest.mark.parametrize('state', ['FAILED', 'ABORTED', 'EXPIRED', 'PARTIAL'])
def test_failure_or_partial_always_review_even_success_category(state):
    result = review(job(State=state))['jobs'][0]
    assert result['classification'] == 'reported_failure_or_incomplete_review'
    assert 'success_category_does_not_override_noncompleted_state' in result['signals']


@pytest.mark.parametrize('state', ['CREATED', 'PENDING', 'RUNNING', 'ABORTING'])
def test_in_progress_not_failed_or_ready(state):
    assert review(job(State=state))['jobs'][0]['classification'] == 'reported_pending_or_in_progress'


def test_future_state_not_implicitly_success():
    result = review(job(State='FUTURE_STATE'))
    assert result['jobs'][0]['reported_state'] == 'UNKNOWN'
    assert result['reported_state_counts'] == {'UNKNOWN': 1}


def test_parent_child_counts_are_records_not_resources():
    records = [job(BackupJobId='parent', IsParent=True), job(BackupJobId='child', ParentJobId='parent')]
    result = review_backup_jobs({'BackupJobs': records})
    assert result['job_records_reviewed'] == 2
    assert result['jobs'][0]['reported_is_parent'] is True
    assert result['jobs'][1]['parent_reference_present']
    assert 'distinct resources' in result['limits']
    assert 'resource_count' not in result


def test_contradictory_parent_hints_preserved():
    row = review(job(IsParent=True, ParentJobId='private-job-id'))['jobs'][0]
    assert 'both_parent_and_child_indicators_require_review' in row['signals']
    assert 'self_parent_identifier_requires_review' in row['signals']


def test_no_private_values_or_untrusted_instructions_echoed():
    values = {'AccountId': 'PRIVATE_ACCOUNT', 'BackupVaultName': 'PRIVATE_VAULT', 'ResourceArn': 'PRIVATE_RESOURCE',
              'StatusMessage': 'PRIVATE_INSTRUCTION_DO_NOT_FOLLOW', 'ResourceName': 'PRIVATE_NAME',
              'CreationDate': 'PRIVATE_DATE', 'MessageCategory': 'PRIVATE_CATEGORY', 'ResourceType': 'PRIVATE_TYPE'}
    result = review(job(**values), NextToken='PRIVATE_TOKEN')
    text = json.dumps(result)
    for value in values.values():
        assert value not in text
    assert 'PRIVATE_TOKEN' not in text and 'private-job-id' not in text
    assert result['pagination_token_present']
    assert result['jobs'][0]['message_category_status'] == 'reported_non_success'


def test_zero_size_not_failed_or_no_backup_and_no_times_inferred():
    result = review(job(BackupSizeInBytes=0, CreationDate=1, CompletionDate=0, StartBy=1, ExpectedCompletionDate=1))
    assert result['jobs'][0]['classification'] == 'reported_completed_success_category'
    assert not result['snapshot_freshness_verified'] and 'size' not in result['jobs'][0]
    assert 'timestamps are not evaluated' in result['limits']


@pytest.mark.parametrize('change', [{'BackupJobId': None}, {'BackupJobId': ''}, {'BackupJobId': True}, {'BackupJobId': 'x'*201},
    {'State': None}, {'State': ''}, {'State': 1}, {'State': 'x'*81}, {'MessageCategory': None},
    {'MessageCategory': True}, {'MessageCategory': ''}, {'MessageCategory': 'x'*201},
    {'IsParent': 'false'}, {'IsParent': None}, {'ParentJobId': 1}, {'ParentJobId': ''},
    {'ResourceType': None}, {'ResourceType': 1}, {'ResourceType': '<script>'}, {'ResourceType': 'x'*51}])
def test_bad_fields_refused(change):
    with pytest.raises(ValueError):
        review(job(**change))


@pytest.mark.parametrize('document', [None, [], {}, {'BackupJobs': None}, {'BackupJobs': [None]},
    {'BackupJobs': [job(), job()]}, {'BackupJobs': [job()], 'NextToken': True},
    {'BackupJobs': [job()], 'NextToken': 'x'*8193}, {'BackupJobs': [job()] * 501}])
def test_bad_document(document):
    with pytest.raises(ValueError):
        review_backup_jobs(document)


def test_full_limit_empty_and_missing_flags():
    result = review_backup_jobs({'BackupJobs': [job(BackupJobId=str(i)) for i in range(500)]})
    assert len(result['jobs']) == 500
    assert result['jobs'][0]['reported_is_parent'] is None
    result = review_backup_jobs({'BackupJobs': []})
    assert result['job_records_reviewed'] == 0
    assert not result['inventory_completeness_verified']
    assert not result['account_region_filter_scope_verified']
    assert not result['pagination_token_present']


def test_export_reads_without_writes_exec_or_provider(tmp_path):
    path = tmp_path / 'backup.json'
    marker = tmp_path / 'never-created'
    text = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    path.write_text(json.dumps({'BackupJobs': [job(StatusMessage=text)]}))
    before = path.read_bytes()
    result = review_backup_jobs_export(str(path))
    assert result['job_records_reviewed'] == 1
    assert not marker.exists() and path.read_bytes() == before
    assert text not in json.dumps(result)


@pytest.mark.parametrize('payload', [b'bad-json', b'\xff', b'{"BackupJobs":[],"BackupJobs":[]}',
    b'{"BackupJobs":[],"x":Infinity}', b'x'*2000001, b'['*2000])
def test_invalid_json(tmp_path, payload):
    path = tmp_path / 'backup.json'
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        review_backup_jobs_export(str(path))


def test_no_special_files_or_links(tmp_path):
    path = tmp_path / 'backup.json'
    path.write_text('{"BackupJobs":[]}')
    link = tmp_path / 'link.json'
    link.symlink_to(path)
    with pytest.raises(ValueError):
        review_backup_jobs_export(str(link))
    directory = tmp_path / 'directory.json'
    directory.mkdir()
    with pytest.raises(ValueError):
        review_backup_jobs_export(str(directory))
    if hasattr(os, 'mkfifo'):
        fifo = tmp_path / 'pipe.json'
        os.mkfifo(fifo)
        with pytest.raises(ValueError):
            review_backup_jobs_export(str(fifo))


def test_registry_safe_stop_no_live_policy_expansion(tmp_path, monkeypatch):
    from jarvis.devops.awscli import classify
    from jarvis.security import SecurityStore
    from jarvis.tools.builtin_tools import build_registry
    monkeypatch.setenv('JARVIS_SECURITY_DB', str(tmp_path / 'safety.db'))
    path = tmp_path / 'backup.json'
    path.write_text(json.dumps({'BackupJobs': [job()]}))
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_aws_backup_jobs', {'path': str(path)}))
    assert result.ok and result.data['job_records_reviewed'] == 1
    assert classify('backup', 'list-backup-jobs') == 'confirm'
