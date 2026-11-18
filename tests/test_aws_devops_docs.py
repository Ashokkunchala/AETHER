from pathlib import Path
import re

from aether.devops.awscli import READ_OPERATIONS
from aether.tools.builtin_tools import build_registry

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs' / 'AWS-DEVOPS.md'


def test_documented_read_pairs_match_exact_runtime_allowlist():
    pairs = set(re.findall(r'^\| `([a-z0-9-]+)` \| `([a-z0-9-]+)` \|$', DOC.read_text(), re.M))
    assert pairs == set(READ_OPERATIONS)


def test_safety_limits_not_wildcard_promise():
    text = DOC.read_text()
    assert text.startswith('# AETHER ')
    for boundary in ['exact allowlist', 'not permission', 'not an\nAWS-side dry run',
                     'not mean free', 'completed-with-issues', 'No protected-resource coverage',
                     'not a verified root cause', 'not an OS sandbox']:
        assert boundary.lower() in text.lower()
    assert '`describe-*`, `list-*`, `get-*`' not in text


def test_offline_tool_table_names_exist_and_links_resolve():
    text = DOC.read_text()
    registry = build_registry(force=True)
    for name in re.findall(r'^\| `(\w+)` \|', text, re.M):
        if name not in {'ec2', 'ecs', 'sts', 's3'}:
            assert registry.get(name) is not None
    for target in re.findall(r'\]\(([^)]+\.md)\)', text):
        assert (DOC.parent / target).is_file()
