# Task Plan: Local conversation history and reference reveal

## Goal

Add a local, unified history for chats and writing/translation drafts, with non-destructive chat branching and explicit confirmation before revealing reference answers and analyses.

## Next Step

Request user review of the implementation plan and native execution method.

## Current Phase

Phase 2: implementation plan

## Phases

### Phase 1: Requirements and design
- [x] Inspect current chat, draft archive, and writing cache boundaries.
- [x] Write and self-review a design spec.
- [x] Obtain user review of the written spec (user: “可以可以,开始写”).
- **Status:** complete

### Phase 2: Implementation plan
- [x] Write and self-review a testable plan after spec approval.
- [ ] Obtain user approval of the plan and execution method.
- **Status:** in_progress

### Phase 3: Implementation
- [ ] Implement local chat history, navigation, and non-destructive branching.
- [ ] Integrate existing draft history into the unified sidebar without deleting records.
- [ ] Add confirmed reference reveal and explicit pending fallback for missing writing content; do not change the paper cache.
- **Status:** pending

### Phase 4: Verification and handoff
- [ ] Run targeted and full tests.
- [ ] Verify existing local drafts and chat flows in Streamlit.
- [ ] Report results and remaining cache coverage limitations.
- **Status:** pending

## Key Questions

1. How can prior drafts be shown without confusing independent submissions with revisions? Use `revision_of` chains, not paper coordinates alone.
2. Where are writing reference essays today? The 38 parsed paper caches do not contain `writing_sample`/`writing_analysis` yet; a prior spec describes them but did not populate them.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Non-destructive branch from old chat turns | User explicitly preferred preserving original conversations and learning records. |
| Reference content hidden until explicit two-step confirmation | User wants to choose when to see answers/analysis; no forced prior draft submission. |
| Keep learning event archive as source of truth for drafts | Existing originals/revisions/feedback already persist there. |
| Separate bulk writing content from this implementation | None of 38 cached essays has a sample or analysis; avoid silent mass mutation of untracked papers. |
| Preserve location-based short chat follow-ups | Existing translation tests require “翻译呢” to reuse the current paper location. |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| Streamlit discovery script could not import from sandbox-visible `.venv` | 1 | Use read-only source inspection; do not modify user's working environment. |
| `git status` reported dubious ownership for parent repository | 1 | Use per-command `git -c safe.directory=...` for read-only checks; do not alter global Git config. |
| Parent Git repository has no `HEAD` commit and its `.git` is outside this task's writable root | 1 | Leave design uncommitted; do not create a root commit or alter Git ownership/config for a spec. |

## Notes

- This plan is task-specific; do not overwrite `.planning/.active_plan`, which points at an older task.
- Existing unrelated workspace changes must be preserved.
