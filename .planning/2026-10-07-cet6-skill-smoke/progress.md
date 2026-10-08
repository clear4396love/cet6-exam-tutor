# Progress

- Started isolated smoke test on 2026-10-07. No production data touched.
- Inspected CLI, Service, and tests. Chose isolated `tmp/cet6-skill-smoke-20261007/learning_events.jsonl` for real CLI run.
- Focused tests 7 passed. Real CLI saved synthetic draft before API connection failure; isolated history recovered it.
- With authorized network access, `review` returned ready; subsequent history recovered feedback. Warning: some feedback quotations could not be verified.
- Verified isolated test folder contained only synthetic input and JSONL archive, then removed both and the empty folder. Every real CLI invocation set an absolute test-only `EXAM_TUTOR_LEARNING_PATH`; the focused test fixture hash-checks the real archive for no modification but does not expose its contents. No real learning archive was edited or cleared.
