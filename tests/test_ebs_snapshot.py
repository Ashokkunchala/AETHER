import asyncio
import json
import os

import pytest

from aether.devops.ebs_snapshot import review_volumes, review_volumes_export


def volume(**kwargs):
    item = {'VolumeId': 'vol-01234567890abcdef', 'State': 'available', 'Size': 8,
            'Attachments': [], 'Encrypted': True, 'MultiAttachEnabled': False}
    item.update(kwargs)
    return item


def review(item=None, **kwargs):
    return review_volumes({'Volumes': [volume() if item is None else item], **kwargs})


def test_candidate_is_not_safe_cleanup_or_unused_claim():
    result = review()
    row = result['volumes'][0]
    assert row['classification'] == 'reported_available_unattached_review_candidate'
    assert row['safe_to_delete'] is False
    assert not result['inventory_completeness_verified']
    assert not result['snapshot_freshness_verified'] and not result['account_region_scope_verified']
    assert 'not proof unused' in result['limits']
    assert 'cost/savings' in result['limits']


@pytest.mark.parametrize('state', ['creating', 'in-use', 'deleting', 'deleted', 'error', 'future-state'])
def test_other_states_never_become_candidates(state):
    result = review(volume(State=state))
    assert result['volumes'][0]['classification'] == 'not_a_candidate_from_this_snapshot'
    assert result['volumes'][0]['safe_to_delete'] is False
    if state == 'future-state':
        assert result['volumes'][0]['reported_state'] == 'unknown'


def test_missing_attachments_is_unknown_not_empty():
    item = volume()
    del item['Attachments']
    row = review(item)['volumes'][0]
    assert row['attachment_records'] is None
    assert 'attachment_field_missing' in row['signals']
    assert row['classification'] != 'reported_available_unattached_review_candidate'


@pytest.mark.parametrize('state', ['attached', 'attaching', 'detaching', 'detached', 'busy', 'future-state'])
def test_even_detached_attachment_records_need_review(state):
    row = review(volume(Attachments=[{'State': state}]))['volumes'][0]
    assert row['attachment_records'] == 1
    assert row['classification'] != 'reported_available_unattached_review_candidate'
    assert 'available_with_attachment_records' in row['signals']


def test_managed_empty_volume_excluded_multi_attach_reported_separately():
    row = review(volume(Operator={'Managed': True, 'Principal': 'PRIVATE_SERVICE'}, MultiAttachEnabled=True))['volumes'][0]
    assert row['classification'] == 'service_managed_review_only'
    assert row['reported_multi_attach_enabled'] is True
    assert 'PRIVATE_SERVICE' not in json.dumps(row)
    assert review(volume(Operator={'Managed': False}))['volumes'][0]['classification'].endswith('review_candidate')


def test_pagination_presence_never_verified_completeness():
    for token in ['PRIVATE_TOKEN', '', None]:
        result = review(NextToken=token)
        assert result['pagination_token_present'] == bool(token)
        assert 'PRIVATE_TOKEN' not in json.dumps(result)
        assert result['inventory_completeness_verified'] is False
    assert review_volumes({'Volumes': []})['volumes_reviewed'] == 0


def test_tags_source_snapshot_and_identifiers_not_echoed_or_followed(tmp_path):
    marker = tmp_path / 'not-created'
    text = f"__import__('pathlib').Path({str(marker)!r}).touch()"
    row = volume(Tags=[{'Key': 'Name', 'Value': text}], SnapshotId='PRIVATE_SNAPSHOT',
                 KmsKeyId='PRIVATE_KEY', VolumeArn='PRIVATE_ARN', OwnerId='PRIVATE_ACCOUNT')
    result = review(row)
    assert not marker.exists()
    for value in [text, 'PRIVATE_SNAPSHOT', 'PRIVATE_KEY', 'PRIVATE_ARN', 'PRIVATE_ACCOUNT']:
        assert value not in json.dumps(result)


@pytest.mark.parametrize('item', [None, [], {}, {'Volumes': None}, {'Volumes': {}}, {'Volumes': [None]}])
def test_wrong_document_shapes(item):
    with pytest.raises(ValueError):
        review_volumes(item)


@pytest.mark.parametrize('change', [
    {'VolumeId': 'invalid'}, {'VolumeId': ['vol-12345678']}, {'State': None}, {'State': []},
    {'Size': True}, {'Size': -1}, {'Size': 1.5}, {'Attachments': None},
    {'Attachments': [None]}, {'Attachments': [{}]}, {'Attachments': [{'State': []}]},
    {'Attachments': [{}] * 101}, {'Encrypted': 'false'}, {'MultiAttachEnabled': 0},
    {'Operator': None}, {'Operator': {'Managed': 'false'}},
])
def test_invalid_fields_rejected_without_partial_success(change):
    with pytest.raises(ValueError):
        review(volume(**change))


def test_unknown_encryption_is_not_unencrypted_and_false_flag_exact():
    item = volume()
    del item['Encrypted']
    assert review(item)['volumes'][0]['reported_encrypted'] is None
    assert 'reported_unencrypted' in review(volume(Encrypted=False))['volumes'][0]['signals']


def test_duplicates_and_volume_bounds():
    with pytest.raises(ValueError, match='Duplicate'):
        review_volumes({'Volumes': [volume(), volume()]})
    with pytest.raises(ValueError, match='500'):
        review_volumes({'Volumes': [volume()] * 501})
    with pytest.raises(ValueError):
        review(NextToken=True)
    assert review(volume(VolumeId='vol-12345678'))['volumes_reviewed'] == 1


def test_export_reads_only_selected_file(tmp_path):
    path = tmp_path / 'volumes.json'
    text = json.dumps({'Volumes': [volume()]})
    path.write_text('\ufeff' + text, encoding='utf-8')
    before = path.read_bytes()
    assert review_volumes_export(str(path))['volumes_reviewed'] == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize('payload', [b'bad-json', b'\xff', b'{"Volumes":[],"Volumes":[]}',
    b'{"Volumes":[],"extra":NaN}', b'x' * 2000001, b'[' * 2000])
def test_bad_export_bytes_refused(tmp_path, payload):
    path = tmp_path / 'volumes.json'
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        review_volumes_export(str(path))


def test_symlink_and_fifo_refused(tmp_path):
    path = tmp_path / 'data.json'
    path.write_text('{"Volumes":[]}')
    link = tmp_path / 'link.json'
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip('symlinks unavailable')
    with pytest.raises(ValueError, match='Symlink'):
        review_volumes_export(str(link))
    if hasattr(os, 'mkfifo'):
        fifo = tmp_path / 'fifo.json'
        os.mkfifo(fifo)
        with pytest.raises(ValueError, match='regular'):
            review_volumes_export(str(fifo))


def test_safe_registry_read_does_not_widen_aws_policy(tmp_path, monkeypatch):
    from aether.devops.awscli import classify
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    path = tmp_path / 'volumes.json'
    path.write_text(json.dumps({'Volumes': [volume()]}))
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_ebs_volumes', {'path': str(path)}))
    assert result.ok and result.data['volumes_reviewed'] == 1
    assert classify('ec2', 'describe-volumes') == 'confirm'
    assert classify('ec2', 'delete-volume') == 'confirm'
