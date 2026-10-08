# Findings & Decisions

## Requirements
- 排除重复卷：2022_6_3、2022_9_2、2022_9_3、2023_3_2、2023_3_3。
- 遇到没有答案页的卷子直接跳过。
- 本阶段再验证 3 套 Section B，不做 Section A/C。
- 不覆盖 parsed_papers；输出放在 eval/ocr_spike。
- Section A 本轮固定随机抽 3 套；重复卷和无答案卷继续跳过，仍不进入 Section C。
- Phase 10 用户同意比较 2022_12_3、2023_3_1、2025_12_2 的智谱 OCR 与 Paddle；新结果只能落到各自 `_zhipu` 缓存，不能覆盖 Paddle 或正式题库。

### Phase 10 预检（2026-09-29）
- 三套对应 PDF 均存在；Paddle 缓存完整：2022_12_3 为 8/8 页、2023_3_1 为 10/10 页、2025_12_2 为 8/8 页。
- 三个目标 `_zhipu` 缓存目录目前均不存在，因此不存在覆盖旧智谱缓存的风险。
- 项目 `.venv` 可运行，`.env` 可读取且 `Zhipu_OCR_TOKEN` 已配置；但当前项目解释器 `importlib.util.find_spec('zai')` 为 False，智谱 SDK 未安装。
- 父级 `.venv` 与已知 LocalCache Python 均无法启动（分别指向不存在的 Python 与 uv trampoline 缺失），不能作为现成 SDK 环境。
- 因 SDK 缺失曾暂停 OCR；用户随后授权仅在项目 `.venv` 安装 SDK。安装 `zai-sdk==0.2.3` 后，`reading/zhipuocr.py` 可导入，且客户端、`layout_parsing.create` 接口均可用。`requirements.txt` 未改；现可继续用户批准的三卷 OCR。
- 首轮同解析器对比已完成 2022_12_3、2023_3_1：两种 OCR 的 A/B/C 均解析出 10 题且答案串与正式题库完全一致。清洗文本逐页 `SequenceMatcher` 平均相似度分别为 0.9423、0.9360（布局变化使该指标不能单独当准确率）。处理 2025_12_2 时，内联路径字符串误写“真題”，命中 Paddle `pages()` 的缺文件保护并在上传前失败；未触发上传，修正为真实文件名后只重跑该卷。
- 三套 A/B/C 的解析器输出已进一步逐字段对照：所有卷的答案串在 Paddle / 智谱 / `parsed_papers` 三方一致；A 的 15 个词条逐项一致，10 题答案词一致；B 的 10 道题干和答案一致、段落键集合一致。B 段落逐字一致数分别为 6/16、10/13、12/17，但归一空白后的相似度均 ≥0.991。C 均为 2 篇、10 题、答案相同；2023_3_1 题干/选项/答案结构完全相同。2022_12_3 仅两处轻微差异（题末句号、直引号/弯引号）；2025_12_2 仅 54 题题干一处词差：Paddle=`advice given`，智谱=`advice giver`，答案与选项一致；正式缓存核对后确认智谱文本一致。
- 已对照正式缓存核实上述差异：2025_12_2 第 54 题正式题干为 “How is the advice giver likely to react to the rejection of their advice?”，因此该处智谱与正式缓存一致、Paddle 少识一个字母；2022_12_3 的差异只是句号和弯引号，不构成实质准确性差异。
- 最终重新从三份正式 JSON 逐项读取答案串确认：2022_12_3 A/B/C=`KALBNMIFJC`/`ELAMDHBOKN`/`ABCBDBAADC`；2023_3_1=`KGLHBJAIND`/`DGCEHKFMBJ`/`ACABCADBCD`；2025_12_2=`IBMCKADFJO`/`FKJEMIOCNH`/`ABCBCDBDAC`。与两种 OCR 的同解析器输出均一致。
- 清洗后逐页 OCR 全文相似度均值（Paddle 对智谱）为：2022_12_3 0.9423、2023_3_1 0.9360、2025_12_2 0.8973；最小单页相似度分别 0.6644、0.5171、0.3318。较低值集中在首页/KEYS 表格页或题页布局差异，不能直接等价成准确率；A/B/C 实际字段一致率高得多。

## Research Findings
- 首轮 2020_7_1：PaddleOCR-VL-1.6 得到 A-M 13 段、36-45 十题、答案 CJBAKEMHDL。
- 实际段标为 [A]，答案格式为【36-40】CJBAK；解析器已按真实格式做最小扩展。
- 2021_6_2 的 PDF 没有答案页，因此不能作为完整 OCR 样本。
- 固定顺序候选 2021_6_3 没有答案页，跳过。
- 固定顺序候选 2022_9_1 没有答案页，跳过。
- 2023_6_3 有完整 KEYS，但 Paddle 输出为 HTML 表格；段落 A-N 和题目 36-45 已完整，旧 parse_keys 尚不能读取表格答案。
- 2023_6_3 修复后验证通过：A-N 14 段、10 题、答案 GDJHBICLEN。
- 2024_12_2 新 OCR 验证通过：A-N 14 段、10 题、答案 EKGBHMFNDJ。
- 2024_12_1 新 OCR 验证通过：A-O 15 段、10 题、答案 FCGJHODIEK。
- 2024_12_1 的 extractProgress 长时间停在 6/9，之后正常 done；进度只用于展示，不能作为失败依据。
- 抽查页位：2023_6_3 的 Section B/第36题在 doc_003、KEYS 在 doc_007；2024_12_2 在 doc_004/doc_007；2024_12_1 在 doc_004/doc_008。
- 原 PDF 视觉抽查与 JSON 完全一致：2023_6_3 为 GDJHBICLEN，2024_12_2 为 EKGBHMFNDJ，2024_12_1 为 FCGJHODIEK。
- 三套抽查页都能看到 Section B 末段、36-45 题以及随后开始的 Section C，说明大板块边界没有切错。
- 自动复核确认三套均为 10 题，且每道答案字母都能在对应 paragraphs 中找到正文。
- 全量测试为 52 passed, 1 warning；唯一警告是既有的 langchain-community 弃用提醒。
- 定点复核：两套都已有 PaddleOCR 缓存。2020_12_2 的 Section B、36-45 题和 HTML KEYS 都存在，答案行为 EICKDGAFIB；2021_6_3 有 Section B 和 36-45 题，但缓存与 PDF 均无 KEYS，按既定规则跳过完整结构化。
- 不需要新增产品代码：直接复用 `paddle_ocr.pages()`、`paragraph_matching.extract_reading()` 和 `parse_keys()` 即可生成与前几套相同形状的试验 JSON。
- 实际解析结果：2020_12_2 有 A-K 11 段、36-45 十题、答案 EICKDGAFIB，题目/答案/答案段落均无缺失；2021_6_3 有 A-L 12 段和十道题，但 36-45 十个答案全部缺失，因此不生成完整试验 JSON。
- 原 PDF 视觉核对：2020_12_2 第 11 页 KEYS 的 36-45 明确为 E I C K D G A F I B，与解析结果完全一致；第 6 页能看到 G-K 段及 36-38 题，板块定位正确。
- 2020_12_2 第 7 页包含 39-45 题，随后紧接 Section C；36-45 的 Section B 结束边界完整。
- 2021_6_3 原 PDF 只有 6 页，末页在第 51-55 题后直接进入翻译并结束，没有答案页；跳过不是解析器漏读。
- 定点复核完成：2020_12_2 独立 JSON 已生成；2021_6_3 保持 `skipped_no_answers` 且没有半成品 JSON；全量测试仍为 52 passed, 1 warning。
- Section A 旧解析器只认 `A)` 词库标记和 `_26_` 形式空位，且 `save()` 会写正式 `parsed_papers`；本轮不调用 `save()`，先用 PaddleOCR 页面和纯解析方法输出独立试验结果。
- Section A 固定随机种子为 `20260924-section-a`；候选顺序开头是 2022_9_1、2020_7_1、2020_9_2、2021_12_1……，遇到缺答案继续向后取。
- Section A 失败可稳定复现：5 套缓存都能正确切到 Section A，Directions 标记也存在，但旧空位正则命中 0 次，因此失败点在小结构解析，不在大板块切分。
- 根因 1：Paddle 实际输出空位为 LaTeX `\\underline{26}`，旧正则只认 `_26_`。
- 根因 2：新卷词库是 HTML 表格，单元格内容为 `A. affect`；旧解析只认纯文本 `A) affect`。
- 根因 3：共享 `parse_keys()` 的 HTML 表格路径只取 36-45，Section A 需要 26-35；即使正文修好，新卷答案仍会为空。
- TDD 验证：3 条新测试先得到 3 failed，最小修改后 Section A/Section B 定向测试 7 passed；修复只覆盖真实出现的 LaTeX 空位、`A)`/`A.` 单词标签和 HTML 答案 26-45。
- 修复后真实缓存结果：2022_9_1 与 2020_9_2 的正文/词库/10 个空位都能解析，但无答案而跳过；2020_7_1 完整答案 GEMKFBLDOA；2021_12_1 完整答案 BHALJMCEDO；两套均为 15 个词、10 个空位且答案词存在。
- 随机顺序下第三个待判定候选是尚无 Paddle 缓存的 2025_12_2；不能直接越过它采用后面的 2022_6_1。
- 2025_12_2 原 PDF 共 8 页，第 8 页包含 KEYS；PaddleOCR-VL-1.6 已完成 8 页解析并落缓存。
- 2025_12_2 Section A 解析通过：15 个候选词、10 个空位、答案 IBMCKADFJO，所有答案字母都有对应单词。
- 三套随机成功样本的独立 JSON 已生成并重新读取校验：2020_7_1（GEMKFBLDOA）、2021_12_1（BHALJMCEDO）、2025_12_2（IBMCKADFJO）。
- 收尾复核发现 `section_a.text` 尾部混入词库 HTML（`<table …><tr><td …>`）：正文截到 `choice[0].start()`，而 HTML 词库首个选项起点在 `<td …>` 之后。先加 `assert "<table" not in result["text"]` 得到 RED（`1 failed, 6 passed`，断言原文实为 `'word word w...ble><tr><td>'`），再改 `reading/sectionA_load.py` 用 `chunk.rfind("<table", 0, stop)` 后退到最近的 `<table` 之前 → 定向 7 passed。
- 2020_7_1 判定为 `answer_conflict`：OCR 转写 `GEMKFBLDOA` 与卷面（第 12 页 `【26-30】GEMKF 【31-35】BLDOA`）一致，但卷面与正文语义冲突（27 `or ___ of war` 只能是 declaration；31 `We are ___ the very foundations` 只有 eroding 成句，卷面印的 declaration 不成句；32 `means certain ___` 应为 disaster）。同页 36–45 的 `CJBAKEMHDL` 与缓存逐字一致，排除“答案页属别卷”。处理：保留 `eval/ocr_spike/2020_7_1_section_a.json` 作 OCR 证据，`parsed_papers/2020_7_1.json`（GBMKCFEDOA）不动，不计入成功样本，不推断/不改写官方答案。
- 补位样本 `2022_6_1`（固定顺序里的下一套）：正文 `doc_002.md`(PDF 第 3 页，空位 26–32) + `doc_003.md`(第 4 页，空位 33–35)，词库同为 `doc_003.md` 的 HTML 表 A.–O.，答案 `doc_009.md`(第 10 页) KEYS 26–35 = `ABKHJGLIEF`。它的词库也是 HTML 表，所以先修 §二.2 才能生成。
- 刷新后三份 spike JSON 与来源 md 直接对（不是解析结果自比）：逐词 15/15 在源 md 中命中（2022_6_1、2021_12_1 在 `doc_003.md`，2025_12_2 在 `doc_002.md`）；KEYS 26–35 行分别在 `doc_009.md`(前两套) / `doc_007.md`(2025_12_2)，字母串与 JSON 答案逐位一致。
- 四份 spike JSON 六项结构检查（words=15/A–O、questions=26–35、answer 非空、answer⊆words、answer_word 一致、q_from/q_to=26/35）全部通过，且四份 `text` 均不含 `<table`。
- 全量 pytest：`51 passed, 4 errors`（4 个 error 全是 `tests/test_paddle_ocr.py` 的 `tmp_path` fixture 在 setup 阶段 `PermissionError: [WinError 5]` 访问 `C:\Users\86195\AppData\Local\Temp\pytest-of-86195`，该目录 2026-09-24 19:55 由另一安全上下文创建，当前进程连 `Get-Acl`/列举/删除都被拒；与本轮改动无关）。改用 `--basetemp=tmp/pytest-tmp` 后 **55 passed, 1 warning**。
- `parsed_papers` 未被改动：最新 mtime 仍是 `2022_12_3.json 2026/9/24 14:19:59`；`tmp/pdfs/` 本轮本来就空，无本轮子目录可删。

### Phase 8：6 卷重扫范围与排除理由
- 重扫范围写死在 `eval/batch_section_a.py` 顶部：5 套旧侧失败卷（2021_12_2、2021_6_1、2022_12_3、2023_6_3、2020_12_2）+ 1 套已成功对照卷（2022_6_1）。
- 明确排除、未发任何 OCR 请求：重复卷 2022_6_2-3 / 2022_9_2-3 / 2023_3_2-3（合卷，按 `skipped_duplicate` 处理，不收录）；无答案卷 2020_9_2 / 2021_6_2 / 2021_6_3 / 2022_9_1 / 2021_12_3；答案冲突卷 2020_7_1（不改、不推断）；以及标记过不要重跑的 2020_9_2 与 2025_6_2。
- OCR 入口直接 `submit → wait → download`，不走 `pages()`、不走 `ensure_mds(force=True)`；原始 markdown 原样落 `eval/ocr_spike/fresh_ocr/<卷>/doc_NNN.md`，`clean()` 只在构造解析页面时调用。旧侧只在 `meta["pages"] == len(doc_*.md)` 检查通过后才调 `pdf_load()`。
- 重扫量：6 卷 59 个版面结果（12+12+8+8+8+11），首次 4 卷 18:10–18:12 落盘，2023_6_3 与 2022_6_1 于 18:25 重试成功。

### Phase 8：新旧对照（逐卷）
| 卷 | 新/旧 OCR 结果数 | 原始正文相似度 | 词库 | 答案串（新/旧） | 新侧判定 |
|---|---|---|---|---|---|
| 2022_6_1（对照） | 11 / 11 | 1.0000（逐字节相同） | 15/15 同 | ABKHJGLIEF / ABKHJGLIEF | **success**，七条门禁全过 |
| 2020_12_2 | 12 / 12 | 1.0000（逐字节相同） | 两侧都只认到 14/15（缺 I） | NIFJGDBHME / NIFJGDBHME | parse_failed：词库 15 个 A-O、答案字母在词库内 |
| 2021_12_2 | 12 / 12 | 0.9997 | 15/15 同 | - / - | parse_failed：extract 返回 None |
| 2021_6_1 | 8 / 8 | 1.0000（逐字节相同） | 15/15 同 | - / - | parse_failed：extract 返回 None |
| 2022_12_3 | 8 / 8 | 0.9999 | 15/15 同 | - / - | parse_failed：extract 返回 None |
| 2023_6_3 | 8 / 8 | 0.9997 | 15/15 同 | - / - | parse_failed：extract 返回 None |
- 「原始正文不同」的三卷差异全是排版归一化，不是内容变化：2021_12_2 是直引号↔弯引号 + 1 个空格（`"`↔`“”`），2022_12_3 只有 `(`→`（`、`)`→`）`，2023_6_3 同类标点差异。**没有任何一卷出现正文/词库/答案的实质变化。**

### Phase 8：五套失败根因（判定结论）
- **2021_12_2 与 2021_6_1 = 解析器规则限制（板块锚点单点依赖）**。`define()` 唯一板块锚点是字面 `Reading Comprehension`：2021_12_2 全文该字面只在 doc_010 的答案页出现（偏移 35190），正文那页 OCR 只输出 `Part III\n\n(40 minutes)`——标题行没被转成文字，于是 `read_idx` 落到卷尾、块长 1 字符；2021_6_1 更彻底，全卷既无 `Reading Comprehension` 也无 `Part III`，正文 doc_002 直接从 `## Section A` 开始，`read_idx = -1` → 空块。两卷重扫内容不变、故障不变，故与旧 OCR 质量无关。
- **2022_12_3 与 2023_6_3 = 解析器规则限制（补白句单点依赖）**。切块本身正确（2022_12_3 = 文档 [607:2792]，2023_6_3 = [642:2717]），块内 15 词库齐、26–35 空位齐（`$ \underline{26} $`），但 `split_passages()` 只认 `You may not use any of the words in the bank more than once.` 这一句，而这两卷的 Directions 段落整卷 OCR 命中 0 次（`has_directions=False`）→ 切出 0 段 → `extract()` 返回 None。
- **2020_12_2 = 稳定的 OCR 字母误识（不是解析器问题，也不是旧 OCR 偶发失真）**。两轮 OCR 在这卷上逐字节相同，词库原文都读成 `B. scale` / `B.credited` / `J.strangle`（真值 I=scale、B=credited，Phase 7 已按句子锁定），答案串新旧都是 NIFJGDBHME。解析器只是照词库给的字母映射，缺 `I` 才会连带触发「答案字母在词库内」失败。重扫无法解决，需要靠答案串与词库做交叉校正。
- 同一版式缺陷在 2023_6_3 也出现：词库原文 `B. probes` / `B. articulates`（真值 I=probes、B=articulates），说明右侧栏的 `I.` 被稳定认成 `B.`，是可复现的版式级误识而非随机噪声。
- 结论汇总：**5 套失败中 4 套（2021_12_2、2021_6_1、2022_12_3、2023_6_3）是解析器规则限制，1 套（2020_12_2）是稳定 OCR 字母误识；0 套属于「旧 OCR 错、重扫后消失」**。因此扩大 Section A 覆盖前应先修共性问题（锚点兜底、Directions 兜底、词库字母交叉校正），本轮按计划不改 `reading/**`。
- 对照链路有效性：对照卷 2022_6_1 新旧零差异且仍 success，另有 2020_12_2（旧侧能解析）新旧逐字节相同 → 重扫链路本身不引入变化，上述差异都来自卷面/解析规则。

### Phase 9：两处单点依赖的修法（只改 `reading/sectionA_load.py`）
- **锚点依赖 → 前置条件式空位兜底**。`Cloze_Passage.define()` 覆写：先调父类；结果块里用 `STEM_RE` 凑齐 26–35 就直接返回（**所有原本正常的卷一行不变**）。块不完整且文档里出现过 `Reading Comprehension` 字面时，按结构重新定位：取 26 之前**最近**的 `Section A` 当起点、35 之后最近的 `Section B` 当终点（无则退 `Section C`，再无则到文末），兜底块仍凑不齐就原样退回父类结果。
- **Directions 依赖 → 0 命中时整块当正文**。`split_passages()` 在 `PASSAGE_RE` 0 命中时返回整块并掐掉行首 `Section A` 标题；有命中时行为与修改前逐字相同。
- 动因是 Phase 8 的判定：2021_12_2 的 `Reading Comprehension` 只在卷尾答案页出现（正文那页只 OCR 出 `Part III` / `(40 minutes)`），2021_6_1 全卷没有；2022_12_3 / 2023_6_3 切块正确但 Directions 原句整卷 0 命中。
- **合成 fixture 先 RED 后 GREEN**：5 条新测试加进 `tests/test_section_a_ocr.py`，每条断言到答案串级别（`BDOAIEGJMF` / `KALBNMIFJC` / `LIAKDCGEHF` / `ABKHJGLIEF`），防止「解析看似成功、实际题号与答案映射错位」。首轮实测 **3 failed, 6 passed**，改代码后定向 `13 passed`（Section A 9 + Section B 4）、全量 `61 passed, 1 warning`。
- **ⓘ 2021_6_1 的事实（本轮刻意不启用）**：去掉前置条件后，它是**能被这套空位兜底切出结构**的（词库 15 个、26–35 空位齐、答案串能与口述 `FEIHKCBGAL` 对上）；但整卷连阅读横幅字面都没有，且它没有 KEYS 页，OCR 侧过不了答案门禁。本轮以「`Reading Comprehension` 字面必须出现过」挡住，它保持 `extract() 返回 None`，不测、不接口述串、不写任何半成品。以后要收它，须把它连同答案来源（口述）与输出规则一起纳入，而不是只放开这一行。
- **2020_12_2 / 2023_6_3 的缺 `I` 仍未处理**：`parse_passage()` 的词库/答案映射逻辑本轮**未动**，两卷词库照旧只认到 14/15（右栏 `I.` 被 OCR 读成 `B.`）。2023_6_3 现在能切出结构并给出正确答案串 `LIAKDCGEHF`，但仍卡在「词库 15 个 A–O / 答案字母在词库内」两条门禁；2020_12_2 输出与 Phase 8 逐字段相同。

### Phase 9：验证证据
- 真实缓存重跑 `eval/batch_section_a.py`（6 卷全部 `[reuse] … 跳过 OCR`，**未发任何 OCR 请求**），对照 Phase 8 的 `_report.json`：`2021_12_2 → success / BDOAIEGJMF`、`2022_12_3 → success / KALBNMIFJC`，与 `parsed_papers/*.json` 里已审核的值逐位一致；`2023_6_3` 新答案 `LIAKDCGEHF`（也一致）但状态仍 `parse_failed`；`2021_6_1` 仍 `extract 返回 None`；`2022_6_1 = ABKHJGLIEF`、`2020_12_2 = NIFJGDBHME`（14 词）均与 Phase 8 完全相同。
- 26 卷旧缓存「原版解析 vs 修复后解析」逐字段（`q_from`/`q_to`/`text`/`words`/`questions`）对比：**23 卷 byte 级相同，只有 3 卷变化**（`None → parsed`，正是 2021_12_2 / 2022_12_3 / 2023_6_3）；2021_6_1 落在「23 卷相同」里，两侧都是 `None`。
- 只读证明：`parsed_papers/**`（38 个 json）最新 mtime 仍为 `2026-09-24 14:19:59`，`databases/**`（343 个文件）最新仍为 `2026-09-24 20:07:58`——都是 Phase 7 的旧时间戳，本轮唯一写入落在 `eval/ocr_spike/fresh_ocr/`。
- 解释器：项目 `.venv\Scripts\python.exe -m pytest -q` 按计划先实测，仍报同一句 `No Python at '…uv\python\cpython-3.11.15-windows-x86_64-none\python.exe'`；改用同一解释器 LocalCache 副本 + `.venv\Lib\site-packages` 的 `PYTHONPATH` + `--ignore=tmp --basetemp=tmp/pytest-tmp`。
- ⚠️ 该替代解释器 stdout 编码是 **gbk**，`pytest`/解析器打印的中文会显示成 `�ʿ�ȱ` 一类乱码；这是显示层问题，不影响断言与结果判定（判定一律读 `eval/ocr_spike/fresh_ocr/_report.json` 与 `parsed_papers/*.json` 的实际值）。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 继续使用 PaddleOCR-VL-1.6 | 官方文档解析默认模型，首轮已经正确保留版面和答案区域 |
| 可以继续扩展其余 Section B | 首轮加本轮共 4 套成功；两种答案格式都有测试保护，正式题库仍未被覆盖 |
| Section A 词库截断用 `rfind("<table", 0, stop)` | 取离词库最近的那个 `<table`，避免正文里出现别的表格标记时误命中更早的位置 |
| 2020_7_1 按 `answer_conflict` 处理而非改写 | 卷面与正文冲突时不自作判断，保留原始证据并如实标注，等人工核对 |
| Phase 8 只重扫 6 卷、不扩到全部 26 套 | 判定规则只需「有变化 vs 无变化」两类样本，5 失败卷 + 1 对照卷即可定论；量级从 26 卷降到 6 卷 |
| 2020_12_2 归到「OCR 误识」而非「解析器限制」 | 解析器忠实映射了词库给出的字母，缺 `I` 的根因在两轮一致的 OCR 识别结果上，归类不能只看失败现象 |
| Phase 9 兜底带「文档里出现过 `Reading Comprehension` 字面」前置条件 | 否则 2021_6_1 会被同一个兜底命中、从 `None` 变成「题切得出、答案为空」，既超出「本轮不动 2021_6_1」的口径，也可能让评测写出不完整样本 |
| 修复测试一律断言到答案串 | 「有 10 题且答案非空」不能发现题号-字母-单词映射错位；答案串能同时锁住切块、题号和词库映射 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 旧解析器只认 A) 和 KEYS 行列格式 | 新增 [A] 和答案区间格式，3 条回归测试锁定 |
| 2023_6_3 的 KEYS 是 HTML 表格 | 已复用为 table_answers()，不维护第二份 HTML 解析逻辑 |
| PDF 渲染提示缺少 Symbol 字体 | 6 张抽查图仍可正常读取英文题目和答案，不影响本轮核对 |
| Phase 8 重扫 2023_6_3 时云端卡在 `running 0/8` 655.1s 后抛 `SSLEOFError`，2022_6_1 在 submit 阶段同样抛 `SSLEOFError` | 判为云端瞬断，不新增重试框架，原样重跑同一命令；第 3 次两卷均 `done` 并落盘，未影响其它卷 |
| 按计划先实测项目 `.venv` 解释器仍报 `No Python at '…uv\python\cpython-3.11.15…'` | 如实记录后改用替代解释器（同一 cpython 的 LocalCache 副本 + `.venv\Lib\site-packages`），未手改 `pyvenv.cfg` |

## Resources
-
