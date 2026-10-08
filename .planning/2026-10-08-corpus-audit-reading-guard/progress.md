# Progress Log

## Session: 2026-10-08

- Design scope approved by user: source-backed scope audit first, runtime explanation guard second.
- Skills read: brainstorming (bounded design already approved), test-driven-development, planning-with-files, ponytail, verification-before-completion.
- Product code and tests changed; cached paper JSON files were not edited.
- Baseline `./.venv/Scripts/python.exe -m pytest -q tests --tb=short`: 224 passed, 1 warning, exit 0; system TEMP emitted an atexit ACL traceback.
- Parent `../.venv` test command failed because its configured WindowsApps interpreter no longer exists; switched to project-local `.venv`.
- Visually inspected source PDF pages for all exceptional cache scopes; confirmed a real A/C gap in 2022-06 set 2 and intentionally omitted/shared reading for 2022-06 set 3, 2022-09 sets 2/3, 2023-03 sets 2/3, and A in 2021-12 set 3.
- Added `tools/corpus_scope.json`, `tools/corpus_audit.py`, and four corpus-audit tests. RED: module missing; GREEN: four passed. Real audit exits 1 and reports exactly two missing sections, A/C of 2022-06 set 2; 31 source scopes remain unknown.
- Added `retrieval/answer_contract.py` and shared headings in `retrieval/answer_prompt.py`; wired B/C service branches to fail closed and record `answer_verified`. RED: new module missing, then two extra edge cases failed; GREEN: eleven focused contract tests passed.
- Updated offline fake explanations to honor the new contract, and reused prompt heading constants in `tools/scenario_eval.py`.
- Read-only review found and helped close: a missing whole-cache file could disappear from the audit; common conflicting-answer phrasings and extra headings could pass; practice feedback had an unguarded Section B path; a truncated cloze word bank could look valid.
- Section B paragraph fidelity cannot be proved by current cache fields; the audit now calls its positive state `answerable`, not `complete`.
- Final full suite: 252 passed, one deprecation warning. Real audit reports only the verified 2022-06 set 2 A/C gap and exits 1 as intended. One intermediate run with forced PYTHONIOENCODING had four GBK subprocess decode failures; removed forced encoding and green rerun.

## Test Results

| Test | Expected | Actual |
|---|---|---|
| Baseline suite | Pass | 224 passed, one warning, plus system TEMP cleanup traceback |
| Focused corpus audit | Pass | 8 passed |
| Focused explanation and practice guard | Pass | 47 passed before final extra cases |
| Full suite | Pass | 252 passed, one deprecation warning |

## Next Step

Delivery complete; the known 2022-06 set 2 cache gap remains a separate content-repair task.
