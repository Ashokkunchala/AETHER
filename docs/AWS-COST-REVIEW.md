# AETHER offline Cost Explorer evidence review

`review_cost_explorer(path)` reads an existing local AWS `get-cost-and-usage`
JSON snapshot through the desktop DevOps evidence registry. It does not call
Cost Explorer, AWS, an SDK, a CLI, a model or any paid service. The existing live
AWS policy stays unchanged; Cost Explorer requests remain approval-path calls,
not silently automatic reads. This feature does not set up credentials.

## Periods, metrics and units stay separate

The reviewer preserves each supplied period's inclusive Start and exclusive End,
reported totals, cost/usage metric names, decimal amount strings, unit labels and
Estimated flag. Negative credits are not clamped. Missing Estimated is unknown;
false means only that the supplied report says not estimated, not proof of a
final bill. Unknown/malformed metric values are refused, not relabelled as money.

Supported cost metrics: AmortizedCost, BlendedCost, NetAmortizedCost,
NetUnblendedCost and UnblendedCost. UsageQuantity and NormalizedUsageAmount are
marked `usage_not_money`. AWS warns that UsageQuantity can combine incompatible
usage units unless scoped by usage type. Never report it as currency.

There is deliberately no grand total across periods, groups, metrics or units.
Blended and unblended are alternative measures, not amounts to add together.
Total fields are shown as supplied. Empty/missing Total is not zero, and group
amounts are not silently promoted to account totals. This avoids double-counting
when both totals and groups appear. Duplicate/overlapping periods are refused;
gaps between periods are disclosed. An empty ResultsByTime is only an empty
supplied result, not a zero invoice.

## Groups, bounds and privacy

At most 2 MB UTF-8 JSON, 366 periods, two grouping definitions, seven supported
metrics per object and 1000 supplied groups across the entire snapshot. All
supplied groups up to the limit are validated, while only 20 per period are
returned with an explicit truncation flag. Group indices refer to positions in
that period of the local file, not persistent IDs across periods.

Group key/definition values and dimension attributes are omitted because they
can contain account identifiers, private tags or arbitrary text. The tool does
not identify a service/account spending driver or interpret omitted labels. A
future separately reviewed attribution design is needed for that. Do not ask a
model to invent names for anonymous group indices.

Regular-file, suffix, symlink/junction and bounded-read checks apply. A file
changed during its size/mtime-checked read is refused. Duplicate JSON fields,
non-finite numbers, malformed flags/amounts/units, duplicate group keys or invalid
periods fail rather than producing a plausible summary. Path hygiene does not
make the parser an OS sandbox against hostile concurrent filesystem changes.

A nonempty NextPageToken is flagged but not returned or followed. Its absence
never proves all accounts, filters, regions, pages or the intended query scope
were supplied. Snapshot freshness, completeness, scope and amounts remain
independently unverified. Keep raw exports private. If the desktop tool is used
in a model-backed chat, its returned metrics can be included in that conversation;
the parser itself does not call an AI provider.

## What this is not

No live billing or final invoice, forecast, root cause, anomaly detector, tax/
credit reconciliation, price quote, budget, alert, savings recommendation or
optimization action. An export may be old, filtered or fabricated. Review the
query and current billing evidence separately before any financial decision.
Nothing is booked, paid, changed or deployed. Existing `analyze_daily_costs`
continues to compare explicit complete-day same-currency caller totals; this new
reviewer does not rewrite or auto-feed that threshold analysis.

Tests use synthetic JSON/temporary files for exact decimals, negative credits,
separate currencies/metrics, usage-not-money, estimated/unknown flags, groups
without totals, pagination/gaps/overlaps, bounds, data minimization, malformed
exports and SAFE registry execution after stop. No real account, paid API call,
user billing data, deployment or device action was used.

Official AWS sources checked November 16, 2026:
- https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html
- https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_ResultByTime.html
