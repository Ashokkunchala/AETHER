import asyncio
import json

import pytest

from jarvis.mentor_javascript_review import review_javascript


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("eval(value)", "eval_call"),
        ("new Function('return value')()", "function_constructor"),
        ("element.innerHTML = markup", "inner_html_assignment"),
        ("document.write(markup)", "document_write"),
        ("document.writeln(markup)", "document_write"),
        ("setTimeout('update()', 1000)", "string_timer_callback"),
        ('setInterval("update()", 1000)', "string_timer_callback"),
    ],
)
def test_exact_patterns(code, rule):
    result = review_javascript(code)
    assert not result["executed"] and not result["runtime_correctness_verified"]
    assert [finding["rule"] for finding in result["findings"]] == [rule]
    assert result["finding_count"] == 1 and not result["partial"]
    assert not result["mastery_assessed"]


@pytest.mark.parametrize(
    "code",
    [
        "const text = 'eval(value)'",
        'const text = "new Function(value)"',
        "// eval(value)\n/* document.write(value) */",
        "const html = element.innerHTML",
        "element.innerHTML == markup",
        "writer.document.write = markup",
        "setTimeout(update, 1000)",
        "setTimeout(() => update(), 1000)",
        "const callback = `eval(value)`",
    ],
)
def test_scope_does_not_claim_undetected_patterns_safe(code):
    result = review_javascript(code)
    assert result["finding_count"] == 0
    assert "zero finding count is not a pass" in result["notice"]


@pytest.mark.parametrize(
    "code",
    [
        None,
        1,
        b"eval(value)",
        True,
        "",
        " \n",
        "x\x00y",
        "\ud800",
        "a" * 65537,
        "x\n" * 2048,
        "eval(password=hunter2)",
        "const key = 'AKIAABCDEFGHIJKLMNOP'",
        "/* -----BEGIN PRIVATE KEY----- */",
    ],
)
def test_invalid_input(code):
    with pytest.raises(ValueError):
        review_javascript(code)


def test_no_source_values_or_side_effects(tmp_path):
    marker = tmp_path / "must-not-exist"
    sentinel = "UNIQUE_PRIVATE_SENTINEL"
    result = review_javascript(f"const marker = '{marker}'\neval('{sentinel}')")
    assert not marker.exists()
    assert sentinel not in json.dumps(result)
    assert str(marker) not in json.dumps(result)


def test_sorted_locations_counts_and_independence():
    code = "eval(value)\nnew Function(value)\nelement.innerHTML = value\ndocument.write(value)\nsetTimeout('value', 1)\n"
    result = review_javascript(code)
    assert result["finding_count"] == 5
    assert [(row["line"], row["rule"]) for row in result["findings"]] == [
        (1, "eval_call"),
        (2, "function_constructor"),
        (3, "inner_html_assignment"),
        (4, "document_write"),
        (5, "string_timer_callback"),
    ]
    result["sources"].clear()
    result["rules_checked"].clear()
    fresh = review_javascript("const value = 1")
    assert len(fresh["sources"]) == 5 and len(fresh["rules_checked"]) == 5


def test_truncation_and_utf8_columns():
    result = review_javascript("eval(value)\n" * 101)
    assert result["finding_count"] == 101
    assert result["returned_count"] == 100 and result["partial"]
    unicode_result = review_javascript('const label = "అ"; eval(value)')
    assert unicode_result["findings"][0]["column_utf8_zero_based"] == len('const label = "అ"; '.encode("utf-8"))


def test_registry_preserves_existing_mentor_and_progress(tmp_path, monkeypatch):
    from jarvis.mentor import MentorStore
    from jarvis.tools.builtin_tools import build_registry

    monkeypatch.setenv("JARVIS_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    before = MentorStore().progress()
    result = asyncio.run(registry.execute("mentor_review_javascript", {"code": "eval(value)"}))
    assert result.ok and result.data["finding_count"] == 1
    assert "mentor_review_python" in registry.tools
    assert "mentor_review_shell" in registry.tools
    assert MentorStore().progress() == before
