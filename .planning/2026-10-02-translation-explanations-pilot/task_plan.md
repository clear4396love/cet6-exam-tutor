# Task Plan: 38 篇翻译逐句解析

## Goal
为 `translation_audit.md` 的 38 篇缓存翻译补齐逐句中文→英文思路，并把获用户确认的解析同步到 `parsed_papers/*.json`。保留现有试译、题库原文及待核标记；不改变问答显示。

## Selection
`Get-Random -Count 4 -SetSeed 20261002` 选出：`2023_3_2` 郑和、`2021_6_2` 青海、`2025_12_1` 尊老、`2020_12_2` 港珠澳大桥。

## Next Step
翻译解析请求已接入缓存；交付实现范围与可用的检查结果。

## Current Phase
Phase 11 complete

## Phases

### Phase 1: Inspect sources and drafts
- [x] Read four original Chinese passages and existing trial translations
- [x] Note OCR/fact uncertainties without silently changing content
- **Status:** complete

### Phase 2: Add explanations
- [x] Add sentence-by-sentence explanations under the four selected entries
- [x] Explain main clause, logic, grammar choice, and information retention
- **Status:** complete

### Phase 3: Verify and deliver
- [x] Confirm exactly four entries changed and originals preserved
- [x] Check explanations align with each English sentence and source
- [x] Deliver sample links for user review
- **Status:** complete

### Phase 4: Complete 2020 (5 remaining)
- [x] Inspect Chinese originals and existing English
- [x] Add aligned explanations; flag source/translation uncertainties
- **Status:** complete

### Phase 5: Complete 2021 (5 remaining)
- [x] Inspect and explain all five
- **Status:** complete

### Phase 6: Complete 2022 (9 remaining)
- [x] Inspect and explain all nine
- **Status:** complete

### Phase 7: Complete 2023–2024 (10 remaining)
- [x] Inspect and explain four 2023 and six 2024 entries
- **Status:** complete

### Phase 8: Complete 2025 (5 remaining)
- [x] Inspect and explain all five
- **Status:** complete

### Phase 9: Final verification and delivery
- [x] Confirm 38 headings each have one explanation section
- [x] Confirm every original trial paragraph remains unchanged
- [x] Check sentence mapping and markdown structure
- [x] Deliver link and note unresolved OCR/fact uncertainties
- **Status:** complete

### Phase 10: Cache the approved explanations
- [x] Add a focused cache-integrity test and observe expected failure
- [x] Add `translation_analysis` to all 38 JSON caches without changing existing fields
- [x] Verify all tests and 38 source-to-cache mappings
- **Status:** complete

### Phase 11: Expose cached translation explanations on request
- [x] Use existing explanation intent and translation cache
- [x] Return the detailed explanation for explicit explanation/strategy requests
- [x] Keep ordinary sample response and pending-review guard intact
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|---|---|
| Reproducible random seed 20261002 | User requested a random four; repeatable selection supports review. |
| Add under existing `translation_audit.md` entries | Keeps each explanation adjacent to its trial translation; other entries stay untouched. |
| Keep the four approved samples and expand in year batches | User approved the pilot format; batching helps verify 34 additions without silently rewriting source/English. |
| Store explanation text only in `translation_analysis` | User approved cache-only scope; existing student answer gate and display remain unchanged. |

## Errors Encountered
| Error | Resolution |
|---|---|
| Five-essay source read exceeded output budget | Read in groups of two or three; no source or draft lost. |
| Git refused repository ownership under sandbox identity | Used section-by-section source-trial and heading checks; source document is untracked, so no tracked-file diff was available. |
| Initial planning skill path was stale | Found the installed version under `planning-with-files/planning-with-files/3.22.0/skills/`; read the full instructions there. |
| `python` command unavailable in sandbox | Used the project's `.venv/Scripts/python.exe` instead. |
| First cache-tail check used parent cwd | Re-ran from `exam-tutor`; no files were changed by the failed read. |
| Default pytest temp directory on C: made an unrelated OCR test fail | Read stack and source: `os.path.relpath` crossed from C: tmp path to D: cwd. Re-ran suite with a fresh workspace-local `--basetemp`; all 93 passed. |
| First translation-display patch had stale context | Re-read exact call site and applied the smaller patch against current source. |
| In-memory syntax check could not start | The workspace `.venv` launcher points to a missing uv-managed Python 3.11 executable; stopped without reinstalling or changing the environment. |

