"""Bounded shell-command teaching checks. Never executes supplied text."""

from __future__ import annotations

import re

SOURCES = [
    "https://pubs.opengroup.org/onlinepubs/9799919799.2024edition/utilities/V3_chap02.html",
    "https://man7.org/linux/man-pages/man1/bash.1.html",
]
_RULES = {
    "command_substitution": (
        "Review nested command substitution",
        "A literal command-substitution marker is present outside single quotes. A substituted command can run before the outer command. Establish its source and effects before any separate reviewed execution.",
        0,
    ),
    "recursive_force_delete": (
        "Review a recursive force delete",
        "A spelled rm command combines recursive and force options. Check the exact target, backups, current directory and recovery path; this reviewer does not resolve variables or paths.",
        0,
    ),
    "output_overwrite": (
        "Review an output overwrite",
        "A literal output redirection operator is present outside single quotes. Redirection can create or truncate a target before the command runs. Check the exact target and shell options.",
        0,
    ),
    "sudo_invocation": (
        "Review elevated execution",
        "A spelled sudo command word is present. Confirm why elevated privileges are needed and use the existing fresh-approval boundary before any separate execution.",
        0,
    ),
    "download_pipe_shell": (
        "Review a download piped to a shell",
        "A spelled curl/wget pipeline sends downloaded text to sh or bash. Prefer downloading, inspecting and verifying before any separately reviewed execution.",
        0,
    ),
}
_SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:password|passwd|token|secret|api[_-]?key)\s*[:=]|\bAKIA[0-9A-Z]{16}\b",
    re.IGNORECASE,
)
_NOTICE = (
    "Limited literal shell teaching checks only, not parsing every shell, a sandbox, security audit, "
    "command approval, execution, correctness test or mastery assessment. No command/path/network/file "
    "access or progress writes. Quoting, aliases, functions, variables, globs, paths, current directory "
    "and remote content are not resolved. Findings may be false positives and unreported risks remain. "
    "A zero finding count is not a pass. Input already supplied to the assistant can remain in logs; "
    "use only small redacted commands. Returned findings omit command text and values."
)


def _outside_single(text: str):
    chars = []
    single = False
    for index, char in enumerate(text):
        if char == "'":
            single = not single
            chars.append(" ")
        elif single:
            chars.append(" ")
        else:
            chars.append(char)
    return "".join(chars)


def _line_column(text: str, index: int):
    line = text.count("\n", 0, index) + 1
    start = text.rfind("\n", 0, index) + 1
    return line, len(text[start:index].encode("utf-8"))


def _add(found, rule, text, index):
    line, column = _line_column(text, index)
    found.add((line, column, rule))


def review_shell(command: str):
    if not isinstance(command, str) or not command.strip() or "\x00" in command:
        raise ValueError("Supply one nonempty redacted shell command without NUL characters.")
    try:
        size = len(command.encode("utf-8"))
    except UnicodeEncodeError:
        raise ValueError("Supply valid UTF-8 shell text.") from None
    if size > 32768:
        raise ValueError("Shell command exceeds 32768 UTF-8 bytes.")
    if command.count("\n") >= 512:
        raise ValueError("Shell command exceeds 512 lines.")
    if _SECRET.search(command):
        raise ValueError("Redact the credential-shaped value and submit only the command shape.")
    visible = _outside_single(command)
    found = set()
    for match in re.finditer(r"\$\(", visible):
        _add(found, "command_substitution", command, match.start())
    offset = 0
    for line in visible.splitlines(keepends=True):
        index = line.find("`")
        if index >= 0:
            _add(found, "command_substitution", command, offset + index)
        offset += len(line)
    for match in re.finditer(r"(?:^|[\n;|&])\s*rm\s+(?=[^\n#]*\S)", visible):
        start = match.start()
        while start < len(visible) and (visible[start].isspace() or visible[start] in ";|&"):
            start += 1
        tail = re.match(r"rm\s+([^\n;|&]*)", visible[start:])
        words = re.findall(r"(?<!\S)(-[A-Za-z]+|--recursive|--force)(?!\S)", tail.group(1) if tail else "")
        short = "".join(word[1:] for word in words if word.startswith("-") and not word.startswith("--"))
        recursive = "r" in short.lower() or "--recursive" in words
        force = "f" in short.lower() or "--force" in words
        if recursive and force:
            _add(found, "recursive_force_delete", command, start)
    for match in re.finditer(r"(?<!>)>(?!>)", visible):
        _add(found, "output_overwrite", command, match.start())
    for match in re.finditer(r"(?<![\w/])sudo(?![\w-])", visible):
        _add(found, "sudo_invocation", command, match.start())
    for match in re.finditer(r"(?<![\w/])(?:curl|wget)(?![\w-])[^\n|]*\|\s*(?:sudo\s+)?(?:sh|bash)(?![\w-])", visible):
        _add(found, "download_pipe_shell", command, match.start())
    common = {
        "executed": False,
        "shell_effects_verified": False,
        "mastery_assessed": False,
        "sources": list(SOURCES),
        "notice": _NOTICE,
        "rules_checked": list(_RULES),
        "scope": "Literal patterns outside single quotes in supplied text; not complete shell parsing.",
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


def register_shell_review(registry):
    from aether.tools.registry import Risk, Tool

    registry.register(
        Tool(
            name="mentor_review_shell",
            description="Review one supplied redacted shell command with bounded literal teaching checks, without executing it or resolving paths/variables. Not command approval, sandboxing or correctness/mastery grading.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "maxLength": 32768,
                        "description": "Small redacted shell text, at most 32768 UTF-8 bytes. No paths with credentials or secret values.",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=review_shell,
            risk=Risk.SAFE,
            category="mentor",
        )
    )

# Input is inspected as text only; it is never executed.
