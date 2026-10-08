---
name: cet6-tutor
description: Use when a user asks this exam-tutor project about a cached CET-6 (英语六级) reading question 26-55, or wants to practice, submit, revise, review, or revisit local writing and translation drafts.
---

# CET-6 tutor

Use this repository's Python service as the source of truth. The Skill is an entrypoint, not a second answer engine. Work from the `exam-tutor` directory that contains `retrieval/service.py` and `tools/cet6_skill.py`.

In this Windows checkout, invoke the existing project interpreter as `& .\.venv\Scripts\python.exe -m tools.cet6_skill ...` from that directory; do not assume `python` is on `PATH`. On a Unix checkout use `.venv/bin/python` instead. If the project interpreter is unavailable, check another installed interpreter and its project dependencies before using it; do not install Python or packages automatically.

## Choose the path

| Request | Action |
| --- | --- |
| Check or explain a cached reading question 26-55 | Require year, month, set, and question number. Run `& .\.venv\Scripts\python.exe -m tools.cet6_skill ask '<full question>'`. Questions 26-35 currently support answer lookup; 36-55 also support explanations. |
| Get a writing/translation task | Require year, month, and set. Run `& .\.venv\Scripts\python.exe -m tools.cet6_skill task YEAR MONTH SET writing|translation`; show only `task_text` and any scope limitation. `unavailable` means this cache cannot support that practice task. |
| Submit a draft in Codex | Save the user's exact draft to one temporary UTF-8 file, then run `& .\.venv\Scripts\python.exe -m tools.cet6_skill submit YEAR MONTH SET writing|translation --text-file PATH`. Report the returned `draft_id` and feedback. If status is `pending` or `feedback_not_saved`, say the draft was saved but the feedback needs retry; run `review DRAFT_ID` only when requested. Remove only the temporary input file after confirming the draft was saved. |
| Revise a saved draft | Use the same `submit` command with `--revision-of DRAFT_ID` of the prior version. Do not infer a parent ID from a different paper or section. |
| Revisit local drafts or retry feedback | Run `history [--section writing|translation]` only for an explicit history request, or `review DRAFT_ID` for explicit retry. Relay actual stored text/feedback as requested; never invent missing feedback. |
| Ask about local writing/translation progress | Run `progress`; report only its counts, warnings, and next steps. |
| Ask for a system reference essay/translation | First ask whether the user wants to reveal it. Only after explicit confirmation run `reference YEAR MONTH SET writing|translation --confirm`. Respect `pending_review`, `missing`, and task mismatch; do not substitute an invented reference. |

In a follow-up within the **same** Codex chat, reconstruct missing coordinates only from explicit earlier messages in that chat. A new Codex chat has no previous chat location: ask for missing coordinates. Do not infer a paper or answer from the student's wording.

## Evidence and privacy

- The answer letter comes only from the service's cached KEYS. The Skill's `ask` mode is cache-only: it must not parse PDFs or create caches. If the service reports a missing, duplicate, unsupported, or uncertain paper, preserve that limitation; do not fill it with general knowledge or an invented answer.
- The `ask` path may use DeepSeek for intent and explanation wording, but its answer selection remains in the existing Python service. Do not bypass that service by asking the model to decide a letter.
- `progress` reads the configured local learning record. `status: no_archive` means there is no record at the resolved path, **not** that a user's lifetime practice count is zero. `status: partial` means report `history_warnings` and avoid treating the counts as complete.
- Do not read or paste raw draft text from `learning_events.jsonl` when the user only requests progress. Never delete or reset the learning record for a Skill query.
- The draft command saves before calling DeepSeek for qualitative feedback. Tell the student their submitted text is sent to the configured model for review. For writing with `review_scope: language_only`, assess grammar, tense, word choice, and coherence, not task compliance or a predicted score. An AI review is not an official CET-6 grade.
- A Codex chat can be reopened for conversation context, but saved draft IDs and feedback come from the local learning record. In a new chat, use `history` when the user asks to resume a draft; do not assume a version ID from remembered conversation.
- This repository Skill does not use Codex account identity, MCP, or the Streamlit chat archive. Local progress persists across chats through the existing record file; conversational context does not.

If the project interpreter is broken and no working installed interpreter can import the dependencies, ask for a working interpreter path. When passing a user question through PowerShell, single-quote the argument and escape embedded single quotes as doubled quotes so the shell cannot evaluate user text. For a draft, pass a file path rather than interpolating student text into a shell command.

Example: `$cet6-tutor 2024年12月第1套第43题为什么不选A` → run the `ask` command with that complete question, then relay the service's answer and evidence without changing its answer letter.
