"""Pins for the extended AWS read allowlist (part 4B services).

Complements test_aws_read_policy.py: new reviewed pairs preview without
execution, while every operation that returns data beyond inventory metadata,
bills per request or changes state stays on the approval path.
"""
import subprocess

import pytest

from aether.devops import awscli

NEW_READS = [
    ('ec2', 'describe-vpcs'), ('ec2', 'describe-subnets'), ('ec2', 'describe-route-tables'),
    ('ec2', 'describe-security-groups'), ('s3api', 'list-buckets'),
    ('iam', 'list-users'), ('iam', 'list-roles'), ('iam', 'list-policies'),
    ('iam', 'get-policy'), ('iam', 'get-policy-version'),
    ('eks', 'list-clusters'), ('eks', 'describe-cluster'),
    ('rds', 'describe-db-instances'), ('lambda', 'list-functions'),
    ('cloudwatch', 'list-metrics'), ('logs', 'describe-log-groups'), ('logs', 'describe-log-streams'),
    ('cloudformation', 'describe-stacks'), ('cloudformation', 'list-stacks'),
    ('secretsmanager', 'list-secrets'),
    ('securityhub', 'get-findings'),
    ('guardduty', 'list-detectors'), ('guardduty', 'list-findings'), ('guardduty', 'get-findings'),
]


@pytest.mark.parametrize('service,operation', NEW_READS)
def test_new_reviewed_pairs_preview_without_execution(service, operation, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('No AWS calls allowed in tests'))
    assert awscli.classify(service, operation) == 'read'
    assert awscli.run_read(service, operation, dry_run=True)['success']


@pytest.mark.parametrize('service,operation', [
    # Data/billing/secret-adjacent operations near the new reads stay approval-gated.
    ('ec2', 'describe-volumes'), ('backup', 'list-backup-jobs'), ('ce', 'get-cost-and-usage'),
    ('cloudwatch', 'get-metric-data'), ('logs', 'get-log-events'), ('logs', 'filter-log-events'),
    ('secretsmanager', 'get-secret-value'), ('lambda', 'get-function'), ('eks', 'get-token'),
    ('rds', 'generate-db-auth-token'), ('iam', 'get-credential-report'),
    ('securityhub', 'batch-update-findings'), ('guardduty', 'create-detector'),
    ('cloudformation', 'create-stack'), ('s3api', 'get-object'), ('iam', 'create-access-key'),
])
def test_neighbor_operations_stay_on_approval_path(service, operation):
    assert awscli.classify(service, operation) in ('confirm', 'blocked')
    assert not awscli.run_read(service, operation, dry_run=True)['success']


def test_new_reads_still_fail_closed_on_unreviewed_flags(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('No AWS calls allowed in tests'))
    for service, operation in NEW_READS:
        assert not awscli.run_read(service, operation, ['--endpoint-url', 'https://example.invalid'], dry_run=True)['success']
        assert not awscli.run_read(service, operation, ['--output', 'text'], dry_run=True)['success']
