# Mentor JavaScript teaching review

`mentor_review_javascript` accepts one small redacted JavaScript snippet as text and returns location-only teaching observations. It does not run the snippet, open a browser, read files, contact a package registry or network service, fix the code, write progress, or grade mastery.

## What it checks

The reviewer masks comments and quoted/template strings, then reports five literal markers:

1. `eval(...)`
2. `new Function(...)`
3. `element.innerHTML = ...`
4. `document.write(...)` or `document.writeln(...)`
5. `setTimeout("...", ...)` or `setInterval("...", ...)` with a string callback

Each finding has a rule, line, zero-based UTF-8 column, fixed explanation and MDN source link. Source text, names and values are omitted.

## Limits

This is not a JavaScript/TypeScript parser, sandbox, security audit, runtime correctness test or certification signal. Template interpolation, aliases, imports, data/control flow, frameworks and generated code are not resolved. Findings may be false positives, and unreported risks remain. A zero finding count is not a pass.

The tool rejects empty, oversized, invalid-UTF-8, NUL-containing and credential-shaped input. Use a small redacted snippet because text already supplied to the assistant can remain in logs.

Sources:

- [MDN eval](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/eval)
- [MDN Function](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Function)
- [MDN innerHTML](https://developer.mozilla.org/en-US/docs/Web/API/Element/innerHTML)
- [MDN document.write](https://developer.mozilla.org/en-US/docs/Web/API/Document/write)
- [MDN setTimeout](https://developer.mozilla.org/en-US/docs/Web/API/Window/setTimeout)
