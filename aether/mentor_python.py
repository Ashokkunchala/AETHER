"""Bounded syntactic Python teaching checks. Never imports or executes supplied code."""

from __future__ import annotations

import ast

SOURCES = [
    "https://docs.python.org/3/library/ast.html",
    "https://docs.python.org/3/library/subprocess.html",
    "https://docs.python.org/3/library/pickle.html",
    "https://docs.python.org/3/tutorial/controlflow.html",
    "https://docs.python.org/3/tutorial/errors.html",
]
_RULES = {
    "dynamic_code": (
        "Review dynamic code execution",
        "A direct eval/exec call is present. Do not execute untrusted text. Prefer a data parser or explicit operations where suitable.",
        0,
    ),
    "shell_true": (
        "Review shell interpretation",
        "A literal shell=True is passed to a spelled subprocess call. Check command construction and untrusted input; prefer a reviewed argv without a shell where suitable.",
        1,
    ),
    "pickle_input": (
        "Review pickle input trust",
        "A spelled pickle.load/loads call is present. Unpickling untrusted input can execute code. Establish the source and trust boundary or choose a suitable data format.",
        2,
    ),
    "mutable_default": (
        "Review a shared mutable default",
        "A list/dict/set literal is a function default. Defaults are evaluated once. Check whether shared state is intended; a None sentinel plus per-call initialization is often suitable.",
        3,
    ),
    "bare_except": (
        "Review an unqualified exception handler",
        "A bare except handler is present. Check which exceptions should be caught and whether interruption/exit signals should propagate. Catch specific expected exceptions where suitable.",
        4,
    ),
}
_NOTICE = (
    "Limited syntactic teaching checks only, not a security audit, type checker, correctness test, "
    "code execution, free-text grading or skill/mastery assessment. No imports, file reads/writes, "
    "commands, network calls, fixes or progress updates. Names/aliases/rebinding, control/data flow, "
    "argument expansion and indirect calls are not resolved. Findings may be false positives and "
    "unreported issues can remain. A zero finding count is not a pass. Input already supplied to "
    "the assistant can remain in chat/model logs; this reviewer does not erase it. Use only small "
    "redacted snippets. Returned findings omit source text, names and literal values."
)


def _spelled(node, module, names):
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == module
        and node.attr in names
    )


def review_python(code: str):
    if not isinstance(code, str) or not code.strip() or "\x00" in code:
        raise ValueError("Supply a nonempty redacted Python snippet without NUL characters.")
    try:
        if len(code) > 65536 or len(code.encode("utf-8")) > 65536:
            raise ValueError("Python snippet exceeds 65536 UTF-8 bytes.")
    except UnicodeEncodeError:
        raise ValueError("Supply valid UTF-8 Python text.") from None
    common = {
        "executed": False,
        "runtime_correctness_verified": False,
        "mastery_assessed": False,
        "sources": list(SOURCES),
        "notice": _NOTICE,
        "rules_checked": list(_RULES),
        "parser_grammar": "The running AETHER Python version; other versions may differ.",
    }
    try:
        tree = ast.parse(code, mode="exec")
        nodes = list(ast.walk(tree))
    except SyntaxError as exc:
        return {
            **common,
            "parsed": False,
            "findings": [],
            "finding_count": 0,
            "partial": True,
            "syntax_location": {"line": exc.lineno, "column": exc.offset},
            "status": "Parser rejected the snippet; no teaching checks completed. No raw diagnostic/source text returned.",
        }
    except (RecursionError, MemoryError, ValueError, OverflowError):
        raise ValueError(
            "Snippet exceeds supported parser complexity or cannot be parsed."
        ) from None
    if len(nodes) > 20000:
        raise ValueError("Snippet exceeds 20000 AST nodes; no teaching report produced.")
    found = set()

    def add(rule, node):
        found.add((node.lineno, node.col_offset, rule))

    for node in nodes:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                add("dynamic_code", node)
            if _spelled(
                node.func,
                "subprocess",
                {
                    "run",
                    "Popen",
                    "call",
                    "check_call",
                    "check_output",
                    "getoutput",
                    "getstatusoutput",
                },
            ):
                if any(
                    k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True
                    for k in node.keywords
                ):
                    add("shell_true", node)
            if _spelled(node.func, "pickle", {"load", "loads"}):
                add("pickle_input", node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    add("mutable_default", default)
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            add("bare_except", node)
    items = []
    for line, column, rule in sorted(found)[:100]:
        title, explanation, source_index = _RULES[rule]
        items.append(
            {
                "rule": rule,
                "line": line,
                "column_utf8_zero_based": column,
                "title": title,
                "explanation": explanation,
                "source": SOURCES[source_index],
            }
        )
    return {
        **common,
        "parsed": True,
        "findings": items,
        "finding_count": len(found),
        "returned_count": len(items),
        "partial": len(found) > 100,
        "status": "Teaching observations only; no pass/fail or safety conclusion.",
    }


def register_python_review(registry):
    from aether.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="mentor_review_python",
            description="Review a supplied redacted Python snippet with five bounded AST teaching checks, without executing/importing it or reading files. Not security/correctness/mastery grading. No fixes or progress writes.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "maxLength": 65536,
                        "description": "Small redacted Python source text, at most65536 UTF-8 bytes. No paths or credentials.",
                    }
                },
                "required": ["code"],
                "additionalProperties": False,
            },
            handler=review_python,
            risk=Risk.SAFE,
            category="mentor",
        )
    )

# Input is parsed only; it is never imported or executed.
