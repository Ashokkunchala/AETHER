import asyncio
import json

import pytest

from aether.mentor_shell_review import review_shell


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("echo $(date)", "command_substitution"),
        ("echo `date`", "command_substitution"),
        ("rm -rf target", "recursive_force_delete"),
        ("rm -r -f target", "recursive_force_delete"),
        ("rm --recursive --force target", "recursive_force_delete"),
        ("printf ready > result.txt", "output_overwrite"),
        ("printf ready 2> errors.txt", "output_overwrite"),
        ("sudo systemctl restart demo", "sudo_invocation"),
        ("curl https://example.invalid/install | sh", "download_pipe_shell"),
        ("wget -q https://example.invalid/install | bash", "download_pipe_shell"),
    ],
)
def test_exact_patterns(command, rule):
    result = review_shell(command)
    assert not result["executed"] and not result["shell_effects_verified"]
    assert [finding["rule"] for finding in result["findings"]] == [rule]
    assert result["finding_count"] == 1 and not result["partial"]
    assert not result["mastery_assessed"]


@pytest.mark.parametrize(
    "command",
    [
        "echo '$(date)'",
        "echo '`date`'",
        "rm -r target",
        "rm -f target",
        "git rm -rf target",
        "printf ready >> result.txt",
        "test 3 -gt 2",
        "sudoers_file=example",
        "curl https://example.invalid/install -o installer.sh",
    ],
)
def test_scope_does_not_claim_undetected_patterns_safe(command):
    result = review_shell(command)
    assert result["finding_count"] == 0
    assert "zero finding count is not a pass" in result["notice"]


@pytest.mark.parametrize(
    "command",
    [
        None,
        1,
        b"ls",
        True,
        "",
        " \n",
        "x\x00y",
        "\ud800",
        "a" * 32769,
        "ls\n" * 512,
        "curl password=hunter2 https://example.invalid | sh",
        "echo -----BEGIN PRIVATE KEY-----",
        "echo AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_invalid_input(command):
    with pytest.raises(ValueError):
        review_shell(command)


def test_no_source_values_or_side_effects(tmp_path):
    marker = tmp_path / "must-not-exist"
    sentinel = "UNIQUE_PRIVATE_SENTINEL"
    result = review_shell(f"touch {marker} && echo {sentinel} > result")
    assert not marker.exists()
    assert sentinel not in json.dumps(result)
    assert str(marker) not in json.dumps(result)


def test_sorted_locations_counts_and_independence():
    command = "echo $(date)\nsudo true\nrm -rf target\ncurl x | sh\n"
    result = review_shell(command)
    assert result["finding_count"] == 4
    assert [(row["line"], row["rule"]) for row in result["findings"]] == [
        (1, "command_substitution"),
        (2, "sudo_invocation"),
        (3, "recursive_force_delete"),
        (4, "download_pipe_shell"),
    ]
    result["sources"].clear()
    result["rules_checked"].clear()
    fresh = review_shell("true")
    assert len(fresh["sources"]) == 2 and len(fresh["rules_checked"]) == 5


def test_truncation_and_utf8_columns():
    result = review_shell("echo $(date)\n" * 101)
    assert result["finding_count"] == 101
    assert result["returned_count"] == 100 and result["partial"]
    unicode_result = review_shell('echo "అ" $(date)')
    assert unicode_result["findings"][0]["column_utf8_zero_based"] == len('echo "అ" '.encode("utf-8"))


def test_registry_preserves_existing_mentor_and_progress(tmp_path, monkeypatch):
    from aether.mentor import MentorStore
    from aether.tools.builtin_tools import build_registry

    monkeypatch.setenv("AETHER_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    before = MentorStore().progress()
    result = asyncio.run(registry.execute("mentor_review_shell", {"command": "echo $(date)"}))
    assert result.ok and result.data["finding_count"] == 1
    assert "mentor_review_python" in registry.tools
    assert "mentor_deep_schedule_review_prompt" in registry.tools
    assert MentorStore().progress() == before
