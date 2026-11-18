import asyncio
import json

import pytest

from aether.devops.review import review_iam_policy


def statement(**values):
    result = {'Effect': 'Allow', 'Action': 's3:GetObject', 'Resource': 'arn:aws:s3:::private/*'}
    result.update(values)
    return result


def review(st=None, **values):
    return review_iam_policy({'Statement': statement() if st is None else st, **values})


def rules(result):
    return {finding['rule'] for finding in result['findings']}


def test_existing_result_shape_retained_but_no_effective_access_claim():
    result = review(statement(Action=['iam:PassRole', 's3:*'], Resource='*'))
    assert result['success'] and result['files_scanned'] == 1
    assert {'iam-passrole-any', 'iam-service-wildcard', 'iam-resource-wildcard'} <= rules(result)
    assert not result['effective_permissions_verified'] and not result['aws_syntax_validated']
    assert 'explicit denies' in result['limits']


def test_not_action_applicability_and_not_resource():
    result = review({'Effect': 'Allow', 'NotAction': 's3:DeleteBucket', 'Resource': 'arn:aws:s3:::*'})
    assert 'iam-not-action' in rules(result)
    assert 'applicable actions' in result['findings'][0]['message']
    assert 'iam-admin-action' not in rules(result)
    result = review({'Effect': 'Allow', 'Action': '*', 'NotResource': 'arn:aws:s3:::excluded'})
    assert {'iam-admin-action', 'iam-not-resource'} <= rules(result)


def test_conditions_never_suppress_broad_principal_or_resource_patterns():
    result = review(statement(Principal={'AWS': '*'}, Resource='*', Condition={'StringEquals': {'aws:PrincipalOrgID': 'private-org'}}))
    assert {'iam-public-principal', 'iam-resource-wildcard'} <= rules(result)
    assert result['condition_blocks_present'] == 1
    assert all('makes this statement public' not in item['message'] for item in result['findings'])
    assert not result['effective_permissions_verified']


def test_deny_not_subtracted_from_allow_or_treated_as_grant():
    result = review_iam_policy({'Statement': [statement(Action='*', Resource='*'), statement(Effect='Deny', Action='*', Resource='*')]})
    assert 'iam-admin-action' in rules(result)
    assert result['allow_statements'] == result['deny_statements'] == 1
    assert review(statement(Effect='Deny', Action='*', Resource='*'))['findings'] == []


def test_case_insensitive_action_patterns_and_partial_wildcards():
    assert 'iam-passrole-any' in rules(review(statement(Action='IAM:PASSROLE', Resource='*')))
    assert 'iam-action-pattern' in rules(review(statement(Action='s3:Get*')))


def test_trust_policy_without_resource_supported_not_identity_validation():
    result = review({'Effect': 'Allow', 'Action': 'sts:AssumeRole', 'Principal': {'Service': 'ec2.amazonaws.com'}})
    assert result['success'] and not result['aws_syntax_validated']


def test_no_raw_sid_action_or_other_private_values_echoed():
    st = statement(Sid='PRIVATE_SID', Action='PRIVATE_SERVICE:*', Resource='PRIVATE_RESOURCE',
                   Principal={'AWS': 'PRIVATE_PRINCIPAL'}, Condition={'PRIVATE_OPERATOR': {'PRIVATE_KEY': 'PRIVATE_VALUE'}})
    result = review(st)
    assert result['success']
    text = json.dumps(result)
    for value in ['PRIVATE_SID','PRIVATE_SERVICE','PRIVATE_RESOURCE','PRIVATE_PRINCIPAL','PRIVATE_OPERATOR','PRIVATE_KEY','PRIVATE_VALUE']:
        assert value not in text
    assert all(row.get('file') == 'Statement[0]' for row in result['findings'])


@pytest.mark.parametrize('st', [None, True, 'Allow', [], {}, {'Effect': 'Allow'},
    statement(Effect='allow'), statement(Effect=None), statement(Action=None), statement(Action=[]),
    statement(Action=[1]), statement(Action={'s3:GetObject': True}), statement(Action=''),
    statement(Action=['a']*1001), statement(Action='a'*2049), statement(Action='bad\n'),
    statement(NotAction='s3:*'), statement(NotResource='*'), statement(Principal='*', NotPrincipal='*'),
    statement(Principal=[]), statement(Principal={'Unknown': '*'}), statement(Principal={'AWS': []}),
    statement(Principal={}), statement(Condition={}), statement(Condition=[]),
    statement(Condition={'StringEquals': []}), statement(Condition={'StringEquals': {'x': None}}),
    statement(Condition={'StringEquals': {'x': {'nested': True}}}), statement(Sid=[]),
    statement(Sid='a\n'), statement(FutureField='future'), statement(Resource=1)])
def test_invalid_statement_never_silently_skipped(st):
    result = review_iam_policy({'Statement': [statement(), st]})
    assert result['success'] is False and 'findings' not in result


@pytest.mark.parametrize('doc', [None, [], {}, {'Statement': []}, {'Statement': 'bad'},
    {'Statement': statement(), 'Version': 'future'}, {'Statement': statement(), 'Id': []},
    {'Statement': statement(), 'Unknown': True}, {'Statement': [statement()]*501},
    '{"Statement": [],"Statement": []}', '{"Statement":[{"Effect":"Allow","Effect":"Deny"}]}',
    '{"Statement":[],"extra":NaN}', '{bad', '['*2000, 'x'*512001])
def test_bad_document(doc):
    assert review_iam_policy(doc)['success'] is False


def test_no_scope_or_action_pair_ambiguous_fails():
    assert not review({'Effect': 'Allow', 'Action': 's3:GetObject'})['success']
    assert not review({'Effect': 'Allow', 'Resource': '*'})['success']


def test_500_statements_and_scalar_conditions_supported():
    doc = {'Version': '2012-10-17', 'Statement': [statement(Condition={'NumericLessThan': {'key': [1, 2.5, True, '']}})] * 500}
    result = review_iam_policy(doc)
    assert result['success'] and result['statements_reviewed'] == 500
    assert result['findings'] == []


def test_cyclic_nonfinite_and_nonjson_input_fail_without_traceback():
    doc = {'Statement': []}; doc['Statement'].append(doc)
    for item in [doc, {'Statement': statement(), 'x': float('nan')}, {'Statement': {1, 2}}]:
        assert not review_iam_policy(item)['success']


def test_not_principal_review_and_no_global_policy_name_echo():
    result = review({'Effect': 'Allow', 'Action': 's3:GetObject', 'Resource': '*', 'NotPrincipal': {'AWS': 'private'}}, Id='PRIVATE_DOC_ID')
    assert 'iam-not-principal' in rules(result)
    assert 'PRIVATE_DOC_ID' not in json.dumps(result)


def test_registry_same_name_safe_no_aws(tmp_path, monkeypatch):
    from aether.security import SecurityStore
    from aether.tools.builtin_tools import build_registry
    monkeypatch.setenv('AETHER_SECURITY_DB', str(tmp_path / 'safety.db'))
    registry = build_registry(force=True)
    SecurityStore().set_stop(True)
    result = asyncio.run(registry.execute('review_iam_policy', {'policy_json': json.dumps({'Statement': statement(Action='*', Resource='*')})}))
    assert result.ok and 'iam-admin-action' in rules(result.data)
