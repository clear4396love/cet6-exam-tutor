# Task Plan: 阅读 OCR 分板块验证

## Goal
在排除重复卷后分阶段验证 Reading 各板块的 OCR 解析与独立 JSON，不覆盖正式题库；Section B 稳定后随机验证 3 套 Section A。

## Next Step
Phase 9 已修掉两处单点依赖（阅读横幅锚点、Directions 补白句），3 套从 `None` 变为可解析且答案串与正式题库逐字一致；第 4 套 2021_6_1 由前置条件挡住、刻意未启用，第 5 套 2020_12_2 仍是稳定的 OCR 字母误识（缺 `I`）留证据未处理。当前新增 Phase 10：对 2022_12_3、2023_3_1、2025_12_2 重新跑智谱 OCR，并与同卷 Paddle 输出用同一解析器对比；不据此自动切换 OCR 服务，也不写正式题库。

## Current Phase
Phase 9（complete）

## Phases

### Phase 1: 候选卷筛选
- [x] 排除 5 套重复卷、首轮试验卷和已确认无答案卷
- [x] 固定随机顺序选择候选卷
- [x] 本地判断答案页是否存在；无答案则记录后继续
- **Status:** complete

### Phase 2: OCR 与结构验收
- [x] 对 3 套合格候选卷运行或复用 PaddleOCR 缓存
- [x] 检查段落、36～45 题和答案完整性
- [x] 新格式先写失败测试，再做最小解析修改
- **Status:** complete

### Phase 3: 独立结果输出
- [x] 写入 eval/ocr_spike，不覆盖 parsed_papers
- [x] 保存每套的验证状态和失败原因
- **Status:** complete

### Phase 4: 测试与复核
- [x] 运行全量 pytest
- [x] 抽查原 PDF 与 OCR 文本
- [x] 汇总 3 套结果
- **Status:** complete

### Phase 5: 交付
- [x] 说明成功、跳过和失败的卷
- [x] 给出是否可继续扩展全部 Section B 的结论
- **Status:** complete

### Phase 6: 定点复核 2020_12_2 与 2021_6_3
- [x] 检查 PDF、OCR 缓存和答案页
- [x] 解析并校验 Section B；无答案页的卷明确跳过
- [x] 抽查原卷并运行全量测试
- **Status:** complete

### Phase 7: 随机验证 3 套 Section A
- [x] 核对现有 Section A 解析链和验收字段
- [x] 用固定种子随机抽取，重复卷与无答案卷按规则跳过
- [x] 取得 3 套完整样本并保存独立试验 JSON
- [x] 对照原 PDF 抽查并运行全量测试
- **Status:** complete
- 成功样本：2021_12_1 = BHALJMCEDO、2025_12_2 = IBMCKADFJO、2022_6_1 = ABKHJGLIEF
- 2020_7_1 = GEMKFBLDOA（与卷面一致，但卷面与正文语义冲突）→ 记为 `answer_conflict`，只作 OCR 证据，不计入成功样本

### Phase 8: Section A 失败卷重扫 + 新旧对照（6 套）
- [x] 新增 `eval/batch_section_a.py`（本轮唯一新增文件），直接 submit → wait → download
- [x] 只对 5 套失败卷 + 1 套对照卷发 OCR 请求，原始 markdown 落 `eval/ocr_spike/fresh_ocr/`
- [x] 新旧四项对照（页数 / 原始正文相似度 / 词库 / 答案串）逐卷列出
- [x] 七条门禁跑新侧，逐卷判定「解析器规则限制 vs 旧 OCR 识别问题」
- [x] 核对 `parsed_papers/**` 与 `databases/**` 本轮零写入，全量 pytest 通过
- **Status:** complete
- 结果：对照卷 2022_6_1 = ABKHJGLIEF（success，新旧零差异）；5 套仍 parse_failed，其中 4 套判为解析器规则限制、1 套（2020_12_2）判为稳定 OCR 字母误识
- 本轮**不改 `reading/**`**，只记录问题；`parsed_papers/**`、`databases/ocr_pdfs/**` 全程只读

### Phase 9: 修 Section A 两处单点依赖（3 套）+ 2020_12_2 只留证据
- [x] 先写 5 条合成 fixture 测试，确认 **3 RED / 2 GREEN**（3 条 RED = `extract()` 返回 None）
- [x] `reading/sectionA_load.py` 加 `_blanks_ready()` / 前置条件式 `define()` 覆写 + `split_passages()` 0 命中兜底
- [x] 定向 13 passed（Section A 9 + Section B 4）、全量 61 passed
- [x] `eval/batch_section_a.py` 原样重跑（6 卷全部 `[reuse]`，未发任何 OCR 请求），逐卷对照 Phase 8 的 `_report.json`
- [x] 26 卷旧缓存「原版 vs 修复后」逐字段对比：**23 卷相同、3 卷变化**（正好是 2021_12_2 / 2022_12_3 / 2023_6_3）
- [x] 只读证明：`parsed_papers/**` 最新 mtime 仍为 2026-09-24 14:19:59，`databases/**` 仍为 2026-09-24 20:07:58
- **Status:** complete
- 结果：2021_12_2 = `BDOAIEGJMF`、2022_12_3 = `KALBNMIFJC` 翻成 success；2023_6_3 已能切出并给出 `LIAKDCGEHF`（与正式题库一致），但仍卡在「词库 15 个 A–O / 答案字母在词库内」两条门禁 → 保持 parse_failed，属下一轮
- 2021_6_1 仍 `parse_failed: extract 返回 None`（前置条件要求卷内出现过 `Reading Comprehension` 字面）；2022_6_1 = `ABKHJGLIEF`、2020_12_2 = `NIFJGDBHME` 14 词，均与 Phase 8 完全相同
- 改动文件只有两个：`reading/sectionA_load.py`、`tests/test_section_a_ocr.py`；`eval/batch_section_a.py` 整份未动

### Phase 10: 三套卷子智谱 OCR 与 Paddle 对比
- [x] 预检 2022_12_3、2023_3_1、2025_12_2 的 PDF、完整 Paddle 缓存与目标 `_zhipu` 目录；三个 PDF / Paddle 缓存均齐全，目标目录均不存在
- [x] 确认智谱 SDK 与令牌可用；SDK 仅安装到项目 `.venv`，未输出令牌、未改 `requirements.txt`
- [x] 串行重新 OCR，结果只写各卷独立 `_zhipu` 缓存；未改 `_paddle`、`parsed_papers` 或产品代码
- [x] 用相同的 A/B/C 解析器对比两种 OCR，记录结构完整性、答案串、文本差异与错误类型
- [x] 复核正式题库答案与缓存路径；给出是否有证据支持更换 OCR 的结论
- **Status:** complete
- 结论：三套 A/B/C 的答案与结构通过率完全相同；只发现一处可确认的题干识别差异（2025_12_2 第 54 题智谱正确、Paddle 少一个字母）。样本不足以支持整体替换 Paddle。

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 固定随机顺序 | 保证结果可复现 |
| 无答案页直接跳过 | 不让模型或旧缓存决定官方答案 |
| 试验结果独立保存 | 保护已审核的正式题库 |
| 判定按「内容变没变」而非「这次过没过」 | 重扫的价值在于区分解析器规则与旧 OCR 质量；只看通过率会把两者混为一谈 |
| 原始 markdown 不经 `clean()` 直接落盘 | 新证据不被清洗改写，新旧两侧才能公平比较 |
| 对照卷 + 成功卷双重对照 | 2022_6_1（旧侧 success）与 2020_12_2（旧侧能解析）都重扫零差异，才排除「重扫链路本身引入变化」 |
| 兜底只在「块内凑不齐 26–35 空位」时启用 | 所有成功卷原路径一行不变，是防止把正常解析弄坏的安全阀；先判断块是否已完整，再谈兜底 |
| 兜底前置条件写「文档里出现过 `Reading Comprehension` 字面」 | 这是 2021_6_1 与本轮范围的唯一分界线；该字面从此只当「能不能兜底」的开关，不再当定位锚点 |
| 兜底按空位（26 之前最近的 `Section A` → 35 之后最近的 `Section B`）定位，不按标题文字 | 2021_12_2 的正文页标题根本没被 OCR 转成文字，任何字面锚点都会再次落空；结构比文字稳 |
| 2020_12_2 / 2023_6_3 的缺 `I` 本轮不做纠正 | 按答案反推词库标签会把错误答案一起带进来；等一条能被测试验证的规则再单独处理 |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| 2021_6_2 没有答案页 | 标记 skipped_no_answers，不作为成功样本 |
| 计划状态补丁引用错文件位置 | 补丁整体被拒绝；读取当前文件后精确重做 |
| 当前目录的 `.git` 不是有效仓库，无法运行 git diff --stat | 不修改 Git 配置；继续以文件与测试结果核对本轮工作 |
| 父仓库对沙箱用户报 dubious ownership | 不修改全局 Git 安全配置；本轮继续以文件、原卷和测试结果验收 |
| PowerShell `foreach` 后直接接管道触发空管道语法错误 | 改为先把循环结果赋给数组，再单独格式化输出 |
| 内联 Python 的嵌套 f-string 转义造成 SyntaxError | 拆出统计变量并用简单 `format()` 输出，避免嵌套引号 |
| 环境有 `pdfinfo`/`pdftoppm` 但没有 `pdftotext` | 改用项目已安装的 PyMuPDF 提取文字，并用页面渲染做视觉确认 |
| 沙箱阻止 PaddleOCR HTTPS 连接（WinError 10013） | 获得授权后在沙箱外重跑同一上传，8 页 OCR 正常完成并缓存 |
| 2020_7_1 答案源冲突：卷面印 `GEMKF`+`BLDOA`，正文语义只能推出 `GBMKC`+`FEDOA` | 记为 `answer_conflict`；保留 OCR 证据 JSON，不改正式题库，不推断、不改写官方答案，不计入成功样本 |
| 词库为 HTML 表时 `section_a.text` 尾部混入 `<table><tr><td…` | 先加断言 `assert "<table" not in result["text"]` 得到 RED，再用 `chunk.rfind("<table", 0, stop)` 最小修改转 GREEN |
| 全量 pytest 有 4 个 `tmp_path` fixture 在 setup 阶段报 `PermissionError: [WinError 5] …Temp\pytest-of-86195` | 环境残留目录（2026-09-24 19:55 由另一安全上下文创建，当前进程连列举/删除都被拒），与本轮改动无关；用 `--basetemp=tmp/pytest-tmp` 重跑得 55 passed |
| 项目 `.venv\Scripts\python.exe` 直接启动报 `No Python at '…\uv\python\cpython-3.11.15…'` | 经用户授权改用同一解释器在 Codex LocalCache 下的副本 + `.venv\Lib\site-packages` 的 `PYTHONPATH`；未手改 `pyvenv.cfg` |
| Phase 8 重扫 2023_6_3 / 2022_6_1 两次 `SSLEOFError: UNEXPECTED_EOF_WHILE_READING`（2023_6_3 还先 `running 0/8` 卡了 655.1s） | 判为云端连接瞬断：不新增重试框架，原样重跑同一条命令；第 3 次两卷都正常 done（18:25 落盘），逐卷 md 数与新 `meta["pages"]` 相等 |
| 项目解释器按计划先实测，仍报同一句 `No Python at …` | 如实记录后改用替代解释器（同一 cpython-3.11.15 的 LocalCache 副本 + `.venv\Lib\site-packages`），并加 `--ignore=tmp --basetemp=tmp/pytest-tmp` 避开上一轮遗留的不可读 basetemp |
