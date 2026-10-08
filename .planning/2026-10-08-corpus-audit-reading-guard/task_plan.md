# Task Plan: Corpus audit and reading explanation guard

## Goal

Report verified cache coverage without guessing source scope, and prevent malformed or KEYS-conflicting reading explanations from reaching users.

## Next Step

Report the verified result and remaining limits to the user.

## Current Phase

Phase 4

## Phases

### Phase 1: Verify scope and baseline
- [x] Inspect sources, cache, service, and tests
- [x] Run existing suite
- **Status:** complete

### Phase 2: Corpus audit (TDD)
- [x] Add tests for declared/unknown/partial source scope
- [x] Add minimal source-backed manifest and audit command
- [x] Verify audit output on real corpus
- **Status:** complete

### Phase 3: Reading explanation guard (TDD)
- [x] Add tests for B/C headings, order, duplicates, empty bodies, KEYS conflicts, and safe fallback
- [x] Implement shared contract and service fail-closed behavior
- **Status:** complete

### Phase 4: Full verification and delivery
- [x] Run focused and full tests
- [x] Inspect changed files and summarize remaining unknowns
- **Status:** complete

## Decisions Made

| Decision | Rationale |
|---|---|
| Keep the current 38 JSON cache files unchanged | Avoid risky migration and preserve existing callers |
| Unknown source scope stays unknown | Parsed cache presence cannot prove what the original paper contained |
| Explanation conflicts fail closed | Observing a mismatch alone does not protect the user |
| Do not require all sections on shared-reading PDFs | Original sources explicitly omit duplicates; 2022-06 set 2 still has a real A/C gap |
| Audit "answerable" means question/KEYS coverage, not passage fidelity | Most B caches lack the full A–R paragraph inventory, so claiming full text completeness would be false |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Parent `.venv` points to deleted WindowsApps interpreter | 1 | Use project-local `.venv`, which passed baseline |
| System TEMP atexit ACL cleanup traceback despite green tests | 1 | Set TEMP/TMP to project `tmp` for remaining runs |
| Forcing PYTHONIOENCODING=utf-8 broke four pre-existing CLI tests that decode child output as GBK | 1 | Do not set that variable for the test suite; final rerun passed 252 tests |
