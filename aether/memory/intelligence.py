"""Structured memory types, local semantic search, digests and sensitive-data screening.

Everything here is local-only: no memory content is sent to a provider or paid
service. Semantic search uses the optional local ChromaDB + sentence-transformers
stack already vendored as optional dependencies; when they are not installed the
tool says so honestly instead of falling back to a network service.
"""
from __future__ import annotations

import re
from collections import Counter

# Structured memory types from the owner-approved spec. Categories stay free-text
# for backward compatibility; this vocabulary is the guidance, not a hard gate.
MEMORY_CATEGORIES = {
    'personal': 'User-approved preferences (language, units, likes and dislikes).',
    'conversational': 'Useful ongoing discussions worth continuing later.',
    'projects': 'Repository names, branches and project status.',
    'technical': 'Tools, technologies and configurations.',
    'learning': 'Topics completed and weak areas.',
    'tasks': 'Pending tasks and deadlines.',
    'work': 'Resume, career goals and interview preparation.',
    'context': 'Current device, application and active workflow.',
    'general': 'Legacy/uncategorized saved facts.',
}

MAX_TEXT = 2000
MAX_SCAN_ROWS = 1000

# Secret-shaped content belongs in the native credential vault (aether.secret_store),
# never in ordinary conversation memory. Detection labels only; values never echoed.
_SECRET_VALUE_PATTERNS = (
    ('private key block', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('aws access key id', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('github personal access token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b')),
    ('slack token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b')),
    ('openai-style api key', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b')),
    ('google api key', re.compile(r'\bAIza[0-9A-Za-z_-]{20,}\b')),
    ('bearer jwt', re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b')),
)
_SECRET_CLAIM_PATTERNS = (
    ('password claim', re.compile(r'\b(pass(word|code|phrase)|pin)\b\s*(is|:|=)\s*\S+', re.IGNORECASE)),
    ('api key claim', re.compile(r'\b(api[-_ ]?key|secret|token)\b\s*(is|:|=)\s*\S+', re.IGNORECASE)),
)

_STOPWORDS = frozenset(
    'a an and are as at be but by for from has have he her his i in is it its my not of on or our she so that the their they this to was we what when which who will with you your'.split()
)


def _store():
    from app.personal_data import _connect
    return _connect()


def memory_categories():
    """List the structured memory types and their purpose. No data read."""
    return {
        'categories': [{'name': name, 'purpose': purpose} for name, purpose in MEMORY_CATEGORIES.items()],
        'notice': 'Guidance vocabulary only: existing free-text categories keep working. Saving under these names makes review, digests and retention decisions reliable.',
    }


def sensitive_text_reasons(text: str):
    """Detection labels for secret-shaped text. Never returns the matched values."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Text to screen must be non-empty.')
    reasons = [label for label, pattern in _SECRET_VALUE_PATTERNS if pattern.search(text)]
    reasons += [label for label, pattern in _SECRET_CLAIM_PATTERNS if pattern.search(text)]
    return reasons


def scan_memories_for_secrets():
    """Report IDs of saved memories whose text looks secret-shaped. Values never echoed."""
    with _store() as db:
        rows = db.execute('SELECT id,text FROM memories ORDER BY id DESC LIMIT ?', (MAX_SCAN_ROWS + 1,)).fetchall()
    flagged = []
    for row in rows[:MAX_SCAN_ROWS]:
        reasons = sensitive_text_reasons(row['text'])
        if reasons:
            flagged.append({'memory_id': row['id'], 'reasons': reasons})
    return {
        'records_scanned': min(len(rows), MAX_SCAN_ROWS),
        'partial_records': len(rows) > MAX_SCAN_ROWS,
        'flagged': flagged,
        'notice': 'Detection is pattern-based and may miss secrets or flag harmless text. Memory text is never shown here; review IDs with memory_search_saved. Move real secrets into the native credential vault, then correct or delete the memory. No record was changed.',
    }


def summarize_memories(category: str = ''):
    """Extractive per-category digest: counts, recency and frequent terms. Not an LLM summary."""
    if not isinstance(category, str) or len(category) > 40:
        raise ValueError('Category must be up to 40 characters.')
    sql, params = 'SELECT id,text,category,created_at,expires_at FROM memories', []
    with _store() as db:
        rows = db.execute(sql + ' ORDER BY id DESC LIMIT ?', (MAX_SCAN_ROWS + 1,)).fetchall()
    by_category: dict[str, list] = {}
    for row in rows[:MAX_SCAN_ROWS]:
        if category and row['category'] != category:
            continue
        by_category.setdefault(row['category'], []).append(dict(row))
    digests = []
    for name, items in sorted(by_category.items()):
        terms: Counter = Counter()
        for item in items:
            for word in re.findall(r'[a-zA-Z][a-zA-Z0-9_+-]{2,}', item['text'].lower()):
                if word not in _STOPWORDS:
                    terms[word] += 1
        digests.append({
            'category': name,
            'record_count': len(items),
            'newest_memory_id': items[0]['id'],
            'oldest_created_at': items[-1]['created_at'],
            'newest_created_at': items[0]['created_at'],
            'frequent_terms': [term for term, _ in terms.most_common(10)],
        })
    return {
        'records_reviewed': min(len(rows), MAX_SCAN_ROWS),
        'partial_records': len(rows) > MAX_SCAN_ROWS,
        'digests': digests,
        'notice': 'Extractive counts and term frequencies only; not an LLM-written summary, importance ranking or truth check. No record was changed. Review full text with memory_search_saved.',
    }


_SUBJECT_SPLIT = re.compile(r'\s*(?::|\bis\b|\bare\b|\bprefers\b|\blike[sd]?\b|\bwants?\b|\buses?\b|=)\s*', re.IGNORECASE)


def conflict_candidates():
    """Same-category same-subject different-remainder pairs. Candidates, never verdicts."""
    with _store() as db:
        rows = db.execute(
            "SELECT id,text,category FROM memories WHERE expires_at IS NULL OR julianday(expires_at)>julianday(datetime('now')) ORDER BY id DESC LIMIT ?",
            (MAX_SCAN_ROWS + 1,),
        ).fetchall()
    subjects: dict[tuple[str, str], list[int]] = {}
    for row in rows[:MAX_SCAN_ROWS]:
        parts = _SUBJECT_SPLIT.split(row['text'].strip(), maxsplit=1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            continue
        subject = ' '.join(parts[0].split()).casefold()[:120]
        remainder = ' '.join(parts[1].split()).casefold()
        if not subject or not remainder:
            continue
        subjects.setdefault((row['category'], subject), []).append((row['id'], remainder))
    candidates = []
    for (cat, subject), entries in subjects.items():
        remainders = {remainder for _, remainder in entries}
        if len(entries) > 1 and len(remainders) > 1:
            candidates.append({'category': cat, 'subject': subject, 'memory_ids': [mid for mid, _ in entries]})
        if len(candidates) >= 50:
            break
    return {
        'records_reviewed': min(len(rows), MAX_SCAN_ROWS),
        'partial_records': len(rows) > MAX_SCAN_ROWS,
        'candidate_groups': candidates,
        'notice': 'Heuristic only: entries in one category that start with the same subject but say different things. This is not contradiction, truth or staleness detection, and nothing was merged or changed. Review IDs with memory_search_saved and use memory_correct_saved for the record the user wants changed.',
    }


def _semantic_collection():
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None, None, None
    from pathlib import Path

    root = Path.home() / '.aether' / 'memory-semantic'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    client = chromadb.PersistentClient(path=str(root), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name='aether_saved_memories', metadata={'hnsw:space': 'cosine'})
    encoder = SentenceTransformer('all-MiniLM-L6-v2')
    return client, collection, encoder


def semantic_search_memories(query: str, limit: int = 10):
    """Local-only semantic search over saved memories. Honest when the local stack is absent."""
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError('Query text must contain 1-500 characters.')
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Limit must be 1-50.')
    client, collection, encoder = _semantic_collection()
    if collection is None:
        return {
            'available': False,
            'results': [],
            'notice': 'Local semantic search needs the optional chromadb and sentence-transformers packages installed locally. Nothing was sent to a network or paid service, and no fallback remote embedding was used. Use memory_search_saved (literal) meanwhile.',
        }
    with _store() as db:
        rows = db.execute(
            "SELECT id,text,category FROM memories WHERE expires_at IS NULL OR julianday(expires_at)>julianday(datetime('now')) ORDER BY id DESC LIMIT ?",
            (MAX_SCAN_ROWS,),
        ).fetchall()
    wanted_ids = [f'mem-{row["id"]}' for row in rows]
    existing = collection.get(include=[]) or {'ids': []}
    stale = [eid for eid in existing['ids'] if eid not in set(wanted_ids)]
    if stale:
        collection.delete(ids=stale)
    if rows:
        collection.upsert(
            ids=wanted_ids,
            documents=[row['text'][:MAX_TEXT] for row in rows],
            metadatas=[{'category': row['category'][:40]} for row in rows],
            embeddings=encoder.encode([row['text'][:MAX_TEXT] for row in rows]).tolist(),
        )
    found = collection.query(query_embeddings=[encoder.encode(query).tolist()], n_results=min(limit, max(len(rows), 1)))
    results = []
    if found and found.get('ids') and found['ids'][0]:
        for position, doc_id in enumerate(found['ids'][0]):
            results.append({
                'memory_id': int(doc_id.removeprefix('mem-')),
                'distance': found['distances'][0][position] if found.get('distances') else None,
            })
    return {
        'available': True,
        'results': results,
        'notice': 'Local embeddings only; no memory content left this machine. IDs reference saved memories; read full text with memory_search_saved. Distance ranking is similarity, not truth or importance.',
    }


def register_memory_intelligence(registry):
    from aether.tools.registry import Risk, Tool
    definitions = [
        ('memory_categories', 'List the structured memory types (personal, conversational, projects, technical, learning, tasks, work, context) and what belongs in each. Guidance only; reads no data.', memory_categories, Risk.SAFE, {}, []),
        ('memory_digest', 'Extractive per-category digest of saved memories: record counts, date range and frequent terms. Not an LLM summary; no content leaves the machine.', summarize_memories, Risk.SAFE,
         {'category': {'type': 'string', 'description': 'Optional exact category to digest'}}, []),
        ('memory_review_conflict_candidates', 'List candidate same-subject/different-claim memory ID groups for user review. Heuristic only, never a contradiction verdict; nothing is merged or changed.', conflict_candidates, Risk.SAFE, {}, []),
        ('memory_scan_sensitive', 'Report IDs of saved memories whose text looks secret-shaped (keys, tokens, passwords). Values are never echoed; move real secrets to the native credential vault.', scan_memories_for_secrets, Risk.SAFE, {}, []),
        ('memory_semantic_search', 'Local-only semantic search over saved memories using on-device embeddings. Honest unavailable result when the optional local stack is not installed; never a network or paid fallback.', semantic_search_memories, Risk.SAFE,
         {'query': {'type': 'string'}, 'limit': {'type': 'integer'}}, ['query']),
    ]
    for name, description, handler, risk, properties, required in definitions:
        registry.register(Tool(name=name, description=description,
                               parameters={'type': 'object', 'properties': properties, 'required': required},
                               handler=handler, risk=risk, category='memory',
                               requires_confirmation=False, never_auto_approve=False))
