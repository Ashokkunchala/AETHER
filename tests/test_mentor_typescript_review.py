import asyncio
import json

import pytest

from aether.mentor_typescript_review import review_typescript


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("const value: any = input", "explicit_any"),
        ("const value = input as any", "explicit_any"),
        ("// @ts-ignore\nconst value = input", "suppression_comment"),
        ("/* @ts-expect-error */\nconst value = input", "suppression_comment"),
        ("const value = item!.name", "non_null_assertion"),
        ("const value = input as unknown as Target", "double_assertion"),
        ("enum Status { Ready }", "runtime_enum"),
    ],
)
def test_exact_patterns(code, rule):
    result = review_typescript(code)
    assert not result["executed"] and not result["type_checked"]
    assert [finding["rule"] for finding in result["findings"]] == [rule]
    assert result["finding_count"] == 1 and not result["partial"]
    assert not result["mastery_assessed"]


@pytest.mark.parametrize(
    "code",
    [
        "const text = ': any'",
        "// const value: any = input\n/* item!.name */",
        "const value = input == null",
        "const value = factorial(3)! == 6",
        "const value = input as unknown",
        "const enum Status { Ready }",
        "const value = { name: 'enum Status' }",
        "// ordinary comment\nconst value: string = input",
    ],
)
def test_scope_does_not_claim_undetected_patterns_safe(code):
    result = review_typescript(code)
    assert result["finding_count"] == 0
    assert "zero finding count is not a pass" in result["notice"]


@pytest.mark.parametrize(
    "code",
    [
        None,
        1,
        b"const value: any = input",
        True,
        "",
        " \n",
        "x\x00y",
        "\ud800",
        "a" * 65537,
        "x\n" * 2048,
        "const value: any = password=hunter2",
        "const key = 'AKIAABCDEFGHIJKLMNOP'",
        "/* -----BEGIN PRIVATE KEY----- */",
    ],
)
def test_invalid_input(code):
    with pytest.raises(ValueError):
        review_typescript(code)


def test_no_source_values_or_side_effects(tmp_path):
    marker = tmp_path / "must-not-exist"
    sentinel = "UNIQUE_PRIVATE_SENTINEL"
    result = review_typescript(f"const marker = '{marker}'\nconst value: any = '{sentinel}'")
    assert not marker.exists()
    assert sentinel not in json.dumps(result)
    assert str(marker) not in json.dumps(result)


def test_sorted_locations_counts_and_independence():
    code = "const one: any = input\n// @ts-ignore\nconst two = item!.name\nconst three = input as unknown as Target\nenum Status { Ready }\n"
    result = review_typescript(code)
    assert result["finding_count"] == 5
    assert [(row["line"], row["rule"]) for row in result["findings"]] == [
        (1, "explicit_any"),
        (2, "suppression_comment"),
        (3, "non_null_assertion"),
        (4, "double_assertion"),
        (5, "runtime_enum"),
    ]
    result["sources"].clear()
    result["rules_checked"].clear()
    fresh = review_typescript("const value: string = 'ready'")
    assert len(fresh["sources"]) == 5 and len(fresh["rules_checked"]) == 5


def test_truncation_and_utf8_columns():
    result = review_typescript("const value: any = input\n" * 101)
    assert result["finding_count"] == 101
    assert result["returned_count"] == 100 and result["partial"]
    unicode_result = review_typescript('const label = "అ"; const value: any = input')
    assert unicode_result["findings"][0]["column_utf8_zero_based"] == len('const label = "అ"; const value'.encode("utf-8"))


def test_registry_preserves_existing_mentor_and_progress(tmp_path, monkeypatch):
    from aether.mentor import MentorStore
    from aether.tools.builtin_tools import build_registry

    monkeypatch.setenv("AETHER_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("AETHER_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    before = MentorStore().progress()
    result = asyncio.run(registry.execute("mentor_review_typescript", {"code": "const value: any = input"}))
    assert result.ok and result.data["finding_count"] == 1
    assert "mentor_review_python" in registry.tools
    assert "mentor_review_javascript" in registry.tools
    assert "mentor_review_shell" in registry.tools
    assert MentorStore().progress() == before
