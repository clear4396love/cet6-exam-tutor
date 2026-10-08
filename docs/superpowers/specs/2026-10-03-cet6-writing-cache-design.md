# CET-6 Writing Cache and Retrieval Design

## Goal

Bring the existing CET-6 writing prompts into the exam tutor as cached practice answers with paragraph-by-paragraph explanations, following the established translation workflow. The user can request either a reference essay or its writing rationale from the Streamlit chat.

## Current State

- `parsed_papers/` contains 38 JSON files with a `writing` prompt field.
- None currently has `writing_sample` or `writing_analysis`.
- The locator recognizes `writing`, but `Service._structured_answer` currently reports writing as unsupported.
- Translation answers and explanations are stored in each paper JSON and served read-only; this is the closest existing pattern.
- The user has received three sample essays with paragraph explanations. These are the style baseline for the remaining corpus.

## Scope

Before editing `parsed_papers/`, make a complete recoverable backup of the directory: the parent Git repository currently has no `HEAD` and these JSON files are untracked. This content project is separate from local chat-history UI work.

1. Complete all 38 cached writing entries, including the three sample essays, with:
   - `writing_sample`: a practice reference essay, normally 150–200 words where the exam directions specify that range.
   - `writing_analysis`: Chinese paragraph-by-paragraph rationale covering prompt interpretation, paragraph purpose, argument development, and notable language choices.
   - `writing_needs_review`: boolean gate, false only when the prompt and any mandatory opening/instructions are sufficiently verified; true for unresolved source or transcription doubts.
2. Reuse the original paper PDFs/OCR and cache metadata to verify the prompt, word range, required opening, and chart values where applicable. Preserve every existing JSON field.
3. Add a read-only writing branch to the existing `Service` and brief Streamlit help examples:
   - “作文怎么写” returns the prompt and clearly labelled non-official practice essay.
   - “作文解析/写作思路” additionally returns the cached analysis.
   - Pending-review entries do not show an unverified sample as if it were verified.
4. Add focused tests for corpus coverage, required opening/word-count constraints when applicable, pending-review behavior, and both response modes.

## Content Rules

- The original exam task overrides generic templates. Preserve a required opening sentence exactly when verified; describe key chart trends and use relevant figures when the task asks for chart description.
- Treat the classroom notes as teaching strategies, not official scoring rules. Keep the teacher's stated approach distinct from the assistant's language corrections.
- Do not invent statistics, quotations, authorities, or causal claims. Use plausible examples as examples, not as measured facts.
- Prefer clear, natural English over forced synonym replacement or decorative vocabulary.
- Label every sample as a practice reference, not an official answer. Analysis explains why the sample addresses the task and where a template is optional.

## Data Flow

The existing locator resolves year, month, set, and writing section. The service loads that exact cached JSON, checks `writing_needs_review`, validates that the prompt/sample exist, then returns prompt plus sample. Only explicit explanation requests append `writing_analysis`. Missing papers, fields, or review status use clear fallback responses and never trigger model-generated essay content.

## Alternatives Considered

- **Data-only cache:** less integration work, but the essays would not be accessible through the app. Rejected because the user wants the writing component alongside translations.
- **Generate essays on every request:** avoids bulk cache authoring, but risks inconsistency, fabricated details, and different answers on repeated queries. Rejected in favor of reviewed static cache content.
- **Separate writing database:** unnecessary duplication; rejected in favor of the existing per-paper JSON schema.

## Verification

- All 38 cached writing prompts have the new fields and explicit review status.
- Verified required opening sentences appear exactly at the start of samples; word counts obey the corresponding exam directions.
- Chart-based prompts retain the required graph description and accurate selected values.
- Tests confirm sample-only and explanation modes, pending-review safeguards, and unchanged translation behavior.
- Streamlit help text gives a year/month/set example for writing queries.

## Known Constraint

Some cached `writing_directions` fields are incomplete. The original paper/OCR should be checked for those entries. If the source remains ambiguous, preserve the known prompt, mark the entry for review, and do not invent missing requirements.
