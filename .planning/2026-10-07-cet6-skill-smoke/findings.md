# Findings

- Existing `cet6-tutor` Skill requires exact paper coordinates and the CLI as source of truth.
- Previous `2026-10-05-cet6-codex-skill` plan is complete; this smoke test uses a separate plan without changing `.planning/.active_plan`.
- Official OpenAI Docs recommends outcome and process checks for Skill evaluations.
- CLI `submit` reads a UTF-8 file, saves a draft before invoking the reviewer, then emits `ready`, `pending`, or `feedback_not_saved` with a `draft_id` when saved.
- `history --section translation` reads the configured `EXAM_TUTOR_LEARNING_PATH`; an absolute isolated path avoids the user's real local archive.
- Existing unit tests mock reviewer success and pending cases. A real API review must be reported separately from those mocks.
- Focused CLI tests: 7 passed, 9 deselected, 1 existing deprecation warning.
- Isolated `task 2024 12 1 translation`: `ready`, task text only, `review_scope=full`.
- Isolated `submit`: draft `a811357de9ef4d4681fc82e555033e3a` saved, initial reviewer call returned `pending` due to sandbox `APIConnectionError`.
- `history --section translation` after failure recovered one synthetic draft with `feedback=null`, no warnings.
- Authorized network retry with `review <draft_id>` returned `ready`; feedback included a warning that some quotations could not be verified.
- Final isolated history recovered exactly one draft with saved feedback and zero archive warnings.
