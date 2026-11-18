import asyncio
import json

import pytest

from jarvis.mentor_html_review import review_html


@pytest.mark.parametrize(
    ("markup", "rule"),
    [
        ("<script src='app.js'></script>", "script_tag"),
        ("<button onclick='save()'>Save</button>", "inline_event_handler"),
        ("<a href='javascript:save()'>Save</a>", "javascript_url"),
        ("<form action='/save' method='post'></form>", "form_tag"),
        ("<iframe src='https://example.invalid'></iframe>", "iframe_tag"),
    ],
)
def test_exact_patterns(markup, rule):
    result = review_html(markup)
    assert not result["rendered"] and not result["validated"]
    assert [finding["rule"] for finding in result["findings"]] == [rule]
    assert result["finding_count"] == 1 and not result["partial"]
    assert not result["mastery_assessed"]


@pytest.mark.parametrize(
    "markup",
    [
        "<p>script tags are discussed</p>",
        "<button data-action='save'>Save</button>",
        "<a href='https://example.invalid/save'>Save</a>",
        "<div data-form='true'></div>",
        "<p>iframe and form are words in text</p>",
        "<template><button>Template</button></template>",
    ],
)
def test_scope_does_not_claim_undetected_patterns_safe(markup):
    result = review_html(markup)
    assert result["finding_count"] == 0
    assert "zero finding count is not a pass" in result["notice"]


@pytest.mark.parametrize(
    "markup",
    [
        None,
        1,
        b"<script></script>",
        True,
        "",
        " \n",
        "x\x00y",
        "\ud800",
        "a" * 65537,
        "x\n" * 2048,
        "<script>password=hunter2</script>",
        "<p>AKIAABCDEFGHIJKLMNOP</p>",
        "<!-- -----BEGIN PRIVATE KEY----- -->",
    ],
)
def test_invalid_input(markup):
    with pytest.raises(ValueError):
        review_html(markup)


def test_no_source_values_or_side_effects(tmp_path):
    marker = tmp_path / "must-not-exist"
    sentinel = "UNIQUE_PRIVATE_SENTINEL"
    result = review_html(f"<form action='{marker}'><script>{sentinel}</script></form>")
    assert not marker.exists()
    assert sentinel not in json.dumps(result)
    assert str(marker) not in json.dumps(result)


def test_sorted_locations_counts_and_independence():
    markup = "<script src='a.js'></script>\n<button onclick='x()'>Go</button>\n<a href='javascript:x()'>Go</a>\n<iframe src='x'></iframe>\n<form action='/x'></form>\n"
    result = review_html(markup)
    assert result["finding_count"] == 5
    assert [(row["line"], row["rule"]) for row in result["findings"]] == [
        (1, "script_tag"),
        (2, "inline_event_handler"),
        (3, "javascript_url"),
        (4, "iframe_tag"),
        (5, "form_tag"),
    ]
    result["sources"].clear()
    result["rules_checked"].clear()
    fresh = review_html("<p>Ready</p>")
    assert len(fresh["sources"]) == 5 and len(fresh["rules_checked"]) == 5


def test_truncation_and_utf8_columns():
    result = review_html("<script></script>\n" * 101)
    assert result["finding_count"] == 101
    assert result["returned_count"] == 100 and result["partial"]
    unicode_result = review_html("<p>అ</p><script></script>")
    assert unicode_result["findings"][0]["column_utf8_zero_based"] == len("<p>అ</p>".encode("utf-8"))


def test_registry_preserves_existing_mentor_and_progress(tmp_path, monkeypatch):
    from jarvis.mentor import MentorStore
    from jarvis.tools.builtin_tools import build_registry

    monkeypatch.setenv("JARVIS_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    before = MentorStore().progress()
    result = asyncio.run(registry.execute("mentor_review_html", {"markup": "<script></script>"}))
    assert result.ok and result.data["finding_count"] == 1
    assert "mentor_review_python" in registry.tools
    assert "mentor_review_javascript" in registry.tools
    assert "mentor_review_typescript" in registry.tools
    assert MentorStore().progress() == before
