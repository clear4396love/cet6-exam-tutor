# Findings: Local Learning Memory Design

## Requirements

- Persist real answer submissions across app restarts on one person's computer.
- Compute weaknesses in code, then give one actionable next step.
- Keep learning data local to the current OS user; no account binding or cloud sync.
- Future Codex Skill calls the same Python core rather than reimplementing grading.
- Do not merge ordinary chat traces or test events into learning progress.

## Research Findings

- `memory/episode.py` appends mixed session events to project-root `episodes/<session_id>.jsonl`.
- `retrieval/service.py` currently computes progress only from `self.episode.lines()`.
- `retrieval/practice.py` already has pure `summarize_attempts(events)` with 0–2, 3–7, and 8+ tiers.
- `streamlit_app.py` stores `Service` in `st.session_state` and tells users refresh will not restore progress.
- Existing practice design explicitly deferred cross-session memory; this new design extends it.
- Git parent repository exists but `HEAD` is unborn (no commit yet). The sandbox account triggers Git's dubious-ownership guard; use command-scoped `-c safe.directory=...` for inspection, and do not assume a clean worktree or create an initial commit as part of this plan.
- `Episode.record()` swallows write failures and still returns a row; durable learning storage must expose save failure instead of claiming history was saved.
- Existing `summarize_attempts()` groups by five question ranges and returns a tier, but its `repeated_misses` output collapses different papers to bare question numbers; cross-session display needs full paper identity.
- Existing feedback validates a recorded attempt against cached KEYS before model explanation; the new history path must not bypass that boundary.
- Existing tests cover attempted submissions, ungradable rejection, unchanged chat location, progress tiers, and model fallback.
- User requires actual typed essay and translation submissions, with feedback focused on grammar, tense, word choice, and overall flow.
- Translation has a cached source, sample and analysis, but `_translation_answer` is read-only; there is no user-draft submission or feedback path.
- Writing prompts are cached, but `Service._structured_answer` still treats writing as unsupported. The separate writing cache/Streamlit work exists as an unexecuted plan; the sampled cache had no `writing_sample` or `writing_analysis`.
- Some `writing_directions` values are OCR-damaged or contain unrelated content. Essay task-compliance feedback must use only verified prompt information; never invent missing directions.
- The current Streamlit practice expander only exposes question numbers 26–55 and single-letter submissions.
- Streamlit's installed 1.61.1 documentation recommends native forms and `st.session_state` only for temporary UI state, not durable learning records.
- `summarize_attempts()` already accepts event sequences with `stage`, `attempt_answer`, `attempt_correct`, and `filters`; durable reading events can retain these fields to reuse it.
- Existing tests assert `repeated_misses == [36]`; a new full-coordinate pending-miss field should not silently change this compatibility shape.
- `tools/scenario_eval.py::run_practice_case()` instantiates `Service` without a learning path and currently depends on session progress; its practice cases need a temporary ledger injected to avoid writing to the real user's home.
- Existing `tests/test_practice.py` and Streamlit `FakePracticeService` assume in-session progress; the implementation plan must migrate those fixtures deliberately.
- The approved spec can be implemented in six dependent tasks: durable ledger, reading persistence, draft submission, grounded model feedback, three-section summary, and Streamlit/scenario integration.
- The plan keeps current `repeated_misses: list[int]` compatible, while the new next-action selector uses full paper coordinates.
- The plan avoids relying on live DeepSeek in unit tests and names the broken current `.venv` as an execution preflight, not a product defect.
- Cache audit: 38 paper JSON files; 26 have no `writing_directions`, 12 do. Three directions explicitly mention chart/graph, but their image material is not safely available to the practice interface. Only `2020_7_1` and `2020_9_1` directions were manually checked as clean for the initial whitelist.
- The old `.planning/.active_plan` pointed at the October 2 video task; the current learning-memory plan is now active.
- Live screenshot (2026-10-05): progress displays reading 1, writing 0, translation 0. The caption renders `C:\Users\86195\.exam-tutor` without the backslash before the leading dot, likely because `st.caption` interprets Markdown escapes; do not infer the actual filesystem path from rendered text.
- Read-only archive check confirms `C:\Users\86195\.exam-tutor\learning_events.jsonl` exists (294 bytes, last write 18:32:27) with exactly one `reading_attempt` and no `draft_submitted`/`feedback_ready`. The visually similar `C:\Users\86195.exam-tutor\learning_events.jsonl` does not exist.
- Latest diagnostic episode is also one reading attempt; no evidence yet that the user submitted through the dedicated draft form. Need user's answer about which input box they used before attributing root cause.
- User confirmed use of the dedicated `你的原稿` form, not the chat box. Real-Service AppTest reproduced translation select → load → text entry → submit against a temporary ledger: no exception, `draft_submitted` persisted, translation progress became 1. Thus the code path works in the test runner but the live browser's form action/result remains unobserved. Requested a screenshot of the expanded draft panel after submission, with draft content hidden.

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Separate learning record from diagnostics | Project-root episodes include non-attempt events and should not be treated as an identity scope |
| Reuse current grading and statistics | KEYS and pure aggregate function already exist |
| Persist only normalized attempt events | Existing `summarize_attempts()` can consume the same subset shape without a second statistics implementation |
| Report write/read failures | A learning record cannot claim durability when the file operation fails |
| Preserve user drafts and feedback as linked event types | Allows model retry without double-counting a submission and keeps revision history |
| No official numeric score for writing/translation | Model quality judgments are advisory; objective progress remains reading KEYS and practice counts |

## Resources

- `docs/superpowers/specs/2026-10-03-cet6-session-practice-design.md`
- `memory/episode.py`
- `retrieval/service.py`
- `retrieval/practice.py`
- `streamlit_app.py`
- `docs/superpowers/specs/2026-10-05-cet6-local-learning-memory-design.md`
