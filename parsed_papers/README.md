# 已收录题目缓存

此目录跟踪 38 套 `*.json` 缓存，供 Skill 和 Streamlit 在克隆后按年份、月份、套数查题。它们包含真题正文、答案及部分参考内容；OCR 产物和 PDF 不在仓库中。`examples/synthetic_paper.json` 则是虚构的离线演示。发布这些缓存前须确认分发权限。

文件名使用 `<year>_<month>_<exam_set>.json`，例如 `2024_12_1.json`。主要字段按板块可选；缺失板块应视为不可练习，而不是补猜：

- Section A（26–35）：`section_a.practice_text`、`text`、`words`、`questions`；每题 `answer` 及对应单词。
- Section B（36–45）：`paragraphs` 字母映射、`questions` 题号映射；每题 `stem` 和从卷内 KEYS 核对的 `answer`。
- Section C（46–55）：`section_c.passages`，每篇含 `text` 和 `questions`；每题含 `stem`、A–D `options` 及核对后的 `answer`。
- 写作/翻译：`writing`、`writing_directions`、`translation` 等题面字段；参考内容及审核标记是可选的，未明确审核通过时不应主动展示。

格式正确不等于内容可信。解析脚本覆盖有限，扫描件与版式变化可能造成漏题、错位、OCR 噪声或错误 KEYS；请用原始资料逐题核对。项目自带的 `tools/corpus_audit.py` 可辅助检查结构，但不能替代人工核对，也不能生成完整语料。
