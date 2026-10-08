# Findings & Decisions

## 本次抽样

- 38 套 JSON 中，31 套的 A/B/C 三节在结构上都有 10 题可用；再排除 2020_7_1 的 A 答案源冲突和已知原卷无答案页的 2020_9_2、2021_6_1/2/3、2022_9_1，候选为 25 套。
- 使用 Python `random.Random("20260929-reading-seven")`，按卷名排序后 `sample(eligible, 7)`，题型顺序 A/B/C/A/B/C/C，随后由同一 RNG 在题号区间取题。
- 抽中：2025_6_3 A28=F；2022_12_1 B36=E；2020_12_1 C52=A；2021_12_1 A27=H；2022_6_1 B42=C；2023_6_2 C52=D；2020_12_2 C54=B。
- 每套新建 Service 和临时 Episode，会话互不继承；真实意图模型与讲解模型均调用。Section A 仅核对查答案，B/C 核对 KEYS、stage、八节标题。

## 实测结果

| 卷 | 板块/题 | KEYS | 入口与格式 | 复核 |
|---|---|---|---|---|
| 2025_6_3 | A28 | F / equity | 正确 | 无异常 |
| 2022_12_1 | B36 | E | explanation、8 节、答案标题 E | 无异常 |
| 2020_12_1 | C52 | A | explanation、8 节、答案标题 A | 引文锚点在缓存原文 |
| 2021_12_1 | A27 | H / noteworthy | 正确 | 无异常 |
| 2022_6_1 | B42 | C | explanation、8 节、答案标题 C | **质量问题**：缓存 C 段漏掉 Every week...，模型称 weekly visits 无依据，但仍解释为选 C |
| 2023_6_2 | C52 | D | explanation、8 节、答案标题 D | 引文锚点在缓存原文 |
| 2020_12_2 | C54 | B | explanation、8 节、答案标题 B | 引文锚点在缓存原文 |

- 七次 intent 均 NEW_QUESTION、state_op 均 RESET、trace.error 均为 null；2 次 Section A 答案文本完全匹配，5 次讲解标题均为 8/8 且第七节字母与 KEYS 一致。7 次耗时分别为 2876、4894、5115、849、4761、4507、4931 ms。
- 2022_6_1 的 `parsed_papers/2022_6_1.json` C 段长 701 字符，缺掉 “Every week, TD's medical operators travel to the islands by boat...” 一整段关键证据。`databases/ocr_pdfs/CET6_2022年6月_第1套_真题_zhipu/doc_004.md` 与对应 Paddle 文本均包含该句，因此不是本轮 OCR 重扫问题；是正式 JSON 的段落拼接/缓存问题。
- 还存在证据长度上限：`retrieval/structured.py` 将每段截为 500 字符，原始 C 段中 Every week 约在第 412 字符，makeshift 约在第 722 字符；即便修复缓存，也要重新检查本题讲解能否同时看到“每周”和“临时中心”。本轮未改任何正式缓存或产品代码。

## Requirements
-

## Research Findings
-

## Technical Decisions
| Decision | Rationale |
|----------|-----------|

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
-
