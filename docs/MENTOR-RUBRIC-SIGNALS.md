# Mentor free-text rubric signals

AETHER can now review one deep-mentor explanation with a deterministic rubric-signal tool. It is a transparent practice aid, not an AI grader.

Use an exact lesson ID from `mentor_deep_catalog`, then call:

```text
mentor_evaluate_reasoning(lesson_id, reasoning)
```

The tool checks three things:

1. Expected concept coverage: phrase and synonym evidence for the lesson's correct decision concepts.
2. Unsafe-choice review: whether an incorrect decision is only mentioned as rejected/warned, or appears without a negation as a possible endorsement.
3. Boundary signals: whether the answer mentions scenario evidence, unsafe-choice rejection, an unknown or next check, and the approval/execution/verified-outcome boundary.

`mentor_deep_submit` returns the same review beside its existing objective decision result. The standalone tool does not write the answer to the mentor database. Results name lesson concepts and matched signal terms, not the supplied answer. Secret-shaped text such as private keys, AWS access-key IDs or bearer tokens is refused; use a redacted explanation.

## Limits

The evaluator uses bounded phrase and synonym matching. It can miss a strong answer written with different words, and it can reward a poor answer that repeats terms. `rubric_signals_complete` means only that the deterministic signals were present. It is not semantic correctness, mastery, certification, interview readiness, code execution or lab evidence. The lab text remains a paper/fake/local-example exercise; no command, compiler, cloud API, CI dispatch or deployment is run.

Use the source link and reference reasoning to review the answer yourself. Existing objective prerequisite, spaced-review, local database, emergency-stop and clear-confirmation behavior is unchanged.
