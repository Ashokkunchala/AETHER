import asyncio
import json

import pytest

from jarvis.mentor_python import review_python


@pytest.mark.parametrize(
    ("code", "rule"),
    [
        ("eval(value)", "dynamic_code"),
        ("exec(value)", "dynamic_code"),
        ("subprocess.run(command, shell=True)", "shell_true"),
        ("subprocess.Popen(command, shell=True)", "shell_true"),
        ("subprocess.call(command, shell=True)", "shell_true"),
        ("subprocess.check_call(command, shell=True)", "shell_true"),
        ("subprocess.check_output(command, shell=True)", "shell_true"),
        ("pickle.load(stream)", "pickle_input"),
        ("pickle.loads(data)", "pickle_input"),
        ("def f(items=[]):\n pass", "mutable_default"),
        ("async def f(*, things={}):\n pass", "mutable_default"),
        ("def f(items={1}):\n pass", "mutable_default"),
        ("try:\n pass\nexcept:\n pass", "bare_except"),
    ],
)
def test_exact_patterns(code, rule):
    result = review_python(code)
    assert result["parsed"] and not result["executed"]
    assert [f["rule"] for f in result["findings"]] == [rule]
    assert result["finding_count"] == 1 and not result["partial"]
    assert not result["runtime_correctness_verified"] and not result["mastery_assessed"]


@pytest.mark.parametrize(
    "code",
    [
        "value = 1",
        "subprocess.run(command, shell=False)",
        "subprocess.run(command, shell=1)",
        "subprocess.run(command, **options)",
        "sp.run(command, shell=True)",
        "other.run(command, shell=True)",
        "obj.eval(value)",
        "p.loads(data)",
        "def f(items=None):\n pass",
        "def f(items=list()):\n pass",
        "try:\n pass\nexcept Exception:\n pass",
        'text="eval(value)"\n# exec(value)\n',
    ],
)
def test_scope_does_not_claim_undetected_patterns_safe(code):
    result = review_python(code)
    assert result["parsed"] and result["finding_count"] == 0
    assert "zero finding count is not a pass" in result["notice"]


@pytest.mark.parametrize(
    "code", [None, 1, b"x", True, "", " \n", "x\x00y", "\ud800", "a" * 65537, "#" + "అ" * 22000]
)
def test_invalid_input(code):
    with pytest.raises(ValueError):
        review_python(code)


def test_no_source_values_or_raw_syntax_error_in_output(tmp_path):
    marker = tmp_path / "must-not-exist"
    sentinel = "UNIQUE_PRIVATE_SENTINEL"
    code = f"from pathlib import Path\nPath({str(marker)!r}).touch()\neval({sentinel!r})"
    result = review_python(code)
    assert (
        not marker.exists()
        and sentinel not in json.dumps(result)
        and str(marker) not in json.dumps(result)
    )
    syntax = review_python(f"{sentinel} = (")
    assert not syntax["parsed"] and syntax["partial"] and syntax["syntax_location"]["line"] == 1
    assert sentinel not in json.dumps(syntax)


def test_bounded_sorted_locations_and_counts():
    result = review_python("eval(x)\n" * 101)
    assert result["finding_count"] == 101 and result["returned_count"] == 100 and result["partial"]
    assert [r["line"] for r in result["findings"]] == list(range(1, 101))
    result = review_python('x="అ"; eval(x)')
    assert result["findings"][0]["column_utf8_zero_based"] == len('x="అ"; '.encode("utf-8"))


def test_ast_node_budget():
    with pytest.raises(ValueError, match="20000 AST nodes"):
        review_python("x=1\n" * 6000)


def test_parser_exceptions_not_raw_tracebacks(monkeypatch):
    import jarvis.mentor_python as mod

    def unavailable(*args, **kwargs):
        raise RecursionError("private details")

    monkeypatch.setattr(mod.ast, "parse", unavailable)
    with pytest.raises(ValueError, match="complexity"):
        review_python("x=1")


def test_results_are_independent():
    first = review_python("eval(x)")
    first["sources"].clear()
    first["rules_checked"].clear()
    assert len(review_python("eval(x)")["sources"]) == 5
    assert len(review_python("eval(x)")["rules_checked"]) == 5


def test_registry_preserves_existing_mentor_and_progress(tmp_path, monkeypatch):
    from jarvis.mentor import MentorStore
    from jarvis.tools.builtin_tools import build_registry

    monkeypatch.setenv("JARVIS_MENTOR_DB", str(tmp_path / "mentor.db"))
    monkeypatch.setenv("JARVIS_SECURITY_DB", str(tmp_path / "security.db"))
    registry = build_registry(force=True)
    before = MentorStore().progress()
    result = asyncio.run(registry.execute("mentor_review_python", {"code": "eval(x)"}))
    assert result.ok and result.data["finding_count"] == 1
    assert "mentor_review_terraform_validate" in registry.tools
    assert MentorStore().progress() == before
