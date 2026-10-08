# CET-6 Writing Cache and Streamlit Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all cached CET-6 writing prompts available in the Streamlit tutor with reviewed practice essays and paragraph-by-paragraph explanations.

**Architecture:** Preserve the per-paper JSON cache and existing locator. Add a cache-only writing response path to `Service`, populate and verify the writing fields against source papers, then update the Streamlit help/capability text. No runtime essay generation or new persistence layer.

**Tech Stack:** Python, Streamlit, JSON, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-cet6-writing-cache-design.md`

## Global Constraints

- Treat every sample as a practice reference, not an official answer.
- Preserve verified required opening sentences and the exam's word limit.
- Do not invent statistics, quotations, authorities, or causal claims.
- Store writing samples and analysis in the existing per-paper JSON files; preserve all existing fields.
- Pending-review writing must not be shown as verified content.
- Queries are cache-only and must never generate an essay at runtime.
- Add no dependencies or separate database.

## Review Focus

- Missing or incomplete year/month/set must ask for the missing paper details and leave no stale section state; test through `Service.process`.
- Missing paper or missing writing fields must return a clear cache-miss response rather than call generation; test with cached-only loader patched.
- `writing_needs_review` missing, true, or a wrong type must not expose a sample; test all pending variants.
- “作文怎么写” and “作文解析/写作思路” must choose sample-only vs sample-plus-analysis consistently; test the response contents and trace stage.
- Writing integration must not change translation sample/analysis behavior; retain existing translation tests as regression checks.

---

### Task 1: Add cache-only writing responses to the service

**Files:**
- Modify: `retrieval/service.py`
- Test: `tests/test_writing.py`

**Interfaces:**
- Consumes: `load_set_cached_only(year, month, exam_set)`, existing locator fields, and existing `wants_explanation` helper.
- Produces: `Service._writing_answer(loc: dict, user_message: str) -> str`, selected by `_structured_answer` when `section == "writing"`.

- [ ] **Step 1: Write failing service tests** for complete vs missing paper, pending review, sample-only query, analysis query, and no runtime generation.
- [ ] **Step 2: Run `pytest tests/test_writing.py -q`** and confirm the tests fail because the writing branch is not implemented.
- [ ] **Step 3: Implement the smallest cache-only branch** using `writing`, `writing_sample`, `writing_analysis`, and `writing_needs_review`; mark each response in the existing trace and never fall back to an LLM.
- [ ] **Step 4: Run `pytest tests/test_writing.py tests/test_translation.py -q`** and confirm both writing behavior and translation regression tests pass.

### Task 2: Populate and source-check cached writing entries

**Files:**
- Modify: `parsed_papers/*.json` (the existing 38 paper records)
- Test: `tests/test_writing.py`

**Interfaces:**
- Consumes: each record's `writing`, `writing_directions`, related source PDF/OCR, and the three previously reviewed sample essays in the conversation.
- Produces: nonempty `writing_sample`, nonempty Chinese `writing_analysis`, and explicit boolean `writing_needs_review` in every writing record.

- [ ] **Step 1: Add corpus tests** asserting all 38 records have the three fields, and verified samples meet source-specific opening/word-count constraints.
- [ ] **Step 2: Run the corpus tests** and confirm they fail on the current uncached writing fields.
- [ ] **Step 3: Verify each prompt and its directions against available source material**, then add a clear, task-responsive practice essay and paragraph-by-paragraph explanation. Use `writing_needs_review: true` wherever original instructions remain uncertain; include the three previously drafted prompts in the matching records.
- [ ] **Step 4: Run `pytest tests/test_writing.py tests/test_corpus_integrity.py -q`** and confirm every cache record is structurally valid and the source-verified constraints pass.

### Task 3: Expose writing support in Streamlit

**Files:**
- Modify: `streamlit_app.py`
- Test: `tests/test_streamlit_app.py`

**Interfaces:**
- Consumes: the `Service.process` writing response from Task 1.
- Produces: accurate capability text and concise examples for full writing queries and explanation follow-ups.

- [ ] **Step 1: Extend the AppTest assertions** to require writing support and examples for `2024年12月第1套作文怎么写` and `作文解析`.
- [ ] **Step 2: Run `pytest tests/test_streamlit_app.py -q`** and confirm the new expectations fail.
- [ ] **Step 3: Update only the caption and existing help expander**; clarify that samples are non-official practice answers and that pending-review content is withheld.
- [ ] **Step 4: Run `pytest tests/test_streamlit_app.py -q`** and confirm the UI renders and retains the existing chat behavior.

### Task 4: Run focused regression verification

**Files:**
- Test: `tests/test_writing.py`, `tests/test_translation.py`, `tests/test_streamlit_app.py`

- [ ] **Step 1: Run** `pytest tests/test_writing.py tests/test_translation.py tests/test_streamlit_app.py -q`.
- [ ] **Step 2: Run** `pytest tests/test_corpus_integrity.py -q`.
- [ ] **Step 3: Inspect the final diff** and verify it contains only writing cache fields, the service/UI changes, focused tests, and this plan; preserve all pre-existing user changes.

