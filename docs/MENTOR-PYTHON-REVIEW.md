# AETHER Python snippet teaching review

`mentor_review_python` accepts a small redacted Python snippet as text and returns
bounded AST observations. It extends the existing mentor registry without changing
Terraform lessons, quiz choices, project journals or progress records. It does not
open a source path, import the snippet, run a test, compile executable bytecode,
write files, install a dependency, contact a provider or modify the code.

## What it checks

Five syntactic patterns produce fixed explanations, line numbers and source links:

- Direct `eval(...)` or `exec(...)` spelled calls.
- Spelled `subprocess.run/Popen/call/check_call/check_output(...)` with a literal
  `shell=True` keyword. Argument expansion, variables and aliases are not resolved.
- Spelled `pickle.load/loads(...)` calls, with an input-trust reminder.
- List, dict or set literals directly used as positional or keyword-only defaults
  in ordinary or async function definitions. Constructors and nested defaults are
  not covered.
- Bare `except:` handlers, with a specific-exception/interruption reminder.

For example, reviewing `def collect(items=[]): return items` points to the mutable
default. It asks whether shared state was intended and suggests considering a
`None` sentinel. It does not edit the function or decide that it is always wrong.
Source text, function/variable names, literal values and raw parser diagnostic text
are not copied into returned findings. Syntax rejection returns only a parser
location and an explicit incomplete-report state.

## Limits and privacy

Input is limited to 65536 UTF-8 bytes and 20000 AST nodes. At most 100 findings are
returned, sorted by line, zero-based UTF-8 byte column and rule. `finding_count`
counts all detected rule/location pairs; `partial=true` reports truncation or a
syntax rejection, never a clean review. Syntax diagnostic columns follow Python's
parser offset convention, separately from the AST byte-column field.

This is not a security audit, linter, type checker, test runner, correctness grade,
mastery assessment or full language mentor. Parsing uses the Python version that
runs AETHER and may accept syntax not executable on another version, or statements
that still fail compilation/runtime checks. Alias/name rebinding and control/data
flow are not resolved. A local object named `pickle` can trigger a false positive;
an aliased genuine pickle call can be missed. Other unsafe shell calls and indirect
code execution can go unreported. No finding is proof of a vulnerability, and zero
findings is not a safety, quality, syntax-compilation or correctness pass.

No source text or result is stored by this module. That does not erase the input
from the conversation, configured assistant/provider context, caller logs, exports
or backups. Supply only small redacted code you intend the assistant to process.
The returned observations are data for review, not permission to run a proposed
fix, install anything, send code or change a repository. Any later test or machine
command still uses its own fresh review boundary. No lesson pass, study duration,
project verification, interview grade or certification readiness is recorded.

## Evidence

Synthetic tests cover the exact patterns, intentionally uncovered forms, strict
input/UTF-8/size/complexity limits, syntax rejection without raw diagnostics,
source-value omission, no snippet side effects, finding order/truncation, result
independence and existing-registry/progress preservation. No user project was
executed or independently reviewed, and no real-device acceptance is claimed.

Official sources checked November 17, 2026:

- https://docs.python.org/3/library/ast.html
- https://docs.python.org/3/library/subprocess.html
- https://docs.python.org/3/library/pickle.html
- https://docs.python.org/3/tutorial/controlflow.html
- https://docs.python.org/3/tutorial/errors.html
