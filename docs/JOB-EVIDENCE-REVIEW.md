# AETHER resume/JD literal evidence review

`review_job_evidence(resume_text, job_text, requirements)` helps navigate exact supplied resume and job-description evidence. It does not rank a person, produce an ATS score, infer skill/proficiency, select a latest resume, verify job authenticity or submit an application.

The owner supplies both exact texts and1-40 requirements, each with `phrase` and `importance` (`required`, `preferred` or `unspecified`). A requirement phrase must occur literally in the supplied JD. Importance is the caller's label, not an automatically verified requirement classification. Each text is limited to60,000 characters; each phrase to120. Duplicate normalized phrases, empty/oversized/control inputs and invented absent requirements are rejected.

Matching uses Unicode NFKC normalization, case folding, whitespace collapse and word-edge checks around alphanumeric phrase ends. It is not stemming, fuzzy search, synonym detection or semantic matching. `k8s` does not automatically match `Kubernetes`. A missing literal mention is not proof of a missing skill. A mention in `No Python production experience` remains a mention, never a positive qualification claim. Exact surrounding lines are returned so the owner can see negation, scope and time context. At most3 excerpts per source/phrase, each bounded to1,200 characters, with truncation labels. Whole-text matches across line breaks may have no line excerpt; that state is explicit rather than inventing a quote.

Output contains no match percentage, hire/reject recommendation, inferred years of experience, protected-trait analysis or new achievement text. It suggests manually checking synonyms and real evidence, and never asks the owner to invent an achievement. Existing resume claims remain assertions, not verified career history. It does not extract identity, age, gender or health traits from text for ranking.

## Provider-free local use

Review [example JSON](examples/job-evidence.json), then from the installed source folder:

```powershell
.\.venv\Scripts\python.exe -B -m jarvis.owner_console job-review --spec docs/examples/job-evidence.json
```

The owner console displays exact supplied text/requirements and the privacy scope, then requires `APPROVE review_job_evidence`. It performs the comparison locally, prints output and saves nothing. No provider/key/backend/listener is needed. Console spec reads are bounded to256KiB. Use a private terminal because resume/JD text and excerpts may be sensitive and terminal capture/history can retain them.

The same tool is available in the normal registry with fresh confirmation and stop enforcement. That AI chat workflow can disclose exact arguments/results to its configured provider; do not use private resumes there without approving that disclosure. The provider-free console does not send them. Tool text is data, not instructions to run code or contact anyone. No file body is read by the analyzer itself; only the console reads the explicitly selected JSON spec. No recruiter contact, job search, browser/application/login, account connection, message, upload or source-file change occurs.

This is one bounded preparation capability. Live job discovery, semantic JD/resume analysis, reviewed factual tailoring, application form automation and approved submission remain separate work. Tests cover negation preservation, literal boundaries/Unicode normalization, missing synonyms, cross-line uncertainty, exact excerpts/limits, unsupported inputs, fixed owner-console dispatch and fresh review/stop. Device/provider behavior remains unverified.
