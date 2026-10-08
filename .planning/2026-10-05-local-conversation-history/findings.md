# Findings: Local conversation history

## Requirements

- Left sidebar lists historical conversations, supports a new conversation, and restores old ones after refresh.
- From an old chat turn, continuing creates a new branch; original chat and learning records remain untouched.
- Writing/translation originals and reviews move from the long standalone history expander into the unified history navigation.
- Existing draft revisions are linked only by `revision_of`.
- System reference answers and analyses stay hidden until the learner explicitly requests and confirms viewing; a draft submission is not required.
- Reference essays are practice examples, not official answers; missing/unverified cache content must not be presented as available.

## Research Findings

- `streamlit_app.py` stores chat `messages` only in `st.session_state`; `Service` keeps the current question in `LocationTable`. Refresh does not restore either chat messages or location.
- `memory/episode.py` logs diagnostic user queries and state snapshots but not assistant response text; it is not a complete chat archive.
- `memory/learning_record.py` stores local `draft_submitted` and `feedback_ready` events. `Service.draft_history()` already returns draft text, task text, `revision_of`, and feedback.
- `retrieval/draft_practice.py:get_draft_task()` intentionally excludes cached samples from the student view.
- All 38 `parsed_papers/*.json` lack `writing_sample` and `writing_analysis`; `docs/superpowers/specs/2026-10-03-cet6-writing-cache-design.md` is a design, not populated data.
- Translation samples exist for at least `parsed_papers/2024_12_2.json`, subject to existing review gates.
- The local `databases/试卷/` directory contains original PDFs for the cached sets; these are the source for any writing-reference verification.
- `tests/conftest.py` already isolates `EXAM_TUTOR_LEARNING_PATH` to `tmp_path` and asserts the real archive is not created by tests.
- The real learning archive already exists (9,383 bytes), so that existing `if not existed_before` guard does not detect writes to it. Task 0 must hash-check it and the new real chats directory before all feature tests.
- All 38 translation caches have sample and analysis text; 33 have `translation_needs_review is False`. All 38 writing caches have no `writing_sample`, `writing_analysis`, or review marker.
- `tests/test_translation.py` explicitly asserts “翻译呢” after a located paper returns a cached sample; a requirement to restate full coordinates in every chat request would be a breaking change.
- `LocationTable.update()` ignores keys not in `FIELDS`; snapshot type validation remains necessary. `to_dict()` returns only non-null keys, so a restored snapshot need not contain all five field names.
- `tmp/baseline-20261005` is not empty (36 files, including six parsed-paper test fixtures), but it is not a complete recoverable backup of `parsed_papers/`.
- The repo has a parent Git index with an unborn `HEAD`; unrelated deletions appeared in read-only `git diff --stat` and must remain untouched.

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Keep chat archive separate from learning-event archive | Conversations and graded/submitted learning events have different semantics and retention needs. |
| Render legacy drafts from existing event records | Avoid destructive migration and duplicate copies of student writing. |
| Require an explicit reveal action plus confirmation | Prevent accidental exposure while permitting viewing before submission. |
| Scope shared display gate to common cache facts | Old-draft task matching is view-specific; it must not make a valid direct chat query fail. |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Streamlit version-matched discovery fails under Codex sandbox because its chosen `.venv` launcher cannot find its base interpreter. | Continue with local code inspection; do not treat user's interactive `.venv` as broken. |
| Parent Git repository has no `HEAD` and contains extensive untracked files; `.git` is outside writable scope. | Do not attempt a root commit as part of this design-only stage. |

## Resources

- `streamlit_app.py`
- `retrieval/service.py`
- `memory/episode.py`
- `memory/learning_record.py`
- `retrieval/draft_practice.py`
- `docs/superpowers/specs/2026-10-03-cet6-writing-cache-design.md`
- `docs/superpowers/specs/2026-10-05-local-history-and-reference-reveal-design.md`
- `docs/superpowers/plans/2026-10-05-local-history-and-reference-reveal.md`

## Visual Findings

- User's DeepSeek screenshot: a left conversation list with a new-chat action and dated entries.
- User's app screenshot: historical drafts/reviews appear as a long standalone expander, making navigation cumbersome.
