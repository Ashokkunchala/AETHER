# Mentor HTML teaching review

`mentor_review_html` accepts one small redacted HTML snippet as text and returns location-only teaching observations. It does not render the markup, open a browser, read files, contact a network service, fix the markup, write progress, or grade mastery.

## What it checks

The reviewer uses Python's tolerant HTML parser and reports five literal markers:

1. `<script>` tags
2. Inline `on*` event-handler attributes
3. `javascript:` URLs in link-like attributes
4. `<iframe>` tags
5. `<form>` tags

Each finding has a rule, line, zero-based UTF-8 column, fixed explanation and MDN source link. Source text, names and attribute values are omitted.

## Limits

This is not an HTML validator, sanitizer, browser parser, sandbox, security audit, runtime correctness test or certification signal. Malformed markup, browser quirks, CSS, scripts, template interpolation, frameworks and generated DOM changes are not resolved. Findings may be false positives, and unreported risks remain. A zero finding count is not a pass.

The tool rejects empty, oversized, invalid-UTF-8, NUL-containing and credential-shaped input. Use a small redacted snippet because text already supplied to the assistant can remain in logs.

Sources:

- [MDN script](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script)
- [MDN HTML attributes](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes)
- [MDN javascript: URLs](https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Schemes/javascript)
- [MDN iframe](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe)
- [MDN form](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/form)
