# Findings

- User approved an incremental cache audit plus runtime reading explanation guard; no cache migration or Skill rewrite.
- Previous read-only audit found 38 cached papers, with 31/33/32 containing questions in sections A/B/C respectively; 12 have writing_directions and 21 have ocr_verified.
- Five caches have no A/B/C question data, but their original source scope needs independent verification.
- `retrieval/service.py` currently returns generated B/C explanations after empty/evidence checks without section or KEYS validation.
- `tools/scenario_eval.py` counts B headings offline but does not enforce order or validate C's distinct heading.
- `memory/episode.py` reserves `answer_verified`; `answer_mentioned` and `answer_agrees` describe user-supplied letters and must not be repurposed.
- The project-local `.venv` works; the parent `../.venv` points to a missing WindowsApps interpreter. Baseline: 224 passed, one langchain-community deprecation warning; default system TEMP caused an atexit permission traceback, so later runs should set TEMP/TMP to project `tmp`.
- Original scanned PDF `CET6_2022年6月_第2-3套_真题.pdf` page 1 contains Section A for set 2 and page 5 contains Section C, while cache `2022_6_2.json` lacks both: a genuine cache gap.
- The same source PDF page 9 explicitly says set 3 reading is the same as prior sets and is omitted, so set 3's lack of A/B/C is not a cache defect for this archive.
- Source PDFs for 2022 September sets 2/3 contain writing and translation only and explicitly say their reading is identical to set 1; 2023 March sets 2/3 similarly omit reading (source page 1 and page 4).
- Source PDF for 2021 December set 3 explicitly omits Section A as shared with other sets, but includes Sections B and C; cache coverage matches that source scope.
- Audit manifest has seven source-verified exceptional scopes; the other 31 caches remain explicitly unknown for source scope, even though they contain reading data. Real audit reports 2022-06 set 2 missing A and C and no other verified-scope gaps.
- Runtime guard now shares B/C headings with prompts and rejects missing/reordered/duplicate/empty sections plus explicit answer conflicts. `answer_verified` is restricted to this structural/KEYS check, not evidence truth.
- Full suite after changes: 239 passed, one pre-existing langchain-community deprecation warning, when TEMP/TMP point to project tmp and PYTHONIOENCODING is not forced.
