# Public-code release preparation

## Goal

Prepare a code-only GitHub release without publishing real CET-6 papers, parsed caches, personal records, or internal process files. Preserve all local data.

## Next Step

Write a failing clean-checkout test for the proposed source-only package, then make the smallest release-scope changes.

## Current Phase

Phase 1

### Phase 1: Scope and safety
- [x] Verify existing data, test dependencies, and ignored paths
- [ ] Add source-only upload boundary and release test
- **Status:** in_progress

### Phase 2: Corpus-free tests and synthetic demo
- [ ] Add fictional cache fixture
- [ ] Make tests pass without local real corpus while retaining optional local-corpus checks
- **Status:** pending

### Phase 3: Public docs and Git boundary
- [ ] Add README and corpus format/setup notes; no LICENSE per user choice
- [ ] Review staged-file candidates and establish project-local Git boundary if permitted
- **Status:** pending

### Phase 4: Verification
- [ ] Run focused and full tests in current checkout
- [ ] Verify a source-only copy without real corpus
- [ ] Report remaining publication or authentication blockers; do not push without visibility choice
- **Status:** pending

## Decisions Made

| Decision | Rationale |
|---|---|
| Keep real `databases/` and `parsed_papers/*.json` locally | User asked to publish code, not to erase local study data |
| Do not add LICENSE | User explicitly chose this |
| Do not claim full cache can be regenerated automatically | Current parser only recovers partial data and may fail on scans |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Existing `.git` is empty; Git walks to inaccessible parent | prior turn | Verify exact project boundary before Git mutation |
