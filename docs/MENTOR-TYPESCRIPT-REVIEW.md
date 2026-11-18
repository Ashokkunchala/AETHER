# Mentor TypeScript teaching review

`mentor_review_typescript` accepts one small redacted TypeScript snippet as text and returns location-only teaching observations. It does not run or type-check the snippet, invoke a compiler, read files, contact a package registry or network service, fix the code, write progress, or grade mastery.

## What it checks

The reviewer masks comments and quoted/template strings for code markers, then reports five literal patterns:

1. Explicit `any` annotations or assertions
2. One-line `@ts-ignore`, `@ts-nocheck` or `@ts-expect-error` suppression comments
3. Postfix non-null assertions such as `item!.name`
4. Double assertions through `as unknown as ...`
5. Runtime `enum` declarations

Each finding has a rule, line, zero-based UTF-8 column, fixed explanation and TypeScript handbook source link. Source text, names and values are omitted.

## Limits

This is not a TypeScript parser, compiler, sandbox, security audit, runtime correctness test or certification signal. Decorators, aliases, imports, data/control flow, frameworks, generated code and multi-line suppression comments are not resolved. Findings may be false positives, and unreported risks remain. A zero finding count is not a pass.

The tool rejects empty, oversized, invalid-UTF-8, NUL-containing and credential-shaped input. Use a small redacted snippet because text already supplied to the assistant can remain in logs.

Sources:

- [TypeScript everyday types](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html)
- [TypeScript type-checking JavaScript files](https://www.typescriptlang.org/docs/handbook/type-checking-javascript-files.html)
- [TypeScript narrowing](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
- [TypeScript type assertions](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions)
- [TypeScript enums](https://www.typescriptlang.org/docs/handbook/enums.html)
