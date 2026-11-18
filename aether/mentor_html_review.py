"""Bounded HTML source teaching checks. Never renders supplied markup."""

from __future__ import annotations

from html.parser import HTMLParser

from aether.mentor_javascript_review import _SECRET

SOURCES = [
    "https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script",
    "https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes",
    "https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Schemes/javascript",
    "https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe",
    "https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/form",
]
_RULES = {
    "script_tag": (
        "Review a script tag",
        "A literal script tag marker is present. Script can execute in a browser context; establish the source, loading boundary and content policy before any separate reviewed rendering.",
        0,
    ),
    "inline_event_handler": (
        "Review an inline event handler",
        "A literal on* attribute marker is present. Inline handlers mix markup and code and may be blocked by a content policy; prefer separately reviewed listeners where suitable.",
        1,
    ),
    "javascript_url": (
        "Review a javascript: URL",
        "A literal javascript: URL marker is present in a link-like attribute. It can execute script when navigated in some contexts; prefer an explicit reviewed URL or event flow where suitable.",
        2,
    ),
    "iframe_tag": (
        "Review an iframe",
        "A literal iframe marker is present. Embedded documents create another browsing context; check the source, sandbox and permission needs before any separate reviewed rendering.",
        3,
    ),
    "form_tag": (
        "Review a form",
        "A literal form marker is present. Forms submit data to a destination; check the action, method, fields and approval flow before any separate reviewed submission.",
        4,
    ),
}
_NOTICE = (
    "Limited literal HTML teaching checks only, not validation, sanitization, rendering, a sandbox, "
    "security audit, execution, correctness test or mastery assessment. No file, browser, network, "
    "package or command access and no progress writes. HTMLParser is tolerant and malformed markup, "
    "browser quirks, CSS, scripts, template interpolation, frameworks and generated DOM changes are "
    "not resolved. Findings may be false positives and unreported risks remain. A zero finding count "
    "is not a pass. Input already supplied to the assistant can remain in logs; use only small redacted "
    "snippets. Returned findings omit source text and attribute values."
)


class _MarkerParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.markers = []

    def handle_starttag(self, tag, attrs):
        self._markers(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._markers(tag, attrs)

    def _markers(self, tag, attrs):
        line, offset = self.getpos()
        if tag == "script":
            self.markers.append((line, offset, "script_tag"))
        if tag == "iframe":
            self.markers.append((line, offset, "iframe_tag"))
        if tag == "form":
            self.markers.append((line, offset, "form_tag"))
        if any(name.startswith("on") for name, _ in attrs):
            self.markers.append((line, offset, "inline_event_handler"))
        for name, value in attrs:
            if value is not None and name in {"href", "src", "action", "formaction"}:
                compact = "".join(value.split()).lower()
                if compact.startswith("javascript:"):
                    self.markers.append((line, offset, "javascript_url"))
                    break


def _utf8_column(code, line, offset):
    current = code.splitlines(keepends=True)[line - 1]
    return len(current[:offset].encode("utf-8"))


def review_html(markup: str):
    if not isinstance(markup, str) or not markup.strip() or "\x00" in markup:
        raise ValueError("Supply one nonempty redacted HTML snippet without NUL characters.")
    try:
        size = len(markup.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError("Supply valid UTF-8 HTML text.") from None
    if size > 65536:
        raise ValueError("HTML snippet exceeds 65536 UTF-8 bytes.")
    if markup.count("\n") >= 2048:
        raise ValueError("HTML snippet exceeds 2048 lines.")
    if _SECRET.search(markup):
        raise ValueError("Redact the credential-shaped value and submit only the markup shape.")

    parser = _MarkerParser()
    parser.feed(markup)
    parser.close()
    unique = set(parser.markers)
    items = []
    for line, offset, rule in sorted(unique)[:100]:
        title, explanation, source_index = _RULES[rule]
        items.append(
            {
                "rule": rule,
                "line": line,
                "column_utf8_zero_based": _utf8_column(markup, line, offset),
                "title": title,
                "explanation": explanation,
                "source": SOURCES[source_index],
            }
        )
    return {
        "rendered": False,
        "validated": False,
        "runtime_correctness_verified": False,
        "mastery_assessed": False,
        "sources": list(SOURCES),
        "notice": _NOTICE,
        "rules_checked": list(_RULES),
        "scope": "Literal tags and attributes in supplied text; not complete browser parsing or sanitization.",
        "findings": items,
        "finding_count": len(unique),
        "returned_count": len(items),
        "partial": len(unique) > 100,
        "status": "Teaching observations only; no pass/fail or safety conclusion.",
    }


def register_html_review(registry):
    from aether.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="mentor_review_html",
            description="Review one supplied redacted HTML snippet with five bounded literal teaching checks, without rendering it or reading files. Not security/correctness/mastery grading. No fixes or progress writes.",
            parameters={
                "type": "object",
                "properties": {
                    "markup": {
                        "type": "string",
                        "maxLength": 65536,
                        "description": "Small redacted HTML source text, at most 65536 UTF-8 bytes. No credential values.",
                    }
                },
                "required": ["markup"],
                "additionalProperties": False,
            },
            handler=review_html,
            risk=Risk.SAFE,
            category="mentor",
        )
    )

# Input is inspected as text only; it is never rendered.
