# Findings

- `translation_audit.md` contains 38 cache translations, grouped by year, with one trial English paragraph and a short method/reminder line per entry.
- Four selected IDs: `2023_3_2`, `2021_6_2`, `2025_12_1`, `2020_12_2`.
- All four `translation_needs_review` values are `false`. Source wording and existing `translation_sample` were read from `parsed_papers/<id>.json` and match the trial English in `translation_audit.md`.
- Bridge source provides `Hong Kong Zhuhai-Macau Bridge`, while the trial uses `Macao`; explanation should note to follow the exam's supplied spelling. The trial also compresses `跨度巨大` into `enormous`, without explicitly naming the span.
- Qinghai trial compresses `地大物博` to abundant resources and gives the English as one paragraph although the source has two paragraphs. Keep the source's topic shift clear in explanation.
- Respect-for-elders trial compresses `广泛传承` to `remains strong` and `有力保障` to `protect`; explain the choice without pretending every modifier was literally rendered.
- Follow-up scope (user approved): copy each essay's numbered `#### 逐句解析` content into `translation_analysis` in its `parsed_papers/<id>.json`; do not alter `retrieval/service.py` or the pending-review gate.
- Each cache currently has `translation`, `translation_sample`, and `translation_needs_review`; no `translation_analysis`. Existing JSON is UTF-8 with two-space indentation. `load_set_cached_only` returns JSON unchanged; the service uses only source/sample and blocks pending entries.
- Translation answers already flow through `Service._structured_answer` into Streamlit Markdown rendering. The existing `wants_explanation` recognizes `解析`/`解释`; local translation keywords add `思路`/`写法`/`说明`/`讲解`/`方法`, so no new intent route or UI widget is needed.
