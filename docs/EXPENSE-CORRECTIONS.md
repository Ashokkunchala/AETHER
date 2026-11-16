# AETHER expense arithmetic, correction and retry API

These APIs record past spending locally. They do not pay money, connect a bank,
convert currencies, change provider accounts or migrate old data.

## Existing paths and response compatibility

`GET /api/life/expenses` and its `month=YYYY-MM` filter keep the existing `items`,
numeric `total`, `by_category` and `currency` fields. The legacy total and categories
are now **INR-only**, matching the existing `currency: "INR"` label. An all-INR caller
gets the same totals and field types. Foreign-currency legacy records are not added
to INR and are not rewritten.

New `totals_by_currency` and `categories_by_currency` fields contain separate decimal
amount strings. There is no exchange-rate lookup. These are recorded currency labels,
not a guarantee that a three-letter label is a supported real currency.

The API scans at most 10,000 newest matching rows and lists at most 1,000 valid rows.
`partial` means totals are incomplete; `items_truncated` means the transaction list is
incomplete. `invalid_records_skipped`, limits and `notice` explain excluded legacy rows.
Invalid rows are not silently corrected or deleted. A month must be a real YYYY-MM.
The existing separate report endpoint and dashboard continue to use their documented
report bounds; a partial report is not a complete account statement.

## Correct a saved record

Each returned expense now includes an opaque `revision`. Use the current record and
review the exact new amount, recorded currency, category, note and spending date before
calling `PUT /api/life/expenses/{id}` with all those fields plus `expected_revision`.
Authentication is required, as for the existing APIs.

A stale revision with different desired values returns 409. The correction does not
replace another writer's changes. An identical correction retried after a lost response
returns the existing current row. Missing rows return 404; missing/invalid revisions or
invalid values return 422. The original id and creation time are retained. Correction
accepts a three-uppercase-letter recorded currency label so an existing foreign-currency
row is not silently relabeled INR. No currency conversion occurs. Ordinary creation
retains its existing INR-only scope.

## Optional idempotent create

Existing `POST /api/life/expenses` clients can still omit the optional `Idempotency-Key`
header. With no key, each valid call creates a record, as before. The local confirmed
chat tool's direct create function remains independent of HTTP request objects.

With a key, create and claim are one SQLite transaction. A key is 1-128 ASCII letters,
digits, dots, colons, underscores or hyphens. Reusing the same key and same normalized
payload with the same credential returns the existing record instead of duplicating it.
A changed payload returns 409. The `Idempotency-Replayed` response header distinguishes
a replay; status remains 201 for compatibility. If the record was corrected, a replay
returns its current values, not an old cached snapshot. If it was deleted, a replay
returns 409 and never recreates it.

Keys are credential-scoped. Different device credentials or a rotated token have separate
key namespaces. Clients must retain their key when retrying an uncertain result. A new
key, or no key, is a new create request, so check transactions before retrying that way.
This is not automatic semantic deduplication of two otherwise identical real expenses.
The browser uses the same key for an unchanged uncertain create while this page remains open. It does not persist retry keys across reloads.

Only the new `life_expense_requests` table is added when a keyed create is used. The old
expense schema and rows are left intact. Claim records retain request hashes and expense
ids, including deletion tombstones; they do not store bearer tokens or copies of note
text. Removing an expense does not remove its retry tombstone.

## Verification boundary

Automated checks use temporary local databases and synthetic expenses. They cover mixed
currencies, decimal sums, invalid/partial records, correction conflicts, deleted-record
retries, concurrent same-key creation, credential namespaces and transaction rollback.
They do not inspect or change the owner's real spending records. The expense form uses the API controls described below.

## Expense form

Use **Correct** beside a transaction, review the fields, then **Review & save correction**.
The confirmation shows before/after amount, currency, category, note and spending date.
A conflicting correction keeps your draft and reports the error; reload transactions,
choose the current row and review again. **Start new / cancel correction** returns to
an unsaved INR draft. Correction does not alter the recorded currency in this form.

New creates get a random retry key and a busy guard. After a network failure, keep the
page open and retry unchanged fields with the same credential. Changing fields or
credentials after an uncertain create is blocked rather than silently generating a
new key. Starting a new record in that state requires a warning acknowledgement to
check transactions first. Reloading/closing the page loses the page-memory retry key.
Draft expense data and retry keys are not saved to browser storage.

A successful save clears the form before refreshing reports. A refresh failure after
that success says the record was saved and must not be resubmitted as a new expense.
The transaction list displays scan/list/invalid-row notices; monthly report currencies
stay separate. Disconnect clears the displayed transaction list and invalidates stale
reads. It cannot cancel a write that already reached the server. These controls are
covered by synthetic browser/state-machine checks, not by changes to real records.
