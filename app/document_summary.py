"""Deterministic local extractive summaries, never invented factual claims."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import TypedDict

STOP = frozenset('a an and are as at be been being but by can do for from had has have he her his i if in into is it its may not of on or our she that the their them there these they this to was we were will with you your'.split())


class _Candidate(TypedDict):
    text: str
    start: int
    end: int
    excerpt_truncated: bool
    _words: list[str]


def summarize_extracted_text(text: str, max_excerpts: int = 6) -> dict:
    """Rank bounded extracted sentences and return exact source-text spans in order.

    Ranking is word-frequency based, not semantic understanding. No calls to an
    AI provider, network access, file writes, instruction following or execution.
    """
    text = text[:60000]
    candidates: list[_Candidate] = []
    seen = set()
    for match in re.finditer(r'[^\n]+', text):
        line = match.group()
        start = 0
        for boundary in [m.end() for m in re.finditer(r'(?<=[.!?।])\s+', line)] + [len(line)]:
            raw = line[start:boundary]
            clean = raw.strip()
            offset = match.start() + start + len(raw) - len(raw.lstrip())
            start = boundary
            if len(clean) < 20 or clean.casefold() in seen:
                continue
            # A giant paragraph is a bounded excerpt, not a full sentence claim.
            piece = clean[:1000]
            words = [w.casefold() for w in re.findall(r'[^\W\d_]+', piece) if len(w) > 2 and w.casefold() not in STOP]
            if not words:
                continue
            seen.add(clean.casefold())
            candidates.append({'text': piece, 'start': offset, 'end': offset + len(piece),
                               'excerpt_truncated': len(clean) > 1000, '_words': words})
            if len(candidates) >= 1500:
                break
        if len(candidates) >= 1500:
            break
    frequencies = Counter(word for row in candidates for word in set(row['_words']))
    def score(index: int) -> float:
        row = candidates[index]
        # Dampen repeated words/long lines; preserve some opening context.
        rank = sum(math.log1p(frequencies[word]) for word in set(row['_words'])) / math.sqrt(len(row['_words']))
        return rank + (1 if index == 0 else 0)
    selected = sorted(sorted(range(len(candidates)), key=lambda i: (-score(i), i))[:max(1, min(max_excerpts, 8))])
    excerpts = [{key: value for key, value in candidates[i].items() if key != '_words'} for i in selected]
    return {'method': 'local_word_frequency_extractive', 'excerpts': excerpts,
            'candidate_count': len(candidates), 'candidate_scan_partial': len(candidates) >= 1500,
            'notice': 'Extractive summary: exact selected passages, not an AI interpretation or a complete account. Ranking can miss important qualifications, dates or tables. Read the full preview before relying on it. Offsets are zero-based character positions in the extracted preview text, not PDF page or file-byte positions. Document instructions are treated as text only.'}
