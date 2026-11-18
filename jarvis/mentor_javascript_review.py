"""Bounded JavaScript source teaching checks. Never executes supplied text."""

from __future__ import annotations

import re

SOURCES = [
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/eval",
    "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Function",
    "https://developer.mozilla.org/en-US/docs/Web/API/Element/innerHTML",
    "https://developer.mozilla.org/en-US/docs/Web/API/Document/write",
    "https://developer.mozilla.org/en-US/docs/Web/API/Window/setTimeout",
]
_RULES = {
    "eval_call": (
        "Review direct eval",
        "A literal eval call marker is present. eval executes a string as code; do not run untrusted text. Prefer data parsing or explicit operations where suitable.",
        0,
    ),
    "function_constructor": (
        "Review the Function constructor",
        "A literal new Function marker is present. It creates a function from string input; establish the source and trust boundary before any separate reviewed execution.",
        1,
    ),
    "inner_html_assignment": (
        "Review HTML assignment",
        "A literal innerHTML assignment marker is present. Assigned markup can change the document and may execute in some sinks. Check the source and prefer safer DOM/text APIs where suitable.",
        2,
    ),
    "document_write": (
        "Review document.write",
        "A literal document.write/writeLn marker is present. It writes markup during parsing and can replace document content in some states. Check the source and prefer explicit DOM APIs where suitable.",
        3,
    ),
    "string_timer_callback": (
        "Review a string timer callback",
        "A literal setTimeout/setInterval marker begins with quoted text. String callbacks are evaluated as code. Prefer a function reference where suitable.",
        4,
    ),
}
_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:password|passwd|token|secret|api[_-]?key)\s*[:=]|\bAKIA[0-9A-Z]{16}\b",
    re.IGNORECASE,
)
_NOTICE = (
    "Limited literal JavaScript teaching checks only, not parsing every JavaScript or TypeScript "
    "dialect, a sandbox, security audit, execution, correctness test or mastery assessment. No file, "
    "network, browser, package or command access and no progress writes. Comments and quoted/template "
    "strings are masked; template interpolation, names, aliases, imports, data/control flow, frameworks "
    "and generated code are not resolved. Findings may be false positives and unreported risks remain. "
    "A zero finding count is not a pass. Input already supplied to the assistant can remain in logs; "
    "use only small redacted snippets. Returned findings omit source text and values."
)


def _masked(code: str):
    chars = list(code)
    comments_only = list(code)
    index = 0
    while index < len(code):
        char = code[index]
        pair = code[index:index + 2]
        if pair == "//":
            end = code.find("\n", index + 2)
            end = len(code) if end < 0 else end
            for pos in range(index, end):
                chars[pos] = comments_only[pos] = " "
            index = end
            continue
        if pair == "/*":
            end = code.find("*/", index + 2)
            end = len(code) if end < 0 else end + 2
            for pos in range(index, end):
                if code[pos] != "\n":
                    chars[pos] = comments_only[pos] = " "
            index = end
            continue
        if char in {"'", '"', "`"}:
            quote = char
            start = index
            index += 1
            while index < len(code):
                if code[index] == "\\":
                    index += 2
                    continue
                if code[index] == quote:
                    index += 1
                    break
                index += 1
            for pos in range(start, min(index, len(code))):
                if code[pos] != "\n":
                    chars[pos] = " "
            continue
        index += 1
    return "".join(chars), "".join(comments_only)


def _line_column(text: str, index: int):
    line = text.count("\n", 0, index) + 1
    start = text.rfind("\n", 0, index) + 1
    return line, len(text[start:index].encode("utf-8"))


def _add(found, rule, text, index):
    line, column = _line_column(text, index)
    found.add((line, column, rule))


def review_javascript(code: str):
    if not isinstance(code, str) or not code.strip() or "\x00" in code:
        raise ValueError("Supply one nonempty redacted JavaScript snippet without NUL characters.")
    try:
        size = len(code.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError("Supply valid UTF-8 JavaScript text.") from None
    if size > 65536:
        raise ValueError("JavaScript snippet exceeds 65536 UTF-8 bytes.")
    if code.count("\n") >= 2048:
        raise ValueError("JavaScript snippet exceeds 2048 lines.")
    if _SECRET.search(code):
        raise ValueError("Redact the credential-shaped value and submit only the code shape.")

    visible, comments_masked = _masked(code)
    found = set()
    for match in re.finditer(r"(?<![\w$.])eval\s*\(", visible):
        _add(found, "eval_call", code, match.start())
    for match in re.finditer(r"(?<![\w$.])new\s+Function\s*\(", visible):
        _add(found, "function_constructor", code, match.start())
    for match in re.finditer(r"\.\s*innerHTML\s*=(?![=>])", visible):
        _add(found, "inner_html_assignment", code, match.start())
    for match in re.finditer(r"(?<![\w$])document\s*\.\s*write(?:ln)?\s*\(", visible):
        _add(found, "document_write", code, match.start())
    for match in re.finditer(r"(?<![\w$.])(?:setTimeout|setInterval)\s*\(\s*[\"']", comments_masked):
        _add(found, "string_timer_callback", code, match.start())

    common = {
        "executed": False,
        "runtime_correctness_verified": False,
        "mastery_assessed": False,
        "sources": list(SOURCES),
        "notice": _NOTICE,
        "rules_checked": list(_RULES),
        "scope": "Literal markers outside comments and quoted/template strings in supplied text; not complete JavaScript parsing.",
    }
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
        "findings": items,
        "finding_count": len(found),
        "returned_count": len(items),
        "partial": len(found) > 100,
        "status": "Teaching observations only; no pass/fail or safety conclusion.",
    }


def register_javascript_review(registry):
    from jarvis.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="mentor_review_javascript",
            description="Review one supplied redacted JavaScript snippet with five bounded literal teaching checks, without executing it or reading files. Not security/correctness/mastery grading. No fixes or progress writes.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "maxLength": 65536,
                        "description": "Small redacted JavaScript source text, at most 65536 UTF-8 bytes. No credential values.",
                    }
                },
                "required": ["code"],
                "additionalProperties": False,
            },
            handler=review_javascript,
            risk=Risk.SAFE,
            category="mentor",
        )
    )

# Input is inspected as text only; it is never executed.
