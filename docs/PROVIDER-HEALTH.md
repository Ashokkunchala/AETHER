# Measured provider health summaries

AETHER records bounded, allow-listed summaries for local AI provider attempts:
provider/model names, timestamps, success or failure, elapsed time and bounded
error types. Prompts, tool arguments, raw exception text, account identifiers,
API keys and other credentials are discarded before the event is retained.

The authenticated endpoint and tool expose an aggregate view:

- `GET /api/provider/health` in both FastAPI backends.
- `provider_health_summary()` in the SAFE `system` tool category.

The response groups the bounded retained sample by provider and reports:

- event, success and failure counts;
- a success rate only when a recorded event carried an explicit boolean result;
- measured latency sample count, average, minimum and maximum;
- models seen in the retained sample;
- the latest retained event result and timestamp;
- whether SQLite persistence or the volatile in-process fallback supplied the
  history.

`latest_result` means only the latest retained local event. It is not a live
provider-health check, account status, quota or remaining-budget value. No
provider, network, quota or billing API is contacted when the summary is read.

The runtime history retains at most 200 low-sensitivity events and the summary
scans at most the latest 100. Older events can be omitted. The sample can mix
chat turns, model fallback attempts and assistant tool-loop turns because the
event schema does not claim that every row is one complete user request.

The summary is for local troubleshooting and dashboard/API inspection. It does
not route traffic, change provider configuration, estimate cost, predict
availability, guarantee privacy properties or prove that a configured provider
will work on the next request.

## Verification

Focused automated tests cover SQLite isolation, aggregation, provider/tool
category separation, explicit empty results, privacy filtering, registry risk
classification and bearer-token authentication for both app variants. They do
not contact Gemini, OpenRouter, Groq or any billing/quota API.
