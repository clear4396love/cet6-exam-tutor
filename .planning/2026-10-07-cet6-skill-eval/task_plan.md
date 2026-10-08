# CET-6 Skill evaluation

Goal: add repeatable Skill evaluations without changing reading answer selection or real learning records. Only tighten draft feedback scope when a real synthetic run demonstrates a violation.

## Phases
- [x] Inspect existing CLI, Skill contract, scenario harness and Codex trace format.
- [x] Add case data and minimal trace scoring with red/green tests.
- [x] Run deterministic checks and a bounded real-agent baseline if available; report separate rates.
- [x] Diagnose the 180-second implicit-reading timeout by comparing direct CLI, Codex trace, and environment boundaries.
- [x] Make only a root-cause-backed fix or observability change, verify regression tests, and rerun a bounded baseline.
- [x] Run the nine remaining real-agent Skill cases with isolated local data; distinguish completed behavior failures from transport/timeouts.
- [x] Fix only reproducible evaluation defects, rerun affected cases, and report the observed trace score separately from Python tests.
- [x] Extend the evaluator with isolated, writable multi-turn draft scenarios and deterministic archive checks (test-first).
- [x] Run a bounded real Codex draft flow: submit, revise in the same chat, and recover from a fresh chat; classify provider interruptions separately.
- [x] Verify failure/retry behavior and qualitative feedback if available, rerun the full Python suite, and document exact coverage limits.
- [x] Add a separate synthetic writing scenario with `language_only` scope and cross-chat history checks.
- [x] Catch and fix a grade-like feedback label with prompt guidance, fail-closed validation, and a persisted-feedback evaluation check.
- [x] Recheck the revised writing feedback and fresh-chat history using isolated synthetic records.

## Next Step
- Evaluation work is complete. Further coverage can add other synthetic writing topics; do not generalize the one essay's feedback result into an accuracy claim.

## Safety
- No test writes to the real learning archive or chats.
- Do not count Python unit tests as proof that Codex followed the Skill.
- Do not alter answer selection. Feedback-scope changes require a reproduced synthetic Skill violation and a regression test.
