"""Bounded TypeScript source teaching checks. Never executes supplied text."""

from __future__ import annotations

import re

from jarvis.mentor_javascript_review import _SECRET, _line_column, _masked

SOURCES = [
    "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html",
    "https://www.typescriptlang.org/docs/handbook/type-checking-javascript-files.html",
    "https://www.typescriptlang.org/docs/handbook/2/narrowing.html",
    "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions",
    "https://www.typescriptlang.org/docs/handbook/enums.html",
]
_RULES = {
    "explicit_any": (
        "Review explicit any",
        "A literal explicit-any marker is present. any can turn off checking for that value; prefer a narrower type or unknown plus narrowing where suitable.",
        0,
    ),
    "suppression_comment": (
        "Review a suppression comment",
        "A literal @ts-ignore, @ts-nocheck or @ts-expect-error comment marker is present. Suppression can hide a type error; check the reason and narrow the declaration where suitable.",
        1,
    ),
    "non_null_assertion": (
        "Review a non-null assertion",
        "A literal postfix exclamation marker is present in a position consistent with a non-null assertion. It tells the compiler to accept the value without a runtime check; prefer visible narrowing where suitable.",
        2,
    ),
    "double_assertion": (
        "Review a double assertion",
        "A literal as-unknown-as marker is present. Double assertions can bypass normal assignability checks; establish the actual value shape and prefer a precise conversion where suitable.",
        3,
    ),
    "runtime_enum": (
        "Review an enum declaration",
        "A literal enum declaration marker is present. TypeScript enums can create runtime objects and have naming/value tradeoffs; confirm that behavior and consider a union or const object where suitable.",
        4,
    ),
}
_NOTICE = (
    "Limited literal TypeScript teaching checks only, not parsing every TypeScript or JavaScript "
    "dialect, type checking, a sandbox, security audit, execution, correctness test or mastery "
    "assessment. No file, compiler, network, package or command access and no progress writes. "
    "Comments and quoted/template strings are masked for code markers; one-line suppression comments "
    "are detected separately. Names, aliases, imports, control/data flow, frameworks, decorators and "
    "generated code are not resolved. Findings may be false positives and unreported risks remain. "
    "A zero finding count is not a pass. Input already supplied to the assistant can remain in logs; "
    "use only small redacted snippets. Returned findings omit source text and values."
)
_SUPPRESSION = re.compile(r"(?://|/\*)\s*@ts-(?:ignore|nocheck|expect-error)\b")


def _add(found, rule, text, index):
    line, column = _line_column(text, index)
    found.add((line, column, rule))


def review_typescript(code: str):
    if not isinstance(code, str) or not code.strip() or "\x00" in code:
        raise ValueError("Supply one nonempty redacted TypeScript snippet without NUL characters.")
    try:
        size = len(code.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError("Supply valid UTF-8 TypeScript text.") from None
    if size > 65536:
        raise ValueError("TypeScript snippet exceeds 65536 UTF-8 bytes.")
    if code.count("\n") >= 2048:
        raise ValueError("TypeScript snippet exceeds 2048 lines.")
    if _SECRET.search(code):
        raise ValueError("Redact the credential-shaped value and submit only the code shape.")

    visible, _ = _masked(code)
    found = set()
    for match in re.finditer(r"(?::|\bas\s+|<)\s*any\b", visible):
        _add(found, "explicit_any", code, match.start())
    for match in _SUPPRESSION.finditer(code):
        _add(found, "suppression_comment", code, match.start())
    for match in re.finditer(r"(?<=[A-Za-z0-9_$\)\]])!(?=[.,;)=\]\n])", visible):
        _add(found, "non_null_assertion", code, match.start())
    for match in re.finditer(r"\bas\s+unknown\s+as\s+", visible):
        _add(found, "double_assertion", code, match.start())
    for match in re.finditer(r"(?<!const\s)\benum\s+[A-Za-z_$]", visible):
        _add(found, "runtime_enum", code, match.start())

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
        "executed": False,
        "type_checked": False,
        "runtime_correctness_verified": False,
        "mastery_assessed": False,
        "sources": list(SOURCES),
        "notice": _NOTICE,
        "rules_checked": list(_RULES),
        "scope": "Literal markers in supplied text; not complete TypeScript parsing or compiler analysis.",
        "findings": items,
        "finding_count": len(found),
        "returned_count": len(items),
        "partial": len(found) > 100,
        "status": "Teaching observations only; no pass/fail or safety conclusion.",
    }


def register_typescript_review(registry):
    from jarvis.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="mentor_review_typescript",
            description="Review one supplied redacted TypeScript snippet with five bounded literal teaching checks, without executing or type checking it. Not security/correctness/mastery grading. No fixes or progress writes.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "maxLength": 65536,
                        "description": "Small redacted TypeScript source text, at most 65536 UTF-8 bytes. No credential values.",
                    }
                },
                "required": ["code"],
                "additionalProperties": False,
            },
            handler=review_typescript,
            risk=Risk.SAFE,
            category="mentor",
        )
    )

# Input is inspected as text only; it is never executed.
