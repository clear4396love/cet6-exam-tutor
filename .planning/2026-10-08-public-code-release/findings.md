# Findings

- `databases/` currently contains 17 OCR PDFs plus Markdown/JSON sidecars; user already removed the 35 original paper PDFs. It totals 82.6 MiB before this turn's edits.
- `parsed_papers/` contains 38 real cache JSON files. Skill `ask` is cache-only and cannot answer real questions in a source-only checkout without user-provided cache.
- Tests directly tied to the local corpus include `test_corpus_integrity.py`, parts of `test_translation.py`, `test_writing_reference_cache.py`, and at least one `test_degrade.py` path.
- `translation_audit.md` contains 38 complete trial translations with source excerpts; generated eval result JSONL also contains raw passages. Both should stay local.
- `.gitignore` does not currently exclude `databases/`, real caches, `.planning/`, `.superpowers/`, or eval artifacts.
- `.git` inside the project is an empty directory. Do not operate on the parent repository index.
