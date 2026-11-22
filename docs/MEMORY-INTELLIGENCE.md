# Smart memory and intelligence: ability map and boundaries

Part 7 of the AETHER spec: structured memory with intelligence features, and a
hard rule that passwords, API keys and auth tokens never live in ordinary
memory. This page maps every requested item to what exists, what this change
adds, and the honest limits.

Standing rules: memory content never leaves the machine for search, digests or
ranking. Semantic search uses the optional local ChromaDB +
sentence-transformers stack only; when it is not installed the tool says so and
nothing is sent to a network or paid service instead. Secrets live in the
native OS credential vault (`aether/secret_store.py`), nowhere else.

## Structured memory types

`memory_categories` lists the agreed vocabulary and what belongs in each:

| Type | What to remember |
| --- | --- |
| personal | User-approved preferences |
| conversational | Useful ongoing discussions |
| projects | Repository names, branches and project status |
| technical | Tools, technologies and configurations |
| learning | Topics completed and weak areas |
| tasks | Pending tasks and deadlines |
| work | Resume, career goals and interview preparation |
| context | Current device, application and active workflow |

Categories stay free-text for backward compatibility (existing `general` and
custom categories keep working); the vocabulary is guidance that makes review,
digests and retention reliable, not a hard gate.

## Memory intelligence features

| Requested feature | Status | Where |
| --- | --- | --- |
| Long-term memory | Exists | `memories` table in the local SQLite store (app/personal_data.py) |
| Short-term conversational memory | Exists | Chat history in the backend app |
| Project-specific memory | Exists | Categories plus opt-in document folders (aether/memory/doc_memory.py) |
| Semantic search | Added | `memory_semantic_search`: local embeddings over saved memories, synced by ID, expired items excluded. Honest unavailable result when the optional local stack is missing; never a remote or paid fallback |
| Context retrieval | Exists | Bounded memory read for chat personalization (latest 20, expiry-aware) |
| Automatic memory summarization | Added | `memory_digest`: extractive per-category counts, date ranges and frequent terms. Labeled as not an LLM summary |
| Memory conflict detection | Added | `memory_review_conflict_candidates`: same-category, same-subject, different-claim ID groups. Heuristic candidates only, never contradiction verdicts; nothing auto-merges |
| Memory correction | Exists | `memory_correct_saved` compare-and-swap on exact expected text |
| Memory export | Exists | `GET /api/export` includes all memories |
| Memory review and deletion | Exists | `memory_search_saved`, per-ID and full delete APIs |
| User-controlled retention | Exists | `memory_set_expiry`, `memory_retention_status`, confirmed `memory_purge_expired` |
| Sensitive-data protection | Added | Save path (POST/PUT /api/memories) refuses secret-shaped text with a 422 pointing to the vault; `memory_scan_sensitive` flags IDs of legacy secret-shaped rows without echoing values |

## Boundaries

- Secret detection is pattern-based: it can miss secrets and can flag harmless
  text. Flagged memory text is never displayed by the scan; review by ID.
- Expiry excludes an item from future chat context; it is not secure erasure,
  and already-sent context cannot be recalled. Purge deletes expired rows only.
- Semantic search ranking is similarity, not truth or importance.
- Digests are extractive counts and term frequencies, not understanding.
- The semantic index lives under `~/.aether/memory-semantic` on the local disk
  only, with anonymized telemetry off.
