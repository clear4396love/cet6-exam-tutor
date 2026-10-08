# Task Plan: Local Learning Memory Design

## Goal

Produce a reviewable design for a per-machine CET-6 learning record covering reading, writing, and translation, shared by Streamlit and a future Codex Skill, without implementing product code.

## Next Step

Execute the approved six-task implementation plan in place, test-first, without touching unrelated user changes.

## Current Phase

Phase 6

## Phases

### Phase 1: Confirm current boundaries

- [x] Record the approved local-only scope
- [x] Inspect persistence, progress calculation, and UI behavior
- **Status:** complete

### Phase 2: Write and self-review specification

- [x] Write a focused design document
- [x] Check for ambiguity, unsupported claims, and scope creep
- **Status:** complete

### Phase 3: Handoff

- [x] Report document location and request review
- **Status:** complete

### Phase 4: Add open-ended writing and translation practice

- [x] Inspect current writing and translation entry points and cache limits
- [x] Revise the local memory specification and self-review it
- [x] Ask user to review the revised specification
- **Status:** complete

### Phase 5: Implementation planning

- [x] Confirm spec approval and inspect current source/tests
- [x] Write exact interfaces, test-first tasks, and verification commands
- [x] Self-review plan against every spec section and hand off for review
- **Status:** complete

### Phase 6: Implement approved local learning loop

- [x] Task 1: durable learning ledger and isolated tests
- [x] Task 2: persisted reading attempts
- [x] Task 3: safe writing/translation tasks and drafts
- [x] Task 4: grounded DeepSeek feedback
- [x] Task 5: combined progress and one next action
- [x] Task 6: Streamlit and scenario regression
- **Status:** complete

### Phase 7: Diagnose live writing/translation progress report

- [x] Confirm actual archive path and event kinds without exposing draft text
- [x] Identify whether the user's submission used the chat box or draft form
- [ ] Reproduce and fix any confirmed UI routing/display defect
- [ ] Verify live progress and tests; report exact remaining limitation
- **Status:** in_progress

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Learning record is local to the OS user | User chose a per-computer assistant; no Codex account binding or cloud sync |
| Skill packaging follows memory core | Streamlit and Skill must consume the same deterministic service |
| No product code in this phase | Architectural design must be reviewed first |
| Do not auto-import old diagnostic episodes | They have no verified learner identity and may include tests |
| Reading and open-ended practice need separate assessment semantics | KEYS provides objective reading correctness; writing and translation require advisory feedback on user text |
| One local append-only event ledger covers all three sections | Keeps durable drafts, revisions and feedback separate from mixed diagnostic episodes without adding a database |
| Save subjective drafts before calling DeepSeek | API failure must not erase a submitted essay or translation |
| Keep the new work in one sequenced plan | Durable storage, draft submission, feedback and UI depend on shared service interfaces |
| Restore draft versions through `Service.draft_history()` | The UI needs a stable read-only view after refresh; it does not parse ledger files itself |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| Initial planning skill path was wrong | 1 | Read the skill from its resolved package path |
| Git commit unavailable in current sandbox | 1 | Parent `.git` is outside writable roots and Git author identity is unset; leave only the new spec uncommitted |
| Streamlit discovery script could not run | 1 | Existing venv points to a missing WindowsApps Python; read the installed Streamlit 1.61.1 bundled references directly |
| `git diff --stat` was misread as no repository | 1 | Parent Git repository exists but `HEAD` has no commit; command-scoped `safe.directory` is needed under the sandbox account |
