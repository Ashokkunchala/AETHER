# Local document summaries and library organization

The Documents page can group its bounded authorized file library by file type or
show filesystem modification-time order. This organizes the view only: it does
not move, rename, copy, delete or infer the latest correct resume.

The local summary endpoint `/api/documents/summary` uses the same authorization,
roots, secret exclusions, supported formats and extraction limits as Preview.
It ranks sentences/passages by word frequency and returns up to six exact text
excerpts in source order, with zero-based character offsets in the extracted
preview. There is no AI provider call, network disclosure, instruction execution
or source-file write. Large passages are capped at 1000 characters; candidate
scans are capped at 1500 passages and the source preview at 60000 characters/80 PDF
pages. Truncation is labeled.

This is an extractive summary, not semantic understanding. Selected passages can
miss important qualifications, negations, dates, tables or context. Short/scanned
files may yield no useful passages. No OCR, document-version verification,
resume selection or factual correctness check is supplied. Read the full preview
and original before relying on a summary. Word-frequency ranking is less useful
for some languages and highly formatted files.

Source file access is a private local application boundary, not a hostile-user
filesystem sandbox. The older integration document-search endpoint remains a
separate implementation with its previous policy.
